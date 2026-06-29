from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import shutil
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .config_schema import normalize_auto_multi_subtitle_mode
from .online_subtitle import build_search_keywords


@dataclass(frozen=True)
class AutoTransferCollaborators:
    online_service_factory: Optional[Callable[[], Any]] = None
    target_from_entry: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    extract_subtitle_files: Optional[Callable[..., List[Dict[str, Any]]]] = None
    write_operations_to_disk: Optional[Callable[..., Tuple[List[Dict[str, Any]], int, int]]] = None
    submit_autosub_for_entries: Optional[Callable[..., Dict[str, Any]]] = None
    prepare_online_ai_subtitle_overrides: Optional[Callable[..., Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]] = None
    normalize_online_download_name: Optional[Callable[..., str]] = None
    detect_language_profile: Optional[Callable[[str, bytes], Dict[str, Any]]] = None
    auto_subtitle_sort_key: Optional[Callable[[Dict[str, Any]], Tuple[int, int, int, str]]] = None
    auto_target_has_chinese_subtitle: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None
    check_online_rate_limit: Optional[Callable[[Iterable[str]], None]] = None
    wait_online_rate_limit: Optional[Callable[..., None]] = None
    logger: Any = None
    threading_module: Any = None
    time_module: Any = None
    http_exception: Any = None

    @classmethod
    def from_owner(
        cls,
        owner: Any,
        *,
        logger: Any,
        threading_module: Any,
        time_module: Any,
        http_exception: Any,
    ) -> "AutoTransferCollaborators":
        return cls(
            online_service_factory=owner._online_service,
            target_from_entry=owner._target_from_entry,
            extract_subtitle_files=owner._extract_subtitle_files,
            write_operations_to_disk=owner._write_operations_to_disk,
            submit_autosub_for_entries=owner._submit_autosub_for_entries,
            prepare_online_ai_subtitle_overrides=owner._prepare_online_ai_subtitle_overrides,
            normalize_online_download_name=owner._normalize_online_download_name,
            detect_language_profile=owner._detect_language_profile,
            auto_subtitle_sort_key=owner._auto_subtitle_sort_key,
            auto_target_has_chinese_subtitle=owner._auto_target_has_chinese_subtitle,
            check_online_rate_limit=owner._check_online_rate_limit,
            wait_online_rate_limit=owner._auto_wait_online_rate_limit,
            logger=logger,
            threading_module=threading_module,
            time_module=time_module,
            http_exception=http_exception,
        )


