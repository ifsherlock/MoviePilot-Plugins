from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import shutil
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .online.online_subtitle import build_search_keywords


@dataclass(frozen=True)
class AutoTransferSeasonCollaborators:
    target_from_entry: Callable[[Dict[str, Any]], Dict[str, Any]]
    auto_target_has_chinese_subtitle: Callable[[Dict[str, Any], Dict[str, Any]], bool]
    chinese_transfer_media_evidence: Callable[[Dict[str, Any]], Tuple[bool, str]]
    media_for_transfer_entry: Callable[[Dict[str, Any]], Dict[str, Any]]
    task_result_key: Callable[[Dict[str, Any]], str]
    search_providers: Callable[[], List[str]]
    wait_online_rate_limit: Callable[..., None]
    online_service: Callable[[], Any]
    online_download_name: Callable[[str, bytes, Dict[str, Any]], str]
    extract_subtitle_files: Callable[[str, bytes, Path], List[Dict[str, Any]]]
    write_prepared_uploads_for_entries: Callable[..., Dict[str, Any]]
    store_cache: Callable[[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]], None]
    load_cache: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]
    write_from_cache: Callable[[List[Dict[str, Any]]], Dict[str, Any]]
    search_write_package: Callable[..., Dict[str, Any]]
    process_entry: Callable[..., Dict[str, Any]]


