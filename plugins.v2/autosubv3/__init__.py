import os
import tempfile
from datetime import datetime
from typing import Tuple, Dict, Any, List, Optional
from threading import Event, Lock
from lxml import etree
from app.core.config import settings
from app.core.event import eventmanager
from app.schemas.types import EventType
from app.log import logger
from app.plugins import _PluginBase
from .core.compat_methods import AutoSubv3CompatMixin
from .core.config_schema import build_config_form
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
from .monitoring.monitor_service import MonitorService
from .pipeline.asr_service import AsrService
from .pipeline.generation_pipeline import GenerationPipeline
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


class AutoSubv3(AutoSubv3CompatMixin, _PluginBase):
    # 插件名称
    plugin_name = "AI字幕生成(联动版)"
    # 插件描述
    plugin_desc = "自动生成字幕并翻译成中文，支持 faster-whisper 识别、字幕提取、大模型并发翻译，并可联动字幕匹配功能。"
    # 插件图标
    plugin_icon = "autosubtitles.jpeg"
    # 主题色
    plugin_color = "#2C4F7E"
    # 插件版本
    plugin_version = "3.5.57"
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
    _monitor_service = None
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

    def _get_monitor_service(self) -> MonitorService:
        if not self._monitor_service:
            self._monitor_service = MonitorService(
                self,
                settings.RMT_MEDIAEXT,
                logger,
                lambda: PluginManager,
            )
        return self._monitor_service

    # 监听媒体入库事件，每个事件触发一次自动字幕任务
    @eventmanager.register(EventType.TransferComplete)
    def _start_file_monitor(self):
        return self._get_monitor_service().start_file_monitor()

    @staticmethod
    def _subtitlemanualupload_auto_transfer_enabled() -> bool:
        return MonitorService.check_subtitlemanualupload_auto_transfer_enabled(lambda: PluginManager, logger)

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
            self._get_monitor_service().stop_observer()
            logger.info("目录监控已停止")
        self._running = False
        self._event.clear()
        logger.info(f"自动字幕生成服务已停止")
