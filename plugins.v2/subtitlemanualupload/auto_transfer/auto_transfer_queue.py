from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Tuple

from .auto_transfer_models import (
    AUTO_TRANSFER_ACTIVE_STATUSES,
    AUTO_TRANSFER_PUBLIC_STATUSES,
    build_auto_transfer_task,
    is_auto_transfer_task_active,
    public_auto_transfer_task,
)


class AutoTransferQueue:
    def __init__(
        self,
        owner: Any,
        *,
        time_module: Any,
        ensure_worker: Optional[Callable[[], None]] = None,
        rate_status: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self._owner = owner
        self._time = time_module
        self._ensure_worker = ensure_worker
        self._rate_status = rate_status or (lambda: {})

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

    def transfer_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        path = owner._normalize_text(entry.get("path") or entry.get("relative_path"))
        if path:
            normalized_path = path.lower().replace("\\", "/")
            return owner._hash_text(f"{normalized_path}|{owner._entry_filesystem_signature(entry)}")
        return owner._normalize_text(entry.get("id") or entry.get("target_label") or entry.get("filename"))

    def claim_entries(self, entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
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
                key = self.transfer_key(entry)
                if not key:
                    claimed.append(entry)
                    continue
                if key in owner._transfer_auto_recent:
                    skipped += 1
                    continue
                owner._transfer_auto_recent[key] = now
                claimed.append(entry)
        return claimed, skipped

    def entry_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        return self.transfer_key(entry) or owner._hash_text(
            f"{entry.get('id')}|{entry.get('target_label')}|{entry.get('filename')}"
        )

    def group_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        if owner._normalize_text(entry.get("media_type")) != "tv":
            return self.entry_key(entry)
        media_key = owner._normalize_text(entry.get("media_key") or entry.get("tmdb_id") or entry.get("title"))
        season = owner._safe_int(entry.get("season"), 0)
        if not media_key or not season:
            return self.entry_key(entry)
        return f"tv|{media_key}|s{season:02d}"

    def trim_locked(self) -> None:
        owner = self._owner
        tasks = owner._auto_transfer_tasks or OrderedDict()
        while len(tasks) > owner._auto_transfer_queue_history_limit:
            removable = next(
                (
                    key
                    for key, task in tasks.items()
                    if task.get("status") not in AUTO_TRANSFER_ACTIVE_STATUSES
                ),
                None,
            )
            if not removable:
                break
            tasks.pop(removable, None)

    def enqueue_entries(self, entries: List[Dict[str, Any]]) -> Tuple[int, int]:
        owner = self._owner
        valid_entries = owner.services.local_media_catalog().filter_existing_local_entries(entries)
        if getattr(owner, "_auto_transfer_stopping", False):
            return 0, len(valid_entries) + (len(entries or []) - len(valid_entries))
        claimed, skipped = self.claim_entries(valid_entries)
        if not claimed:
            return 0, skipped + (len(entries or []) - len(valid_entries))
        now = self._time.time()
        queued = 0
        with owner._transfer_auto_lock:
            active_keys = {
                owner._normalize_text(task.get("entry_key"))
                for task in (owner._auto_transfer_tasks or OrderedDict()).values()
                if task.get("status") in AUTO_TRANSFER_ACTIVE_STATUSES
            }
            for entry in claimed:
                entry_key = self.entry_key(entry)
                if entry_key in active_keys:
                    skipped += 1
                    continue
                task_id = owner._hash_text(f"auto-transfer|{entry_key}|{now}")[:16]
                owner._auto_transfer_tasks[task_id] = build_auto_transfer_task(
                    task_id=task_id,
                    entry_key=entry_key,
                    group_key=self.group_key(entry),
                    entry=entry,
                    now=now,
                    safe_int=owner._safe_int,
                )
                active_keys.add(entry_key)
                queued += 1
            self.trim_locked()
        if queued and self._ensure_worker:
            self._ensure_worker()
        return queued, skipped

    def update_task(self, task_id: str, **updates: Any) -> None:
        owner = self._owner
        with owner._transfer_auto_lock:
            task = (owner._auto_transfer_tasks or OrderedDict()).get(task_id)
            if not task:
                return
            task.update(updates)
            task["updated_ts"] = self._time.time()
            if task.get("status") not in AUTO_TRANSFER_ACTIVE_STATUSES:
                task["active"] = False
                task["next_run_ts"] = 0
            owner._auto_transfer_tasks.move_to_end(task_id)
            self.trim_locked()

    def claim_next_batch(self) -> Tuple[List[Dict[str, Any]], float]:
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

    def summary(self) -> Dict[str, Any]:
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
            if status in AUTO_TRANSFER_PUBLIC_STATUSES:
                summary[status] += 1
            if is_auto_transfer_task_active(task):
                summary["active"] += 1
        return summary

    def snapshot(self, limit: int = 100) -> Dict[str, Any]:
        owner = self._owner
        with owner._transfer_auto_lock:
            tasks = [owner._json_clone(task) for task in (owner._auto_transfer_tasks or OrderedDict()).values()]
        pending_position = 0
        public_tasks: List[Dict[str, Any]] = []
        for task in tasks[-limit:]:
            if task.get("status") == "pending":
                pending_position += 1
            public_tasks.append(
                public_auto_transfer_task(
                    task,
                    timestamp_iso=owner._timestamp_iso,
                    queue_position=pending_position,
                )
            )
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
            "summary": self.summary(),
            "tasks": public_tasks,
            "rate_limits": self._rate_status(),
            "season_package_cache": cache_items,
            "debounce_seconds": owner._auto_transfer_queue_debounce_seconds,
            "rate_limit_scope": "provider",
        }
