import os
import re
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
from threading import Event, Lock
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import iso639
import srt
from lxml import etree
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.event import eventmanager, Event as MPEvent
from app.schemas import TransferInfo
from app.schemas.types import EventType
from app.log import logger
from app.plugins import _PluginBase
from app.utils.system import SystemUtils
from .core.config_schema import (
    build_config_form,
    normalize_generation_mode,
    normalize_overwrite_policy,
    normalize_source_policy,
    normalize_text,
    normalize_trigger,
)
from .core.legacy_views import build_legacy_page
from .core.models import (
    GenerationMode,
    OverwritePolicy,
    ResolvedSource,
    SourcePolicy,
    TaskItem,
    TaskSource,
    TaskStatus,
    TranslationQualityException,
    TriggerType,
    UserInterruptException,
)
from .ffmpeg import Ffmpeg
from .pipeline.asr_service import AsrService
from .pipeline.generation_pipeline import GenerationPipeline
from .pipeline.source_resolver import SourceResolver
from .pipeline.subtitle_output import SubtitleOutputService
from .pipeline.translation_service import TranslationService
from .storage.task_store import TaskStore
from .tasks.api import AutoSubTaskApi
from .tasks.queue_worker import QueueWorker
from .tasks.task_service import TaskService
from .translate.openai_translate import OpenAi

try:
    from app.core.plugin import PluginManager
except Exception:
    PluginManager = None


class FileMonitorHandler(FileSystemEventHandler):
    """
    目录监控响应类，监听新增文件事件
    """

    def __init__(self, mon_path: str, plugin):
        super(FileMonitorHandler, self).__init__()
        self._watch_path = mon_path
        self._plugin = plugin

    def on_created(self, event):
        if not event.is_directory:
            logger.debug(f"检测到新文件：{event.src_path}")
            self._plugin._add_monitor_task(event.src_path)


