from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import Body
from fastapi.responses import Response

from app import schemas
from app.plugins import _PluginBase
from .api import AgentMascotApi
from .config import apply_config_state, current_config_state
from .manifest import (
    AUTH_LEVEL,
    AUTHOR_URL,
    PLUGIN_AUTHOR,
    PLUGIN_CONFIG_PREFIX,
    PLUGIN_DESC,
    PLUGIN_ICON,
    PLUGIN_NAME,
    PLUGIN_ORDER,
    SIDEBAR_NAV_ICON,
    SIDEBAR_NAV_PERMISSION,
    SIDEBAR_NAV_SECTION,
    SIDEBAR_NAV_TITLE,
)


class AgentMascot(_PluginBase):
    """
    MoviePilot Agent 桌宠形象 demo。
    """

    plugin_name = PLUGIN_NAME
    plugin_desc = PLUGIN_DESC
    plugin_icon = PLUGIN_ICON
    plugin_version = "0.1.13"
    plugin_author = PLUGIN_AUTHOR
    author_url = AUTHOR_URL
    plugin_config_prefix = PLUGIN_CONFIG_PREFIX
    plugin_order = PLUGIN_ORDER
    auth_level = AUTH_LEVEL

    def init_plugin(self, config: dict = None):
        self._api = AgentMascotApi(self, Path(__file__).resolve().parent)
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
                "title": SIDEBAR_NAV_TITLE,
                "icon": SIDEBAR_NAV_ICON,
                "section": SIDEBAR_NAV_SECTION,
                "permission": SIDEBAR_NAV_PERMISSION,
                "order": PLUGIN_ORDER,
            }
        ]

    def stop_service(self):
        pass

    def _current_config(self) -> Dict[str, Any]:
        return current_config_state(self)

    def _save_config(self) -> None:
        self.update_config(self._current_config())

    def get_status(self) -> schemas.Response:
        return self._api.get_status()

    def get_public_status(self) -> schemas.Response:
        return self._api.get_public_status()

    def get_loader(self) -> Response:
        return self._api.get_loader()

    def save_config_api(self, config: dict = Body(...)) -> schemas.Response:
        return self._api.save_config(config)
