import json
from typing import Any, Dict, List

from fastapi import HTTPException, Request

from ..core.models import OverwritePolicy, SourcePolicy, TaskSource, TriggerType


class AutoSubTaskApi:
    def __init__(self, plugin: Any):
        self._plugin = plugin

    def routes(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 AI 字幕生成联动状态",
            },
            {
                "path": "/submit",
                "endpoint": self.api_submit,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "提交 AI 字幕生成任务",
            },
            {
                "path": "/tasks",
                "endpoint": self.api_tasks,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 AI 字幕生成任务状态",
            },
            {
                "path": "/cancel",
                "endpoint": self.api_cancel,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消 AI 字幕生成任务",
            },
            {
                "path": "/delete",
                "endpoint": self.api_delete,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除 AI 字幕任务记录",
            },
            {
                "path": "/restart",
                "endpoint": self.api_restart,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重新生成 AI 字幕任务",
            },
        ]

    def api_status(self) -> Dict[str, Any]:
        return self._plugin._ok(self._plugin._status_payload())

    async def api_submit(self, request: Request) -> Dict[str, Any]:
        if not self._plugin._running or not self._plugin._task_queue:
            raise HTTPException(status_code=409, detail=self._plugin._status_payload()["message"])
        body = await request.json()
        paths = body.get("paths") or []
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list):
            paths = []
        subtitle_overrides = body.get("subtitle_overrides") if isinstance(body.get("subtitle_overrides"), dict) else None
        result = self._plugin.submit_tasks(
            paths,
            source=self._plugin._normalize_text(body.get("source")) or TaskSource.MANUAL.value,
            subtitle_overrides=subtitle_overrides,
            trigger=self._plugin._normalize_text(body.get("trigger")) or TriggerType.MANUAL.value,
            source_policy=self._plugin._normalize_text(body.get("source_policy")) or SourcePolicy.AUTO.value,
            overwrite_policy=self._plugin._normalize_text(body.get("overwrite_policy")) or OverwritePolicy.SKIP.value,
        )
        return self._plugin._ok(
            result,
            message=f"已提交 {len(result['added'])} 个 AI 字幕生成任务，跳过 {len(result['skipped'])} 个，失败 {len(result['failed'])} 个",
        )

    async def api_cancel(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        paths = body.get("paths") or []
        task_ids = body.get("task_ids") or []
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        result = self._plugin.cancel_tasks(task_ids=task_ids if isinstance(task_ids, list) else [], paths=paths if isinstance(paths, list) else [])
        return self._plugin._ok(
            result,
            message=f"已取消 {len(result.get('cancelled') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    async def api_delete(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        paths = body.get("paths") or []
        task_ids = body.get("task_ids") or []
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        result = self._plugin.delete_tasks(task_ids=task_ids if isinstance(task_ids, list) else [], paths=paths if isinstance(paths, list) else [])
        return self._plugin._ok(
            result,
            message=f"已删除 {len(result.get('deleted') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    async def api_restart(self, request: Request) -> Dict[str, Any]:
        if not self._plugin._running or not self._plugin._task_queue:
            raise HTTPException(status_code=409, detail=self._plugin._status_payload()["message"])
        body = await request.json()
        task_ids = body.get("task_ids") or []
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        result = self._plugin.restart_tasks(
            task_ids=task_ids if isinstance(task_ids, list) else [],
            source_policy=self._plugin._normalize_text(body.get("source_policy")) or SourcePolicy.REUSE.value,
            overwrite_policy=self._plugin._normalize_text(body.get("overwrite_policy")) or OverwritePolicy.BACKUP_REPLACE.value,
        )
        return self._plugin._ok(
            result,
            message=f"已重新提交 {len(result.get('added') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    def api_tasks(self, request: Request) -> Dict[str, Any]:
        raw_paths = request.query_params.get("paths") or ""
        filter_paths = set()
        if raw_paths:
            try:
                parsed = json.loads(raw_paths)
                if isinstance(parsed, list):
                    filter_paths = {self._plugin._normalize_text(item) for item in parsed if self._plugin._normalize_text(item)}
            except Exception:
                filter_paths = {self._plugin._normalize_text(item) for item in raw_paths.split(",") if self._plugin._normalize_text(item)}
        try:
            limit = int(request.query_params.get("limit") or 300)
        except Exception:
            limit = 300
        limit = min(max(limit, 1), 1000)
        return self._plugin._ok(self._plugin.tasks_payload(paths=list(filter_paths), limit=limit))
