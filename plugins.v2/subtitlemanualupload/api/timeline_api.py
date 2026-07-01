from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException, Request

from ..timeline_fixer import check_timeline_fixer_dependencies
from .request_helpers import locked_target_ids_from_body, target_ids_from_body


class TimelineApi:
    def __init__(self, owner: Any):
        self.owner = owner

    def _existing_timeline_operations(
        self,
        requested_items: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self.owner.services.history().existing_timeline_operations(requested_items)

    def _run_existing_timeline_fix(
        self,
        session_dir: Path,
        operations: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> None:
        self.owner.services.writer().run_existing_timeline_fix(
            session_dir,
            operations,
            allow_risky_offset=allow_risky_offset,
        )

    async def timeline_fix_existing(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        requested_items = body.get("items") if isinstance(body, dict) else []
        allow_risky_offset = bool(body.get("allow_risky_offset")) if isinstance(body, dict) else False
        if not isinstance(requested_items, list) or not requested_items:
            raise HTTPException(status_code=400, detail="请先选择要调轴的历史字幕")
        locked_ids = locked_target_ids_from_body(body if isinstance(body, dict) else {}, owner._normalize_text)
        locked_skipped: List[Dict[str, str]] = []
        if locked_ids:
            filtered_items = []
            for item in requested_items:
                target_id = owner._normalize_text((item or {}).get("target_id")) if isinstance(item, dict) else ""
                if target_id in locked_ids:
                    locked_skipped.append({"target_id": target_id, "reason": "目标已锁定"})
                    continue
                filtered_items.append(item)
            requested_items = filtered_items
        if not requested_items:
            return owner._ok(
                {
                    "accepted": 0,
                    "skipped": locked_skipped,
                    "failed": [],
                    "summary": owner._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                },
                message="没有可提交智能调轴的历史字幕，锁定项已跳过",
            )
        timeline_status = check_timeline_fixer_dependencies()
        if not timeline_status.get("available"):
            missing = [
                key
                for key, value in {
                    "ffmpeg": timeline_status.get("ffmpeg"),
                    "ffprobe": timeline_status.get("ffprobe"),
                    **(timeline_status.get("modules") or {}),
                }.items()
                if not value and key != "webrtcvad"
            ]
            raise HTTPException(status_code=409, detail=f"智能调轴不可用：缺少 {', '.join(missing) or '依赖'}")
        operations, skipped, failed = self._existing_timeline_operations(requested_items)
        skipped = [*locked_skipped, *skipped]
        if not operations:
            return owner._ok(
                {
                    "accepted": 0,
                    "skipped": skipped,
                    "failed": failed,
                    "summary": owner._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                },
                message="没有可提交智能调轴的历史字幕",
            )
        timeline_tasks = owner.services.timeline_tasks()
        for operation in operations:
            timeline_tasks.set_task(operation, status="pending", message="等待历史字幕智能调轴")
        session_id = owner._hash_text(f"existing-timeline|{datetime.now().isoformat()}|{len(operations)}")[:16]
        session_dir = owner.services.upload_session().get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(
            target=self._run_existing_timeline_fix,
            args=(session_dir, operations, allow_risky_offset),
            name="SubtitleManualUploadExistingTimelineFix",
            daemon=True,
        ).start()
        target_entries = [operation["target_entry"] for operation in operations]
        task_data = timeline_tasks.tasks_for_entries(target_entries)
        return owner._ok(
            {
                "accepted": len(operations),
                "skipped": skipped,
                "failed": failed,
                **task_data,
            },
            message=f"已提交 {len(operations)} 个历史字幕智能调轴任务，跳过 {len(skipped)} 个，失败 {len(failed)} 个",
        )

    async def timeline_tasks(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        if not target_ids:
            return owner._ok(
                {
                    "summary": owner._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                }
            )
        target_entries = list(owner.services.local_media_catalog().resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        return owner._ok(owner.services.timeline_tasks().tasks_for_entries(target_entries))
