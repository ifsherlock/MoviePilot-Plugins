from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .automation_facade import SubtitleAutomationFacade

try:
    from app.agent.tools.base import MoviePilotTool
except Exception:
    class MoviePilotTool:
        pass

try:
    from app.core.plugin import PluginManager
except Exception:
    PluginManager = None


class SubtitleStatusInput(BaseModel):
    target_ids: List[str] = Field(default_factory=list, description="要查询的字幕匹配目标 ID 列表")
    keyword: str = Field(default="", description="匹配历史查询关键字")
    include_history: bool = Field(default=False, description="是否返回最近匹配历史")
    include_tasks: bool = Field(default=True, description="是否返回目标相关 AI 和调轴任务")


class SubtitleOnlineMatchInput(BaseModel):
    target_ids: List[str] = Field(default_factory=list, description="要在线匹配字幕的目标 ID 列表")
    dry_run: bool = Field(default=True, description="是否只预检不写入")
    confirm_write: bool = Field(default=False, description="确认写入字幕时设为 true")


class SubtitleAiGenerateInput(BaseModel):
    target_ids: List[str] = Field(default_factory=list, description="要提交 AI 字幕生成的目标 ID 列表")
    source_policy: str = Field(default="auto", description="AI 字幕源策略")
    overwrite_policy: str = Field(default="skip", description="已存在字幕时的处理策略")
    confirm_submit: bool = Field(default=False, description="确认提交 AI 任务时设为 true")


class SubtitleTaskStatusInput(BaseModel):
    target_ids: List[str] = Field(default_factory=list, description="要查询任务的目标 ID 列表")
    limit: int = Field(default=100, description="自动入库队列最多返回条数")


class SubtitleTimelineFixInput(BaseModel):
    target_ids: List[str] = Field(default_factory=list, description="要执行智能调轴的目标 ID 列表")
    subtitle_paths: Any = Field(default=None, description="可选，按目标指定的外挂字幕路径")
    allow_risky_offset: bool = Field(default=False, description="是否允许较大调轴偏移")
    confirm_fix: bool = Field(default=False, description="确认执行调轴时设为 true")


class BaseSubtitleTool(MoviePilotTool):
    def _plugin_instance(self) -> Any:
        if PluginManager is None:
            return None
        running_plugins = getattr(PluginManager(), "running_plugins", {}) or {}
        plugin = running_plugins.get("SubtitleManualUpload") or running_plugins.get("subtitlemanualupload")
        if plugin:
            return plugin
        for candidate in running_plugins.values():
            if candidate.__class__.__name__ == "SubtitleManualUpload":
                return candidate
        return None

    def _facade(self) -> Optional[SubtitleAutomationFacade]:
        plugin = self._plugin_instance()
        if not plugin:
            return None
        return SubtitleAutomationFacade(plugin)

    @staticmethod
    def _tool_result(result: Dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False, default=str)

    def _missing_plugin_result(self) -> str:
        return self._tool_result(
            {
                "success": False,
                "message": "SubtitleManualUpload 插件未运行",
                "data": {},
            }
        )


class SubtitleStatusTool(BaseSubtitleTool):
    name: str = "subtitle_status_tool"
    description: str = "Query SubtitleManualUpload plugin status, subtitle targets, history, and related tasks."
    args_schema: Type[BaseModel] = SubtitleStatusInput

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        target_count = len(kwargs.get("target_ids") or [])
        return f"正在查询字幕匹配状态，目标数量：{target_count}"

    async def run(
        self,
        target_ids: Optional[List[str]] = None,
        keyword: str = "",
        include_history: bool = False,
        include_tasks: bool = True,
        **kwargs: Any,
    ) -> str:
        facade = self._facade()
        if facade is None:
            return self._missing_plugin_result()
        return self._tool_result(
            facade.query_status(
                target_ids=target_ids or [],
                keyword=keyword,
                include_history=include_history,
                include_tasks=include_tasks,
            )
        )


