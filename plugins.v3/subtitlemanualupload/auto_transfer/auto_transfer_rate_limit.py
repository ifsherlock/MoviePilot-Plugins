from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


RATE_LIMIT_WINDOW_SECONDS = 60


class AutoTransferRateLimiter:
    def __init__(self, owner: Any, *, time_module: Any) -> None:
        self._owner = owner
        self._time = time_module

    def wait(self, providers: Iterable[str], task_ids: Optional[List[str]] = None) -> None:
        owner = self._owner
        provider_ids = self._provider_ids(providers)
        if not provider_ids:
            return
        task_ids = task_ids or []
        while True:
            now = self._time.time()
            wait_until = 0.0
            with owner._transfer_auto_lock:
                for provider_id in provider_ids:
                    records = self._recent_records(provider_id, now, persist=True)
                    if len(records) >= owner._online_rate_limit_per_minute:
                        wait_until = max(wait_until, min(records) + RATE_LIMIT_WINDOW_SECONDS)
                if wait_until <= now:
                    for provider_id in provider_ids:
                        records = self._recent_records(provider_id, now, persist=False)
                        records.append(now)
                        owner._online_rate_records[provider_id] = records
                    self._clear_waiting_tasks(task_ids)
                    return
                self._update_waiting_tasks(task_ids, wait_until, provider_ids)
            self._time.sleep(max(0.5, min(wait_until - now, 5.0)))

    def status(self, providers: Iterable[str]) -> Dict[str, Any]:
        owner = self._owner
        now = self._time.time()
        status: Dict[str, Any] = {}
        with owner._transfer_auto_lock:
            for provider_id in self._provider_ids(providers):
                records = self._recent_records(provider_id, now, persist=False)
                remaining = max(0, owner._online_rate_limit_per_minute - len(records))
                reset_ts = min(records) + RATE_LIMIT_WINDOW_SECONDS if records else 0
                status[provider_id] = {
                    "used": len(records),
                    "remaining": remaining,
                    "limit_per_minute": owner._online_rate_limit_per_minute,
                    "reset_at": owner._timestamp_iso(reset_ts),
                }
        return status

    def _provider_ids(self, providers: Iterable[str]) -> List[str]:
        owner = self._owner
        return sorted({owner._normalize_text(provider).lower() for provider in providers if owner._normalize_text(provider)})

    def _recent_records(self, provider_id: str, now: float, *, persist: bool) -> List[float]:
        records_by_provider = self._owner._online_rate_records
        if not isinstance(records_by_provider, dict):
            raise ValueError("Invalid online rate-limit state: provider records must be a dict")
        raw_records = records_by_provider.get(provider_id, [])
        if not isinstance(raw_records, list):
            raise ValueError(f"Invalid online rate-limit state for provider {provider_id}: records must be a list")
        records: List[float] = []
        for item in raw_records:
            if not isinstance(item, (int, float)):
                raise ValueError(f"Invalid online rate-limit timestamp for provider {provider_id}: {item!r}")
            timestamp = float(item)
            if now - timestamp < RATE_LIMIT_WINDOW_SECONDS:
                records.append(timestamp)
        if persist:
            records_by_provider[provider_id] = records
        return records

    def _update_waiting_tasks(self, task_ids: List[str], wait_until: float, provider_ids: List[str]) -> None:
        owner = self._owner
        for task_id in task_ids:
            task = owner._auto_transfer_tasks.get(task_id)
            if task and task.get("status") == "in_progress":
                task["next_run_ts"] = wait_until
                task["message"] = f"等待字幕源限速窗口：{','.join(provider_ids)}"

    def _clear_waiting_tasks(self, task_ids: List[str]) -> None:
        owner = self._owner
        for task_id in task_ids:
            task = owner._auto_transfer_tasks.get(task_id)
            if task and task.get("status") == "in_progress":
                task["next_run_ts"] = 0
                task["message"] = "入库自动字幕处理中"
