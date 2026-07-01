from __future__ import annotations

from typing import Any, Dict, List

from .automation_facade import SubtitleAutomationFacade


class SubtitleWorkflowActions:
    def __init__(self, owner: Any) -> None:
        self._facade = SubtitleAutomationFacade(owner)

    def query_status(self, action_content: Any = None, **kwargs: Any) -> Dict[str, Any]:
        payload = self._payload(action_content, kwargs)
        return self._facade.query_status(
            target_ids=payload.get("target_ids"),
            keyword=payload.get("keyword", ""),
            include_history=bool(payload.get("include_history", False)),
            include_tasks=bool(payload.get("include_tasks", True)),
        )

    def refresh_index(self, action_content: Any = None, **kwargs: Any) -> Dict[str, Any]:
        payload = self._payload(action_content, kwargs)
        return self._facade.refresh_index(sync=bool(payload.get("sync", False)))

    def online_match(self, action_content: Any = None, **kwargs: Any) -> Dict[str, Any]:
        payload = self._payload(action_content, kwargs)
        return self._facade.online_match(
            target_ids=payload.get("target_ids") or [],
            dry_run=bool(payload.get("dry_run", True)),
            confirm_write=bool(payload.get("confirm_write", False)),
        )

    def ai_generate(self, action_content: Any = None, **kwargs: Any) -> Dict[str, Any]:
        payload = self._payload(action_content, kwargs)
        return self._facade.ai_generate(
            target_ids=payload.get("target_ids") or [],
            source_policy=payload.get("source_policy", "auto"),
            overwrite_policy=payload.get("overwrite_policy", "skip"),
            confirm_submit=bool(payload.get("confirm_submit", False)),
        )

    def timeline_fix(self, action_content: Any = None, **kwargs: Any) -> Dict[str, Any]:
        payload = self._payload(action_content, kwargs)
        return self._facade.timeline_fix(
            target_ids=payload.get("target_ids") or [],
            subtitle_paths=payload.get("subtitle_paths"),
            allow_risky_offset=bool(payload.get("allow_risky_offset", False)),
            confirm_fix=bool(payload.get("confirm_fix", False)),
        )

    @staticmethod
    def _payload(action_content: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if isinstance(action_content, dict):
            payload.update(action_content)
        else:
            for attr in ("kwargs", "data", "params", "content"):
                value = getattr(action_content, attr, None)
                if isinstance(value, dict):
                    payload.update(value)
        payload.update(kwargs)
        return payload


def build_actions(owner: Any) -> List[Dict[str, Any]]:
    actions = SubtitleWorkflowActions(owner)
    return [
        {
            "id": "subtitlemanualupload_query_status",
            "name": "字幕匹配：查询状态",
            "func": actions.query_status,
            "kwargs": {"include_history": False, "include_tasks": True},
        },
        {
            "id": "subtitlemanualupload_refresh_index",
            "name": "字幕匹配：刷新本地索引",
            "func": actions.refresh_index,
            "kwargs": {"sync": False},
        },
        {
            "id": "subtitlemanualupload_online_match",
            "name": "字幕匹配：在线自动匹配",
            "func": actions.online_match,
            "kwargs": {"dry_run": True, "confirm_write": False},
        },
        {
            "id": "subtitlemanualupload_ai_generate",
            "name": "字幕匹配：AI 生成字幕",
            "func": actions.ai_generate,
            "kwargs": {
                "source_policy": "auto",
                "overwrite_policy": "skip",
                "confirm_submit": False,
            },
        },
        {
            "id": "subtitlemanualupload_timeline_fix",
            "name": "字幕匹配：智能调轴",
            "func": actions.timeline_fix,
            "kwargs": {"allow_risky_offset": False, "confirm_fix": False},
        },
    ]
