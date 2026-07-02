from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import Body
from fastapi.responses import Response

from app import schemas
from app.log import logger
from app.plugins import _PluginBase
from .config import apply_config_state, current_config_state
from .loader import build_loader_response


class AgentMascot(_PluginBase):
    """
    MoviePilot Agent 桌宠形象 demo。
    """

    plugin_name = "Agent 桌宠形象"
    plugin_desc = "为 MoviePilot 智能体提供可自定义的 Web 桌宠形象，内置小天照 Shimeji demo。"
    plugin_icon = "agentresourceofficer.png"
    plugin_version = "0.1.11"
    plugin_author = "ifsherlock"
    author_url = "https://github.com/ifsherlock/MoviePilot-Plugins"
    plugin_config_prefix = "agentmascot_"
    plugin_order = 47
    auth_level = 1

    def init_plugin(self, config: dict = None):
        apply_config_state(self, config)
        self._save_config()

    def get_state(self) -> bool:
        return bool(getattr(self, "_enabled", False))

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.get_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 Agent 桌宠配置",
            },
            {
                "path": "/public_status",
                "endpoint": self.get_public_status,
                "methods": ["GET"],
                "allow_anonymous": True,
                "summary": "获取 Agent 桌宠全局入口公开配置",
            },
            {
                "path": "/config",
                "endpoint": self.save_config_api,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存 Agent 桌宠配置",
            },
            {
                "path": "/loader",
                "endpoint": self.get_loader,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 Agent 桌宠全局入口脚本",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [], self._current_config()

    def get_page(self) -> List[dict]:
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self.get_state() or not getattr(self, "_show_sidebar_nav", True):
            return []
        return [
            {
                "nav_key": "main",
                "title": "Agent 桌宠",
                "icon": "mdi-paw",
                "section": "system",
                "permission": "manage",
                "order": 47,
            }
        ]

    def stop_service(self):
        pass

    def _current_config(self) -> Dict[str, Any]:
        return current_config_state(self)

    def _save_config(self) -> None:
        self.update_config(self._current_config())

    def get_status(self) -> schemas.Response:
        return schemas.Response(
            success=True,
            data={
                "config": self._current_config(),
                "summary": {
                    "enabled": self.get_state(),
                    "replace_agent_entry": bool(getattr(self, "_replace_agent_entry", True)),
                    "avatar": "小天照 Shimeji demo",
                    "actions": ["idle", "walk", "run", "follow", "drag", "sleep", "wall", "ceiling", "fall"],
                },
            },
        )

    def get_public_status(self) -> schemas.Response:
        return schemas.Response(
            success=True,
            data={
                "config": self._current_config(),
                "summary": {
                    "enabled": self.get_state(),
                    "replace_agent_entry": bool(getattr(self, "_replace_agent_entry", True)),
                },
            },
        )

    def get_loader(self) -> Response:
        return build_loader_response(Path(__file__).resolve().parent)

    def save_config_api(self, config: dict = Body(...)) -> schemas.Response:
        try:
            apply_config_state(self, config)
            self._save_config()
            return schemas.Response(success=True, data=self.get_status().data)
        except Exception as err:
            logger.error(f"保存 Agent 桌宠配置失败: {err}")
            return schemas.Response(success=False, message=str(err))
