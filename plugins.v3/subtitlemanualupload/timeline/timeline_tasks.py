from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


NormalizeText = Callable[[Any], str]
CacheLoadedAt = Callable[[Any], Optional[datetime]]
JsonClone = Callable[[Any], Any]


def timeline_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "skipped": 0,
        "failed": 0,
        "active": 0,
        "total": len(tasks),
    }
    for task in tasks:
        status = task.get("status")
        if status in counts:
            counts[status] += 1
        if task.get("active") or status in {"pending", "in_progress"}:
            counts["active"] += 1
    return counts


class TimelineTaskStore:
    def __init__(
        self,
        owner: Any,
        *,
        normalize_text: NormalizeText,
        cache_loaded_at: CacheLoadedAt,
        json_clone: JsonClone,
        timeline_task_ttl_seconds: int,
        max_tasks: int,
    ) -> None:
        self._owner = owner
        self._normalize_text = normalize_text
        self._cache_loaded_at = cache_loaded_at
        self._json_clone = json_clone
        self._timeline_task_ttl_seconds = timeline_task_ttl_seconds
        self._max_tasks = max_tasks

    def cleanup(self) -> None:
        tasks = self._owner._timeline_tasks or OrderedDict()
        cutoff = datetime.now() - timedelta(seconds=self._timeline_task_ttl_seconds)
        for key in list(tasks.keys()):
            updated_at = self._cache_loaded_at((tasks.get(key) or {}).get("updated_at"))
            if updated_at and updated_at < cutoff:
                tasks.pop(key, None)
        self._owner._timeline_tasks = tasks

    def task_for_target_id(self, target_id: Any) -> Optional[Dict[str, Any]]:
        self.cleanup()
        clean_id = self._normalize_text(target_id)
        if not clean_id:
            return None
        task = (self._owner._timeline_tasks or {}).get(clean_id)
        return self._json_clone(task) if task else None

    def set_task(
        self,
        operation: Dict[str, Any],
        *,
        status: str,
        message: str = "",
        timeline_result: Optional[Any] = None,
    ) -> None:
        target_entry = operation.get("target_entry") or {}
        target_id = self._normalize_text(target_entry.get("id"))
        if not target_id:
            return
        now = datetime.now().isoformat(timespec="seconds")
        timeline = timeline_result.to_dict() if timeline_result else None
        active = status in {"pending", "in_progress"}
        task = {
            "target_id": target_id,
            "target_label": target_entry.get("target_label")
            or target_entry.get("filename")
            or Path(self._normalize_text(target_entry.get("path"))).name,
            "source_name": (operation.get("upload_info") or {}).get("source_name", ""),
            "output_name": operation.get("destination_name", ""),
            "status": status,
            "active": active,
            "message": message or status,
            "status_label": {
                "pending": "等待调轴",
                "in_progress": "智能调轴中",
                "completed": "调轴完成",
                "skipped": "已跳过",
                "failed": "调轴失败",
            }.get(status, status),
            "timeline": timeline,
            "updated_at": now,
        }
        existing = (self._owner._timeline_tasks or OrderedDict()).get(target_id) or {}
        task["created_at"] = existing.get("created_at") or now
        self._owner._timeline_tasks[target_id] = task
        self._owner._timeline_tasks.move_to_end(target_id)
        while len(self._owner._timeline_tasks) > self._max_tasks:
            self._owner._timeline_tasks.popitem(last=False)

    def tasks_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        tasks: List[Dict[str, Any]] = []
        task_by_target: Dict[str, Any] = {}
        for entry in target_entries:
            target_id = self._normalize_text(entry.get("id"))
            task = self.task_for_target_id(target_id)
            if task:
                task_by_target[target_id] = task
                tasks.append(task)
            else:
                task_by_target[target_id] = None
        return {
            "summary": timeline_task_summary(tasks),
            "tasks": tasks,
            "task_by_target": task_by_target,
        }