class AutoTransferSeasonCache:
    def __init__(self, owner: Any, *, logger: Any, collaborators: AutoTransferSeasonCollaborators) -> None:
        self._owner = owner
        self._logger = logger
        self._collaborators = collaborators

    def cache_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        media_key = owner._normalize_text(entry.get("media_key") or entry.get("tmdb_id") or entry.get("title"))
        season = owner._safe_int(entry.get("season"), 0)
        if not media_key or not season:
            return ""
        return owner._hash_text(f"{media_key}|s{season:02d}")[:20]

    def cache_dir(self, cache_key: str) -> Path:
        return self._owner.get_data_path() / "auto_season_packages" / cache_key

    def store_cache(
        self,
        entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        selected_result: Dict[str, Any],
    ) -> None:
        owner = self._owner
        if not entries or not prepared_uploads:
            return
        cache_key = self.cache_key(entries[0])
        if not cache_key:
            return
        cache_dir = self.cache_dir(cache_key)
        cache_dir.mkdir(parents=True, exist_ok=True)
        manifest_items = []
        for item in prepared_uploads:
            source_path = Path(owner._normalize_text(item.get("stored_path")))
            if not source_path.is_file():
                continue
            stored_name = f"{item.get('upload_id')}{source_path.suffix.lower()}"
            target_path = cache_dir / stored_name
            shutil.copyfile(source_path, target_path)
            manifest_items.append(
                {
                    **item,
                    "stored_path": str(target_path),
                }
            )
        if not manifest_items:
            return
        payload = {
            "key": cache_key,
            "title": entries[0].get("title"),
            "media_key": entries[0].get("media_key"),
            "season": owner._safe_int(entries[0].get("season"), 0),
            "provider": selected_result.get("provider"),
            "source_title": selected_result.get("title"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "items": manifest_items,
        }
        try:
            (cache_dir / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 写入整季字幕包缓存失败: %s", exc)
        owner._auto_season_package_cache[cache_key] = payload
        owner._auto_season_package_cache.move_to_end(cache_key)
        while len(owner._auto_season_package_cache) > 50:
            owner._auto_season_package_cache.popitem(last=False)

    def load_cache(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        owner = self._owner
        cache_key = self.cache_key(entry)
        if not cache_key:
            return None
        cached = (owner._auto_season_package_cache or OrderedDict()).get(cache_key)
        if cached:
            return cached
        manifest = self.cache_dir(cache_key) / "manifest.json"
        if not manifest.is_file():
            return None
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取整季字幕包缓存失败: %s", exc)
            return None
        items = [
            item
            for item in payload.get("items") or []
            if isinstance(item, dict) and Path(owner._normalize_text(item.get("stored_path"))).is_file()
        ]
        if not items:
            return None
        payload["items"] = items
        owner._auto_season_package_cache[cache_key] = payload
        owner._auto_season_package_cache.move_to_end(cache_key)
        return payload

    def write_from_cache(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        owner = self._owner
        if not entries:
            return {"status": "skipped", "reason": "没有待处理目标", "written_by_target": {}}
        cached = self._collaborators.load_cache(entries[0])
        if not cached:
            return {"status": "skipped", "reason": "没有整季字幕包缓存", "written_by_target": {}}
        session_id = owner._hash_text(f"auto-season-cache|{datetime.now().isoformat()}|{cached.get('key')}")[:16]
        session_dir = owner.services.upload_session().get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = self._collaborators.write_prepared_uploads_for_entries(
                target_entries=entries,
                prepared_uploads=cached.get("items") or [],
                session_dir=session_dir,
                selected_result={"provider": cached.get("provider"), "title": cached.get("source_title")},
            )
            if result.get("status") == "written":
                result["from_cache"] = True
            return result
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)

    def search_write_package(
        self,
        entries: List[Dict[str, Any]],
        *,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        if not entries:
            return {"status": "skipped", "reason": "没有待处理目标", "written_by_target": {}}
        providers = self._collaborators.search_providers()
        if not providers:
            return {"status": "skipped", "reason": "未配置可用 API 字幕源", "written_by_target": {}}
        targets = [self._collaborators.target_from_entry(entry) for entry in entries]
        media = self._collaborators.media_for_transfer_entry(entries[0])
        owner._apply_tmdb_detail(targets[0], media)
        keywords = build_search_keywords(media, targets, "season")[:8]
        if not keywords:
            return {"status": "skipped", "reason": "没有可用整季搜索关键词", "written_by_target": {}}

        self._collaborators.wait_online_rate_limit(providers, task_ids=task_ids)
        service = self._collaborators.online_service()
        search_result = service.search(
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope="season",
        )
        candidates = [
            item
            for item in search_result.get("results") or []
            if item.get("downloadable") is not False and owner._safe_int(item.get("score"), 0) >= owner._auto_search_min_score
        ]
        if not candidates:
            return {
                "status": "skipped",
                "reason": "没有高置信可下载整季结果",
                "written_by_target": {},
                "search_results": len(search_result.get("results") or []),
            }

        last_reason = ""
        best_partial_result: Optional[Dict[str, Any]] = None
        for selected in candidates[:3]:
            session_id = owner._hash_text(f"auto-season|{datetime.now().isoformat()}|{entries[0].get('id')}")[:16]
            session_dir = owner.services.upload_session().get_session_root() / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            try:
                downloads = service.download([selected])
                prepared_uploads: List[Dict[str, Any]] = []
                for downloaded in downloads:
                    result = downloaded.get("result") or {}
                    source_name = self._collaborators.online_download_name(
                        downloaded.get("source_name", ""),
                        downloaded.get("content") or b"",
                        result,
                    )
                    extracted = self._collaborators.extract_subtitle_files(
                        source_name,
                        downloaded.get("content") or b"",
                        session_dir,
                    )
                    for item in extracted:
                        item["online_source"] = downloaded.get("provider")
                        item["online_title"] = result.get("title", "")
                        if not item.get("archive_name") and source_name != item.get("source_name"):
                            item["archive_name"] = source_name
                    prepared_uploads.extend(extracted)
                if not prepared_uploads:
                    last_reason = "整季结果未解析到字幕文件"
                    continue
                self._collaborators.store_cache(entries, prepared_uploads, selected)
                write_result = self._collaborators.write_prepared_uploads_for_entries(
                    target_entries=entries,
                    prepared_uploads=prepared_uploads,
                    session_dir=session_dir,
                    selected_result=selected,
                )
                if write_result.get("status") == "written":
                    write_result["candidate_count"] = len(candidates)
                    write_result["search_results"] = len(search_result.get("results") or [])
                    write_result["season_package"] = True
                    if write_result.get("coverage_complete", True):
                        return write_result
                    current_completed = owner._safe_int(write_result.get("completed_count"), 0)
                    best_completed = owner._safe_int((best_partial_result or {}).get("completed_count"), 0)
                    if not best_partial_result or current_completed > best_completed:
                        best_partial_result = write_result
                    last_reason = write_result.get("reason") or "整季包未完整覆盖当前集数"
                    continue
                last_reason = write_result.get("reason") or "整季包未匹配当前集数"
            except Exception as exc:
                last_reason = f"整季包下载/解析失败: {owner._normalize_text(exc)}"
                self._logger.warning(
                    "[SubtitleManualUpload] %s provider=%s result=%s",
                    last_reason,
                    selected.get("provider"),
                    selected.get("title"),
                )
            finally:
                shutil.rmtree(session_dir, ignore_errors=True)
        if best_partial_result:
            self._logger.warning(
                "[SubtitleManualUpload] 未找到完整覆盖整季字幕包，使用最佳部分覆盖结果 result=%s completed=%s missing=%s",
                best_partial_result.get("result"),
                best_partial_result.get("completed_count"),
                len(best_partial_result.get("missing_target_ids") or []),
            )
            return best_partial_result
        return {
            "status": "skipped",
            "reason": last_reason or "整季包未能写入任何字幕",
            "written_by_target": {},
            "candidate_count": len(candidates),
            "search_results": len(search_result.get("results") or []),
        }

    def process_group(self, entries: List[Dict[str, Any]], task_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        results: Dict[str, Dict[str, Any]] = {}
        strategy = owner._normalize_auto_transfer_subtitle_strategy(owner._auto_transfer_subtitle_strategy)
        if not entries:
            return results
        if strategy == "ai_source_only":
            for entry in entries:
                results[self._collaborators.task_result_key(entry)] = self._collaborators.process_entry(
                    entry,
                    queue_rate_limited=True,
                    task_ids=task_ids,
                )
            return results

        pending_entries: List[Dict[str, Any]] = []
        for entry in entries:
            key = self._collaborators.task_result_key(entry)
            target = self._collaborators.target_from_entry(entry)
            base = {"strategy": strategy, "target": target.get("label")}
            if self._collaborators.auto_target_has_chinese_subtitle(entry, target):
                results[key] = {**base, "status": "skipped", "reason": "目标已有中文字幕"}
                continue
            if target.get("has_subtitle"):
                self._logger.info(
                    "[SubtitleManualUpload] 目标已有外挂字幕但未确认中文，继续自动匹配/AI target=%s",
                    target.get("label"),
                )
            if owner._auto_skip_chinese_media_on_transfer:
                is_chinese, evidence = self._collaborators.chinese_transfer_media_evidence(entry)
                if is_chinese:
                    results[key] = {**base, "status": "skipped", "reason": f"中文资源自动跳过：{evidence}"}
                    continue
            pending_entries.append(entry)

        cache_result = self._collaborators.write_from_cache(pending_entries)
        remaining_entries = self._collect_remaining_after_season_result(
            entries=pending_entries,
            results=results,
            season_result=cache_result,
            strategy=strategy,
            from_cache=True,
        )

        if remaining_entries:
            season_result = self._collaborators.search_write_package(remaining_entries, task_ids=task_ids)
            remaining_entries = self._collect_remaining_after_season_result(
                entries=remaining_entries,
                results=results,
                season_result=season_result,
                strategy=strategy,
                from_cache=False,
            )

        for entry in remaining_entries:
            key = self._collaborators.task_result_key(entry)
            results[key] = self._collaborators.process_entry(
                entry,
                queue_rate_limited=True,
                task_ids=task_ids,
            )
        return results

    def _collect_remaining_after_season_result(
        self,
        *,
        entries: List[Dict[str, Any]],
        results: Dict[str, Dict[str, Any]],
        season_result: Dict[str, Any],
        strategy: str,
        from_cache: bool,
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        written_by_target = season_result.get("written_by_target") or {}
        ai_by_target = season_result.get("ai_by_target") or {}
        remaining_entries: List[Dict[str, Any]] = []
        for entry in entries:
            key = self._collaborators.task_result_key(entry)
            target_id = owner._normalize_text(entry.get("id"))
            common = {
                "strategy": strategy,
                "target": self._collaborators.target_from_entry(entry).get("label"),
                "result": season_result.get("result"),
                "season_package": True,
            }
            if from_cache:
                common["from_cache"] = True
            else:
                common["candidate_count"] = season_result.get("candidate_count")
                common["search_results"] = season_result.get("search_results")
            if target_id in written_by_target:
                results[key] = {
                    **common,
                    "status": "written",
                    "written": [written_by_target[target_id]],
                }
            elif target_id in ai_by_target:
                results[key] = {
                    **common,
                    "status": "ai_submitted",
                    "fixed_subtitles": [ai_by_target[target_id]],
                    "ai": season_result.get("ai_translate"),
                }
            else:
                remaining_entries.append(entry)
        return remaining_entries
