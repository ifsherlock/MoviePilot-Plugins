from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..autosub_bridge import autosub_task_summary as bridge_autosub_task_summary
from .request_helpers import filter_unlocked_target_ids, locked_target_ids_from_body, target_ids_from_body


class AiApi:
    def __init__(self, owner: Any):
        self.owner = owner

    async def ai_submit(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        locked_ids = locked_target_ids_from_body(body, owner._normalize_text)
        target_ids, locked_skipped = filter_unlocked_target_ids(target_ids, locked_ids, owner._normalize_text)
        if not target_ids:
            if locked_skipped:
                return owner._ok(
                    {"added": [], "skipped": locked_skipped, "failed": [], "targets": [], "tasks": {}},
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有提交 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="请先选择要生成 AI 字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        autosub_bridge = owner._autosub_bridge()
        source_policy = owner._normalize_text(body.get("source_policy")) or "auto"
        if source_policy == "reuse":
            source_policy = "auto"
        source_subtitle_path = owner._normalize_text(body.get("source_subtitle_path") or body.get("subtitle_path"))
        source_subtitle_lang = owner._normalize_text(body.get("source_subtitle_lang") or body.get("lang"))
        overwrite_policy = owner._normalize_text(body.get("overwrite_policy")) or (
            "new_variant" if source_policy != "auto" else "skip"
        )
        if source_policy == "matched_external":
            if not source_subtitle_path:
                raise HTTPException(status_code=400, detail="请选择要用于 AI 生成的外挂 SRT 字幕")
            subtitle_overrides = autosub_bridge.selected_external_subtitle_override_for_entries(
                target_entries,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                overwrite_policy=overwrite_policy,
            )
            result = autosub_bridge.submit_autosub_for_entries(
                target_entries,
                subtitle_overrides=subtitle_overrides,
                trigger="manual",
                source_policy="matched_external",
                overwrite_policy=overwrite_policy,
            )
        else:
            result = autosub_bridge.submit_autosub_for_entries(
                target_entries,
                trigger="manual",
                source_policy=source_policy,
                overwrite_policy=overwrite_policy,
            )
        if locked_skipped:
            result["skipped"] = [*(result.get("skipped") or []), *locked_skipped]
        return owner._ok(
            result,
            message=f"已提交 {len(result.get('added') or [])} 个 AI 字幕生成任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    async def online_ai_submit(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        locked_ids = locked_target_ids_from_body(body, owner._normalize_text)
        allow_risky_offset = bool(body.get("allow_risky_offset")) if isinstance(body, dict) else False
        target_ids, locked_skipped = filter_unlocked_target_ids(target_ids, locked_ids, owner._normalize_text)
        if not target_ids:
            if locked_skipped:
                raise HTTPException(status_code=423, detail="选中的目标均已锁定，不能提交在线字幕 AI 翻译")
            raise HTTPException(status_code=400, detail="请先选择要生成 AI 字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries or len(target_entries) != len(set(target_ids)):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        selected_results = owner._results_from_body(body)
        if not selected_results:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕结果")
        online_ai_service = owner._online_ai_service()
        return await run_in_threadpool(
            online_ai_service.submit_online_ai_translate,
            target_entries,
            selected_results,
            allow_risky_offset,
        )

    async def ai_cancel(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        locked_ids = locked_target_ids_from_body(body, owner._normalize_text)
        target_ids, locked_skipped = filter_unlocked_target_ids(target_ids, locked_ids, owner._normalize_text)
        if not target_ids:
            if locked_skipped:
                return owner._ok(
                    {"cancelled": [], "skipped": locked_skipped, "targets": [], "tasks": {}},
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有取消 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="请先选择要取消的 AI 字幕任务")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        result = owner._autosub_bridge().cancel_autosub_for_entries(target_entries)
        if locked_skipped:
            result["skipped"] = [*(result.get("skipped") or []), *locked_skipped]
        return owner._ok(
            result,
            message=f"已取消 {len(result.get('cancelled') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    async def ai_restart(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        requested_target_ids = list(target_ids)
        task_ids = body.get("task_ids") or []
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        task_ids = (
            [owner._normalize_text(item) for item in task_ids if owner._normalize_text(item)]
            if isinstance(task_ids, list)
            else []
        )
        locked_ids = locked_target_ids_from_body(body, owner._normalize_text)
        target_ids, locked_skipped = filter_unlocked_target_ids(target_ids, locked_ids, owner._normalize_text)
        if not target_ids and not task_ids:
            if locked_skipped:
                return owner._ok(
                    {"added": [], "skipped": locked_skipped, "failed": [], "targets": [], "tasks": {}},
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有重新生成 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="请先选择要重新生成 AI 字幕的本地视频")
        if target_ids:
            target_entries = list(owner._resolve_targets(target_ids).values())
        elif requested_target_ids:
            target_entries = []
        else:
            target_entries = owner._local_media_catalog().cached_unlocked_targets(locked_ids)
        if requested_target_ids and not target_ids and locked_skipped:
            skipped = [
                {"task_id": task_id, "reason": "任务不属于当前可操作目标或目标已锁定"}
                for task_id in task_ids
            ]
            return owner._ok(
                {
                    "added": [],
                    "skipped": [*locked_skipped, *skipped],
                    "failed": [],
                    "targets": [],
                    "tasks": {},
                },
                message=f"已跳过 {len(locked_skipped) + len(skipped)} 个锁定或不可操作的 AI 字幕任务",
            )
        if requested_target_ids and (not target_entries or len(target_entries) != len(set(target_ids))):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        if not target_entries:
            if task_ids:
                return owner._ok(
                    {
                        "added": [],
                        "skipped": [{"task_id": task_id, "reason": "任务不属于当前可操作目标或目标已锁定"} for task_id in task_ids],
                        "failed": [],
                        "targets": [],
                        "tasks": {},
                    },
                    message=f"已跳过 {len(task_ids)} 个无法确认目标归属的 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        result = owner._autosub_bridge().restart_autosub_for_entries(
            target_entries,
            source_policy=owner._normalize_text(body.get("source_policy")) or "reuse",
            overwrite_policy=owner._normalize_text(body.get("overwrite_policy")) or "backup_replace",
            source_subtitle_path=owner._normalize_text(body.get("source_subtitle_path") or body.get("subtitle_path")),
            source_subtitle_lang=owner._normalize_text(body.get("source_subtitle_lang") or body.get("lang")),
            task_ids=task_ids,
        )
        if locked_skipped:
            result["skipped"] = [*(result.get("skipped") or []), *locked_skipped]
        return owner._ok(
            result,
            message=f"已重新提交 {len(result.get('added') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    async def ai_tasks(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        autosub_bridge = owner._autosub_bridge()
        if not target_ids:
            return owner._ok(
                {
                    "status": autosub_bridge.autosub_status(),
                    "summary": bridge_autosub_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                    "tasks_by_target": {},
                }
            )
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        if len(target_entries) != len(set(target_ids)):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        return owner._ok(autosub_bridge.autosub_tasks_for_entries(target_entries))
