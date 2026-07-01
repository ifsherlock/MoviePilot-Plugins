import os
import traceback
from typing import Any, Callable, List

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..core.models import GenerationMode, OverwritePolicy, SourcePolicy, TaskSource, TriggerType


class FileMonitorHandler(FileSystemEventHandler):
    """Watchdog handler that submits newly created media files to AutoSubv3."""

    def __init__(self, mon_path: str, monitor_service: "MonitorService"):
        super(FileMonitorHandler, self).__init__()
        self._watch_path = mon_path
        self._monitor_service = monitor_service

    def on_created(self, event):
        if not event.is_directory:
            logger = getattr(self._monitor_service, "logger", None)
            if logger:
                logger.debug(f"检测到新文件：{event.src_path}")
            if hasattr(self._monitor_service, "add_monitor_task"):
                self._monitor_service.add_monitor_task(event.src_path)
            else:
                self._monitor_service._add_monitor_task(event.src_path)


class MonitorService:
    def __init__(
        self,
        plugin: Any,
        media_extensions: List[str],
        logger: Any,
        plugin_manager_getter: Callable[[], Any],
        observer_factory: Callable[..., Any] = Observer,
    ):
        self._plugin = plugin
        self._media_extensions = media_extensions
        self._logger = logger
        self._plugin_manager_getter = plugin_manager_getter
        self._observer_factory = observer_factory

    @property
    def logger(self):
        return self._logger

    def start_file_monitor(self):
        """Start watchdog directory monitoring and optional full scan."""
        self.stop_observer()

        if not self._plugin._monitor_paths:
            self._logger.info("未配置监控路径，不启动目录监控")
            return
        if self._plugin._generation_mode == GenerationMode.FALLBACK.value:
            self._logger.info("AI 字幕生成当前为后备模式，不启动主动目录监控")
            return
        if self.subtitlemanualupload_auto_transfer_enabled():
            self._logger.info("字幕匹配入库自动处理已启用，AutoSubv3 不启动独立目录监控")
            return

        if not self._plugin._process_new_only:
            self._logger.info("仅处理新增关闭，开始全量扫描监控路径 ...")
            for mon_path in self._plugin._monitor_paths:
                if os.path.isdir(mon_path):
                    for video_file in self.library_files(mon_path, self._media_extensions):
                        self._plugin.add_task(
                            video_file,
                            TaskSource.EVENT,
                            trigger=TriggerType.MANUAL.value,
                            source_policy=SourcePolicy.AUTO.value,
                            overwrite_policy=OverwritePolicy.SKIP.value,
                        )
            self._logger.info("全量扫描完成")

        try:
            self._plugin._observer = self._observer_factory(timeout=10)
            for mon_path in self._plugin._monitor_paths:
                if os.path.isdir(mon_path):
                    handler = FileMonitorHandler(mon_path, self)
                    self._plugin._observer.schedule(handler, path=mon_path, recursive=True)
                    self._logger.info(f"启动目录监控：{mon_path}")
            self._plugin._observer.daemon = True
            self._plugin._observer.start()
            self._logger.info("目录监控服务已启动")
        except Exception as e:
            self._logger.error(f"启动目录监控失败：{e}")
            self._logger.error(traceback.format_exc())

    def add_monitor_task(self, file_path: str):
        """Add a media file discovered by the directory monitor."""
        if not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[-1].lower()
        if ext not in self._media_extensions:
            return
        if self._plugin._generation_mode == GenerationMode.FALLBACK.value:
            self._logger.info("AI 字幕生成当前为后备模式，忽略主动监控新增文件：%s", file_path)
            return
        if self.subtitlemanualupload_auto_transfer_enabled():
            self._logger.info("字幕匹配入库自动处理已启用，忽略 AutoSubv3 独立监控新增文件：%s", file_path)
            return
        with self._plugin._lock:
            self._plugin.add_task(
                file_path,
                TaskSource.EVENT,
                trigger=TriggerType.MANUAL.value,
                source_policy=SourcePolicy.AUTO.value,
                overwrite_policy=OverwritePolicy.SKIP.value,
            )

    def run_at_once(self, path_list: List[str]):
        # Immediate run uses configured library paths and does not apply the monitor whitelist.
        for path in path_list:
            if not os.path.exists(path) or not os.path.isabs(path):
                self._logger.warn(f"目录/文件无效，不进行处理:{path}")
                continue
            if os.path.isdir(path):
                for video_file in self.library_files(path, self._media_extensions):
                    self._plugin.add_task(
                        video_file,
                        TaskSource.MANUAL,
                        trigger=TriggerType.MANUAL.value,
                        source_policy=SourcePolicy.AUTO.value,
                        overwrite_policy=OverwritePolicy.SKIP.value,
                    )
            elif os.path.splitext(path)[-1].lower() in self._media_extensions:
                self._plugin.add_task(
                    path,
                    TaskSource.MANUAL,
                    trigger=TriggerType.MANUAL.value,
                    source_policy=SourcePolicy.AUTO.value,
                    overwrite_policy=OverwritePolicy.SKIP.value,
                )

    def check_asr(self):
        if not self._plugin._faster_whisper_model_path or not self._plugin._faster_whisper_model:
            self._logger.warn(f"faster-whisper配置信息不完整，不进行处理")
            return False
        if not os.path.exists(self._plugin._faster_whisper_model_path):
            self._logger.info(f"创建faster-whisper模型目录：{self._plugin._faster_whisper_model_path}")
            os.mkdir(self._plugin._faster_whisper_model_path)
        try:
            from faster_whisper import WhisperModel, download_model  # noqa: F401
        except ImportError:
            self._logger.warn(f"faster-whisper 未安装，不进行处理")
            return False
        return True

    def stop_observer(self):
        if self._plugin._observer:
            try:
                self._plugin._observer.stop()
                self._plugin._observer.join(timeout=5)
            except Exception:
                pass
            self._plugin._observer = None

    def subtitlemanualupload_auto_transfer_enabled(self) -> bool:
        return self.check_subtitlemanualupload_auto_transfer_enabled(
            self._plugin_manager_getter,
            self._logger,
        )

    @staticmethod
    def check_subtitlemanualupload_auto_transfer_enabled(plugin_manager_getter, logger) -> bool:
        plugin_manager = plugin_manager_getter() if plugin_manager_getter else None
        if plugin_manager is None:
            return False
        try:
            running_plugins = plugin_manager().running_plugins or {}
        except Exception as exc:
            logger.warning("[AutoSubv3] 读取字幕匹配插件状态失败: %s", exc)
            return False
        plugin = running_plugins.get("SubtitleManualUpload") or running_plugins.get("subtitlemanualupload")
        if not plugin:
            for candidate in running_plugins.values():
                if candidate.__class__.__name__ == "SubtitleManualUpload":
                    plugin = candidate
                    break
        if not plugin:
            return False
        try:
            enabled = bool(plugin.get_state()) if hasattr(plugin, "get_state") else bool(getattr(plugin, "_enabled", False))
            auto_transfer = bool(getattr(plugin, "_auto_search_on_transfer", False))
            ai_link_enabled = bool(getattr(plugin, "_ai_link_enabled", True))
            strategy = str(getattr(plugin, "_auto_transfer_subtitle_strategy", "") or "").strip()
        except Exception as exc:
            logger.warning("[AutoSubv3] 判断字幕匹配入库自动处理状态失败: %s", exc)
            return False
        ai_takeover_strategies = {"online_then_ai_source", "ai_source_only"}
        return enabled and auto_transfer and ai_link_enabled and strategy in ai_takeover_strategies

    @staticmethod
    def library_files(in_path, media_extensions, exclude_path=None):
        if not os.path.isdir(in_path):
            yield in_path
            return

        for root, dirs, files in os.walk(in_path):
            if exclude_path and any(os.path.abspath(root).startswith(os.path.abspath(path))
                                    for path in exclude_path.split(",")):
                continue

            for file in files:
                cur_path = os.path.join(root, file)
                if os.path.splitext(file)[-1].lower() in media_extensions:
                    yield cur_path
