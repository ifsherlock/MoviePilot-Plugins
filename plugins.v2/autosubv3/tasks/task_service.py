import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..core.models import (
    GenerationMode,
    OverwritePolicy,
    SourcePolicy,
    TaskItem,
    TaskSource,
    TaskStatus,
    TriggerType,
)


class TaskService:
    def __init__(self, plugin: Any, media_extensions: List[str], logger: Any):
        self._plugin = plugin
        self._media_extensions = media_extensions
        self._logger = logger

    def task_counts(self) -> Dict[str, int]:
        counts = {status.value: 0 for status in TaskStatus}
        for task in (self._plugin._tasks or {}).values():
            key = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
            counts[key] = counts.get(key, 0) + 1
        counts["queue_size"] = self._plugin._get_queue_worker().queue_size() if self._plugin._task_queue else 0
        return counts

    def task_to_api(self, task: TaskItem, queue_positions: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        queue_positions = queue_positions or {}
        status = task.status if isinstance(task.status, TaskStatus) else TaskStatus.FAILED
        source = task.source if isinstance(task.source, TaskSource) else TaskSource.MANUAL
        queue_position = queue_positions.get(task.task_id)
        message = task.error_message or self._plugin._status_message(status)
        if status == TaskStatus.PENDING and queue_position:
            message = f"排队第 {queue_position} 位"
        if status == TaskStatus.IN_PROGRESS:
            message = "正在生成字幕"
        if bool(task.cancel_requested):
            message = task.error_message or "已请求取消，当前步骤结束后停止"
        return {
            "task_id": task.task_id,
            "video_file": task.video_file,
            "video_name": os.path.basename(task.video_file or ""),
            "source": source.value,
            "source_label": self._plugin._source_label(source),
            "force_generate": bool(task.force_generate),
            "source_subtitle_path": task.source_subtitle_path or "",
            "source_subtitle_name": os.path.basename(task.source_subtitle_path or ""),
            "source_subtitle_lang": task.source_subtitle_lang or "",
            "trigger": task.trigger or TriggerType.MANUAL.value,
            "source_policy": task.source_policy or SourcePolicy.AUTO.value,
            "source_policy_label": self._plugin._source_policy_label(task.source_policy or SourcePolicy.AUTO.value),
            "resolved_source": task.resolved_source or "",
            "resolved_source_label": self._plugin._resolved_source_label(task.resolved_source),
            "source_asset_path": task.source_asset_path or "",
            "source_asset_name": os.path.basename(task.source_asset_path or ""),
            "source_lang": task.source_lang or task.source_subtitle_lang or "",
            "output_path": task.output_path or "",
            "output_name": os.path.basename(task.output_path or ""),
            "output_variant": task.output_variant or "",
            "reuse_output_path": task.reuse_output_path or "",
            "reuse_source_lang": task.reuse_source_lang or "",
            "overwrite_policy": task.overwrite_policy or OverwritePolicy.SKIP.value,
            "rerun_of": task.rerun_of or "",
            "status": status.value,
            "status_label": self._plugin._status_label(status),
            "message": message,
            "queue_position": queue_position,
            "add_time": task.add_time.isoformat(timespec="seconds") if task.add_time else "",
            "complete_time": task.complete_time.isoformat(timespec="seconds") if task.complete_time else "",
            "cancel_requested": bool(task.cancel_requested),
            "active": status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) and not bool(task.cancel_requested),
        }

    def status_payload(self) -> Dict[str, Any]:
        ready = bool(self._plugin._running and self._plugin._task_queue)
        monitor_taken_over = self._plugin._subtitlemanualupload_auto_transfer_enabled()
        if not self._plugin._enabled:
            message = "插件未启用"
        elif monitor_taken_over:
            message = "独立入库监控已由字幕匹配接管，仍可接收手动和联动任务"
        elif not ready:
            message = "插件已启用但任务队列未启动，请检查 Whisper 或 OpenAI 配置"
        else:
            message = "可提交 AI 字幕生成任务"
        latest_time = ""
        for task in (self._plugin._tasks or {}).values():
            for candidate in (task.complete_time, task.add_time):
                if candidate and candidate.isoformat() > latest_time:
                    latest_time = candidate.isoformat(timespec="seconds")
        return {
            "available": ready,
            "enabled": bool(self._plugin._enabled),
            "running": bool(self._plugin._running),
            "queue_ready": bool(self._plugin._task_queue),
            "plugin_name": self._plugin.plugin_name,
            "plugin_version": self._plugin.plugin_version,
            "generation_mode": self._plugin._generation_mode or GenerationMode.MONITOR.value,
            "generation_mode_label": self._plugin._generation_mode_label(self._plugin._generation_mode or GenerationMode.MONITOR.value),
            "independent_monitor_enabled": self._plugin._generation_mode != GenerationMode.FALLBACK.value and not monitor_taken_over,
            "independent_monitor_blocked_reason": "字幕匹配入库自动处理已启用" if monitor_taken_over else "",
            "message": message,
            "counts": self.task_counts(),
            "updated_at": latest_time,
        }

    def submit_tasks(
        self,
        paths: List[str],
        source: str = TaskSource.MANUAL.value,
        subtitle_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
    ) -> Dict[str, Any]:
        if not self._plugin._running or not self._plugin._task_queue:
            raise RuntimeError(self.status_payload()["message"])
        try:
            task_source = TaskSource(self._plugin._normalize_text(source) or TaskSource.MANUAL.value)
        except Exception:
            task_source = TaskSource.MANUAL
        normalized_trigger = self._plugin._normalize_trigger(trigger)
        normalized_policy = self._plugin._normalize_source_policy(source_policy)
        if normalized_policy == SourcePolicy.REUSE.value:
            normalized_policy = SourcePolicy.AUTO.value
        normalized_overwrite = self._plugin._normalize_overwrite_policy(overwrite_policy)
        added: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        failed: List[Dict[str, str]] = []
        seen_paths = set()
        overrides = subtitle_overrides if isinstance(subtitle_overrides, dict) else {}
        for raw_path in paths or []:
            video_file = self._plugin._normalize_text(raw_path)
            if not video_file:
                continue
            if video_file in seen_paths:
                skipped.append({"path": video_file, "reason": "重复路径"})
                continue
            seen_paths.add(video_file)
            if not os.path.isabs(video_file) or not os.path.isfile(video_file):
                failed.append({"path": video_file, "reason": "视频文件不存在或不是绝对路径"})
                continue
            if os.path.splitext(video_file)[-1].lower() not in self._media_extensions:
                failed.append({"path": video_file, "reason": "不是 MoviePilot 支持的视频文件"})
                continue
            if self.is_duplicate_task(video_file):
                skipped.append({"path": video_file, "reason": "任务已在队列中或正在处理"})
                continue
            override = overrides.get(video_file) or overrides.get(os.path.abspath(video_file)) or {}
            if not isinstance(override, dict):
                override = {}
            source_subtitle_path = self._plugin._normalize_text(override.get("subtitle_path") or override.get("source_subtitle_path"))
            source_subtitle_lang = self._plugin._normalize_text(override.get("lang") or override.get("source_subtitle_lang") or "en")
            item_policy = self._plugin._normalize_source_policy(override.get("source_policy"), normalized_policy)
            if source_subtitle_path and item_policy == SourcePolicy.AUTO.value:
                item_policy = SourcePolicy.MATCHED_EXTERNAL.value
            if source_subtitle_path and item_policy not in (SourcePolicy.AUTO.value, SourcePolicy.MATCHED_EXTERNAL.value):
                source_subtitle_path = ""
                source_subtitle_lang = ""
            if item_policy == SourcePolicy.MATCHED_EXTERNAL.value and not source_subtitle_path:
                failed.append({"path": video_file, "reason": "指定字幕匹配外挂来源时必须提供字幕文件"})
                continue
            if source_subtitle_path:
                if not os.path.isabs(source_subtitle_path) or not os.path.isfile(source_subtitle_path):
                    failed.append({"path": video_file, "reason": "指定字幕文件不存在或不是绝对路径"})
                    continue
                if os.path.splitext(source_subtitle_path)[-1].lower() != ".srt":
                    failed.append({"path": video_file, "reason": "指定 AI 翻译字幕必须是 SRT 格式"})
                    continue
            force_generate = task_source == TaskSource.SUBTITLE_MANUAL_UPLOAD
            if self.add_task(
                video_file,
                task_source,
                force_generate=force_generate,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                trigger=normalized_trigger,
                source_policy=item_policy,
                overwrite_policy=self._plugin._normalize_overwrite_policy(override.get("overwrite_policy"), normalized_overwrite),
                source_name=self._plugin._normalize_text(override.get("source_name")) or os.path.basename(source_subtitle_path),
            ):
                item = {"path": video_file}
                if source_subtitle_path:
                    item["source_subtitle_name"] = os.path.basename(source_subtitle_path)
                    item["source_subtitle_lang"] = source_subtitle_lang
                added.append(item)
            else:
                skipped.append({"path": video_file, "reason": "任务已存在"})

        self._logger.info(
            "[AutoSubv3] 联动任务提交 source=%s requested=%s added=%s skipped=%s failed=%s",
            task_source.value,
            len(paths or []),
            len(added),
            len(skipped),
            len(failed),
        )
        return {
            "added": added,
            "skipped": skipped,
            "failed": failed,
            "status": self.status_payload(),
        }

    def cancel_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        filter_task_ids = {self._plugin._normalize_text(item) for item in (task_ids or []) if self._plugin._normalize_text(item)}
        filter_paths = {self._plugin._normalize_text(item) for item in (paths or []) if self._plugin._normalize_text(item)}
        if not filter_task_ids and not filter_paths:
            return {
                "cancelled": [],
                "skipped": [{"reason": "未提供要取消的任务"}],
                "status": self.status_payload(),
            }

        cancelled: List[Dict[str, str]] = []
        skipped: List[Dict[str, str]] = []
        matched_task_ids = set()
        matched_paths = set()

        for task in list((self._plugin._tasks or {}).values()):
            match_task = bool(filter_task_ids and task.task_id in filter_task_ids)
            match_path = bool(filter_paths and task.video_file in filter_paths)
            if not (match_task or match_path):
                continue
            matched_task_ids.add(task.task_id)
            matched_paths.add(task.video_file)
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                task.cancel_requested = True
                task.complete_time = datetime.now()
                task.error_message = "用户已取消"
                cancelled.append({"task_id": task.task_id, "path": task.video_file, "status": task.status.value})
                continue
            if task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.CANCELLED
                task.cancel_requested = True
                task.complete_time = datetime.now()
                task.error_message = "已请求取消，当前步骤结束后停止"
                cancelled.append({"task_id": task.task_id, "path": task.video_file, "status": task.status.value})
                continue
            skipped.append({
                "task_id": task.task_id,
                "path": task.video_file,
                "reason": f"任务已是 {self._plugin._status_label(task.status)}",
            })

        if self._plugin._task_queue:
            self._plugin._get_queue_worker().remove_pending(matched_task_ids, reason="取消任务")

        for item in filter_task_ids:
            if item not in matched_task_ids:
                skipped.append({"task_id": item, "reason": "未找到任务"})
        for item in filter_paths:
            if item not in matched_paths:
                skipped.append({"path": item, "reason": "未找到任务"})

        if cancelled:
            self._plugin.save_tasks()
        self._logger.info("[AutoSubv3] 取消任务 requested=%s cancelled=%s skipped=%s", len(filter_task_ids) + len(filter_paths), len(cancelled), len(skipped))
        return {
            "cancelled": cancelled,
            "skipped": skipped,
            "status": self.status_payload(),
        }

    def delete_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        filter_task_ids = {self._plugin._normalize_text(item) for item in (task_ids or []) if self._plugin._normalize_text(item)}
        filter_paths = {self._plugin._normalize_text(item) for item in (paths or []) if self._plugin._normalize_text(item)}
        if not filter_task_ids and not filter_paths:
            return {
                "deleted": [],
                "skipped": [{"reason": "未提供要删除的任务"}],
                "status": self.status_payload(),
            }

        deleted: List[Dict[str, str]] = []
        skipped: List[Dict[str, str]] = []
        matched_task_ids = set()
        matched_paths = set()
        queue_delete_ids = set()

        for task_id, task in list((self._plugin._tasks or {}).items()):
            match_task = bool(filter_task_ids and task_id in filter_task_ids)
            match_path = bool(filter_paths and task.video_file in filter_paths)
            if not (match_task or match_path):
                continue
            matched_task_ids.add(task_id)
            matched_paths.add(task.video_file)
            if task.status == TaskStatus.IN_PROGRESS:
                skipped.append({
                    "task_id": task_id,
                    "path": task.video_file,
                    "reason": "任务正在处理，请先取消后再删除",
                })
                continue
            if task.status == TaskStatus.PENDING:
                task.cancel_requested = True
                queue_delete_ids.add(task_id)
            self._plugin._tasks.pop(task_id, None)
            deleted.append({"task_id": task_id, "path": task.video_file, "status": task.status.value})

        if queue_delete_ids and self._plugin._task_queue:
            self._plugin._get_queue_worker().remove_pending(queue_delete_ids, reason="删除任务")

        for item in filter_task_ids:
            if item not in matched_task_ids:
                skipped.append({"task_id": item, "reason": "未找到任务"})
        for item in filter_paths:
            if item not in matched_paths:
                skipped.append({"path": item, "reason": "未找到任务"})

        if deleted:
            self._plugin.save_tasks()
        self._logger.info("[AutoSubv3] 删除任务 requested=%s deleted=%s skipped=%s", len(filter_task_ids) + len(filter_paths), len(deleted), len(skipped))
        return {
            "deleted": deleted,
            "skipped": skipped,
            "status": self.status_payload(),
        }

    def restart_tasks(
        self,
        task_ids: Optional[List[str]] = None,
        source_policy: str = SourcePolicy.REUSE.value,
        overwrite_policy: str = OverwritePolicy.BACKUP_REPLACE.value,
    ) -> Dict[str, Any]:
        filter_task_ids = {self._plugin._normalize_text(item) for item in (task_ids or []) if self._plugin._normalize_text(item)}
        if not filter_task_ids:
            return {
                "added": [],
                "skipped": [{"reason": "未提供要重新生成的任务"}],
                "failed": [],
                "status": self.status_payload(),
            }
        added: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        failed: List[Dict[str, str]] = []
        requested_policy = self._plugin._normalize_source_policy(source_policy, SourcePolicy.REUSE.value)
        requested_overwrite = self._plugin._normalize_overwrite_policy(overwrite_policy, OverwritePolicy.BACKUP_REPLACE.value)
        restartable_statuses = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.IGNORED,
            TaskStatus.NO_AUDIO,
        }

        for task_id in filter_task_ids:
            task = (self._plugin._tasks or {}).get(task_id)
            if not task:
                skipped.append({"task_id": task_id, "reason": "未找到任务"})
                continue
            if task.status not in restartable_statuses:
                skipped.append({"task_id": task_id, "path": task.video_file, "reason": f"任务状态 {self._plugin._status_label(task.status)} 不能重新生成"})
                continue
            reuse_requested = requested_policy == SourcePolicy.REUSE.value
            next_source_subtitle = task.source_asset_path or task.source_subtitle_path
            if reuse_requested:
                next_policy = self._plugin._source_policy_for_resolved_source(task.resolved_source) or task.source_policy
            else:
                next_policy = requested_policy
            next_policy = self._plugin._normalize_source_policy(next_policy)
            if reuse_requested and next_source_subtitle and next_policy == SourcePolicy.AUTO.value:
                next_policy = SourcePolicy.MATCHED_EXTERNAL.value
            if next_policy == SourcePolicy.MATCHED_EXTERNAL.value:
                if not next_source_subtitle or not os.path.isfile(next_source_subtitle):
                    failed.append({
                        "task_id": task_id,
                        "path": task.video_file,
                        "reason": "原字幕匹配外挂源已不存在，请改选自动选择、视频内嵌字幕或音轨 ASR",
                    })
                    continue
            elif next_policy != SourcePolicy.MATCHED_EXTERNAL.value:
                next_source_subtitle = ""
            force_generate = True
            reuse_output_variant = task.output_variant if reuse_requested else ""
            reuse_output_path = task.output_path if reuse_requested and requested_overwrite == OverwritePolicy.BACKUP_REPLACE.value else ""
            reuse_source_lang = task.source_lang or task.source_subtitle_lang or ""
            ok = self.add_task(
                task.video_file,
                task.source if isinstance(task.source, TaskSource) else TaskSource.MANUAL,
                force_generate=force_generate,
                source_subtitle_path=next_source_subtitle,
                source_subtitle_lang=task.source_subtitle_lang or task.source_lang or "",
                trigger=TriggerType.MANUAL.value,
                source_policy=next_policy,
                overwrite_policy=requested_overwrite,
                rerun_of=task.task_id,
                source_name=os.path.basename(next_source_subtitle or ""),
                output_variant=reuse_output_variant,
                reuse_output_path=reuse_output_path,
                reuse_source_lang=reuse_source_lang if reuse_requested else "",
            )
            if ok:
                added.append({"task_id": task_id, "path": task.video_file, "source_policy": next_policy})
            else:
                skipped.append({"task_id": task_id, "path": task.video_file, "reason": "任务已在队列中或正在处理"})
        self._logger.info(
            "[AutoSubv3] 重新生成任务 requested=%s added=%s skipped=%s failed=%s",
            len(filter_task_ids),
            len(added),
            len(skipped),
            len(failed),
        )
        return {
            "added": added,
            "skipped": skipped,
            "failed": failed,
            "status": self.status_payload(),
        }

    def tasks_payload(self, paths: Optional[List[str]] = None, limit: int = 300) -> Dict[str, Any]:
        filter_paths = {self._plugin._normalize_text(item) for item in (paths or []) if self._plugin._normalize_text(item)}
        limit = min(max(limit, 1), 1000)
        queue_positions = self._plugin._queue_positions()
        tasks = sorted(
            (self._plugin._tasks or {}).values(),
            key=lambda item: item.add_time or datetime.min,
            reverse=True,
        )
        if filter_paths:
            tasks = [task for task in tasks if task.video_file in filter_paths]
        return {
            "status": self.status_payload(),
            "tasks": [self.task_to_api(task, queue_positions) for task in tasks[:limit]],
        }

    def add_task(
        self,
        video_file: str,
        source: TaskSource,
        force_generate: bool = False,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
        rerun_of: str = "",
        source_name: str = "",
        output_variant: str = "",
        reuse_output_path: str = "",
        reuse_source_lang: str = "",
    ):
        task_id = str(uuid4())
        normalized_policy = self._plugin._normalize_source_policy(source_policy)
        if normalized_policy == SourcePolicy.REUSE.value:
            normalized_policy = SourcePolicy.AUTO.value
        if source_subtitle_path and normalized_policy == SourcePolicy.AUTO.value:
            normalized_policy = SourcePolicy.MATCHED_EXTERNAL.value
        task = TaskItem(
            task_id=task_id,
            video_file=video_file,
            source=source,
            force_generate=force_generate,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            trigger=self._plugin._normalize_trigger(trigger),
            source_policy=normalized_policy,
            overwrite_policy=self._plugin._normalize_overwrite_policy(overwrite_policy),
            rerun_of=rerun_of,
            output_variant=self._plugin._normalize_text(output_variant),
            reuse_output_path=self._plugin._normalize_text(reuse_output_path),
            reuse_source_lang=self._plugin._normalize_text(reuse_source_lang),
            add_time=datetime.now()
        )
        if source_subtitle_path:
            try:
                task.source_asset_path = self._plugin._copy_source_asset(task.task_id, source_subtitle_path, source_name)
                task.source_subtitle_path = task.source_asset_path
            except Exception as exc:
                self._logger.error("复制 AI 字幕源资产失败: %s", exc)
                return False

        if self.is_duplicate_task(task.video_file):
            self._logger.info(f"任务已存在，跳过添加：{video_file}")
            return False

        worker = self._plugin._get_queue_worker()
        worker.enqueue(task)
        self._plugin._task_queue = worker.task_queue
        self._plugin._tasks[task.task_id] = task
        self._plugin.save_tasks()
        self._logger.info(
            "加入任务队列: %s force_generate=%s source_subtitle=%s",
            video_file,
            force_generate,
            os.path.basename(source_subtitle_path or "") or "-",
        )
        return True

    def is_duplicate_task(self, video_file: str) -> bool:
        return self._plugin._get_queue_worker().is_duplicate(video_file)
