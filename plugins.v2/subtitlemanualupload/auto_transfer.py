from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Tuple


class AutoTransferService:
    def __init__(
        self,
        owner: Any,
        *,
        logger: Any,
        threading_module: Any,
        time_module: Any,
    ) -> None:
        self._owner = owner
        self._logger = logger
        self._threading = threading_module
        self._time = time_module

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
            results = owner._auto_process_transfer_group(entries, task_ids=task_ids)
        else:
            results = {
                owner._auto_task_result_key(entry): owner._auto_process_transfer_entry(
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
                result = owner._auto_process_transfer_entry(entry)
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