class AutoSubv3(_PluginBase):
    # 插件名称
    plugin_name = "AI字幕生成(联动版)"
    # 插件描述
    plugin_desc = "自动生成字幕并翻译成中文，支持 faster-whisper 识别、字幕提取、大模型并发翻译，并可联动字幕匹配功能。"
    # 插件图标
    plugin_icon = "autosubtitles.jpeg"
    # 主题色
    plugin_color = "#2C4F7E"
    # 插件版本
    plugin_version = "3.5.54"
    # 插件作者
    plugin_author = "ifsherlock"
    # 作者主页
    author_url = "https://github.com/ifsherlock"
    # 插件配置项ID前缀
    plugin_config_prefix = "autosubv3"
    # 加载顺序
    plugin_order = 14
    # 可使用的用户级别
    auth_level = 2
    # 翻译失败率超过该阈值时不输出字幕文件，避免生成大量 [翻译失败]
    _max_translation_failure_rate = 0.30

    # 私有属性
    _tasks: Dict[str, TaskItem] = None
    _task_queue = None
    _consumer_thread = None
    _current_processing_task = None
    _running = False
    _event = Event()
    _enabled = None
    _clear_history = None
    _send_notify = None
    _translate_preference = None
    _run_now = None
    _path_list = None
    _file_size = None
    _translate_zh = None
    _openai = None
    _enable_batch = None
    _batch_size = None
    _parallel_workers = None
    _context_window = None
    _max_retries = None
    _enable_merge = None
    _enable_asr = None
    _auto_detect_language = None
    _huggingface_proxy = None
    _faster_whisper_model_path = None
    _faster_whisper_model = None
    _max_segment_duration = None
    _max_segment_chars = None
    _process_new_only = None
    _generation_mode = None
    _task_store = None
    _queue_worker = None
    _task_service = None
    _task_api = None
    _subtitle_output = None
    _asr_service = None
    _translation_service = None
    _generation_pipeline = None
    _observer = None
    _monitor_paths = None
    _lock = Lock()

    def init_plugin(self, config=None):
        # 如果没有配置信息， 则不处理
        if not config:
            return
        # 清理插件启动前的残留临时文件
        tempdir = tempfile.gettempdir()
        for file in os.listdir(tempdir):
            if file.startswith('autosub-'):
                try:
                    os.remove(os.path.join(tempdir, file))
                    logger.info(f"清理残留临时文件：{file}")
                except Exception:
                    pass
        self._tasks = self.load_tasks()
        self._enabled = config.get('enabled', False)
        self._clear_history = config.get('clear_history', False)
        self._generation_mode = self._normalize_generation_mode(config.get("generation_mode"))
        # 监控路径配置
        monitor_str = config.get('path_whitelist', '').strip()
        self._monitor_paths = [p.strip() for p in monitor_str.split('\n') if p.strip()] if monitor_str else []
        self._process_new_only = config.get('process_new_only', True)
        self._run_now = config.get('run_now')
        if self._run_now:
            self._path_list = list(set(config.get('path_list').split('\n')))
        self._send_notify = config.get('send_notify', False)
        self._file_size = int(config.get('file_size')) if config.get('file_size') else 10
        # 字幕生成设置
        self._translate_preference = config.get('translate_preference', 'english_first')
        self._enable_asr = config.get('enable_asr', True)
        self._faster_whisper_model = config.get('faster_whisper_model', 'base')
        self._faster_whisper_model_path = config.get('faster_whisper_model_path',
                                                     self.get_data_path() / "faster-whisper-models")
        self._huggingface_proxy = config.get('proxy', True)
        self._auto_detect_language = config.get('auto_detect_language', False)
        self._skip_chinese = config.get('skip_chinese', False)
        self._max_segment_duration = float(config.get('max_segment_duration')) if config.get('max_segment_duration') else 8.0
        self._max_segment_chars = int(config.get('max_segment_chars')) if config.get('max_segment_chars') else 50
        self._translate_zh = config.get('translate_zh', False)
        if self._translate_zh:
            openai_key = config.get('openai_key')
            if not openai_key:
                logger.error(f"翻译依赖于OpenAI，请先维护openai_key")
                return
            openai_url = config.get('openai_url', "https://api.openai.com")
            openai_proxy = config.get('openai_proxy', False)
            openai_model = config.get('openai_model', "inclusionAI/Ling-flash-2.0")
            compatible = config.get('compatible', False)
            self._openai = OpenAi(api_key=openai_key, api_url=openai_url,
                                  proxy=settings.PROXY if openai_proxy else None,
                                  model=openai_model, compatible=bool(compatible))
            self._enable_batch = config.get('enable_batch', True)
            self._batch_size = int(config.get('batch_size')) if config.get('batch_size') else 20
            self._parallel_workers = int(config.get('parallel_workers')) if config.get('parallel_workers') else 10
            self._context_window = int(config.get('context_window')) if config.get('context_window') else 5
            self._max_retries = int(config.get('max_retries')) if config.get('max_retries') else 3
            self._enable_merge = config.get('enable_merge', False)
            self._subtitle_output_mode = config.get('subtitle_output_mode', 'bilingual')

        if self._clear_history:
            config['clear_history'] = False
            self.update_config(config)
            self.clear_tasks()
            self.save_skip_chinese_videos({})
        if self._enabled:
            logger.info("AI生成字幕服务已启动")
            # asr 配置检查
            if self._enable_asr and not self.__check_asr():
                return

            if not self._running:
                worker = self._get_queue_worker()
                self._task_queue, self._consumer_thread = worker.start()
                logger.info("任务队列和消费者线程已启动")
                self._running = True

            # 启动目录监控
            self._start_file_monitor()

            if self._run_now:
                config['run_now'] = False
                self.update_config(config)
                logger.info("立即运行一次")
                self._run_at_once(path_list=self._path_list)
        else:
            self.stop_service()

    def _get_task_store(self) -> TaskStore:
        if not self._task_store:
            self._task_store = TaskStore(self.get_data, self.save_data, logger)
        return self._task_store

    def _set_current_processing_task(self, task: Optional[TaskItem]):
        self._current_processing_task = task

    def _get_queue_worker(self) -> QueueWorker:
        if not self._queue_worker:
            self._queue_worker = QueueWorker(
                self._event,
                lambda: self._tasks,
                self.save_tasks,
                self.__process_autosub,
                self._status_message,
                logger,
                get_current_task=lambda: self._current_processing_task,
                set_current_task=self._set_current_processing_task,
                task_queue=self._task_queue,
                consumer_thread=self._consumer_thread,
            )
        self._queue_worker.sync_legacy_handles(self._task_queue, self._consumer_thread)
        return self._queue_worker

    def _get_task_service(self) -> TaskService:
        if not self._task_service:
            self._task_service = TaskService(self, settings.RMT_MEDIAEXT, logger)
        return self._task_service

    def _get_task_api(self) -> AutoSubTaskApi:
        if not self._task_api:
            self._task_api = AutoSubTaskApi(self)
        return self._task_api

    def _get_subtitle_output(self) -> SubtitleOutputService:
        if not self._subtitle_output:
            self._subtitle_output = SubtitleOutputService(
                self.get_data_path,
                self._normalize_text,
                self._normalize_overwrite_policy,
                self.__get_video_prefer_subtitle,
                lambda: bool(self._translate_zh),
                lambda: self._translate_preference,
                Ffmpeg,
            )
        return self._subtitle_output

    def _get_asr_service(self) -> AsrService:
        if not self._asr_service:
            self._asr_service = AsrService(
                logger,
                self._event,
                self._is_current_task_cancelled,
                self._raise_if_task_cancelled,
                self.__is_chinese_lang,
                lambda: self._faster_whisper_model_path,
                lambda: self._faster_whisper_model,
                lambda: bool(self._huggingface_proxy),
                lambda: settings.PROXY,
                lambda: self._max_segment_duration,
                lambda: self._max_segment_chars,
                etree.HTML,
            )
        return self._asr_service

    def _get_translation_service(self) -> TranslationService:
        if not self._translation_service:
            self._translation_service = TranslationService(
                logger,
                lambda path: self.__load_srt(path),
                lambda path, items: self.__save_srt(path, items),
                self.__is_chinese_lang,
                self.__subtitle_content_looks_chinese,
                self._raise_if_task_cancelled,
                lambda: self._openai,
                lambda: self._stats,
                lambda: self._subtitle_output_mode,
                self._set_subtitle_output_mode,
                lambda: bool(self._skip_chinese),
                lambda: bool(self._enable_batch),
                lambda: self._batch_size,
                lambda: self._parallel_workers,
                lambda: self._context_window,
                lambda: self._max_retries,
                lambda: self._max_translation_failure_rate,
            )
        return self._translation_service

    def _get_generation_pipeline(self) -> GenerationPipeline:
        if not self._generation_pipeline:
            self._generation_pipeline = GenerationPipeline(self, logger)
        return self._generation_pipeline

    def load_tasks(self) -> Dict[str, TaskItem]:
        return self._get_task_store().load_tasks()

    @staticmethod
    def _serialize_task(task: TaskItem) -> dict:
        return TaskStore.serialize_task(task)

    def save_tasks(self):
        self._get_task_store().save_tasks(self._tasks)

    @staticmethod
    def _ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    def _set_subtitle_output_mode(self, value: str):
        self._subtitle_output_mode = value

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return normalize_text(value)

    @staticmethod
    def _enum_value(enum_cls: Any, value: Any, default: str) -> str:
        text = str(value or "").strip()
        try:
            return enum_cls(text).value
        except Exception:
            return default

    @classmethod
    def _normalize_generation_mode(cls, value: Any) -> str:
        return normalize_generation_mode(value)

    @classmethod
    def _normalize_trigger(cls, value: Any) -> str:
        return normalize_trigger(value)

    @classmethod
    def _normalize_source_policy(cls, value: Any, default: str = SourcePolicy.AUTO.value) -> str:
        return normalize_source_policy(value, default)

    @classmethod
    def _normalize_overwrite_policy(cls, value: Any, default: str = OverwritePolicy.SKIP.value) -> str:
        return normalize_overwrite_policy(value, default)

    @staticmethod
    def _source_label(source: TaskSource) -> str:
        return {
            TaskSource.MANUAL: "手动添加",
            TaskSource.EVENT: "入库触发",
            TaskSource.SUBTITLE_MANUAL_UPLOAD: "字幕匹配联动",
        }.get(source, getattr(source, "value", str(source)))

    @staticmethod
    def _source_policy_label(source_policy: Any) -> str:
        return {
            SourcePolicy.AUTO.value: "自动选择",
            SourcePolicy.MATCHED_EXTERNAL.value: "字幕匹配外挂",
            SourcePolicy.LOCAL_EXTERNAL.value: "本地外挂",
            SourcePolicy.EMBEDDED.value: "视频内嵌字幕",
            SourcePolicy.ASR.value: "音轨 ASR",
            SourcePolicy.REUSE.value: "沿用原任务",
        }.get(str(source_policy or ""), str(source_policy or ""))

    @staticmethod
    def _resolved_source_label(resolved_source: Any) -> str:
        return {
            ResolvedSource.AUTO.value: "自动选择",
            ResolvedSource.MATCHED_EXTERNAL.value: "字幕匹配外挂",
            ResolvedSource.LOCAL_EXTERNAL.value: "本地外挂",
            ResolvedSource.EMBEDDED.value: "视频内嵌字幕",
            ResolvedSource.ASR.value: "音轨 ASR",
        }.get(str(resolved_source or ""), str(resolved_source or ""))

    @staticmethod
    def _generation_mode_label(value: Any) -> str:
        return {
            GenerationMode.FALLBACK.value: "独立入库监控关闭",
            GenerationMode.MONITOR.value: "独立入库监控开启",
            GenerationMode.MIXED.value: "独立入库监控开启",
        }.get(str(value or ""), str(value or ""))

    @staticmethod
    def _status_label(status: TaskStatus) -> str:
        return {
            TaskStatus.PENDING: "等待中",
            TaskStatus.IN_PROGRESS: "处理中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.IGNORED: "已忽略",
            TaskStatus.NO_AUDIO: "无声音跳过",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "已取消",
        }.get(status, getattr(status, "value", str(status)))

    @staticmethod
    def _status_message(status: TaskStatus) -> str:
        return {
            TaskStatus.PENDING: "任务已进入等待队列",
            TaskStatus.IN_PROGRESS: "正在生成字幕",
            TaskStatus.COMPLETED: "字幕生成完成",
            TaskStatus.IGNORED: "已按插件规则跳过，通常是字幕已存在或文件不满足处理条件",
            TaskStatus.NO_AUDIO: "视频未检测到有效音轨，已跳过",
            TaskStatus.FAILED: "字幕生成失败，请查看 AI字幕生成(联动版) 日志",
            TaskStatus.CANCELLED: "用户已取消",
        }.get(status, "")

    @staticmethod
    def _source_policy_for_resolved_source(resolved_source: Any) -> str:
        return {
            ResolvedSource.ASR.value: SourcePolicy.ASR.value,
            ResolvedSource.EMBEDDED.value: SourcePolicy.EMBEDDED.value,
            ResolvedSource.LOCAL_EXTERNAL.value: SourcePolicy.LOCAL_EXTERNAL.value,
            ResolvedSource.MATCHED_EXTERNAL.value: SourcePolicy.MATCHED_EXTERNAL.value,
        }.get(str(resolved_source or ""), "")

    @staticmethod
    def _subtitlemanualupload_auto_transfer_enabled() -> bool:
        if PluginManager is None:
            return False
        try:
            running_plugins = PluginManager().running_plugins or {}
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
        # 只有会触发 AI 来源生成的字幕匹配策略才接管 AutoSubv3 独立监控；
        # online_source_only 只负责在线字幕来源，应允许 AutoSubv3 独立监控并行工作。
        ai_takeover_strategies = {"online_then_ai_source", "ai_source_only"}
        return enabled and auto_transfer and ai_link_enabled and strategy in ai_takeover_strategies

    def _queue_positions(self) -> Dict[str, int]:
        return self._get_queue_worker().positions()

    def _task_counts(self) -> Dict[str, int]:
        return self._get_task_service().task_counts()

    def _task_to_api(self, task: TaskItem, queue_positions: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        return self._get_task_service().task_to_api(task, queue_positions)

    def _status_payload(self) -> Dict[str, Any]:
        return self._get_task_service().status_payload()

    def api_status(self) -> Dict[str, Any]:
        return self._get_task_api().api_status()

    def submit_tasks(
        self,
        paths: List[str],
        source: str = TaskSource.MANUAL.value,
        subtitle_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
    ) -> Dict[str, Any]:
        return self._get_task_service().submit_tasks(
            paths,
            source=source,
            subtitle_overrides=subtitle_overrides,
            trigger=trigger,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
        )

    async def api_submit(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_submit(request)

    def cancel_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._get_task_service().cancel_tasks(task_ids=task_ids, paths=paths)

    async def api_cancel(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_cancel(request)

    def delete_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._get_task_service().delete_tasks(task_ids=task_ids, paths=paths)

    async def api_delete(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_delete(request)

    def restart_tasks(
        self,
        task_ids: Optional[List[str]] = None,
        source_policy: str = SourcePolicy.REUSE.value,
        overwrite_policy: str = OverwritePolicy.BACKUP_REPLACE.value,
    ) -> Dict[str, Any]:
        return self._get_task_service().restart_tasks(
            task_ids=task_ids,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
        )

    async def api_restart(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_restart(request)

    def tasks_payload(self, paths: Optional[List[str]] = None, limit: int = 300) -> Dict[str, Any]:
        return self._get_task_service().tasks_payload(paths=paths, limit=limit)

    def api_tasks(self, request) -> Dict[str, Any]:
        return self._get_task_api().api_tasks(request)

    def load_skipped_videos(self) -> Dict[str, dict]:
        """加载无声音跳过的视频记录"""
        return self._get_task_store().load_skipped_videos()

    def save_skipped_videos(self, skipped: Dict[str, dict]):
        """保存无声音跳过的视频记录"""
        self._get_task_store().save_skipped_videos(skipped)

    def add_skipped_video(self, video_file: str):
        """添加无声音跳过的视频记录"""
        self._get_task_store().add_skipped_video(video_file)

    def is_video_skipped(self, video_file: str) -> bool:
        """检查视频是否因无声音已被跳过"""
        return self._get_task_store().is_video_skipped(video_file)

    @staticmethod
    def __is_chinese_lang(lang: str) -> bool:
        if not lang:
            return False
        return lang.lower() in ('zh', 'chi', 'chs', 'cht', 'zh-cn', 'zh-tw', 'zh-hk', 'chinese')

    @staticmethod
    def __subtitle_content_looks_chinese(subs: List[srt.Subtitle]) -> bool:
        text = "\n".join(str(getattr(item, "content", "") or "") for item in subs[:80])
        if not text.strip():
            return False
        chinese_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_chars = len(re.findall(r"[A-Za-z]", text))
        return chinese_chars >= 8 and chinese_chars >= latin_chars

    def load_skip_chinese_videos(self):
        return self._get_task_store().load_skip_chinese_videos()

    def save_skip_chinese_videos(self, skipped):
        self._get_task_store().save_skip_chinese_videos(skipped)

    def add_skip_chinese_video(self, video_file: str):
        self._get_task_store().add_skip_chinese_video(video_file)

    def is_video_skip_chinese(self, video_file: str) -> bool:
        return self._get_task_store().is_video_skip_chinese(video_file)

    def add_task(
        self,
        video_file: str,
        source: TaskSource,
        force_generate: bool = False,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
        rerun_of: str = "",
        source_name: str = "",
        output_variant: str = "",
        reuse_output_path: str = "",
        reuse_source_lang: str = "",
    ):
        return self._get_task_service().add_task(
            video_file,
            source,
            force_generate=force_generate,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            trigger=trigger,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
            rerun_of=rerun_of,
            source_name=source_name,
            output_variant=output_variant,
            reuse_output_path=reuse_output_path,
            reuse_source_lang=reuse_source_lang,
        )

    def clear_tasks(self):
        self._tasks = {task_id: task for task_id, task in self._tasks.items() if task.status in [
            TaskStatus.PENDING, TaskStatus.IN_PROGRESS
        ]}
        self.save_tasks()
        self.save_skipped_videos({})
        logger.info("插件历史任务已清除")

    def __is_duplicate_task(self, video_file: str) -> bool:
        return self._get_task_service().is_duplicate_task(video_file)

    def _consume_tasks(self):
        self._get_queue_worker().consume()

    # 监听媒体入库事件，每个事件触发一次自动字幕任务
    @eventmanager.register(EventType.TransferComplete)
    def _start_file_monitor(self):
        """启动目录监控"""
        # 停止现有 observer
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None

        if not self._monitor_paths:
            logger.info("未配置监控路径，不启动目录监控")
            return
        if self._generation_mode == GenerationMode.FALLBACK.value:
            logger.info("AI 字幕生成当前为后备模式，不启动主动目录监控")
            return
        if self._subtitlemanualupload_auto_transfer_enabled():
            logger.info("字幕匹配入库自动处理已启用，AutoSubv3 不启动独立目录监控")
            return

        # 全量扫描（仅处理新增关闭时）
        if not self._process_new_only:
            logger.info("仅处理新增关闭，开始全量扫描监控路径 ...")
            for mon_path in self._monitor_paths:
                if os.path.isdir(mon_path):
                    for video_file in self._get_library_files(mon_path):
                        self.add_task(
                            video_file,
                            TaskSource.EVENT,
                            trigger=TriggerType.MANUAL.value,
                            source_policy=SourcePolicy.AUTO.value,
                            overwrite_policy=OverwritePolicy.SKIP.value,
                        )
            logger.info("全量扫描完成")

        # 启动 watchdog 监控
        try:
            self._observer = Observer(timeout=10)
            for mon_path in self._monitor_paths:
                if os.path.isdir(mon_path):
                    handler = FileMonitorHandler(mon_path, self)
                    self._observer.schedule(handler, path=mon_path, recursive=True)
                    logger.info(f"启动目录监控：{mon_path}")
            self._observer.daemon = True
            self._observer.start()
            logger.info("目录监控服务已启动")
        except Exception as e:
            logger.error(f"启动目录监控失败：{e}")
            logger.error(traceback.format_exc())

    def _add_monitor_task(self, file_path: str):
        """监控处理器回调，添加新文件任务"""
        if not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[-1].lower()
        if ext not in settings.RMT_MEDIAEXT:
            return
        if self._generation_mode == GenerationMode.FALLBACK.value:
            logger.info("AI 字幕生成当前为后备模式，忽略主动监控新增文件：%s", file_path)
            return
        if self._subtitlemanualupload_auto_transfer_enabled():
            logger.info("字幕匹配入库自动处理已启用，忽略 AutoSubv3 独立监控新增文件：%s", file_path)
            return
        with self._lock:
            self.add_task(
                file_path,
                TaskSource.EVENT,
                trigger=TriggerType.MANUAL.value,
                source_policy=SourcePolicy.AUTO.value,
                overwrite_policy=OverwritePolicy.SKIP.value,
            )

    def _run_at_once(self, path_list: List[str]):
        # 立即执行一次：执行配置的媒体库目录，不受白名单限制
        # 白名单仅在自动入库事件中生效
        for path in path_list:
            if not os.path.exists(path) or not os.path.isabs(path):
                logger.warn(f"目录/文件无效，不进行处理:{path}")
                continue
            if os.path.isdir(path):
                for video_file in self.__get_library_files(path):
                    self.add_task(
                        video_file,
                        TaskSource.MANUAL,
                        trigger=TriggerType.MANUAL.value,
                        source_policy=SourcePolicy.AUTO.value,
                        overwrite_policy=OverwritePolicy.SKIP.value,
                    )
            elif os.path.splitext(path)[-1].lower() in settings.RMT_MEDIAEXT:
                self.add_task(
                    path,
                    TaskSource.MANUAL,
                    trigger=TriggerType.MANUAL.value,
                    source_policy=SourcePolicy.AUTO.value,
                    overwrite_policy=OverwritePolicy.SKIP.value,
                )

    def __check_asr(self):
        if not self._faster_whisper_model_path or not self._faster_whisper_model:
            logger.warn(f"faster-whisper配置信息不完整，不进行处理")
            return False
        if not os.path.exists(self._faster_whisper_model_path):
            logger.info(f"创建faster-whisper模型目录：{self._faster_whisper_model_path}")
            os.mkdir(self._faster_whisper_model_path)
        try:
            from faster_whisper import WhisperModel, download_model
        except ImportError:
            logger.warn(f"faster-whisper 未安装，不进行处理")
            return False
        return True

    @staticmethod
    def _is_subtitle_manual_upload_source(source: Any) -> bool:
        if isinstance(source, TaskSource):
            return source == TaskSource.SUBTITLE_MANUAL_UPLOAD
        return str(source or "").strip() == TaskSource.SUBTITLE_MANUAL_UPLOAD.value

    def _is_current_task_cancelled(self) -> bool:
        return self._get_queue_worker().is_current_task_cancelled()

    def _raise_if_task_cancelled(self):
        self._get_queue_worker().raise_if_task_cancelled()

    @staticmethod
    def __subtitle_lang_suffix(source_lang: Any, output_mode: str = "bilingual") -> str:
        return SubtitleOutputService.subtitle_lang_suffix(source_lang, output_mode)

    @classmethod
    def __translated_subtitle_path(cls, file_path: str, source_lang: Any = "", output_mode: str = "bilingual") -> str:
        return SubtitleOutputService.translated_subtitle_path(file_path, source_lang, output_mode)

    @staticmethod
    def _variant_for_source(resolved_source: Any) -> str:
        return SubtitleOutputService.variant_for_source(resolved_source)

    @classmethod
    def __translated_subtitle_path_with_variant(
        cls,
        file_path: str,
        source_lang: Any = "",
        output_mode: str = "bilingual",
        output_variant: str = "ai",
    ) -> str:
        variant = cls._normalize_text(output_variant) or "ai"
        suffix = SubtitleOutputService.subtitle_lang_suffix(source_lang, output_mode)
        return f"{file_path}.{suffix}.{variant}.srt"

    def _prepare_output_path(
        self,
        file_path: str,
        source_lang: Any,
        output_mode: str,
        resolved_source: str,
        overwrite_policy: str,
        inherited_variant: str = "",
        inherited_output_path: str = "",
    ) -> Tuple[str, str]:
        return self._get_subtitle_output().prepare_output_path(
            file_path,
            source_lang,
            output_mode,
            resolved_source,
            overwrite_policy,
            inherited_variant=inherited_variant,
            inherited_output_path=inherited_output_path,
        )

    @staticmethod
    def _backup_existing_file(path: str, suffix: str = ".mp-ai-bk") -> str:
        return SubtitleOutputService.backup_existing_file(path, suffix)

    def _copy_source_asset(self, task_id: str, source_path: str, source_name: str = "") -> str:
        return self._get_subtitle_output().copy_source_asset(task_id, source_path, source_name)

    def __process_autosub(
        self,
        video_file,
        *,
        source: TaskSource = TaskSource.MANUAL,
        force_generate: bool = False,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
        output_variant: str = "",
        reuse_output_path: str = "",
        reuse_source_lang: str = "",
    ) -> TaskStatus:
        return self._get_generation_pipeline().process_autosub(
            video_file,
            source=source,
            force_generate=force_generate,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
            output_variant=output_variant,
            reuse_output_path=reuse_output_path,
            reuse_source_lang=reuse_source_lang,
        )

    def __do_speech_recognition(self, audio_lang, audio_file, video_file=None):
        return self._get_asr_service().do_speech_recognition(
            audio_lang,
            audio_file,
            video_file,
            skip_chinese=bool(self._skip_chinese),
        )

    def __generate_subtitle(
        self,
        video_file,
        subtitle_file,
        enable_asr=True,
        *,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        source_policy: str = SourcePolicy.AUTO.value,
    ):
        """
        生成字幕
        :param video_file: 视频文件
        :param subtitle_file: 字幕文件, 不包含后缀
        :return: 生成成功返回True，字幕语言,字幕路径，否则返回False, None, None
        """
        policy = self._normalize_source_policy(source_policy)
        if policy == SourcePolicy.REUSE.value:
            policy = SourcePolicy.AUTO.value
        source_path = self._normalize_text(source_subtitle_path)
        if source_path and policy in (SourcePolicy.AUTO.value, SourcePolicy.MATCHED_EXTERNAL.value):
            subtitle_path = Path(source_path)
            if not subtitle_path.exists() or subtitle_path.suffix.lower() != ".srt":
                logger.error(f"[GenSub] 指定字幕不可用或不是 SRT：{source_path}")
                return False, None, None
            lang = self._normalize_text(source_subtitle_lang) or "en"
            logger.info(f"[GenSub] 使用联动指定字幕：{subtitle_path.name} lang={lang}")
            return True, lang, (subtitle_path, ResolvedSource.MATCHED_EXTERNAL.value)

        # 获取文件元数据
        logger.info(f"[GenSub] 获取视频元数据：{video_file}")
        video_meta = Ffmpeg().get_video_metadata(video_file)
        if not video_meta:
            logger.error(f"[GenSub] 获取视频元数据失败，跳过后续处理")
            return False, None, None
        logger.info(f"[GenSub] 获取视频元数据成功")
        # 获取字幕语言偏好
        if self._translate_preference == "english_only":
            prefer_subtitle_langs = ['en', 'eng']
            strict = True
        elif self._translate_preference == "english_first":
            prefer_subtitle_langs = ['en', 'eng']
            strict = False
        else:  # self.translate_preference == "origin_first"
            prefer_subtitle_langs = None
            strict = False

        # 从视频文件音轨获取语言信息
        logger.info(f"[GenSub Step 2] 获取音轨信息")
        ret, audio_index, audio_lang = self.__get_video_prefer_audio(video_meta, prefer_lang=prefer_subtitle_langs)
        if not ret:
            logger.info(f"字幕源偏好：{self._translate_preference} 获取音轨元数据失败")
            return False, None, None

        # 如果开启了自动语言检测，直接设置为auto，跳过metadata的语言信息
        if self._auto_detect_language:
            logger.info("已开启自动语言检测，将使用whisper模型自动识别语言")
            audio_lang = 'auto'
        elif not iso639.find(audio_lang) or not iso639.to_iso639_1(audio_lang):
            logger.info(f"字幕源偏好：{self._translate_preference} 未从音轨元数据中获取到语言信息")
            audio_lang = 'auto'

        # 当字幕源偏好为origin_first时，优先使用音轨语言
        if self._translate_preference == "origin_first":
            prefer_subtitle_langs = ['en', 'eng'] if audio_lang == 'auto' else [audio_lang,
                                                                                iso639.to_iso639_1(audio_lang)]

        def get_sub_path():
            video_dir, _ = os.path.split(video_file)
            return os.path.join(video_dir, exist_sub_name)

        external_sub_exist, external_sub_lang, exist_sub_name = False, None, None
        if policy in (SourcePolicy.AUTO.value, SourcePolicy.LOCAL_EXTERNAL.value):
            logger.info(f"[GenSub Step 3] 检查外挂字幕")
            logger.info(f"使用 {prefer_subtitle_langs} 匹配已有外挂字幕文件 ...")
            external_sub_exist, external_sub_lang, exist_sub_name = self.__external_subtitle_exists(
                video_file,
                prefer_subtitle_langs,
                only_srt=True,
                strict=strict,
            )
            if policy == SourcePolicy.LOCAL_EXTERNAL.value:
                if not external_sub_exist:
                    logger.info("[GenSub] 已指定本地外挂字幕，但未找到可用 SRT")
                    return False, None, None
                logger.info(f"[GenSub] 使用本地外挂字幕：{exist_sub_name} lang={external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)

        inner_sub_exist, subtitle_index, inner_sub_lang = False, None, None
        if policy in (SourcePolicy.AUTO.value, SourcePolicy.EMBEDDED.value):
            logger.info(f"[GenSub Step 4] 检查内嵌字幕")
            logger.info(f"使用 {prefer_subtitle_langs} 匹配内嵌字幕文件 ...")
            inner_sub_exist, subtitle_index, inner_sub_lang, = self.__get_video_prefer_subtitle(
                video_meta,
                prefer_subtitle_langs,
                strict=strict,
            )
            if policy == SourcePolicy.EMBEDDED.value and not inner_sub_exist:
                logger.info("[GenSub] 已指定视频内嵌字幕，但未找到可用字幕轨")
                return False, None, None

        extract_subtitle = False
        if policy == SourcePolicy.ASR.value:
            logger.info("[GenSub] 已指定音轨 ASR，跳过外挂和内嵌字幕")
        elif policy == SourcePolicy.EMBEDDED.value:
            extract_subtitle = True
        elif self._translate_preference == "english_only":
            if external_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 外挂字幕存在，字幕语言 {external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)
            elif inner_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 内嵌字幕存在，字幕语言 {inner_sub_lang}")
                extract_subtitle = True
            else:
                logger.info(f"字幕源偏好：{self._translate_preference} 未匹配到外挂或内嵌字幕,需要使用asr提取")
        else:  # english_first/origin_first
            if external_sub_exist and external_sub_lang in prefer_subtitle_langs:
                logger.info(f"字幕源偏好：{self._translate_preference} 外挂字幕存在，字幕语言 {external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)
            elif inner_sub_exist and inner_sub_lang in prefer_subtitle_langs:
                logger.info(f"字幕源偏好：{self._translate_preference} 内嵌字幕存在，字幕语言 {inner_sub_lang}")
                extract_subtitle = True
            elif external_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 外挂字幕存在，字幕语言 {external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)
            elif inner_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 内嵌字幕存在，字幕语言 {inner_sub_lang}")
                extract_subtitle = True
            else:
                logger.info(f"字幕源偏好：{self._translate_preference} 未匹配到外挂或内嵌字幕,需要使用asr提取")
        # 提取内嵌字幕
        if extract_subtitle:
            return SourceResolver.extract_embedded_subtitle(
                video_file,
                subtitle_file,
                subtitle_index,
                inner_sub_lang,
                Ffmpeg,
                logger,
            )
        # 使用asr音轨识别字幕
        if audio_lang != 'auto':
            audio_lang = iso639.to_iso639_1(audio_lang)

        if not enable_asr and policy != SourcePolicy.ASR.value:
            logger.info(f"未开启语音识别，且无已有字幕文件，跳过后续处理")
            return False, None, None
        if policy == SourcePolicy.ASR.value and not self.__check_asr():
            logger.info("已指定音轨 ASR，但 ASR 依赖或 Whisper 配置不可用")
            return False, None, None

        ret, lang, output = self._get_asr_service().generate_from_audio(
            video_file,
            subtitle_file,
            audio_index,
            audio_lang,
            Ffmpeg,
            SystemUtils.copy,
            skip_chinese=bool(self._skip_chinese),
        )
        if ret == "skip_chinese":
            logger.info(f"视频识别为中文且已开启中文视频不翻译，跳过字幕生成：{video_file}")
            self.add_skip_chinese_video(video_file)
            return False, "skip_chinese", None
        if ret:
            return ret, lang, output
        if ret is None:
            logger.info(f"视频无声音，跳过字幕生成：{video_file}")
            self.add_skipped_video(video_file)
            return False, None, None
        logger.error("生成字幕失败")
        return False, None, None

    @staticmethod
    def __get_library_files(in_path, exclude_path=None):
        """
        获取目录媒体文件列表
        """
        if not os.path.isdir(in_path):
            yield in_path
            return

        for root, dirs, files in os.walk(in_path):
            if exclude_path and any(os.path.abspath(root).startswith(os.path.abspath(path))
                                    for path in exclude_path.split(",")):
                continue

            for file in files:
                cur_path = os.path.join(root, file)
                # 检查后缀
                if os.path.splitext(file)[-1].lower() in settings.RMT_MEDIAEXT:
                    yield cur_path

    @staticmethod
    def __load_srt(file_path):
        return AsrService.load_srt(file_path)

    @staticmethod
    def __save_srt(file_path, srt_data):
        AsrService.save_srt(file_path, srt_data)

    def __merge_srt(self, subtitle_data, max_duration=None, max_chars=None):
        return self._get_asr_service().merge_srt(subtitle_data, max_duration, max_chars)

    @staticmethod
    def __get_video_prefer_audio(video_meta, prefer_lang=None):
        return SourceResolver.get_video_prefer_audio(video_meta, prefer_lang, logger)

    @staticmethod
    def __get_video_prefer_subtitle(video_meta, prefer_lang=None, strict=False, only_srt=True):
        return SourceResolver.get_video_prefer_subtitle(video_meta, prefer_lang, strict, only_srt, logger)

    @staticmethod
    def __is_noisy_subtitle(content):
        return AsrService.is_noisy_subtitle(content)

    @staticmethod
    def __normalize_subtitle_text_line(value: Any) -> str:
        return TranslationService.normalize_subtitle_text_line(value)

    def __format_translated_content(self, original: Any, translated: Any) -> str:
        return self._get_translation_service().format_translated_content(original, translated)

    def __get_context(self, all_subs: list, target_indices: List[int], is_batch: bool) -> str:
        return self._get_translation_service().get_context(all_subs, target_indices, is_batch)

    def __process_items(self, all_subs: list, items: list) -> list:
        return self._get_translation_service().process_items(
            all_subs,
            items,
            process_batch=self.__process_batch,
            process_single=self.__process_single,
        )

    def __translate_to_zh(self, text: str, context: str = None, max_retries: int = None) -> str:
        return self._get_translation_service().translate_to_zh(text, context, max_retries)

    def __process_batch(self, all_subs: list, batch: list) -> list:
        return self._get_translation_service().process_batch(
            all_subs,
            batch,
            process_single=self.__process_single,
            translate_to_zh=self.__translate_to_zh,
        )

    def __process_single(self, all_subs: List[srt.Subtitle], item: srt.Subtitle) -> srt.Subtitle:
        return self._get_translation_service().process_single(
            all_subs,
            item,
            translate_to_zh=self.__translate_to_zh,
        )

    def __enforce_translation_quality(self) -> Tuple[int, int, float]:
        return self._get_translation_service().enforce_translation_quality()

    def __translate_zh_subtitle(self, source_lang: str, source_subtitle: str, dest_subtitle: str,
                                  output_mode: str = None):
        """
        翻译字幕为中文
        :param source_lang: 源语言
        :param source_subtitle: 源字幕文件路径
        :param dest_subtitle: 目标字幕文件路径
        :param output_mode: 输出模式，'bilingual'=双语（翻译+原文），'chinese_only'=纯中文
        """
        self._stats = TranslationService.initial_stats()
        return self._get_translation_service().translate_zh_subtitle(
            source_lang,
            source_subtitle,
            dest_subtitle,
            output_mode,
            translate_parallel=self.__translate_parallel,
            process_single=self.__process_single,
        )

    def __translate_parallel(self, valid_subs: list):
        return self._get_translation_service().translate_parallel(
            valid_subs,
            translate_to_zh=self.__translate_to_zh,
        )

    @staticmethod
    def __external_subtitle_exists(video_file, prefer_langs=None, only_srt=False, strict=True):
        return SubtitleOutputService.external_subtitle_exists(video_file, prefer_langs, only_srt, strict)

    def __target_subtitle_exists(self, video_file):
        return self._get_subtitle_output().target_subtitle_exists(video_file)

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return build_config_form()

    def get_api(self) -> List[Dict[str, Any]]:
        return self._get_task_api().routes()

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_page(self) -> List[dict]:
        return build_legacy_page(self.load_tasks())

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_state(self) -> bool:
        """
        获取插件状态，如果插件正在运行， 则返回True
        """
        return self._running

    def stop_service(self):
        """
        退出插件
        """
        if self._running:
            self._event.set()
        if self._task_queue or self._consumer_thread or self._queue_worker:
            worker = self._get_queue_worker()
            worker.stop()
            self._task_queue = worker.task_queue
            self._consumer_thread = worker.consumer_thread
        if self._tasks is not None:
            for task_id in list(self._tasks.keys()):
                task = self._tasks[task_id]
                if task.status == TaskStatus.PENDING or task.status == TaskStatus.IN_PROGRESS:
                    task.status = TaskStatus.FAILED
                    task.complete_time = datetime.now()
            self.save_tasks()  # 持久化更新后的任务列表
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
                logger.info("目录监控已停止")
            except Exception:
                pass
            self._observer = None
        self._running = False
        self._event.clear()
        logger.info(f"自动字幕生成服务已停止")
