from pathlib import Path
from typing import Any, Dict, Mapping

from fastapi.responses import Response

from app import schemas
from app.log import logger
from .config import apply_config_state
from .loader import build_loader_response
from .manifest import ACTION_SUMMARY, AVATAR_SUMMARY


class AgentMascotApi:
    def __init__(self, plugin: Any, plugin_root: Path):
        self._plugin = plugin
        self._plugin_root = plugin_root

    def get_status(self) -> schemas.Response:
        return schemas.Response(
            success=True,
            data={
                "config": self._plugin._current_config(),
                "summary": {
                    "enabled": self._plugin.get_state(),
                    "replace_agent_entry": bool(getattr(self._plugin, "_replace_agent_entry", True)),
                    "avatar": AVATAR_SUMMARY,
                    "actions": ACTION_SUMMARY,
                },
            },
        )

    def get_public_status(self) -> schemas.Response:
        return schemas.Response(
            success=True,
            data={
                "config": self._plugin._current_config(),
                "summary": {
                    "enabled": self._plugin.get_state(),
                    "replace_agent_entry": bool(getattr(self._plugin, "_replace_agent_entry", True)),
                },
            },
        )

    def get_loader(self) -> Response:
        return build_loader_response(self._plugin_root)

    def save_config(self, config: Mapping[str, Any]) -> schemas.Response:
        try:
            apply_config_state(self._plugin, config)
            self._plugin._save_config()
            return schemas.Response(success=True, data=self.get_status().data)
        except Exception as err:
            logger.error(f"保存 Agent 桌宠配置失败: {err}")
            return schemas.Response(success=False, message=str(err))
