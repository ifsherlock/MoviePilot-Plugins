from __future__ import annotations

from typing import Any, Callable, Dict


AUTO_TRANSFER_ACTIVE_STATUSES = {"pending", "in_progress"}
AUTO_TRANSFER_PUBLIC_STATUSES = {"pending", "in_progress", "completed", "skipped", "failed"}


def build_auto_transfer_task(
    *,
    task_id: str,
    entry_key: str,
    group_key: str,
    entry: Dict[str, Any],
    now: float,
    safe_int: Callable[[Any, int], int],
) -> Dict[str, Any]:
    return {
        "id": task_id,
        "entry_key": entry_key,
        "group_key": group_key,
        "entry": entry,
        "target_label": entry.get("target_label") or entry.get("filename"),
        "media_type": entry.get("media_type"),
        "title": entry.get("title"),
        "season": safe_int(entry.get("season"), 0),
        "episode": safe_int(entry.get("episode"), 0),
        "status": "pending",
        "active": True,
        "message": "等待入库自动字幕处理",
        "created_ts": now,
        "updated_ts": now,
        "next_run_ts": 0,
        "result": {},
    }


def is_auto_transfer_task_active(task: Dict[str, Any]) -> bool:
    status = task.get("status")
    return bool(task.get("active")) or status in AUTO_TRANSFER_ACTIVE_STATUSES


def public_auto_transfer_task(
    task: Dict[str, Any],
    *,
    timestamp_iso: Callable[[Any], str],
    queue_position: int = 0,
) -> Dict[str, Any]:
    public_task = dict(task)
    if public_task.get("status") == "pending" and queue_position:
        public_task["queue_position"] = queue_position
    public_task.pop("entry", None)
    public_task["created_at"] = timestamp_iso(public_task.pop("created_ts", 0))
    public_task["updated_at"] = timestamp_iso(public_task.pop("updated_ts", 0))
    public_task["next_run_at"] = timestamp_iso(public_task.pop("next_run_ts", 0))
    return public_task
