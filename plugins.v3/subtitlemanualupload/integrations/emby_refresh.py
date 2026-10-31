from __future__ import annotations

from importlib import import_module
from typing import Any, Iterable
from urllib.parse import quote


_EXTERNAL_SUBTITLE_SCAN_TASK_KEYS = (
    "ScanExternalTrackTask",
    "ScanExternalSubtitleTask",
)
_REQUEST_TIMEOUT_SECONDS = 15


class EmbyRefreshService:
    """Scan external subtitles on configured Emby servers."""

    def __init__(self, logger: Any) -> None:
        self._logger = logger

    def _configured_instances(self) -> dict[str, Any]:
        """Read configured instances across MoviePilot V2 and V3 service APIs."""
        for module_name in ("app.application.mediaserver", "app.helper.mediaserver"):
            try:
                helper_module = import_module(module_name)
            except ModuleNotFoundError as exc:
                if exc.name not in {module_name, module_name.rsplit(".", 1)[0]}:
                    raise
                continue
            try:
                services = helper_module.MediaServerHelper().get_services() or {}
            except Exception as exc:
                self._logger.warning("[SubtitleManualUpload] 读取 MoviePilot 媒体服务器目录失败: %s", exc)
                continue
            instances = {
                name or "default": service.instance
                for name, service in services.items()
                if getattr(service, "instance", None) is not None
                and not self._is_inactive(service.instance)
            }
            if instances:
                return instances

        try:
            try:
                module_manager = import_module("app.sdk.plugin").ModuleManager
            except ModuleNotFoundError as exc:
                if exc.name not in {"app.sdk", "app.sdk.plugin"}:
                    raise
                module_manager = import_module("app.core.module").ModuleManager
            module = module_manager().get_running_module("EmbyModule")
            return dict(module.get_instances()) if module else {}
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取 MoviePilot Emby 实例失败: %s", exc)
            return {}

    @staticmethod
    def _is_inactive(instance: Any) -> bool:
        inactive = getattr(instance, "is_inactive", None)
        return bool(inactive()) if callable(inactive) else False

    def refresh_for_videos(self, targets: Iterable[dict[str, Any]]) -> bool:
        """Prefer Strm Assistant's external subtitle task, then refresh the library if absent."""
        if not any(target for target in targets):
            return False

        instances = self._configured_instances()
        if not instances:
            self._logger.info("[SubtitleManualUpload] 未配置可用的 Emby 实例，跳过外挂字幕扫描")
            return False

        try:
            request_utils = self._request_utils()
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] MoviePilot HTTP 客户端不可用: %s", exc)
            return False

        started = False
        for name, instance in instances.items():
            if self._start_external_track_scan(name, instance, request_utils):
                started = True
        return started

    def _start_external_track_scan(self, name: str, instance: Any, request_utils: Any) -> bool:
        host = getattr(instance, "_host", None)
        api_key = getattr(instance, "_apikey", None)
        if not host or not api_key:
            self._logger.warning("[SubtitleManualUpload] Emby 实例缺少连接信息 name=%s", name)
            return False

        base_url = host.rstrip("/") + "/"
        params = {"api_key": api_key}
        try:
            response = request_utils.get_res(
                base_url + "emby/ScheduledTasks",
                params=params,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            if response is None or not 200 <= response.status_code < 300:
                status = getattr(response, "status_code", None)
                self._logger.warning("[SubtitleManualUpload] 查询 Emby 计划任务失败 name=%s status=%s", name, status)
                return False

            tasks = response.json()
            if isinstance(tasks, dict):
                tasks = tasks.get("Items", [])
            if not isinstance(tasks, list):
                self._logger.warning("[SubtitleManualUpload] Emby 计划任务响应格式错误 name=%s", name)
                return False

            task = next((
                item for item in tasks
                if isinstance(item, dict) and item.get("Key") in _EXTERNAL_SUBTITLE_SCAN_TASK_KEYS
            ), None)
            if task is None:
                return self._refresh_library(name, base_url, params, request_utils)
            if not task.get("Id"):
                self._logger.warning(
                    "[SubtitleManualUpload] 找到神医助手外挂字幕扫描任务但缺少任务 ID name=%s key=%s",
                    name,
                    task.get("Key"),
                )
                return False

            task_id = str(task["Id"])
            if task.get("State") == "Running":
                self._logger.info("[SubtitleManualUpload] 神医助手外挂字幕扫描已在运行 name=%s task_id=%s", name, task_id)
                return True

            response = request_utils.post_res(
                base_url + "emby/ScheduledTasks/Running/" + quote(task_id, safe=""),
                params=params,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            if response is None or not 200 <= response.status_code < 300:
                status = getattr(response, "status_code", None)
                self._logger.warning(
                    "[SubtitleManualUpload] 启动神医助手外挂字幕扫描失败 name=%s task_id=%s status=%s",
                    name,
                    task_id,
                    status,
                )
                return False

            self._logger.info(
                "[SubtitleManualUpload] 已启动神医助手外挂字幕扫描 name=%s task_id=%s",
                name,
                task_id,
            )
            return True
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 调用神医助手外挂字幕扫描失败 name=%s error=%s", name, exc)
            return False

    def _refresh_library(self, name: str, base_url: str, params: dict, request_utils: Any) -> bool:
        """Use Emby's supported full-library refresh only when no dedicated task exists."""
        self._logger.info("[SubtitleManualUpload] 未找到神医助手外挂字幕任务，改为全库刷新 name=%s", name)
        try:
            response = request_utils.post_res(
                base_url + "emby/Library/Refresh",
                params=params,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] Emby 全库刷新请求异常 name=%s error=%s", name, exc)
            return False
        if response is None or not 200 <= response.status_code < 300:
            status = getattr(response, "status_code", None)
            self._logger.warning("[SubtitleManualUpload] Emby 全库刷新失败 name=%s status=%s", name, status)
            return False
        self._logger.info("[SubtitleManualUpload] 已触发 Emby 全库刷新 name=%s", name)
        return True

    @staticmethod
    def _request_utils() -> Any:
        """Load the MoviePilot HTTP wrapper from either supported generation."""
        try:
            module = import_module("app.adapters.network.http")
        except ModuleNotFoundError as exc:
            if exc.name not in {"app.adapters", "app.adapters.network", "app.adapters.network.http"}:
                raise
            module = import_module("app.utils.http")
        return module.RequestUtils()
