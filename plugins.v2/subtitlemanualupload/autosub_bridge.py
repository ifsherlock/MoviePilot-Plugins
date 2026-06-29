from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def autosub_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "ignored": 0,
        "no_audio": 0,
        "failed": 0,
        "cancelled": 0,
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


class AutoSubBridge:
    def __init__(
        self,
        owner: Any,
        *,
        plugin_manager: Any,
        http_exception: Any,
        logger: Any,
    ) -> None:
        self._owner = owner
        self._plugin_manager = plugin_manager
        self._http_exception = http_exception
        self._logger = logger

    def autosub_plugin(self) -> Tuple[Any, str]:
        owner = self._owner
        if not owner._ai_link_enabled:
            return None, "字幕匹配未启用 AI 字幕联动"
        if self._plugin_manager is None:
            return None, "MoviePilot 插件管理器不可用"
        try:
            running_plugins = self._plugin_manager().running_plugins or {}
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取运行中插件失败: %s", exc)
            return None, "读取运行中插件失败"
        plugin = running_plugins.get("AutoSubv3") or running_plugins.get("autosubv3")
        if not plugin:
            for candidate in running_plugins.values():
                if candidate.__class__.__name__ == "AutoSubv3":
                    plugin = candidate
                    break
        if not plugin:
            return None, "请先安装并启用 AI字幕生成(联动版)"
        return plugin, ""

    def autosub_status(self) -> Dict[str, Any]:
        owner = self._owner
        status = {
            "enabled": bool(owner._ai_link_enabled),
            "installed": False,
            "available": False,
            "running": False,
            "queue_ready": False,
            "plugin_name": "AI字幕生成(联动版)",
            "plugin_version": "",
            "message": "请先安装并启用 AI字幕生成(联动版)",
            "counts": {},
            "updated_at": "",
        }
        if not owner._ai_link_enabled:
            status["message"] = "AI 字幕联动已关闭"
            return status
        plugin, reason = owner._autosub_plugin()
        if not plugin:
            status["message"] = reason
            return status
        try:
            if hasattr(plugin, "_status_payload"):
                plugin_status = plugin._status_payload()
            else:
                running = bool(plugin.get_state()) if hasattr(plugin, "get_state") else False
                plugin_status = {
                    "available": running,
                    "running": running,
                    "queue_ready": running,
                    "plugin_name": getattr(plugin, "plugin_name", "AI字幕生成(联动版)"),
                    "plugin_version": getattr(plugin, "plugin_version", ""),
                    "message": "可提交 AI 字幕生成任务" if running else "AI 字幕插件未运行",
                    "counts": {},
                    "updated_at": "",
                }
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取 AI 字幕插件状态失败: %s", exc)
            status["installed"] = True
            status["message"] = "读取 AI 字幕插件状态失败"
            return status
        status.update(plugin_status)
        status["enabled"] = bool(owner._ai_link_enabled)
        status["installed"] = True
        status["available"] = bool(plugin_status.get("available")) and bool(owner._ai_link_enabled)
        return status

    def autosub_tasks_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        owner = self._owner
        status = self.autosub_status()
        paths = [owner._normalize_text(entry.get("path")) for entry in target_entries if owner._normalize_text(entry.get("path"))]
        task_by_target: Dict[str, Any] = {}
        tasks_by_target: Dict[str, List[Dict[str, Any]]] = {}
        if not status.get("available"):
            return {
                "status": status,
                "summary": owner._autosub_task_summary([]),
                "tasks": [],
                "task_by_target": task_by_target,
                "tasks_by_target": tasks_by_target,
            }
        plugin, reason = owner._autosub_plugin()
        if not plugin or not hasattr(plugin, "tasks_payload"):
            status["available"] = False
            status["message"] = reason or "AI 字幕插件版本过旧，请更新到联动版"
            return {
                "status": status,
                "summary": owner._autosub_task_summary([]),
                "tasks": [],
                "task_by_target": task_by_target,
                "tasks_by_target": tasks_by_target,
            }
        try:
            payload = plugin.tasks_payload(paths=paths, limit=max(300, len(paths) * 20))
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取 AI 字幕任务失败: %s", exc)
            status["available"] = False
            status["message"] = "读取 AI 字幕任务失败"
            return {
                "status": status,
                "summary": owner._autosub_task_summary([]),
                "tasks": [],
                "task_by_target": task_by_target,
                "tasks_by_target": tasks_by_target,
            }
        status = {**status, **(payload.get("status") or {})}
        tasks_by_path: Dict[str, List[Dict[str, Any]]] = {}
        for task in payload.get("tasks") or []:
            path = owner._normalize_text(task.get("video_file"))
            if path:
                tasks_by_path.setdefault(path, []).append(task)

        tasks: List[Dict[str, Any]] = []
        for entry in target_entries:
            target_id = owner._normalize_text(entry.get("id"))
            path = owner._normalize_text(entry.get("path"))
            target_label = entry.get("target_label") or entry.get("filename") or Path(path).name
            target_tasks = []
            for raw_task in tasks_by_path.get(path) or []:
                task = dict(raw_task)
                task["target_id"] = target_id
                task["target_label"] = target_label
                target_tasks.append(task)
                tasks.append(task)
            tasks_by_target[target_id] = target_tasks
            task_by_target[target_id] = target_tasks[0] if target_tasks else None
        return {
            "status": status,
            "summary": owner._autosub_task_summary(tasks),
            "tasks": tasks,
            "task_by_target": task_by_target,
            "tasks_by_target": tasks_by_target,
        }

    def submit_autosub_for_entries(
        self,
        target_entries: List[Dict[str, Any]],
        subtitle_overrides: Optional[Dict[str, Dict[str, str]]] = None,
        *,
        trigger: str = "manual",
        source_policy: str = "auto",
        overwrite_policy: str = "skip",
    ) -> Dict[str, Any]:
        owner = self._owner
        stream_entries = [entry for entry in target_entries if owner._is_stream_path(entry.get("path"))]
        submit_entries = [entry for entry in target_entries if not owner._is_stream_path(entry.get("path"))]
        paths = [owner._normalize_text(entry.get("path")) for entry in submit_entries if owner._normalize_text(entry.get("path"))]
        if not paths and not stream_entries:
            raise self._http_exception(status_code=400, detail="没有可提交 AI 字幕生成的本地视频")
        skipped_streams = [
            {
                "path": owner._normalize_text(entry.get("path")),
                "reason": "STRM 资源暂不支持 AI 生成字幕",
            }
            for entry in stream_entries
        ]
        if not paths:
            tasks = self.autosub_tasks_for_entries(target_entries)
            return {
                "added": [],
                "skipped": skipped_streams,
                "failed": [],
                "targets": [owner._target_from_entry(entry) for entry in target_entries],
                "tasks": tasks,
            }

        plugin, reason = owner._autosub_plugin()
        if not plugin:
            raise self._http_exception(status_code=409, detail=reason)
        if not hasattr(plugin, "submit_tasks"):
            raise self._http_exception(status_code=409, detail="AI 字幕插件版本过旧，请更新到联动版")

        try:
            if subtitle_overrides:
                result = plugin.submit_tasks(
                    paths,
                    source="subtitle_manual_upload",
                    subtitle_overrides=subtitle_overrides,
                    trigger=trigger,
                    source_policy=source_policy,
                    overwrite_policy=overwrite_policy,
                )
            else:
                result = plugin.submit_tasks(
                    paths,
                    source="subtitle_manual_upload",
                    trigger=trigger,
                    source_policy=source_policy,
                    overwrite_policy=overwrite_policy,
                )
        except RuntimeError as exc:
            raise self._http_exception(status_code=409, detail=str(exc)) from exc
        except TypeError as exc:
            if subtitle_overrides:
                raise self._http_exception(status_code=409, detail="AI 字幕插件版本过旧，请更新到支持在线字幕输入的联动版") from exc
            raise
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] AI 字幕任务提交失败: %s", exc)
            raise self._http_exception(status_code=500, detail=f"AI 字幕任务提交失败: {exc}") from exc

        tasks = self.autosub_tasks_for_entries(target_entries)
        result = {
            **result,
            "added": result.get("added") or [],
            "skipped": [*(result.get("skipped") or []), *skipped_streams],
            "failed": result.get("failed") or [],
        }
        self._logger.info(
            "[SubtitleManualUpload] AI 字幕任务提交完成 targets=%s added=%s skipped=%s failed=%s",
            len(target_entries),
            len(result.get("added") or []),
            len(result.get("skipped") or []),
            len(result.get("failed") or []),
        )
        return {
            **result,
            "targets": [owner._target_from_entry(entry) for entry in target_entries],
            "tasks": tasks,
        }

    def cancel_autosub_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        owner = self._owner
        plugin, reason = owner._autosub_plugin()
        if not plugin:
            raise self._http_exception(status_code=409, detail=reason)
        if not hasattr(plugin, "cancel_tasks"):
            raise self._http_exception(status_code=409, detail="AI 字幕插件版本过旧，请更新到支持取消任务的联动版")

        paths = [owner._normalize_text(entry.get("path")) for entry in target_entries if owner._normalize_text(entry.get("path"))]
        try:
            result = plugin.cancel_tasks(paths=paths)
        except RuntimeError as exc:
            raise self._http_exception(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] AI 字幕任务取消失败: %s", exc)
            raise self._http_exception(status_code=500, detail=f"AI 字幕任务取消失败: {exc}") from exc

        tasks = self.autosub_tasks_for_entries(target_entries)
        self._logger.info(
            "[SubtitleManualUpload] AI 字幕任务取消完成 targets=%s cancelled=%s skipped=%s",
            len(target_entries),
            len(result.get("cancelled") or []),
            len(result.get("skipped") or []),
        )
        return {
            **result,
            "targets": [owner._target_from_entry(entry) for entry in target_entries],
            "tasks": tasks,
        }

    def restart_autosub_for_entries(
        self,
        target_entries: List[Dict[str, Any]],
        *,
        source_policy: str = "reuse",
        overwrite_policy: str = "backup_replace",
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        plugin, reason = owner._autosub_plugin()
        if not plugin:
            raise self._http_exception(status_code=409, detail=reason)
        if not hasattr(plugin, "restart_tasks"):
            raise self._http_exception(status_code=409, detail="AI 字幕插件版本过旧，请更新到支持重新生成的联动版")
        tasks_data = self.autosub_tasks_for_entries(target_entries)
        requested_task_ids = [owner._normalize_text(item) for item in (task_ids or []) if owner._normalize_text(item)]
        explicit_task_ids = bool(requested_task_ids)
        ownership_skipped: List[Dict[str, str]] = []
        if requested_task_ids:
            requested_task_ids, ownership_skipped = owner._filter_restart_task_ids_by_targets(
                requested_task_ids,
                tasks_data,
                target_entries,
            )
        if source_policy == "matched_external" and source_subtitle_path:
            effective_overwrite_policy = "new_variant" if overwrite_policy == "backup_replace" else overwrite_policy
            if explicit_task_ids and not requested_task_ids:
                return {
                    "added": [],
                    "skipped": ownership_skipped or [{"reason": "当前范围没有可重新生成的已完成/失败/取消 AI 任务"}],
                    "failed": [],
                    "targets": [owner._target_from_entry(entry) for entry in target_entries],
                    "tasks": tasks_data,
                }
            subtitle_overrides = owner._selected_external_subtitle_override_for_entries(
                target_entries,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                overwrite_policy=effective_overwrite_policy,
            )
            result = owner._submit_autosub_for_entries(
                target_entries,
                subtitle_overrides=subtitle_overrides,
                trigger="manual",
                source_policy="matched_external",
                overwrite_policy=effective_overwrite_policy,
            )
            result["skipped"] = [*ownership_skipped, *(result.get("skipped") or [])]
            return result
        if explicit_task_ids:
            restart_task_ids = requested_task_ids
        else:
            restart_task_ids = [
                task.get("task_id")
                for task in (tasks_data.get("tasks") or [])
                if task.get("task_id") and not task.get("active")
            ]
        if not restart_task_ids:
            return {
                "added": [],
                "skipped": ownership_skipped or [{"reason": "当前范围没有可重新生成的已完成/失败/取消 AI 任务"}],
                "failed": [],
                "targets": [owner._target_from_entry(entry) for entry in target_entries],
                "tasks": tasks_data,
            }
        try:
            result = plugin.restart_tasks(
                task_ids=restart_task_ids,
                source_policy=source_policy,
                overwrite_policy=overwrite_policy,
            )
        except RuntimeError as exc:
            raise self._http_exception(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] AI 字幕任务重新生成失败: %s", exc)
            raise self._http_exception(status_code=500, detail=f"AI 字幕任务重新生成失败: {exc}") from exc
        refreshed_tasks = self.autosub_tasks_for_entries(target_entries)
        self._logger.info(
            "[SubtitleManualUpload] AI 字幕任务重新生成完成 targets=%s added=%s skipped=%s failed=%s",
            len(target_entries),
            len(result.get("added") or []),
            len(result.get("skipped") or []),
            len(result.get("failed") or []),
        )
        return {
            **result,
            "added": result.get("added") or [],
            "skipped": [*ownership_skipped, *(result.get("skipped") or [])],
            "failed": result.get("failed") or [],
            "targets": [owner._target_from_entry(entry) for entry in target_entries],
            "tasks": refreshed_tasks,
        }

    def filter_restart_task_ids_by_targets(
        self,
        task_ids: List[str],
        tasks_data: Dict[str, Any],
        target_entries: List[Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        owner = self._owner
        allowed_paths = {
            owner._normalize_text(entry.get("path"))
            for entry in target_entries
            if owner._normalize_text(entry.get("path"))
        }
        if not allowed_paths:
            return [], [{"task_id": task_id, "reason": "任务不属于当前可操作目标或目标已锁定"} for task_id in task_ids]
        task_by_id = {
            owner._normalize_text(task.get("task_id")): task
            for task in (tasks_data.get("tasks") or [])
            if owner._normalize_text(task.get("task_id"))
        }
        allowed: List[str] = []
        skipped: List[Dict[str, str]] = []
        for task_id in task_ids:
            task = task_by_id.get(task_id)
            if not task:
                skipped.append({"task_id": task_id, "reason": "任务不属于当前可操作目标或目标已锁定"})
                continue
            video_file = owner._normalize_text(task.get("video_file"))
            if video_file not in allowed_paths:
                skipped.append({"task_id": task_id, "path": video_file, "reason": "任务不属于当前可操作目标"})
                continue
            if task.get("active") or task.get("status") in {"pending", "in_progress"}:
                skipped.append({"task_id": task_id, "path": video_file, "reason": "任务正在处理，不能重新生成"})
                continue
            allowed.append(task_id)
        return allowed, skipped

    def selected_external_subtitle_override_for_entries(
        self,
        target_entries: List[Dict[str, Any]],
        *,
        source_subtitle_path: str,
        source_subtitle_lang: str = "",
        overwrite_policy: str = "new_variant",
    ) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        if len(target_entries) != 1:
            raise self._http_exception(status_code=400, detail="选中外挂字幕重新生成一次只能选择单个目标")
        entry = target_entries[0]
        video_path = owner._normalize_text(entry.get("path"))
        candidate = Path(owner._normalize_text(source_subtitle_path))
        if not video_path or not candidate.exists() or candidate.suffix.lower() != ".srt":
            raise self._http_exception(status_code=400, detail="请选择当前集已有的 SRT 外挂字幕")
        try:
            candidate_resolved = str(candidate.resolve())
        except Exception:
            candidate_resolved = str(candidate)
        allowed_paths = set()
        for subtitle in owner._subtitle_inventory().subtitle_files_for_target(entry):
            if owner._normalize_text(subtitle.get("ext")).lower() != ".srt":
                continue
            try:
                allowed_paths.add(str(Path(owner._normalize_text(subtitle.get("path"))).resolve()))
            except Exception:
                allowed_paths.add(owner._normalize_text(subtitle.get("path")))
        if candidate_resolved not in allowed_paths:
            raise self._http_exception(status_code=400, detail="请选择当前集已有的外挂 SRT 字幕")
        try:
            raw_bytes = candidate.read_bytes()
        except Exception:
            raw_bytes = b""
        profile = owner._detect_language_profile(candidate.name, raw_bytes)
        lang = source_subtitle_lang or owner._autosub_lang_from_suffix(profile.get("suffix"))
        return {
            video_path: {
                "subtitle_path": str(candidate),
                "lang": lang,
                "source_policy": "matched_external",
                "source_name": candidate.name,
                "timeline_fixed": False,
                "overwrite_policy": overwrite_policy,
            }
        }