class AutoTransferService:
    def __init__(
        self,
        owner: Any,
        *,
        logger: Any,
        threading_module: Any,
        time_module: Any,
        http_exception: Any,
        collaborators: Optional[AutoTransferCollaborators] = None,
    ) -> None:
        self._owner = owner
        self._collaborators = collaborators or AutoTransferCollaborators()
        self._logger = self._collaborators.logger or logger
        self._threading = self._collaborators.threading_module or threading_module
        self._time = self._collaborators.time_module or time_module
        self._http_exception = self._collaborators.http_exception or http_exception

    def _callback(self, name: str, fallback_name: str) -> Callable[..., Any]:
        callback = getattr(self._collaborators, name)
        return callback or getattr(self._owner, fallback_name)

    def _online_service(self) -> Any:
        return self._callback("online_service_factory", "_online_service")()

    def _target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return self._callback("target_from_entry", "_target_from_entry")(entry)

    def _check_online_rate_limit(self, providers: Iterable[str]) -> None:
        self._callback("check_online_rate_limit", "_check_online_rate_limit")(providers)

    def _wait_online_rate_limit(self, providers: Iterable[str], task_ids: Optional[List[str]] = None) -> None:
        self._callback("wait_online_rate_limit", "_auto_wait_online_rate_limit")(providers, task_ids=task_ids)

    def _normalize_online_download_name(self, name: str, content: bytes, result: Dict[str, Any]) -> str:
        return self._callback("normalize_online_download_name", "_normalize_online_download_name")(name, content, result)

    def _extract_subtitle_files(self, upload_name: str, raw_bytes: bytes, session_dir: Path) -> List[Dict[str, Any]]:
        return self._callback("extract_subtitle_files", "_extract_subtitle_files")(upload_name, raw_bytes, session_dir)

    def _auto_target_has_chinese_subtitle(self, entry: Dict[str, Any], target: Dict[str, Any]) -> bool:
        return self._callback("auto_target_has_chinese_subtitle", "_auto_target_has_chinese_subtitle")(entry, target)

    def _auto_search_write_subtitle(self, entry: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return self._callback("auto_search_write_subtitle", "_auto_search_write_subtitle")(entry, target)

    def _submit_autosub_for_entries(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._callback("submit_autosub_for_entries", "_submit_autosub_for_entries")(*args, **kwargs)

    def _detect_language_profile(self, file_name: str, raw_bytes: bytes) -> Dict[str, Any]:
        return self._callback("detect_language_profile", "_detect_language_profile")(file_name, raw_bytes)

    def _auto_subtitle_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, int, str]:
        return self._callback("auto_subtitle_sort_key", "_auto_subtitle_sort_key")(item)

    def _write_operations_to_disk(self, **kwargs: Any) -> Tuple[List[Dict[str, Any]], int, int]:
        return self._callback("write_operations_to_disk", "_write_operations_to_disk")(**kwargs)

    def _prepare_online_ai_subtitle_overrides(self, *args: Any, **kwargs: Any):
        return self._callback("prepare_online_ai_subtitle_overrides", "_prepare_online_ai_subtitle_overrides")(*args, **kwargs)

    def stop(self) -> None:
        owner = self._owner
        with owner._transfer_auto_lock:
            owner._auto_transfer_stopping = True
            tasks = owner._auto_transfer_tasks or OrderedDict()
            now = self._time.time()
            for task in tasks.values():
                if task.get("status") == "pending":
                    task["status"] = "skipped"
                    task["active"] = False
                    task["next_run_ts"] = 0
                    task["updated_ts"] = now
                    task["message"] = "服务已停止，未继续处理新任务"
            worker = owner._auto_transfer_worker
            if not worker or not worker.is_alive():
                owner._auto_transfer_worker = None

    def transfer_auto_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        path = owner._normalize_text(entry.get("path") or entry.get("relative_path"))
        if path:
            normalized_path = path.lower().replace("\\", "/")
            return owner._hash_text(f"{normalized_path}|{owner._entry_filesystem_signature(entry)}")
        return owner._normalize_text(entry.get("id") or entry.get("target_label") or entry.get("filename"))

    def claim_transfer_auto_entries(self, entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        owner = self._owner
        now = self._time.time()
        claimed: List[Dict[str, Any]] = []
        skipped = 0
        with owner._transfer_auto_lock:
            owner._transfer_auto_recent = {
                key: ts
                for key, ts in (owner._transfer_auto_recent or {}).items()
                if now - ts < owner._transfer_auto_dedupe_seconds
            }
            for entry in entries:
                key = owner._transfer_auto_key(entry)
                if not key:
                    claimed.append(entry)
                    continue
                if key in owner._transfer_auto_recent:
                    skipped += 1
                    continue
                owner._transfer_auto_recent[key] = now
                claimed.append(entry)
        return claimed, skipped

    def auto_transfer_entry_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        return owner._transfer_auto_key(entry) or owner._hash_text(
            f"{entry.get('id')}|{entry.get('target_label')}|{entry.get('filename')}"
        )

    def auto_transfer_group_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        if owner._normalize_text(entry.get("media_type")) != "tv":
            return owner._auto_transfer_entry_key(entry)
        media_key = owner._normalize_text(entry.get("media_key") or entry.get("tmdb_id") or entry.get("title"))
        season = owner._safe_int(entry.get("season"), 0)
        if not media_key or not season:
            return owner._auto_transfer_entry_key(entry)
        return f"tv|{media_key}|s{season:02d}"

    def trim_auto_transfer_tasks_locked(self) -> None:
        owner = self._owner
        tasks = owner._auto_transfer_tasks or OrderedDict()
        while len(tasks) > owner._auto_transfer_queue_history_limit:
            removable = next(
                (
                    key
                    for key, task in tasks.items()
                    if task.get("status") not in {"pending", "in_progress"}
                ),
                None,
            )
            if not removable:
                break
            tasks.pop(removable, None)

    def enqueue_transfer_auto_entries(self, entries: List[Dict[str, Any]]) -> Tuple[int, int]:
        owner = self._owner
        valid_entries = owner._filter_existing_local_entries(entries)
        if getattr(owner, "_auto_transfer_stopping", False):
            return 0, len(valid_entries) + (len(entries or []) - len(valid_entries))
        claimed, skipped = owner._claim_transfer_auto_entries(valid_entries)
        if not claimed:
            return 0, skipped + (len(entries or []) - len(valid_entries))
        now = self._time.time()
        queued = 0
        with owner._transfer_auto_lock:
            active_keys = {
                owner._normalize_text(task.get("entry_key"))
                for task in (owner._auto_transfer_tasks or OrderedDict()).values()
                if task.get("status") in {"pending", "in_progress"}
            }
            for entry in claimed:
                entry_key = owner._auto_transfer_entry_key(entry)
                if entry_key in active_keys:
                    skipped += 1
                    continue
                task_id = owner._hash_text(f"auto-transfer|{entry_key}|{now}")[:16]
                owner._auto_transfer_tasks[task_id] = {
                    "id": task_id,
                    "entry_key": entry_key,
                    "group_key": owner._auto_transfer_group_key(entry),
                    "entry": entry,
                    "target_label": entry.get("target_label") or entry.get("filename"),
                    "media_type": entry.get("media_type"),
                    "title": entry.get("title"),
                    "season": owner._safe_int(entry.get("season"), 0),
                    "episode": owner._safe_int(entry.get("episode"), 0),
                    "status": "pending",
                    "active": True,
                    "message": "等待入库自动字幕处理",
                    "created_ts": now,
                    "updated_ts": now,
                    "next_run_ts": 0,
                    "result": {},
                }
                active_keys.add(entry_key)
                queued += 1
            owner._trim_auto_transfer_tasks_locked()
        if queued:
            owner._ensure_transfer_auto_worker()
        return queued, skipped

    def ensure_transfer_auto_worker(self) -> None:
        owner = self._owner
        with owner._transfer_auto_lock:
            if getattr(owner, "_auto_transfer_stopping", False):
                return
            worker = owner._auto_transfer_worker
            if worker and worker.is_alive():
                return
            worker = self._threading.Thread(
                target=owner._auto_transfer_queue_loop,
                name="SubtitleManualUploadTransferQueue",
                daemon=True,
            )
            owner._auto_transfer_worker = worker
            worker.start()

    def update_auto_transfer_task(self, task_id: str, **updates: Any) -> None:
        owner = self._owner
        with owner._transfer_auto_lock:
            task = (owner._auto_transfer_tasks or OrderedDict()).get(task_id)
            if not task:
                return
            task.update(updates)
            task["updated_ts"] = self._time.time()
            if task.get("status") not in {"pending", "in_progress"}:
                task["active"] = False
                task["next_run_ts"] = 0
            owner._auto_transfer_tasks.move_to_end(task_id)
            owner._trim_auto_transfer_tasks_locked()

    def claim_next_auto_transfer_batch(self) -> Tuple[List[Dict[str, Any]], float]:
        owner = self._owner
        with owner._transfer_auto_lock:
            if getattr(owner, "_auto_transfer_stopping", False):
                owner._auto_transfer_worker = None
                return [], -1
            pending = [
                task
                for task in (owner._auto_transfer_tasks or OrderedDict()).values()
                if task.get("status") == "pending"
            ]
            if not pending:
                owner._auto_transfer_worker = None
                return [], -1
            first = pending[0]
            group_key = owner._normalize_text(first.get("group_key"))
            group = [task for task in pending if owner._normalize_text(task.get("group_key")) == group_key]
            is_tv_group = owner._normalize_text(first.get("media_type")) == "tv"
            if is_tv_group:
                newest = max(float(task.get("created_ts") or 0) for task in group)
                wait_seconds = owner._auto_transfer_queue_debounce_seconds - (self._time.time() - newest)
                if wait_seconds > 0:
                    for task in group:
                        task["next_run_ts"] = self._time.time() + wait_seconds
                        task["message"] = "等待同季入库事件聚合"
                    return [], min(wait_seconds, 1.0)
                batch = group
            else:
                batch = [first]
            now = self._time.time()
            for task in batch:
                task["status"] = "in_progress"
                task["active"] = True
                task["message"] = "入库自动字幕处理中"
                task["updated_ts"] = now
                task["next_run_ts"] = 0
            return [owner._json_clone(task) for task in batch], 0

    def auto_wait_online_rate_limit(self, providers: Iterable[str], task_ids: Optional[List[str]] = None) -> None:
        owner = self._owner
        provider_ids = sorted({owner._normalize_text(provider).lower() for provider in providers if owner._normalize_text(provider)})
        if not provider_ids:
            return
        task_ids = task_ids or []
        while True:
            now = self._time.time()
            wait_until = 0.0
            with owner._transfer_auto_lock:
                for provider_id in provider_ids:
                    records = [item for item in owner._online_rate_records.get(provider_id, []) if now - item < 60]
                    owner._online_rate_records[provider_id] = records
                    if len(records) >= owner._online_rate_limit_per_minute:
                        wait_until = max(wait_until, min(records) + 60)
                if wait_until <= now:
                    for provider_id in provider_ids:
                        records = [item for item in owner._online_rate_records.get(provider_id, []) if now - item < 60]
                        records.append(now)
                        owner._online_rate_records[provider_id] = records
                    for task_id in task_ids:
                        task = owner._auto_transfer_tasks.get(task_id)
                        if task and task.get("status") == "in_progress":
                            task["next_run_ts"] = 0
                            task["message"] = "入库自动字幕处理中"
                    return
                for task_id in task_ids:
                    task = owner._auto_transfer_tasks.get(task_id)
                    if task and task.get("status") == "in_progress":
                        task["next_run_ts"] = wait_until
                        task["message"] = f"等待字幕源限速窗口：{','.join(provider_ids)}"
            self._time.sleep(max(0.5, min(wait_until - now, 5.0)))

    def auto_transfer_rate_status(self) -> Dict[str, Any]:
        owner = self._owner
        now = self._time.time()
        status: Dict[str, Any] = {}
        for provider_id in owner._auto_search_providers():
            records = [item for item in owner._online_rate_records.get(provider_id, []) if now - item < 60]
            remaining = max(0, owner._online_rate_limit_per_minute - len(records))
            reset_ts = min(records) + 60 if records else 0
            status[provider_id] = {
                "used": len(records),
                "remaining": remaining,
                "limit_per_minute": owner._online_rate_limit_per_minute,
                "reset_at": owner._timestamp_iso(reset_ts),
            }
        return status

    def auto_transfer_queue_summary(self) -> Dict[str, Any]:
        owner = self._owner
        with owner._transfer_auto_lock:
            tasks = list((owner._auto_transfer_tasks or OrderedDict()).values())
            worker_alive = bool(owner._auto_transfer_worker and owner._auto_transfer_worker.is_alive())
        summary = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "skipped": 0,
            "failed": 0,
            "active": 0,
            "total": len(tasks),
            "worker_alive": worker_alive,
        }
        for task in tasks:
            status = task.get("status")
            if status in summary:
                summary[status] += 1
            if task.get("active") or status in {"pending", "in_progress"}:
                summary["active"] += 1
        return summary

    def auto_transfer_queue_snapshot(self, limit: int = 100) -> Dict[str, Any]:
        owner = self._owner
        with owner._transfer_auto_lock:
            tasks = [owner._json_clone(task) for task in (owner._auto_transfer_tasks or OrderedDict()).values()]
        pending_position = 0
        public_tasks: List[Dict[str, Any]] = []
        for task in tasks[-limit:]:
            if task.get("status") == "pending":
                pending_position += 1
                task["queue_position"] = pending_position
            task.pop("entry", None)
            task["created_at"] = owner._timestamp_iso(task.pop("created_ts", 0))
            task["updated_at"] = owner._timestamp_iso(task.pop("updated_ts", 0))
            task["next_run_at"] = owner._timestamp_iso(task.pop("next_run_ts", 0))
            public_tasks.append(task)
        cache_items = []
        for item in list((owner._auto_season_package_cache or OrderedDict()).values())[-20:]:
            cache_items.append(
                {
                    "key": item.get("key"),
                    "title": item.get("title"),
                    "season": item.get("season"),
                    "subtitle_count": len(item.get("items") or []),
                    "updated_at": item.get("updated_at", ""),
                    "provider": item.get("provider", ""),
                    "source_title": item.get("source_title", ""),
                }
            )
        return {
            "summary": owner._auto_transfer_queue_summary(),
            "tasks": public_tasks,
            "rate_limits": owner._auto_transfer_rate_status(),
            "season_package_cache": cache_items,
            "debounce_seconds": owner._auto_transfer_queue_debounce_seconds,
            "rate_limit_scope": "provider",
        }

    def auto_transfer_queue_loop(self) -> None:
        owner = self._owner
        while True:
            batch, wait_seconds = owner._claim_next_auto_transfer_batch()
            if wait_seconds < 0:
                return
            if not batch:
                self._time.sleep(max(0.2, wait_seconds))
                continue
            try:
                owner._process_transfer_auto_task_batch(batch)
            except Exception as exc:
                self._logger.warning("[SubtitleManualUpload] 入库自动字幕队列批次失败: %s", exc)
                for task in batch:
                    owner._update_auto_transfer_task(
                        task["id"],
                        status="failed",
                        message=f"入库自动字幕处理异常: {exc}",
                    )

    def auto_search_keywords_for_entry(self, entry: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
        owner = self._owner
        media = owner._auto_media_for_entry(entry)
        owner._apply_tmdb_detail(target, media)
        return build_search_keywords(media, [target], "auto")[:8]


    def auto_search_providers(self) -> List[str]:
        owner = self._owner
        return [item for item in (owner._online_provider_ids or []) if item in {"assrt", "opensubtitles"}]


    def auto_search_write_subtitle(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        target = target or self._target_from_entry(entry)
        providers = owner._auto_search_providers()
        if not providers:
            return {"status": "skipped", "reason": "未配置可用 API 字幕源", "target": target.get("label")}
        keywords = owner._auto_search_keywords_for_entry(entry, target)
        if not keywords:
            return {"status": "skipped", "reason": "没有可用搜索关键词", "target": target.get("label")}

        if queue_rate_limited:
            self._wait_online_rate_limit(providers, task_ids=task_ids)
        else:
            self._check_online_rate_limit(providers)
        service = self._online_service()
        search_result = service.search(
            keywords=keywords,
            providers=providers,
            targets=[target],
            scope="auto",
        )
        candidates = [
            item
            for item in search_result.get("results") or []
            if item.get("downloadable") is not False and owner._safe_int(item.get("score"), 0) >= owner._auto_search_min_score
        ]
        if not candidates:
            return {
                "status": "skipped",
                "reason": "没有高置信可下载结果",
                "target": target.get("label"),
                "results": len(search_result.get("results") or []),
                "search_results": len(search_result.get("results") or []),
            }

        last_reason = ""
        for selected in candidates[:5]:
            session_id = owner._hash_text(f"auto|{datetime.now().isoformat()}|{entry.get('id')}")[:16]
            session_dir = owner._get_session_root() / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            try:
                downloads = service.download([selected])
                prepared_uploads: List[Dict[str, Any]] = []
                for downloaded in downloads:
                    result = downloaded.get("result") or {}
                    source_name = self._normalize_online_download_name(
                        downloaded.get("source_name", ""),
                        downloaded.get("content") or b"",
                        result,
                    )
                    try:
                        extracted = self._extract_subtitle_files(
                            source_name,
                            downloaded.get("content") or b"",
                            session_dir,
                        )
                    except ValueError as exc:
                        last_reason = f"下载包解析失败: {owner._normalize_text(exc)}"
                        self._logger.warning(
                            "[SubtitleManualUpload] 自动字幕候选解析失败 target=%s provider=%s result=%s error=%s",
                            target.get("label"),
                            selected.get("provider"),
                            selected.get("title"),
                            exc,
                        )
                        continue
                    if not extracted:
                        last_reason = "下载包未解析到字幕文件"
                        self._logger.info(
                            "[SubtitleManualUpload] 自动字幕候选无字幕文件，尝试下一结果 target=%s provider=%s result=%s",
                            target.get("label"),
                            selected.get("provider"),
                            selected.get("title"),
                        )
                        continue
                    for item in extracted:
                        item["online_source"] = downloaded.get("provider")
                        item["online_title"] = result.get("title", "")
                        if not item.get("archive_name") and source_name != item.get("source_name"):
                            item["archive_name"] = source_name
                    prepared_uploads.extend(extracted)
                if not prepared_uploads:
                    continue
                write_result = owner._auto_write_prepared_uploads_for_entries(
                    target_entries=[entry],
                    prepared_uploads=prepared_uploads,
                    session_dir=session_dir,
                    selected_result=selected,
                )
                if write_result.get("status") == "written":
                    ai_count = owner._safe_int(write_result.get("ai_count"), 0)
                    written_count = owner._safe_int(write_result.get("written_count"), 0)
                    if ai_count and not written_count:
                        ai_submit = write_result.get("ai_translate") or {}
                        ai_result = {
                            "status": "ai_submitted" if ai_submit.get("added") else "skipped",
                            "reason": "自动入库外语字幕已智能调轴后提交 AI 翻译",
                            "target": target.get("label"),
                            "ai": {
                                "added": len(ai_submit.get("added") or []),
                                "skipped": len(ai_submit.get("skipped") or []),
                                "failed": len(ai_submit.get("failed") or []),
                            },
                            "tasks": ai_submit.get("tasks"),
                        }
                        return {
                            "status": ai_result["status"],
                            "target": target.get("label"),
                            "result": selected.get("title"),
                            "fixed_subtitles": write_result.get("fixed_subtitles") or [],
                            "candidate_count": len(candidates),
                            "search_results": len(search_result.get("results") or []),
                            "ai": ai_result,
                        }
                    return {
                        "status": "written",
                        "target": target.get("label"),
                        "result": selected.get("title"),
                        "written": write_result.get("written") or [],
                        "written_by_target": write_result.get("written_by_target") or {},
                        "ai_by_target": write_result.get("ai_by_target") or {},
                        "ai_translate": write_result.get("ai_translate"),
                        "fixed_subtitles": write_result.get("fixed_subtitles") or [],
                        "written_count": written_count,
                        "ai_count": ai_count,
                        "simplified_count": write_result.get("simplified_count", 0),
                        "candidate_count": len(candidates),
                        "search_results": len(search_result.get("results") or []),
                    }
                last_reason = write_result.get("reason") or "下载包字幕未按偏好匹配"
            except Exception as exc:
                last_reason = f"自动下载在线字幕失败: {owner._normalize_text(exc)}"
                self._logger.warning(
                    "[SubtitleManualUpload] %s target=%s provider=%s result=%s",
                    last_reason,
                    target.get("label"),
                    selected.get("provider"),
                    selected.get("title"),
                )
            finally:
                shutil.rmtree(session_dir, ignore_errors=True)

        return {
            "status": "skipped",
            "reason": last_reason or "高置信结果未解析到可用字幕文件",
            "target": target.get("label"),
            "candidate_count": len(candidates),
            "search_results": len(search_result.get("results") or []),
        }


    def auto_search_and_write_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        owner = self._owner
        target = self._target_from_entry(entry)
        if self._auto_target_has_chinese_subtitle(entry, target):
            return {"status": "skipped", "reason": "目标已有中文字幕", "target": target.get("label")}
        if target.get("has_subtitle"):
            self._logger.info(
                "[SubtitleManualUpload] 目标已有外挂字幕但未确认中文，继续自动匹配/AI target=%s",
                target.get("label"),
            )
        return self._auto_search_write_subtitle(entry, target)


    def auto_submit_ai_for_entry(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        owner = self._owner
        target = target or self._target_from_entry(entry)
        try:
            result = self._submit_autosub_for_entries(
                [entry],
                trigger="subtitle_fallback",
                source_policy="auto",
                overwrite_policy="skip",
            )
        except self._http_exception as exc:
            return {
                "status": "failed",
                "reason": owner._normalize_text(getattr(exc, "detail", "")) or str(exc),
                "target": target.get("label"),
                "ai_reason": reason,
            }
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 入库自动字幕提交 AI 失败 target=%s error=%s", target.get("label"), exc)
            return {
                "status": "failed",
                "reason": f"AI 字幕任务提交失败: {exc}",
                "target": target.get("label"),
                "ai_reason": reason,
            }

        added = result.get("added") or []
        skipped = result.get("skipped") or []
        failed = result.get("failed") or []
        if added:
            status = "ai_submitted"
            message = f"已提交 AI 字幕任务 {len(added)} 个"
        elif failed:
            status = "failed"
            message = (
                owner._normalize_text((failed[0] or {}).get("reason"))
                if isinstance(failed[0], dict)
                else "AI 字幕任务提交失败"
            )
        elif skipped:
            status = "skipped"
            first = skipped[0] if isinstance(skipped[0], dict) else {}
            message = owner._normalize_text(first.get("reason")) or "AI 字幕任务已跳过"
        else:
            status = "skipped"
            message = "AI 插件未返回新增任务"
        return {
            "status": status,
            "reason": message,
            "target": target.get("label"),
            "ai_reason": reason,
            "ai": {
                "added": len(added),
                "skipped": len(skipped),
                "failed": len(failed),
            },
        }


    def auto_process_transfer_entry(
        self,
        entry: Dict[str, Any],
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        target = self._target_from_entry(entry)
        strategy = owner._normalize_auto_transfer_subtitle_strategy(owner._auto_transfer_subtitle_strategy)
        base = {"strategy": strategy, "target": target.get("label")}

        if self._auto_target_has_chinese_subtitle(entry, target):
            return {**base, "status": "skipped", "reason": "目标已有中文字幕"}
        if target.get("has_subtitle"):
            self._logger.info(
                "[SubtitleManualUpload] 目标已有外挂字幕但未确认中文，继续自动匹配/AI target=%s",
                target.get("label"),
            )

        if owner._auto_skip_chinese_media_on_transfer:
            is_chinese, evidence = owner._is_chinese_transfer_media(entry)
            if is_chinese:
                return {**base, "status": "skipped", "reason": f"中文资源自动跳过：{evidence}"}
            self._logger.info(
                "[SubtitleManualUpload] 入库自动字幕中文识别未跳过 target=%s evidence=%s",
                target.get("label"),
                evidence,
            )

        if strategy == "ai_source_only":
            return {**base, **owner._auto_submit_ai_for_entry(entry, target, "策略 ai_source_only")}

        search_result = owner._call_auto_search_write_subtitle(
            entry,
            target,
            queue_rate_limited=queue_rate_limited,
            task_ids=task_ids,
        )
        if strategy == "online_source_only" or search_result.get("status") == "written":
            return {**base, **search_result}

        ai_result = owner._auto_submit_ai_for_entry(entry, target, "搜索无单一高置信结果后兜底")
        return {**base, **ai_result, "search": search_result}


    def auto_prepared_items_for_targets(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            try:
                raw_bytes = Path(prepared["stored_path"]).read_bytes()
            except Exception:
                raw_bytes = b""
            language_profile = self._detect_language_profile(prepared.get("source_name", ""), raw_bytes)
            items.append(
                {
                    "upload_id": prepared["upload_id"],
                    "source_name": prepared.get("source_name", ""),
                    "archive_name": prepared.get("archive_name", ""),
                    "ext": prepared.get("ext") or Path(prepared.get("source_name", "")).suffix.lower() or ".srt",
                    "target_id": owner._suggest_target(prepared, targets),
                    "detected_label": language_profile["label"],
                    "language_suffix": language_profile["suffix"],
                    "online_source": prepared.get("online_source", ""),
                }
            )
        owner._auto_fill_missing_targets(items, targets)
        return items


    def select_auto_subtitle_items(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        items = owner._auto_prepared_items_for_targets(prepared_uploads, targets)
        if not items:
            return []

        mode = normalize_auto_multi_subtitle_mode(getattr(owner, "_auto_multi_subtitle_mode", "best"))
        target_lookup = {item.get("id"): item for item in targets if item.get("id")}
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            target_id = owner._normalize_text(item.get("target_id"))
            if not target_id:
                continue
            grouped.setdefault(target_id, []).append(item)

        selected: List[Dict[str, Any]] = []
        for target_id, group in grouped.items():
            sorted_group = sorted(group, key=self._auto_subtitle_sort_key)
            chinese_group = [item for item in sorted_group if owner._is_chinese_language_suffix(item.get("language_suffix"))]
            foreign_group = [item for item in sorted_group if not owner._is_chinese_language_suffix(item.get("language_suffix"))]
            if mode == "all":
                chosen = [*chinese_group, *foreign_group]
            elif mode == "chinese_all":
                chosen = chinese_group or sorted_group[:1]
            else:
                chosen = sorted_group[:1]

            seen_destinations = set()
            target = target_lookup.get(target_id)
            for item in chosen:
                if target:
                    destination_key = owner._build_destination_name(target, item)
                else:
                    destination_key = f"{target_id}|{item.get('source_name')}"
                if destination_key in seen_destinations:
                    continue
                seen_destinations.add(destination_key)
                selected.append(item)
        return selected


    def auto_write_prepared_uploads_for_entries(
        self,
        *,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        session_dir: Path,
        selected_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        targets = [self._target_from_entry(entry) for entry in target_entries]
        target_entry_map = {owner._normalize_text(entry.get("id")): entry for entry in target_entries}
        upload_map = {item["upload_id"]: item for item in prepared_uploads if item.get("upload_id")}
        chosen_items = [
            item
            for item in owner._select_auto_subtitle_items(prepared_uploads, targets)
            if owner._normalize_text(item.get("target_id")) in target_entry_map
        ]
        used_targets = {owner._normalize_text(item.get("target_id")) for item in chosen_items}
        if not chosen_items:
            return {
                "status": "skipped",
                "reason": "整季包未能匹配到当前入库集数",
                "written_by_target": {},
                "prepared_count": len(prepared_uploads),
            }

        missing_target_ids = [
            target_id
            for target_id in target_entry_map
            if target_id not in used_targets
        ]
        chinese_items = [item for item in chosen_items if owner._is_chinese_language_suffix(item.get("language_suffix"))]
        foreign_items = [item for item in chosen_items if not owner._is_chinese_language_suffix(item.get("language_suffix"))]

        written: List[Dict[str, Any]] = []
        simplified_count = 0
        operations: List[Dict[str, Any]] = []
        if chinese_items:
            operations = owner._build_write_operations(chinese_items, upload_map, target_entry_map)
            written, _, simplified_count = self._write_operations_to_disk(
                session_dir=session_dir,
                operations=operations,
                fix_timeline=True,
            )

        ai_submit_result: Optional[Dict[str, Any]] = None
        fixed_subtitles: List[Dict[str, Any]] = []
        if foreign_items:
            foreign_target_ids = {owner._normalize_text(item.get("target_id")) for item in foreign_items}
            foreign_entries = [entry for target_id, entry in target_entry_map.items() if target_id in foreign_target_ids]
            foreign_upload_ids = {item.get("upload_id") for item in foreign_items}
            foreign_uploads = [item for item in prepared_uploads if item.get("upload_id") in foreign_upload_ids]
            subtitle_overrides, fixed_subtitles = self._prepare_online_ai_subtitle_overrides(
                session_dir=session_dir,
                target_entries=foreign_entries,
                prepared_uploads=foreign_uploads,
            )
            ai_submit_result = self._submit_autosub_for_entries(
                foreign_entries,
                subtitle_overrides=subtitle_overrides,
                trigger="subtitle_fallback",
                source_policy="matched_external",
                overwrite_policy="new_variant",
            )

        written_by_target: Dict[str, Dict[str, Any]] = {}
        for operation, written_item in zip(operations, written):
            target_id = owner._normalize_text(operation["target_entry"].get("id"))
            written_by_target[target_id] = written_item
        ai_by_target: Dict[str, Dict[str, Any]] = {}
        if ai_submit_result:
            path_to_target_id = {
                owner._normalize_text(entry.get("path")): target_id
                for target_id, entry in target_entry_map.items()
                if owner._normalize_text(entry.get("path"))
            }
            added_target_ids = {
                path_to_target_id.get(owner._normalize_text(item.get("path")))
                for item in ai_submit_result.get("added") or []
                if isinstance(item, dict)
            }
            added_target_ids.discard(None)
            for fixed_item in fixed_subtitles:
                target_id = owner._normalize_text(fixed_item.get("target_id"))
                if target_id and target_id in added_target_ids:
                    ai_by_target[target_id] = fixed_item

        total_completed = len(written_by_target) + len(ai_by_target)
        coverage_complete = not missing_target_ids and total_completed >= len(target_entry_map)
        ai_failed_count = len((ai_submit_result or {}).get("failed") or [])
        ai_skipped_count = len((ai_submit_result or {}).get("skipped") or [])
        reason = "" if coverage_complete else f"整季包覆盖 {total_completed}/{len(target_entry_map)} 集"
        if not ai_by_target and (ai_failed_count or ai_skipped_count):
            reason = f"AI 字幕任务未新增，跳过 {ai_skipped_count} 个，失败 {ai_failed_count} 个"
        return {
            "status": "written" if total_completed else "skipped",
            "reason": reason,
            "result": (selected_result or {}).get("title"),
            "provider": (selected_result or {}).get("provider"),
            "written": written,
            "written_by_target": written_by_target,
            "ai_by_target": ai_by_target,
            "ai_translate": ai_submit_result,
            "fixed_subtitles": fixed_subtitles,
            "written_count": len(written),
            "ai_count": len(ai_by_target),
            "completed_count": total_completed,
            "prepared_count": len(prepared_uploads),
            "simplified_count": simplified_count,
            "missing_target_ids": missing_target_ids,
            "coverage_complete": coverage_complete,
        }


    def store_auto_season_package_cache(
        self,
        entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        selected_result: Dict[str, Any],
    ) -> None:
        owner = self._owner
        if not entries or not prepared_uploads:
            return
        cache_key = owner._auto_season_cache_key(entries[0])
        if not cache_key:
            return
        cache_dir = owner._auto_season_cache_dir(cache_key)
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


    def load_auto_season_package_cache(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        owner = self._owner
        cache_key = owner._auto_season_cache_key(entry)
        if not cache_key:
            return None
        cached = (owner._auto_season_package_cache or OrderedDict()).get(cache_key)
        if cached:
            return cached
        manifest = owner._auto_season_cache_dir(cache_key) / "manifest.json"
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


    def auto_write_from_season_cache(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        owner = self._owner
        if not entries:
            return {"status": "skipped", "reason": "没有待处理目标", "written_by_target": {}}
        cached = owner._load_auto_season_package_cache(entries[0])
        if not cached:
            return {"status": "skipped", "reason": "没有整季字幕包缓存", "written_by_target": {}}
        session_id = owner._hash_text(f"auto-season-cache|{datetime.now().isoformat()}|{cached.get('key')}")[:16]
        session_dir = owner._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = owner._auto_write_prepared_uploads_for_entries(
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


    def auto_search_write_season_package(
        self,
        entries: List[Dict[str, Any]],
        *,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        if not entries:
            return {"status": "skipped", "reason": "没有待处理目标", "written_by_target": {}}
        providers = owner._auto_search_providers()
        if not providers:
            return {"status": "skipped", "reason": "未配置可用 API 字幕源", "written_by_target": {}}
        targets = [self._target_from_entry(entry) for entry in entries]
        media = owner._auto_media_for_entry(entries[0])
        owner._apply_tmdb_detail(targets[0], media)
        keywords = build_search_keywords(media, targets, "season")[:8]
        if not keywords:
            return {"status": "skipped", "reason": "没有可用整季搜索关键词", "written_by_target": {}}

        self._wait_online_rate_limit(providers, task_ids=task_ids)
        service = self._online_service()
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
            session_dir = owner._get_session_root() / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            try:
                downloads = service.download([selected])
                prepared_uploads: List[Dict[str, Any]] = []
                for downloaded in downloads:
                    result = downloaded.get("result") or {}
                    source_name = self._normalize_online_download_name(
                        downloaded.get("source_name", ""),
                        downloaded.get("content") or b"",
                        result,
                    )
                    extracted = self._extract_subtitle_files(
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
                owner._store_auto_season_package_cache(entries, prepared_uploads, selected)
                write_result = owner._auto_write_prepared_uploads_for_entries(
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


    def auto_process_transfer_group(self, entries: List[Dict[str, Any]], task_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        results: Dict[str, Dict[str, Any]] = {}
        strategy = owner._normalize_auto_transfer_subtitle_strategy(owner._auto_transfer_subtitle_strategy)
        if not entries:
            return results
        if strategy == "ai_source_only":
            for entry in entries:
                results[owner._auto_task_result_key(entry)] = self.auto_process_transfer_entry(
                    entry,
                    queue_rate_limited=True,
                    task_ids=task_ids,
                )
            return results

        pending_entries: List[Dict[str, Any]] = []
        for entry in entries:
            key = owner._auto_task_result_key(entry)
            target = self._target_from_entry(entry)
            base = {"strategy": strategy, "target": target.get("label")}
            if self._auto_target_has_chinese_subtitle(entry, target):
                results[key] = {**base, "status": "skipped", "reason": "目标已有中文字幕"}
                continue
            if target.get("has_subtitle"):
                self._logger.info(
                    "[SubtitleManualUpload] 目标已有外挂字幕但未确认中文，继续自动匹配/AI target=%s",
                    target.get("label"),
                )
            if owner._auto_skip_chinese_media_on_transfer:
                is_chinese, evidence = owner._is_chinese_transfer_media(entry)
                if is_chinese:
                    results[key] = {**base, "status": "skipped", "reason": f"中文资源自动跳过：{evidence}"}
                    continue
            pending_entries.append(entry)

        cache_result = owner._auto_write_from_season_cache(pending_entries)
        written_by_target = cache_result.get("written_by_target") or {}
        ai_by_target = cache_result.get("ai_by_target") or {}
        remaining_entries: List[Dict[str, Any]] = []
        for entry in pending_entries:
            key = owner._auto_task_result_key(entry)
            target_id = owner._normalize_text(entry.get("id"))
            if target_id in written_by_target:
                results[key] = {
                    "strategy": strategy,
                    "status": "written",
                    "target": self._target_from_entry(entry).get("label"),
                    "result": cache_result.get("result"),
                    "written": [written_by_target[target_id]],
                    "from_cache": True,
                    "season_package": True,
                }
            elif target_id in ai_by_target:
                results[key] = {
                    "strategy": strategy,
                    "status": "ai_submitted",
                    "target": self._target_from_entry(entry).get("label"),
                    "result": cache_result.get("result"),
                    "fixed_subtitles": [ai_by_target[target_id]],
                    "ai": cache_result.get("ai_translate"),
                    "from_cache": True,
                    "season_package": True,
                }
            else:
                remaining_entries.append(entry)

        if remaining_entries:
            season_result = owner._auto_search_write_season_package(remaining_entries, task_ids=task_ids)
            written_by_target = season_result.get("written_by_target") or {}
            ai_by_target = season_result.get("ai_by_target") or {}
            next_remaining: List[Dict[str, Any]] = []
            for entry in remaining_entries:
                key = owner._auto_task_result_key(entry)
                target_id = owner._normalize_text(entry.get("id"))
                if target_id in written_by_target:
                    results[key] = {
                        "strategy": strategy,
                        "status": "written",
                        "target": self._target_from_entry(entry).get("label"),
                        "result": season_result.get("result"),
                        "written": [written_by_target[target_id]],
                        "season_package": True,
                        "candidate_count": season_result.get("candidate_count"),
                        "search_results": season_result.get("search_results"),
                    }
                elif target_id in ai_by_target:
                    results[key] = {
                        "strategy": strategy,
                        "status": "ai_submitted",
                        "target": self._target_from_entry(entry).get("label"),
                        "result": season_result.get("result"),
                        "fixed_subtitles": [ai_by_target[target_id]],
                        "ai": season_result.get("ai_translate"),
                        "season_package": True,
                        "candidate_count": season_result.get("candidate_count"),
                        "search_results": season_result.get("search_results"),
                    }
                else:
                    next_remaining.append(entry)
            remaining_entries = next_remaining

        for entry in remaining_entries:
            key = owner._auto_task_result_key(entry)
            results[key] = self.auto_process_transfer_entry(
                entry,
                queue_rate_limited=True,
                task_ids=task_ids,
            )
        return results


    def process_transfer_auto_task_batch(self, tasks: List[Dict[str, Any]]) -> None:
        owner = self._owner
        entries = [task.get("entry") for task in tasks if isinstance(task.get("entry"), dict)]
        task_ids = [task["id"] for task in tasks if task.get("id")]
        is_tv_batch = (
            bool(entries)
            and all(owner._normalize_text(entry.get("media_type")) == "tv" for entry in entries)
            and len({owner._auto_transfer_group_key(entry) for entry in entries}) == 1
        )
        if is_tv_batch:
            results = self.auto_process_transfer_group(entries, task_ids=task_ids)
        else:
            results = {
                owner._auto_task_result_key(entry): self.auto_process_transfer_entry(
                    entry,
                    queue_rate_limited=True,
                    task_ids=task_ids,
                )
                for entry in entries
            }
        for task in tasks:
            entry = task.get("entry") or {}
            result = results.get(owner._auto_task_result_key(entry)) or {
                "status": "failed",
                "reason": "入库自动字幕任务没有返回结果",
            }
            status = result.get("status") if result.get("status") in {"completed", "written", "skipped", "failed", "ai_submitted"} else "completed"
            public_status = "completed" if status in {"written", "ai_submitted"} else status
            owner._update_auto_transfer_task(
                task["id"],
                status=public_status,
                message=result.get("reason") or result.get("status") or public_status,
                result=result,
            )
            self._logger.info(
                "[SubtitleManualUpload] 入库自动字幕处理完成 target=%s strategy=%s status=%s reason=%s",
                result.get("target") or entry.get("target_label") or entry.get("filename"),
                result.get("strategy"),
                result.get("status"),
                result.get("reason", ""),
            )

    def process_transfer_auto_subtitles(self, entries: List[Dict[str, Any]]) -> None:
        owner = self._owner
        for entry in entries:
            try:
                result = self.auto_process_transfer_entry(entry)
                self._logger.info(
                    "[SubtitleManualUpload] 入库自动字幕处理完成 target=%s strategy=%s status=%s reason=%s",
                    result.get("target"),
                    result.get("strategy"),
                    result.get("status"),
                    result.get("reason", ""),
                )
            except Exception as exc:
                self._logger.warning(
                    "[SubtitleManualUpload] 入库自动字幕处理失败 target=%s error=%s",
                    entry.get("target_label") or entry.get("filename"),
                    exc,
                )
