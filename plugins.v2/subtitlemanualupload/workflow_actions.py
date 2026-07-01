from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Tuple

from .automation_facade import SubtitleAutomationFacade


class WorkflowActionCallable(str):
    """Callable string: serializable for the workflow API, callable for execution."""

    def __new__(cls, action_id: str, func: Callable[..., Tuple[bool, Any]]) -> "WorkflowActionCallable":
        obj = str.__new__(cls, action_id)
        obj._func = func
        obj.__signature__ = inspect.signature(func)
        return obj

    def __call__(self, action_content: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        return self._func(action_content, **kwargs)


class SubtitleWorkflowActions:
    def __init__(self, owner: Any) -> None:
        self._facade = SubtitleAutomationFacade(owner)

    def query_status(self, action_content: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        payload = self._payload(action_content, kwargs)
        result = self._facade.query_status(
            target_ids=payload.get("target_ids"),
            keyword=payload.get("keyword", ""),
            include_history=bool(payload.get("include_history", False)),
            include_tasks=bool(payload.get("include_tasks", True)),
        )
        return self._complete("subtitlemanualupload_query_status", action_content, result)

    def refresh_index(self, action_content: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        payload = self._payload(action_content, kwargs)
        result = self._facade.refresh_index(sync=bool(payload.get("sync", False)))
        return self._complete("subtitlemanualupload_refresh_index", action_content, result)

    def online_match(self, action_content: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        payload = self._payload(action_content, kwargs)
        result = self._facade.online_match(
            target_ids=payload.get("target_ids") or [],
            dry_run=bool(payload.get("dry_run", True)),
            confirm_write=bool(payload.get("confirm_write", False)),
        )
        return self._complete("subtitlemanualupload_online_match", action_content, result)

    def ai_generate(self, action_content: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        payload = self._payload(action_content, kwargs)
        result = self._facade.ai_generate(
            target_ids=payload.get("target_ids") or [],
            source_policy=payload.get("source_policy", "auto"),
            overwrite_policy=payload.get("overwrite_policy", "skip"),
            confirm_submit=bool(payload.get("confirm_submit", False)),
        )
        return self._complete("subtitlemanualupload_ai_generate", action_content, result)

    def timeline_fix(self, action_content: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        payload = self._payload(action_content, kwargs)
        result = self._facade.timeline_fix(
            target_ids=payload.get("target_ids") or [],
            subtitle_paths=payload.get("subtitle_paths"),
            allow_risky_offset=bool(payload.get("allow_risky_offset", False)),
            confirm_fix=bool(payload.get("confirm_fix", False)),
        )
        return self._complete("subtitlemanualupload_timeline_fix", action_content, result)

    @staticmethod
    def _complete(action_id: str, action_content: Any, result: Dict[str, Any]) -> Tuple[bool, Any]:
        success = bool(result.get("success"))
        if action_content is None:
            return success, result
        SubtitleWorkflowActions._write_result(action_content, action_id, result)
        return success, action_content

    @staticmethod
    def _write_result(action_content: Any, action_id: str, result: Dict[str, Any]) -> None:
        if isinstance(action_content, dict):
            bucket = action_content.setdefault("subtitlemanualupload", {})
            if isinstance(bucket, dict):
                bucket["last_action"] = action_id
                bucket["last_result"] = result
                bucket[action_id] = result
            return

        workflow_context = getattr(action_content, "workflow_context", None)
        if not isinstance(workflow_context, dict):
            workflow_context = {}
            try:
                setattr(action_content, "workflow_context", workflow_context)
            except Exception:
                workflow_context = None
        if isinstance(workflow_context, dict):
            bucket = workflow_context.setdefault("subtitlemanualupload", {})
            if isinstance(bucket, dict):
                bucket["last_action"] = action_id
                bucket["last_result"] = result
                bucket[action_id] = result

        node_outputs = getattr(action_content, "node_outputs", None)
        if not isinstance(node_outputs, dict):
            node_outputs = {}
            try:
                setattr(action_content, "node_outputs", node_outputs)
            except Exception:
                node_outputs = None
        if isinstance(node_outputs, dict):
            bucket = node_outputs.setdefault("subtitlemanualupload", {})
            if isinstance(bucket, dict):
                bucket[action_id] = result

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


def _action_entry(
    action_id: str,
    name: str,
    func: Callable[..., Tuple[bool, Any]],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": action_id,
        "action_id": action_id,
        "name": name,
        "func": WorkflowActionCallable(action_id, func),
        "kwargs": kwargs,
    }


def build_actions(owner: Any) -> List[Dict[str, Any]]:
    actions = SubtitleWorkflowActions(owner)
    return [
        _action_entry(
            "subtitlemanualupload_query_status",
            "字幕匹配：查询状态",
            actions.query_status,
            {"include_history": False, "include_tasks": True},
        ),
        _action_entry(
            "subtitlemanualupload_refresh_index",
            "字幕匹配：刷新本地索引",
            actions.refresh_index,
            {"sync": False},
        ),
        _action_entry(
            "subtitlemanualupload_online_match",
            "字幕匹配：在线自动匹配",
            actions.online_match,
            {"dry_run": True, "confirm_write": False},
        ),
        _action_entry(
            "subtitlemanualupload_ai_generate",
            "字幕匹配：AI 生成字幕",
            actions.ai_generate,
            {
                "source_policy": "auto",
                "overwrite_policy": "skip",
                "confirm_submit": False,
            },
        ),
        _action_entry(
            "subtitlemanualupload_timeline_fix",
            "字幕匹配：智能调轴",
            actions.timeline_fix,
            {"allow_risky_offset": False, "confirm_fix": False},
        ),
    ]
