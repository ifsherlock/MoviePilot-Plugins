from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


class SubtitleHistory:
    def __init__(
        self,
        owner: Any,
        *,
        http_exception: Any,
        logger: Any,
        target_entry_cache: Any,
    ) -> None:
        self._owner = owner
        self._http_exception = http_exception
        self._logger = logger
        self._target_entry_cache = target_entry_cache

    def match_history_cache_file(self) -> Path:
        return self._owner.get_data_path() / "match_history_cache.json"

    def match_history_signature(self, entries: List[Dict[str, Any]]) -> str:
        owner = self._owner
        loaded_at = owner._cache_loaded_at((owner._local_entries_cache or {}).get("loaded_at"))
        parts = [
            loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            str(len(entries)),
        ]
        for entry in entries:
            parts.append(
                "|".join(
                    [
                        owner._normalize_text(entry.get("id")),
                        owner._normalize_text(entry.get("path")),
                        owner._normalize_text(entry.get("date")),
                        owner._entry_filesystem_signature(entry),
                    ]
                )
            )
        return owner._hash_text("\n".join(parts))

    def persist_match_history_cache(self) -> None:
        owner = self._owner
        cache = owner._match_history_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        payload = {
            "loaded_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "signature": owner._normalize_text(cache.get("signature")),
            "entry_count": int(cache.get("entry_count") or 0),
            "items": cache.get("items") or [],
        }
        try:
            cache_file = self.match_history_cache_file()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 写入匹配历史缓存失败: %s", exc)

    def restore_persisted_match_history_cache(self) -> bool:
        owner = self._owner
        try:
            cache_file = self.match_history_cache_file()
            if not cache_file.exists():
                return False
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取匹配历史缓存失败: %s", exc)
            return False
        if not isinstance(payload, dict):
            return False
        loaded_at = owner._cache_loaded_at(payload.get("loaded_at"))
        items = payload.get("items")
        if not loaded_at or not isinstance(items, list):
            return False
        owner._match_history_cache = {
            "loaded_at": loaded_at,
            "signature": owner._normalize_text(payload.get("signature")),
            "items": [item for item in items if isinstance(item, dict)],
            "entry_count": int(payload.get("entry_count") or 0),
            "persisted": True,
        }
        for item in owner._match_history_cache["items"]:
            self._target_entry_cache.remember([target for target in item.get("targets") or [] if isinstance(target, dict)])
        self._logger.info(
            "[SubtitleManualUpload] 已恢复匹配历史缓存 items=%s",
            len(owner._match_history_cache["items"]),
        )
        return True

    def invalidate_match_history_cache(self) -> None:
        owner = self._owner
        owner._match_history_cache = {
            "loaded_at": None,
            "signature": "",
            "items": [],
            "entry_count": 0,
            "persisted": False,
        }
        try:
            self.match_history_cache_file().unlink(missing_ok=True)
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 删除匹配历史缓存失败: %s", exc)

    def filter_match_history_items(
        self,
        items: List[Dict[str, Any]],
        *,
        keyword: str = "",
        media_type: str = "all",
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword)
        expected_type = owner._media_type_text(media_type)
        filtered: List[Dict[str, Any]] = []
        for item in items:
            if expected_type and item.get("media_type") != expected_type:
                continue
            if clean_keyword:
                target_entries = item.get("targets") or []
                synthetic_entry = {
                    "title": item.get("title"),
                    "filename": "",
                    "basename": "",
                    "relative_path": "",
                }
                if not owner._entry_matches_keyword(synthetic_entry, clean_keyword) and not any(
                    owner._entry_matches_keyword(target, clean_keyword)
                    for target in target_entries
                    if isinstance(target, dict)
                ):
                    continue
            filtered.append(item)
        cloned = owner._json_clone(filtered)
        for item in cloned:
            for target in item.get("targets") or []:
                if isinstance(target, dict):
                    target["timeline_task"] = owner._timeline_task_for_target_id(target.get("id"))
        return cloned

    def match_history_items(self, *, keyword: str = "", media_type: str = "all") -> List[Dict[str, Any]]:
        owner = self._owner
        media_catalog = owner._local_media_catalog()
        target_resolver = owner._target_resolver()
        entries = media_catalog.load_local_entries(allow_stale=True)
        signature = self.match_history_signature(entries)
        cache = owner._match_history_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        if (
            loaded_at
            and owner._normalize_text(cache.get("signature")) == signature
            and (datetime.now() - loaded_at).total_seconds() < owner._match_history_cache_ttl_seconds
        ):
            return self.filter_match_history_items(
                cache.get("items") or [],
                keyword=keyword,
                media_type=media_type,
            )

        groups: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            target = target_resolver.target_from_entry(entry)
            subtitles = target.get("subtitles") or []
            if not subtitles:
                continue
            key = entry.get("media_key") or entry.get("id")
            group = groups.setdefault(
                key,
                {
                    "id": key,
                    "media_type": entry.get("media_type"),
                    "title": entry.get("title"),
                    "year": entry.get("year"),
                    "tmdb_id": entry.get("tmdb_id"),
                    "douban_id": entry.get("douban_id"),
                    "poster_url": entry.get("poster_url"),
                    "poster_thumb_url": entry.get("poster_thumb_url") or owner._poster_url(entry.get("poster_url"), "w185"),
                    "subtitle_count": 0,
                    "target_count": 0,
                    "latest_at": "",
                    "targets": [],
                },
            )
            group["target_count"] += 1
            group["subtitle_count"] += len(subtitles)
            latest = max((item.get("modified_at") or "" for item in subtitles), default="")
            if latest and latest > group.get("latest_at", ""):
                group["latest_at"] = latest
            group["targets"].append(target)

        items = list(groups.values())
        for item in items:
            item["targets"].sort(key=lambda target: (target.get("season", 0), target.get("episode", 0), target.get("basename", "")))
        items.sort(key=lambda item: (item.get("latest_at", ""), item.get("title", "")), reverse=True)
        owner._match_history_cache = {
            "loaded_at": datetime.now(),
            "signature": signature,
            "items": owner._json_clone(items),
            "entry_count": len(entries),
            "persisted": False,
        }
        self.persist_match_history_cache()
        return self.filter_match_history_items(items, keyword=keyword, media_type=media_type)

    def existing_timeline_operations(
        self,
        requested_items: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        owner = self._owner
        target_ids = [owner._normalize_text(item.get("target_id")) for item in requested_items if isinstance(item, dict)]
        target_entries = owner._resolve_targets(target_ids)
        operations: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        seen = set()
        for request_item in requested_items:
            if not isinstance(request_item, dict):
                continue
            target_id = owner._normalize_text(request_item.get("target_id"))
            if not target_id:
                skipped.append({"reason": "缺少 target_id"})
                continue
            entry = target_entries.get(target_id)
            if not entry:
                skipped.append({"target_id": target_id, "reason": "目标视频已失效"})
                continue
            target = owner._target_from_entry(entry)
            if target.get("is_stream"):
                skipped.append({"target_id": target_id, "reason": "STRM 资源不启用智能调轴"})
                continue
            subtitles = target.get("subtitles") or []
            expected_path = owner._normalize_text(request_item.get("subtitle_path"))
            if expected_path:
                subtitles = [
                    item for item in subtitles
                    if owner._normalize_text(item.get("path")) == expected_path
                ]
            if not subtitles:
                skipped.append({"target_id": target_id, "reason": "没有可调轴的外挂字幕"})
                continue
            for subtitle in subtitles:
                subtitle_path = Path(owner._normalize_text(subtitle.get("path")))
                key = f"{target_id}|{subtitle_path}"
                if key in seen:
                    continue
                seen.add(key)
                if not subtitle_path.is_file():
                    skipped.append({"target_id": target_id, "subtitle_path": str(subtitle_path), "reason": "外挂字幕不存在"})
                    continue
                try:
                    raw_bytes = subtitle_path.read_bytes()
                except Exception:
                    raw_bytes = b""
                language_profile = owner._detect_language_profile(subtitle_path.name, raw_bytes)
                upload_id = owner._hash_text(f"existing-timeline|{target_id}|{subtitle_path}|{subtitle_path.stat().st_mtime_ns}")[:16]
                upload_info = {
                    "upload_id": upload_id,
                    "source_name": subtitle_path.name,
                    "archive_name": "",
                    "stored_path": str(subtitle_path),
                    "ext": subtitle_path.suffix.lower(),
                }
                item = {
                    "upload_id": upload_id,
                    "target_id": target_id,
                    "ext": subtitle_path.suffix.lower(),
                    "language_suffix": language_profile["suffix"],
                }
                try:
                    operation = owner._subtitle_writer().build_write_operations(
                        [item],
                        {upload_id: upload_info},
                        {target_id: entry},
                    )[0]
                except self._http_exception as exc:
                    failed.append(
                        {
                            "target_id": target_id,
                            "subtitle_path": str(subtitle_path),
                            "reason": owner._normalize_text(getattr(exc, "detail", "")) or str(exc),
                        }
                    )
                    continue
                operations.append(operation)
        return operations, skipped, failed
