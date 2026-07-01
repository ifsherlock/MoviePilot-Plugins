from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..timeline.timeline_fixer import check_timeline_fixer_dependencies


class SubtitleAutomationFacade:
    """Shared automation boundary for workflow actions and agent tools."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def query_status(
        self,
        *,
        target_ids: Optional[Iterable[Any]] = None,
        keyword: str = "",
        include_history: bool = False,
        include_tasks: bool = True,
    ) -> Dict[str, Any]:
        enabled = self._ensure_enabled()
        if enabled:
            return enabled
        services = self.owner.services
        data: Dict[str, Any] = {
            "enabled": True,
            "index": services.local_media_catalog().cache_status(),
            "auto_transfer_queue": services.auto_transfer().auto_transfer_queue_summary(),
            "ai_subtitle": services.autosub_bridge().autosub_status(),
        }
        entries: List[Dict[str, Any]] = []
        clean_target_ids = self._target_ids(target_ids)
        if clean_target_ids:
            resolved = self._resolve_entries(clean_target_ids)
            if isinstance(resolved, dict):
                return resolved
            entries, targets = resolved
            data["targets"] = targets
            if include_tasks:
                data["ai_tasks"] = services.autosub_bridge().autosub_tasks_for_entries(entries)
                data["timeline_tasks"] = services.timeline_tasks().tasks_for_entries(entries)
        if include_history:
            data["history"] = services.history().match_history_items(
                keyword=self._normalize(keyword),
                media_type="all",
            )[:20]
        return self._ok(data, "字幕匹配状态查询完成")

    def refresh_index(self, *, sync: bool = False) -> Dict[str, Any]:
        enabled = self._ensure_enabled()
        if enabled:
            return enabled
        catalog = self.owner.services.local_media_catalog()
        if sync:
            entries = catalog.refresh_local_cache()
            return self._ok(
                {
                    "realtime": True,
                    "background": False,
                    "entry_count": len(entries),
                    "index": catalog.cache_status(),
                },
                f"媒体库资源清单已同步刷新，读取 {len(entries)} 个目标",
            )
        catalog.start_background_cache_refresh()
        return self._ok(
            {
                "realtime": False,
                "background": True,
                "index": catalog.cache_status(),
            },
            "媒体库资源清单已在后台刷新",
        )

    def online_match(
        self,
        *,
        target_ids: Iterable[Any],
        dry_run: bool = True,
        confirm_write: bool = False,
    ) -> Dict[str, Any]:
        enabled = self._ensure_enabled()
        if enabled:
            return enabled
        resolved = self._resolve_entries(self._target_ids(target_ids), require_targets=True)
        if isinstance(resolved, dict):
            return resolved
        entries, targets = resolved
        auto_transfer = self.owner.services.auto_transfer()
        if dry_run or not confirm_write:
            return self._ok(
                {
                    "dry_run": True,
                    "requires_confirmation": True,
                    "confirm_write": bool(confirm_write),
                    "targets": targets,
                    "keywords_by_target": self._keywords_by_target(auto_transfer, entries, targets),
                },
                "在线自动匹配预检完成，写入需 confirm_write=true",
            )
        results = [auto_transfer.auto_search_and_write_entry(entry) for entry in entries]
        return self._ok(
            {
                "dry_run": False,
                "confirm_write": True,
                "targets": targets,
                "results": results,
            },
            f"在线自动匹配已执行 {len(results)} 个目标",
        )

    def ai_generate(
        self,
        *,
        target_ids: Iterable[Any],
        source_policy: str = "auto",
        overwrite_policy: str = "skip",
        confirm_submit: bool = False,
    ) -> Dict[str, Any]:
        enabled = self._ensure_enabled()
        if enabled:
            return enabled
        resolved = self._resolve_entries(self._target_ids(target_ids), require_targets=True)
        if isinstance(resolved, dict):
            return resolved
        entries, targets = resolved
        autosub_bridge = self.owner.services.autosub_bridge()
        if not confirm_submit:
            return self._ok(
                {
                    "requires_confirmation": True,
                    "confirm_submit": False,
                    "targets": targets,
                    "tasks": autosub_bridge.autosub_tasks_for_entries(entries),
                },
                "AI 字幕生成预检完成，提交需 confirm_submit=true",
            )
        result = autosub_bridge.submit_autosub_for_entries(
            entries,
            trigger="workflow",
            source_policy=self._normalize(source_policy) or "auto",
            overwrite_policy=self._normalize(overwrite_policy) or "skip",
        )
        return self._ok(
            {
                "requires_confirmation": False,
                "confirm_submit": True,
                "targets": targets,
                **result,
            },
            f"AI 字幕生成已提交 {len(entries)} 个目标",
        )

    def task_status(self, *, target_ids: Optional[Iterable[Any]] = None, limit: int = 100) -> Dict[str, Any]:
        enabled = self._ensure_enabled()
        if enabled:
            return enabled
        services = self.owner.services
        clean_target_ids = self._target_ids(target_ids)
        data: Dict[str, Any] = {
            "auto_transfer_queue": services.auto_transfer().auto_transfer_queue_snapshot(
                limit=min(max(self._safe_int(limit, 100), 1), 200)
            ),
            "ai_subtitle": services.autosub_bridge().autosub_status(),
        }
        if clean_target_ids:
            resolved = self._resolve_entries(clean_target_ids)
            if isinstance(resolved, dict):
                return resolved
            entries, targets = resolved
            data["targets"] = targets
            data["ai_tasks"] = services.autosub_bridge().autosub_tasks_for_entries(entries)
            data["timeline_tasks"] = services.timeline_tasks().tasks_for_entries(entries)
        return self._ok(data, "字幕匹配任务状态查询完成")

    def timeline_fix(
        self,
        *,
        target_ids: Iterable[Any],
        subtitle_paths: Any = None,
        allow_risky_offset: bool = False,
        confirm_fix: bool = False,
    ) -> Dict[str, Any]:
        enabled = self._ensure_enabled()
        if enabled:
            return enabled
        clean_target_ids = self._target_ids(target_ids)
        if not clean_target_ids:
            return self._fail("请提供 target_ids")
        requested_items = self._timeline_request_items(clean_target_ids, subtitle_paths)
        services = self.owner.services
        operations, skipped, failed = services.history().existing_timeline_operations(requested_items)
        target_entries = [operation["target_entry"] for operation in operations]
        if not confirm_fix:
            return self._ok(
                {
                    "requires_confirmation": True,
                    "confirm_fix": False,
                    "preview_count": len(operations),
                    "skipped": skipped,
                    "failed": failed,
                    "timeline_tasks": services.timeline_tasks().tasks_for_entries(target_entries) if target_entries else {},
                },
                "智能调轴预检完成，提交需 confirm_fix=true",
            )
        if not operations:
            return self._ok(
                {
                    "accepted": 0,
                    "skipped": skipped,
                    "failed": failed,
                    "summary": self.owner._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                },
                "没有可提交智能调轴的历史字幕",
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
            return self._fail(f"智能调轴不可用：缺少 {', '.join(missing) or '依赖'}", {"timeline_fixer": timeline_status})
        timeline_tasks = services.timeline_tasks()
        for operation in operations:
            timeline_tasks.set_task(operation, status="pending", message="等待历史字幕智能调轴")
        session_id = self.owner._hash_text(f"existing-timeline|{datetime.now().isoformat()}|{len(operations)}")[:16]
        session_dir = services.upload_session().get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(
            target=services.writer().run_existing_timeline_fix,
            args=(session_dir, operations),
            kwargs={"allow_risky_offset": bool(allow_risky_offset)},
            name="SubtitleManualUploadExistingTimelineFix",
            daemon=True,
        ).start()
        task_data = timeline_tasks.tasks_for_entries(target_entries)
        return self._ok(
            {
                "accepted": len(operations),
                "skipped": skipped,
                "failed": failed,
                **task_data,
            },
            f"已提交 {len(operations)} 个历史字幕智能调轴任务，跳过 {len(skipped)} 个，失败 {len(failed)} 个",
        )

    def _ensure_enabled(self) -> Optional[Dict[str, Any]]:
        if not self.owner.get_state():
            return self._fail("SubtitleManualUpload 插件未启用", {"enabled": False})
        return None

    def _resolve_entries(
        self,
        target_ids: List[str],
        *,
        require_targets: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]] | Dict[str, Any]:
        if require_targets and not target_ids:
            return self._fail("请提供 target_ids")
        entries_by_id = self.owner.services.local_media_catalog().resolve_targets(target_ids)
        missing = [target_id for target_id in target_ids if target_id not in entries_by_id]
        if missing:
            return self._fail(
                "目标视频已失效，请重新选择资源",
                {
                    "missing_target_ids": missing,
                    "resolved_target_ids": list(entries_by_id.keys()),
                },
            )
        entries = [entries_by_id[target_id] for target_id in target_ids if target_id in entries_by_id]
        targets = [self.owner.services.target_resolver().target_from_entry(entry) for entry in entries]
        return entries, targets

    def _keywords_by_target(
        self,
        auto_transfer: Any,
        entries: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for entry, target in zip(entries, targets):
            target_id = self._normalize(entry.get("id"))
            result[target_id] = auto_transfer.auto_search_keywords_for_entry(entry, target)
        return result

    def _timeline_request_items(self, target_ids: List[str], subtitle_paths: Any) -> List[Dict[str, str]]:
        if isinstance(subtitle_paths, dict):
            return [
                {"target_id": target_id, "subtitle_path": self._normalize(subtitle_paths.get(target_id))}
                for target_id in target_ids
            ]
        if isinstance(subtitle_paths, list):
            path_by_target = {
                target_id: self._normalize(subtitle_paths[index])
                for index, target_id in enumerate(target_ids)
                if index < len(subtitle_paths)
            }
            return [{"target_id": target_id, "subtitle_path": path_by_target.get(target_id, "")} for target_id in target_ids]
        return [{"target_id": target_id} for target_id in target_ids]

    def _target_ids(self, values: Optional[Iterable[Any]]) -> List[str]:
        if values is None:
            return []
        if isinstance(values, str):
            values = [values]
        result: List[str] = []
        seen = set()
        for value in values:
            text = self._normalize(value)
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    @staticmethod
    def _ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data or {}}

    @staticmethod
    def _fail(message: str, data: Any = None) -> Dict[str, Any]:
        return {"success": False, "message": message, "data": data or {}}

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _normalize(value: Any) -> str:
        return str(value or "").strip()