class SubtitleOnlineMatchTool(BaseSubtitleTool):
    name: str = "subtitle_online_match_tool"
    description: str = "Run SubtitleManualUpload online subtitle matching for explicit target IDs."
    args_schema: Type[BaseModel] = SubtitleOnlineMatchInput

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        target_count = len(kwargs.get("target_ids") or [])
        if kwargs.get("confirm_write"):
            return f"正在为 {target_count} 个目标在线匹配并写入字幕"
        return f"正在预检 {target_count} 个目标的在线字幕匹配"

    async def run(
        self,
        target_ids: Optional[List[str]] = None,
        dry_run: bool = True,
        confirm_write: bool = False,
        **kwargs: Any,
    ) -> str:
        facade = self._facade()
        if facade is None:
            return self._missing_plugin_result()
        return self._tool_result(
            facade.online_match(
                target_ids=target_ids or [],
                dry_run=dry_run,
                confirm_write=confirm_write,
            )
        )


class SubtitleAiGenerateTool(BaseSubtitleTool):
    name: str = "subtitle_ai_generate_tool"
    description: str = "Submit SubtitleManualUpload AI subtitle generation for explicit target IDs."
    args_schema: Type[BaseModel] = SubtitleAiGenerateInput

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        target_count = len(kwargs.get("target_ids") or [])
        if kwargs.get("confirm_submit"):
            return f"正在提交 {target_count} 个目标的 AI 字幕生成任务"
        return f"正在预检 {target_count} 个目标的 AI 字幕生成"

    async def run(
        self,
        target_ids: Optional[List[str]] = None,
        source_policy: str = "auto",
        overwrite_policy: str = "skip",
        confirm_submit: bool = False,
        **kwargs: Any,
    ) -> str:
        facade = self._facade()
        if facade is None:
            return self._missing_plugin_result()
        return self._tool_result(
            facade.ai_generate(
                target_ids=target_ids or [],
                source_policy=source_policy,
                overwrite_policy=overwrite_policy,
                confirm_submit=confirm_submit,
            )
        )


class SubtitleTaskStatusTool(BaseSubtitleTool):
    name: str = "subtitle_task_status_tool"
    description: str = "Query SubtitleManualUpload AI subtitle tasks, timeline tasks, and auto-transfer queue."
    args_schema: Type[BaseModel] = SubtitleTaskStatusInput

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        target_count = len(kwargs.get("target_ids") or [])
        return f"正在查询字幕匹配任务状态，目标数量：{target_count}"

    async def run(self, target_ids: Optional[List[str]] = None, limit: int = 100, **kwargs: Any) -> str:
        facade = self._facade()
        if facade is None:
            return self._missing_plugin_result()
        return self._tool_result(facade.task_status(target_ids=target_ids or [], limit=limit))


class SubtitleTimelineFixTool(BaseSubtitleTool):
    name: str = "subtitle_timeline_fix_tool"
    description: str = "Run SubtitleManualUpload timeline fixing for existing external subtitles."
    args_schema: Type[BaseModel] = SubtitleTimelineFixInput

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        target_count = len(kwargs.get("target_ids") or [])
        if kwargs.get("confirm_fix"):
            return f"正在提交 {target_count} 个目标的智能调轴任务"
        return f"正在预检 {target_count} 个目标的智能调轴"

    async def run(
        self,
        target_ids: Optional[List[str]] = None,
        subtitle_paths: Any = None,
        allow_risky_offset: bool = False,
        confirm_fix: bool = False,
        **kwargs: Any,
    ) -> str:
        facade = self._facade()
        if facade is None:
            return self._missing_plugin_result()
        return self._tool_result(
            facade.timeline_fix(
                target_ids=target_ids or [],
                subtitle_paths=subtitle_paths,
                allow_risky_offset=allow_risky_offset,
                confirm_fix=confirm_fix,
            )
        )


def get_agent_tools() -> List[type]:
    return [
        SubtitleStatusTool,
        SubtitleOnlineMatchTool,
        SubtitleAiGenerateTool,
        SubtitleTaskStatusTool,
        SubtitleTimelineFixTool,
    ]
