import copy
import os
import re
import shutil
import tempfile
import time
import traceback
from datetime import timedelta, datetime
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
from threading import Event, Lock
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import iso639
import psutil
import srt
from lxml import etree
from dataclasses import dataclass
from enum import Enum
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from uuid import uuid4
from fastapi import HTTPException, Request
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.event import eventmanager, Event as MPEvent
from app.schemas import TransferInfo
from app.schemas.types import NotificationType, EventType
from app.log import logger
from app.plugins import _PluginBase
from app.utils.system import SystemUtils
from .ffmpeg import Ffmpeg
from .translate.openai_translate import OpenAi

try:
    from app.core.plugin import PluginManager
except Exception:
    PluginManager = None


class UserInterruptException(Exception):
    """用户中断当前任务的异常"""
    pass


class TranslationQualityException(Exception):
    """翻译质量未达标，拒绝输出字幕文件"""
    pass


class TaskSource(Enum):
    MANUAL = "manual"
    EVENT = "event"
    SUBTITLE_MANUAL_UPLOAD = "subtitle_manual_upload"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    IGNORED = "ignored"
    NO_AUDIO = "no_audio"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationMode(Enum):
    FALLBACK = "fallback"
    MONITOR = "monitor"
    MIXED = "mixed"


class TriggerType(Enum):
    MANUAL = "manual"
    SUBTITLE_FALLBACK = "subtitle_fallback"


class SourcePolicy(Enum):
    AUTO = "auto"
    MATCHED_EXTERNAL = "matched_external"
    LOCAL_EXTERNAL = "local_external"
    EMBEDDED = "embedded"
    ASR = "asr"
    REUSE = "reuse"


class ResolvedSource(Enum):
    AUTO = "auto"
    MATCHED_EXTERNAL = "matched_external"
    LOCAL_EXTERNAL = "local_external"
    EMBEDDED = "embedded"
    ASR = "asr"


class OverwritePolicy(Enum):
    SKIP = "skip"
    BACKUP_REPLACE = "backup_replace"
    NEW_VARIANT = "new_variant"


@dataclass
class TaskItem:
    task_id: str
    video_file: str
    source: TaskSource
    add_time: datetime
    force_generate: bool = False
    source_subtitle_path: str = ""
    source_subtitle_lang: str = ""
    trigger: str = TriggerType.MANUAL.value
    source_policy: str = SourcePolicy.AUTO.value
    resolved_source: str = ""
    source_asset_path: str = ""
    source_lang: str = ""
    output_path: str = ""
    output_variant: str = ""
    overwrite_policy: str = OverwritePolicy.SKIP.value
    rerun_of: str = ""
    status: TaskStatus = TaskStatus.PENDING
    complete_time: datetime = None
    error_message: str = ""
    cancel_requested: bool = False


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
    plugin_version = "3.5.52"
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
                self._task_queue = queue.Queue()
                self._consumer_thread = threading.Thread(target=self._consume_tasks, daemon=True)
                self._consumer_thread.start()
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

    def load_tasks(self) -> Dict[str, TaskItem]:
        raw_tasks = self.get_data("tasks") or {}
        tasks = {}
        for task_id, task_dict in raw_tasks.items():
            try:
                task = TaskItem(
                    task_id=task_dict["task_id"],
                    video_file=task_dict["video_file"],
                    source=TaskSource(task_dict["source"]),
                    add_time=datetime.fromisoformat(task_dict["add_time"]),
                    force_generate=bool(task_dict.get("force_generate", False)),
                    source_subtitle_path=task_dict.get("source_subtitle_path", ""),
                    source_subtitle_lang=task_dict.get("source_subtitle_lang", ""),
                    trigger=task_dict.get("trigger") or TriggerType.MANUAL.value,
                    source_policy=task_dict.get("source_policy") or SourcePolicy.AUTO.value,
                    resolved_source=task_dict.get("resolved_source", ""),
                    source_asset_path=task_dict.get("source_asset_path", ""),
                    source_lang=task_dict.get("source_lang", ""),
                    output_path=task_dict.get("output_path", ""),
                    output_variant=task_dict.get("output_variant", ""),
                    overwrite_policy=task_dict.get("overwrite_policy") or OverwritePolicy.SKIP.value,
                    rerun_of=task_dict.get("rerun_of", ""),
                    status=TaskStatus(task_dict["status"]),
                    complete_time=datetime.fromisoformat(task_dict["complete_time"])
                    if task_dict.get("complete_time") else None,
                    error_message=task_dict.get("error_message", ""),
                    cancel_requested=bool(task_dict.get("cancel_requested", False)),
                )
                tasks[task_id] = task
            except Exception as e:
                logger.error(f"恢复任务失败：{e}")
        return tasks

    @staticmethod
    def _serialize_task(task: TaskItem) -> dict:
        return {
            "task_id": task.task_id,
            "video_file": task.video_file,
            "source": task.source.value,
            "add_time": task.add_time.isoformat() if task.add_time else None,
            "force_generate": bool(task.force_generate),
            "source_subtitle_path": task.source_subtitle_path or "",
            "source_subtitle_lang": task.source_subtitle_lang or "",
            "trigger": task.trigger or TriggerType.MANUAL.value,
            "source_policy": task.source_policy or SourcePolicy.AUTO.value,
            "resolved_source": task.resolved_source or "",
            "source_asset_path": task.source_asset_path or "",
            "source_lang": task.source_lang or "",
            "output_path": task.output_path or "",
            "output_variant": task.output_variant or "",
            "overwrite_policy": task.overwrite_policy or OverwritePolicy.SKIP.value,
            "rerun_of": task.rerun_of or "",
            "status": task.status.value,
            "complete_time": task.complete_time.isoformat() if task.complete_time else None,
            "error_message": task.error_message or "",
            "cancel_requested": bool(task.cancel_requested),
        }

    def save_tasks(self):
        tasks_dict = {task_id: self._serialize_task(task) for task_id, task in self._tasks.items()}
        self.save_data("tasks", tasks_dict)

    @staticmethod
    def _ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _enum_value(enum_cls: Any, value: Any, default: str) -> str:
        text = str(value or "").strip()
        try:
            return enum_cls(text).value
        except Exception:
            return default

    @classmethod
    def _normalize_generation_mode(cls, value: Any) -> str:
        mode = cls._enum_value(GenerationMode, value, GenerationMode.MONITOR.value)
        return GenerationMode.MONITOR.value if mode == GenerationMode.MIXED.value else mode

    @classmethod
    def _normalize_trigger(cls, value: Any) -> str:
        return cls._enum_value(TriggerType, value, TriggerType.MANUAL.value)

    @classmethod
    def _normalize_source_policy(cls, value: Any, default: str = SourcePolicy.AUTO.value) -> str:
        return cls._enum_value(SourcePolicy, value, default)

    @classmethod
    def _normalize_overwrite_policy(cls, value: Any, default: str = OverwritePolicy.SKIP.value) -> str:
        return cls._enum_value(OverwritePolicy, value, default)

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
        except Exception as exc:
            logger.warning("[AutoSubv3] 判断字幕匹配入库自动处理状态失败: %s", exc)
            return False
        return enabled and auto_transfer

    def _queue_positions(self) -> Dict[str, int]:
        positions: Dict[str, int] = {}
        if self._current_processing_task:
            positions[self._current_processing_task.task_id] = 0
        if not self._task_queue:
            return positions
        try:
            with self._task_queue.mutex:
                for index, task in enumerate(list(self._task_queue.queue), start=1):
                    positions[task.task_id] = index
        except Exception:
            return positions
        return positions

    def _task_counts(self) -> Dict[str, int]:
        counts = {status.value: 0 for status in TaskStatus}
        for task in (self._tasks or {}).values():
            key = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
            counts[key] = counts.get(key, 0) + 1
        counts["queue_size"] = self._task_queue.qsize() if self._task_queue else 0
        return counts

    def _task_to_api(self, task: TaskItem, queue_positions: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        queue_positions = queue_positions or {}
        status = task.status if isinstance(task.status, TaskStatus) else TaskStatus.FAILED
        source = task.source if isinstance(task.source, TaskSource) else TaskSource.MANUAL
        queue_position = queue_positions.get(task.task_id)
        message = task.error_message or self._status_message(status)
        if status == TaskStatus.PENDING and queue_position:
            message = f"排队第 {queue_position} 位"
        if status == TaskStatus.IN_PROGRESS:
            message = "正在生成字幕"
        if bool(task.cancel_requested):
            message = task.error_message or "已请求取消，当前步骤结束后停止"
        return {
            "task_id": task.task_id,
            "video_file": task.video_file,
            "video_name": os.path.basename(task.video_file or ""),
            "source": source.value,
            "source_label": self._source_label(source),
            "force_generate": bool(task.force_generate),
            "source_subtitle_path": task.source_subtitle_path or "",
            "source_subtitle_name": os.path.basename(task.source_subtitle_path or ""),
            "source_subtitle_lang": task.source_subtitle_lang or "",
            "trigger": task.trigger or TriggerType.MANUAL.value,
            "source_policy": task.source_policy or SourcePolicy.AUTO.value,
            "source_policy_label": self._source_policy_label(task.source_policy or SourcePolicy.AUTO.value),
            "resolved_source": task.resolved_source or "",
            "resolved_source_label": self._resolved_source_label(task.resolved_source),
            "source_asset_path": task.source_asset_path or "",
            "source_asset_name": os.path.basename(task.source_asset_path or ""),
            "source_lang": task.source_lang or task.source_subtitle_lang or "",
            "output_path": task.output_path or "",
            "output_name": os.path.basename(task.output_path or ""),
            "output_variant": task.output_variant or "",
            "overwrite_policy": task.overwrite_policy or OverwritePolicy.SKIP.value,
            "rerun_of": task.rerun_of or "",
            "status": status.value,
            "status_label": self._status_label(status),
            "message": message,
            "queue_position": queue_position,
            "add_time": task.add_time.isoformat(timespec="seconds") if task.add_time else "",
            "complete_time": task.complete_time.isoformat(timespec="seconds") if task.complete_time else "",
            "cancel_requested": bool(task.cancel_requested),
            "active": status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) and not bool(task.cancel_requested),
        }

    def _status_payload(self) -> Dict[str, Any]:
        ready = bool(self._running and self._task_queue)
        monitor_taken_over = self._subtitlemanualupload_auto_transfer_enabled()
        if not self._enabled:
            message = "插件未启用"
        elif monitor_taken_over:
            message = "独立入库监控已由字幕匹配接管，仍可接收手动和联动任务"
        elif not ready:
            message = "插件已启用但任务队列未启动，请检查 Whisper 或 OpenAI 配置"
        else:
            message = "可提交 AI 字幕生成任务"
        latest_time = ""
        for task in (self._tasks or {}).values():
            for candidate in (task.complete_time, task.add_time):
                if candidate and candidate.isoformat() > latest_time:
                    latest_time = candidate.isoformat(timespec="seconds")
        return {
            "available": ready,
            "enabled": bool(self._enabled),
            "running": bool(self._running),
            "queue_ready": bool(self._task_queue),
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "generation_mode": self._generation_mode or GenerationMode.MONITOR.value,
            "generation_mode_label": self._generation_mode_label(self._generation_mode or GenerationMode.MONITOR.value),
            "independent_monitor_enabled": self._generation_mode != GenerationMode.FALLBACK.value and not monitor_taken_over,
            "independent_monitor_blocked_reason": "字幕匹配入库自动处理已启用" if monitor_taken_over else "",
            "message": message,
            "counts": self._task_counts(),
            "updated_at": latest_time,
        }

    def api_status(self) -> Dict[str, Any]:
        return self._ok(self._status_payload())

    def submit_tasks(
        self,
        paths: List[str],
        source: str = TaskSource.MANUAL.value,
        subtitle_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
    ) -> Dict[str, Any]:
        if not self._running or not self._task_queue:
            raise RuntimeError(self._status_payload()["message"])
        try:
            task_source = TaskSource(self._normalize_text(source) or TaskSource.MANUAL.value)
        except Exception:
            task_source = TaskSource.MANUAL
        normalized_trigger = self._normalize_trigger(trigger)
        normalized_policy = self._normalize_source_policy(source_policy)
        if normalized_policy == SourcePolicy.REUSE.value:
            normalized_policy = SourcePolicy.AUTO.value
        normalized_overwrite = self._normalize_overwrite_policy(overwrite_policy)
        added: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        failed: List[Dict[str, str]] = []
        seen_paths = set()
        overrides = subtitle_overrides if isinstance(subtitle_overrides, dict) else {}
        for raw_path in paths or []:
            video_file = self._normalize_text(raw_path)
            if not video_file:
                continue
            if video_file in seen_paths:
                skipped.append({"path": video_file, "reason": "重复路径"})
                continue
            seen_paths.add(video_file)
            if not os.path.isabs(video_file) or not os.path.isfile(video_file):
                failed.append({"path": video_file, "reason": "视频文件不存在或不是绝对路径"})
                continue
            if os.path.splitext(video_file)[-1].lower() not in settings.RMT_MEDIAEXT:
                failed.append({"path": video_file, "reason": "不是 MoviePilot 支持的视频文件"})
                continue
            if self.__is_duplicate_task(video_file):
                skipped.append({"path": video_file, "reason": "任务已在队列中或正在处理"})
                continue
            override = overrides.get(video_file) or overrides.get(os.path.abspath(video_file)) or {}
            if not isinstance(override, dict):
                override = {}
            source_subtitle_path = self._normalize_text(override.get("subtitle_path") or override.get("source_subtitle_path"))
            source_subtitle_lang = self._normalize_text(override.get("lang") or override.get("source_subtitle_lang") or "en")
            item_policy = self._normalize_source_policy(override.get("source_policy"), normalized_policy)
            if source_subtitle_path and item_policy == SourcePolicy.AUTO.value:
                item_policy = SourcePolicy.MATCHED_EXTERNAL.value
            if source_subtitle_path and item_policy not in (SourcePolicy.AUTO.value, SourcePolicy.MATCHED_EXTERNAL.value):
                source_subtitle_path = ""
                source_subtitle_lang = ""
            if item_policy == SourcePolicy.MATCHED_EXTERNAL.value and not source_subtitle_path:
                failed.append({"path": video_file, "reason": "指定字幕匹配外挂来源时必须提供字幕文件"})
                continue
            if source_subtitle_path:
                if not os.path.isabs(source_subtitle_path) or not os.path.isfile(source_subtitle_path):
                    failed.append({"path": video_file, "reason": "指定字幕文件不存在或不是绝对路径"})
                    continue
                if os.path.splitext(source_subtitle_path)[-1].lower() != ".srt":
                    failed.append({"path": video_file, "reason": "指定 AI 翻译字幕必须是 SRT 格式"})
                    continue
            force_generate = task_source == TaskSource.SUBTITLE_MANUAL_UPLOAD
            if self.add_task(
                video_file,
                task_source,
                force_generate=force_generate,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                trigger=normalized_trigger,
                source_policy=item_policy,
                overwrite_policy=self._normalize_overwrite_policy(override.get("overwrite_policy"), normalized_overwrite),
                source_name=self._normalize_text(override.get("source_name")) or os.path.basename(source_subtitle_path),
            ):
                item = {"path": video_file}
                if source_subtitle_path:
                    item["source_subtitle_name"] = os.path.basename(source_subtitle_path)
                    item["source_subtitle_lang"] = source_subtitle_lang
                added.append(item)
            else:
                skipped.append({"path": video_file, "reason": "任务已存在"})

        logger.info(
            "[AutoSubv3] 联动任务提交 source=%s requested=%s added=%s skipped=%s failed=%s",
            task_source.value,
            len(paths or []),
            len(added),
            len(skipped),
            len(failed),
        )
        return {
            "added": added,
            "skipped": skipped,
            "failed": failed,
            "status": self._status_payload(),
        }

    async def api_submit(self, request: Request) -> Dict[str, Any]:
        if not self._running or not self._task_queue:
            raise HTTPException(status_code=409, detail=self._status_payload()["message"])
        body = await request.json()
        paths = body.get("paths") or []
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list):
            paths = []
        subtitle_overrides = body.get("subtitle_overrides") if isinstance(body.get("subtitle_overrides"), dict) else None
        result = self.submit_tasks(
            paths,
            source=self._normalize_text(body.get("source")) or TaskSource.MANUAL.value,
            subtitle_overrides=subtitle_overrides,
            trigger=self._normalize_text(body.get("trigger")) or TriggerType.MANUAL.value,
            source_policy=self._normalize_text(body.get("source_policy")) or SourcePolicy.AUTO.value,
            overwrite_policy=self._normalize_text(body.get("overwrite_policy")) or OverwritePolicy.SKIP.value,
        )
        return self._ok(
            result,
            message=f"已提交 {len(result['added'])} 个 AI 字幕生成任务，跳过 {len(result['skipped'])} 个，失败 {len(result['failed'])} 个",
        )

    def cancel_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        filter_task_ids = {self._normalize_text(item) for item in (task_ids or []) if self._normalize_text(item)}
        filter_paths = {self._normalize_text(item) for item in (paths or []) if self._normalize_text(item)}
        if not filter_task_ids and not filter_paths:
            return {
                "cancelled": [],
                "skipped": [{"reason": "未提供要取消的任务"}],
                "status": self._status_payload(),
            }

        cancelled: List[Dict[str, str]] = []
        skipped: List[Dict[str, str]] = []
        matched_task_ids = set()
        matched_paths = set()

        for task in list((self._tasks or {}).values()):
            match_task = bool(filter_task_ids and task.task_id in filter_task_ids)
            match_path = bool(filter_paths and task.video_file in filter_paths)
            if not (match_task or match_path):
                continue
            matched_task_ids.add(task.task_id)
            matched_paths.add(task.video_file)
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                task.cancel_requested = True
                task.complete_time = datetime.now()
                task.error_message = "用户已取消"
                cancelled.append({"task_id": task.task_id, "path": task.video_file, "status": task.status.value})
                continue
            if task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.CANCELLED
                task.cancel_requested = True
                task.complete_time = datetime.now()
                task.error_message = "已请求取消，当前步骤结束后停止"
                cancelled.append({"task_id": task.task_id, "path": task.video_file, "status": task.status.value})
                continue
            skipped.append({
                "task_id": task.task_id,
                "path": task.video_file,
                "reason": f"任务已是 {self._status_label(task.status)}",
            })

        if self._task_queue:
            try:
                with self._task_queue.mutex:
                    kept_tasks = [task for task in self._task_queue.queue if task.task_id not in matched_task_ids]
                    removed_count = len(self._task_queue.queue) - len(kept_tasks)
                    self._task_queue.queue = type(self._task_queue.queue)(kept_tasks)
                    self._task_queue.unfinished_tasks = max(0, self._task_queue.unfinished_tasks - removed_count)
                    if self._task_queue.unfinished_tasks == 0:
                        self._task_queue.all_tasks_done.notify_all()
            except Exception as exc:
                logger.warning("[AutoSubv3] 从队列移除取消任务失败: %s", exc)

        for item in filter_task_ids:
            if item not in matched_task_ids:
                skipped.append({"task_id": item, "reason": "未找到任务"})
        for item in filter_paths:
            if item not in matched_paths:
                skipped.append({"path": item, "reason": "未找到任务"})

        if cancelled:
            self.save_tasks()
        logger.info("[AutoSubv3] 取消任务 requested=%s cancelled=%s skipped=%s", len(filter_task_ids) + len(filter_paths), len(cancelled), len(skipped))
        return {
            "cancelled": cancelled,
            "skipped": skipped,
            "status": self._status_payload(),
        }

    async def api_cancel(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        paths = body.get("paths") or []
        task_ids = body.get("task_ids") or []
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        result = self.cancel_tasks(task_ids=task_ids if isinstance(task_ids, list) else [], paths=paths if isinstance(paths, list) else [])
        return self._ok(
            result,
            message=f"已取消 {len(result.get('cancelled') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    def delete_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        filter_task_ids = {self._normalize_text(item) for item in (task_ids or []) if self._normalize_text(item)}
        filter_paths = {self._normalize_text(item) for item in (paths or []) if self._normalize_text(item)}
        if not filter_task_ids and not filter_paths:
            return {
                "deleted": [],
                "skipped": [{"reason": "未提供要删除的任务"}],
                "status": self._status_payload(),
            }

        deleted: List[Dict[str, str]] = []
        skipped: List[Dict[str, str]] = []
        matched_task_ids = set()
        matched_paths = set()
        queue_delete_ids = set()

        for task_id, task in list((self._tasks or {}).items()):
            match_task = bool(filter_task_ids and task_id in filter_task_ids)
            match_path = bool(filter_paths and task.video_file in filter_paths)
            if not (match_task or match_path):
                continue
            matched_task_ids.add(task_id)
            matched_paths.add(task.video_file)
            if task.status == TaskStatus.IN_PROGRESS:
                skipped.append({
                    "task_id": task_id,
                    "path": task.video_file,
                    "reason": "任务正在处理，请先取消后再删除",
                })
                continue
            if task.status == TaskStatus.PENDING:
                task.cancel_requested = True
                queue_delete_ids.add(task_id)
            self._tasks.pop(task_id, None)
            deleted.append({"task_id": task_id, "path": task.video_file, "status": task.status.value})

        if queue_delete_ids and self._task_queue:
            try:
                with self._task_queue.mutex:
                    kept_tasks = [task for task in self._task_queue.queue if task.task_id not in queue_delete_ids]
                    removed_count = len(self._task_queue.queue) - len(kept_tasks)
                    self._task_queue.queue = type(self._task_queue.queue)(kept_tasks)
                    self._task_queue.unfinished_tasks = max(0, self._task_queue.unfinished_tasks - removed_count)
                    if self._task_queue.unfinished_tasks == 0:
                        self._task_queue.all_tasks_done.notify_all()
            except Exception as exc:
                logger.warning("[AutoSubv3] 从队列移除删除任务失败: %s", exc)

        for item in filter_task_ids:
            if item not in matched_task_ids:
                skipped.append({"task_id": item, "reason": "未找到任务"})
        for item in filter_paths:
            if item not in matched_paths:
                skipped.append({"path": item, "reason": "未找到任务"})

        if deleted:
            self.save_tasks()
        logger.info("[AutoSubv3] 删除任务 requested=%s deleted=%s skipped=%s", len(filter_task_ids) + len(filter_paths), len(deleted), len(skipped))
        return {
            "deleted": deleted,
            "skipped": skipped,
            "status": self._status_payload(),
        }

    async def api_delete(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        paths = body.get("paths") or []
        task_ids = body.get("task_ids") or []
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        result = self.delete_tasks(task_ids=task_ids if isinstance(task_ids, list) else [], paths=paths if isinstance(paths, list) else [])
        return self._ok(
            result,
            message=f"已删除 {len(result.get('deleted') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    def restart_tasks(
        self,
        task_ids: Optional[List[str]] = None,
        source_policy: str = SourcePolicy.REUSE.value,
        overwrite_policy: str = OverwritePolicy.BACKUP_REPLACE.value,
    ) -> Dict[str, Any]:
        filter_task_ids = {self._normalize_text(item) for item in (task_ids or []) if self._normalize_text(item)}
        if not filter_task_ids:
            return {
                "added": [],
                "skipped": [{"reason": "未提供要重新生成的任务"}],
                "failed": [],
                "status": self._status_payload(),
            }
        added: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        failed: List[Dict[str, str]] = []
        requested_policy = self._normalize_source_policy(source_policy, SourcePolicy.REUSE.value)
        requested_overwrite = self._normalize_overwrite_policy(overwrite_policy, OverwritePolicy.BACKUP_REPLACE.value)
        restartable_statuses = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.IGNORED,
            TaskStatus.NO_AUDIO,
        }

        for task_id in filter_task_ids:
            task = (self._tasks or {}).get(task_id)
            if not task:
                skipped.append({"task_id": task_id, "reason": "未找到任务"})
                continue
            if task.status not in restartable_statuses:
                skipped.append({"task_id": task_id, "path": task.video_file, "reason": f"任务状态 {self._status_label(task.status)} 不能重新生成"})
                continue
            next_source_subtitle = task.source_asset_path or task.source_subtitle_path
            next_policy = task.source_policy if requested_policy == SourcePolicy.REUSE.value else requested_policy
            next_policy = self._normalize_source_policy(next_policy)
            if requested_policy == SourcePolicy.REUSE.value and next_source_subtitle and next_policy == SourcePolicy.AUTO.value:
                next_policy = SourcePolicy.MATCHED_EXTERNAL.value
            if next_policy == SourcePolicy.MATCHED_EXTERNAL.value:
                if not next_source_subtitle or not os.path.isfile(next_source_subtitle):
                    failed.append({
                        "task_id": task_id,
                        "path": task.video_file,
                        "reason": "原字幕匹配外挂源已不存在，请改选自动选择、视频内嵌字幕或音轨 ASR",
                    })
                    continue
            elif next_policy != SourcePolicy.MATCHED_EXTERNAL.value:
                next_source_subtitle = ""
            force_generate = True
            reuse_output_variant = task.output_variant if requested_policy == SourcePolicy.REUSE.value else ""
            ok = self.add_task(
                task.video_file,
                task.source if isinstance(task.source, TaskSource) else TaskSource.MANUAL,
                force_generate=force_generate,
                source_subtitle_path=next_source_subtitle,
                source_subtitle_lang=task.source_subtitle_lang or task.source_lang or "",
                trigger=TriggerType.MANUAL.value,
                source_policy=next_policy,
                overwrite_policy=requested_overwrite,
                rerun_of=task.task_id,
                source_name=os.path.basename(next_source_subtitle or ""),
                output_variant=reuse_output_variant,
            )
            if ok:
                added.append({"task_id": task_id, "path": task.video_file, "source_policy": next_policy})
            else:
                skipped.append({"task_id": task_id, "path": task.video_file, "reason": "任务已在队列中或正在处理"})
        logger.info(
            "[AutoSubv3] 重新生成任务 requested=%s added=%s skipped=%s failed=%s",
            len(filter_task_ids),
            len(added),
            len(skipped),
            len(failed),
        )
        return {
            "added": added,
            "skipped": skipped,
            "failed": failed,
            "status": self._status_payload(),
        }

    async def api_restart(self, request: Request) -> Dict[str, Any]:
        if not self._running or not self._task_queue:
            raise HTTPException(status_code=409, detail=self._status_payload()["message"])
        body = await request.json()
        task_ids = body.get("task_ids") or []
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        result = self.restart_tasks(
            task_ids=task_ids if isinstance(task_ids, list) else [],
            source_policy=self._normalize_text(body.get("source_policy")) or SourcePolicy.REUSE.value,
            overwrite_policy=self._normalize_text(body.get("overwrite_policy")) or OverwritePolicy.BACKUP_REPLACE.value,
        )
        return self._ok(
            result,
            message=f"已重新提交 {len(result.get('added') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    def tasks_payload(self, paths: Optional[List[str]] = None, limit: int = 300) -> Dict[str, Any]:
        filter_paths = {self._normalize_text(item) for item in (paths or []) if self._normalize_text(item)}
        limit = min(max(limit, 1), 1000)
        queue_positions = self._queue_positions()
        tasks = sorted(
            (self._tasks or {}).values(),
            key=lambda item: item.add_time or datetime.min,
            reverse=True,
        )
        if filter_paths:
            tasks = [task for task in tasks if task.video_file in filter_paths]
        return {
            "status": self._status_payload(),
            "tasks": [self._task_to_api(task, queue_positions) for task in tasks[:limit]],
        }

    def api_tasks(self, request: Request) -> Dict[str, Any]:
        raw_paths = request.query_params.get("paths") or ""
        filter_paths = set()
        if raw_paths:
            try:
                parsed = json.loads(raw_paths)
                if isinstance(parsed, list):
                    filter_paths = {self._normalize_text(item) for item in parsed if self._normalize_text(item)}
            except Exception:
                filter_paths = {self._normalize_text(item) for item in raw_paths.split(",") if self._normalize_text(item)}
        try:
            limit = int(request.query_params.get("limit") or 300)
        except Exception:
            limit = 300
        limit = min(max(limit, 1), 1000)
        return self._ok(self.tasks_payload(paths=list(filter_paths), limit=limit))

    def load_skipped_videos(self) -> Dict[str, dict]:
        """加载无声音跳过的视频记录"""
        return self.get_data("skipped_videos") or {}

    def save_skipped_videos(self, skipped: Dict[str, dict]):
        """保存无声音跳过的视频记录"""
        self.save_data("skipped_videos", skipped)

    def add_skipped_video(self, video_file: str):
        """添加无声音跳过的视频记录"""
        skipped = self.load_skipped_videos()
        skipped[video_file] = {
            "skip_time": datetime.now().isoformat(),
            "reason": "no_audio"
        }
        self.save_skipped_videos(skipped)
        logger.info(f"已记录无声音视频：{video_file}")

    def is_video_skipped(self, video_file: str) -> bool:
        """检查视频是否因无声音已被跳过"""
        skipped = self.load_skipped_videos()
        return video_file in skipped

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
        return self.get_data("skip_chinese_videos") or {}

    def save_skip_chinese_videos(self, skipped):
        self.save_data("skip_chinese_videos", skipped)

    def add_skip_chinese_video(self, video_file: str):
        skipped = self.load_skip_chinese_videos()
        skipped[video_file] = {
            "skip_time": datetime.now().isoformat(),
            "reason": "chinese"
        }
        self.save_skip_chinese_videos(skipped)
        logger.info(f"已记录中文视频跳过：{video_file}")

    def is_video_skip_chinese(self, video_file: str) -> bool:
        return video_file in self.load_skip_chinese_videos()

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
    ):
        """
        添加新任务到队列和任务列表中，若任务已存在则跳过。
        :param video_file: 视频文件路径
        :param source: 任务来源（手动/事件）
        """
        task_id = str(uuid4())
        normalized_policy = self._normalize_source_policy(source_policy)
        if normalized_policy == SourcePolicy.REUSE.value:
            normalized_policy = SourcePolicy.AUTO.value
        if source_subtitle_path and normalized_policy == SourcePolicy.AUTO.value:
            normalized_policy = SourcePolicy.MATCHED_EXTERNAL.value
        task = TaskItem(
            task_id=task_id,
            video_file=video_file,
            source=source,
            force_generate=force_generate,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            trigger=self._normalize_trigger(trigger),
            source_policy=normalized_policy,
            overwrite_policy=self._normalize_overwrite_policy(overwrite_policy),
            rerun_of=rerun_of,
            output_variant=self._normalize_text(output_variant),
            add_time=datetime.now()
        )
        if source_subtitle_path:
            try:
                task.source_asset_path = self._copy_source_asset(task.task_id, source_subtitle_path, source_name)
                task.source_subtitle_path = task.source_asset_path
            except Exception as exc:
                logger.error("复制 AI 字幕源资产失败: %s", exc)
                return False

        if self.__is_duplicate_task(task.video_file):
            logger.info(f"任务已存在，跳过添加：{video_file}")
            return False

        self._task_queue.put(task)
        self._tasks[task.task_id] = task
        self.save_tasks()
        logger.info(
            "加入任务队列: %s force_generate=%s source_subtitle=%s",
            video_file,
            force_generate,
            os.path.basename(source_subtitle_path or "") or "-",
        )
        return True

    def clear_tasks(self):
        self._tasks = {task_id: task for task_id, task in self._tasks.items() if task.status in [
            TaskStatus.PENDING, TaskStatus.IN_PROGRESS
        ]}
        self.save_tasks()
        self.save_skipped_videos({})
        logger.info("插件历史任务已清除")

    def __is_duplicate_task(self, video_file: str) -> bool:
        with self._task_queue.mutex:
            for task in self._task_queue.queue:
                if task.video_file == video_file and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) and not task.cancel_requested:
                    return True
            # 还要检查当前正在处理的任务（即可能不在队列中，但正在被消费）
            if (
                self._consumer_thread
                and self._current_processing_task
                and self._current_processing_task.video_file == video_file
                and self._current_processing_task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
                and not self._current_processing_task.cancel_requested
            ):
                return True
        return False

    def _consume_tasks(self):
        while not self._event.is_set():
            try:
                task = self._task_queue.get(timeout=1)
                if task is None:
                    continue
                if task.cancel_requested or task.status == TaskStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    task.complete_time = task.complete_time or datetime.now()
                    task.error_message = task.error_message or "用户已取消"
                    self._tasks[task.task_id] = task
                    self.save_tasks()
                    self._task_queue.task_done()
                    continue
                self._current_processing_task = task
                logger.info(f"开始处理任务 {task.task_id}: {task.video_file}")
                task.status = TaskStatus.IN_PROGRESS
                task.error_message = ""
                self._tasks[task.task_id] = task
                self.save_tasks()
                result_status = self.__process_autosub(
                    task.video_file,
                    source=task.source,
                    force_generate=task.force_generate,
                    source_subtitle_path=task.source_subtitle_path,
                    source_subtitle_lang=task.source_subtitle_lang,
                    source_policy=task.source_policy,
                    overwrite_policy=task.overwrite_policy,
                    output_variant=task.output_variant,
                )
                if task.cancel_requested or task.status == TaskStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    task.complete_time = task.complete_time or datetime.now()
                    task.error_message = task.error_message or "用户已取消"
                else:
                    task.status = result_status
                    task.complete_time = datetime.now()
                    task.error_message = "" if task.status == TaskStatus.COMPLETED else self._status_message(task.status)
                self._tasks[task.task_id] = task
                self.save_tasks()
                self._task_queue.task_done()
                self._current_processing_task = None
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"消费任务时发生异常: {e}")
                logger.error(traceback.format_exc())
                if self._current_processing_task:
                    if self._current_processing_task.cancel_requested or self._current_processing_task.status == TaskStatus.CANCELLED:
                        self._current_processing_task.status = TaskStatus.CANCELLED
                        self._current_processing_task.complete_time = self._current_processing_task.complete_time or datetime.now()
                        self._current_processing_task.error_message = self._current_processing_task.error_message or "用户已取消"
                    else:
                        self._current_processing_task.status = TaskStatus.FAILED
                        self._current_processing_task.complete_time = datetime.now()
                        self._current_processing_task.error_message = str(e)
                    self._tasks[self._current_processing_task.task_id] = self._current_processing_task
                    self.save_tasks()
                self._current_processing_task = None
        logger.info("消费线程已退出")

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
        task = self._current_processing_task
        return bool(task and (task.cancel_requested or task.status == TaskStatus.CANCELLED))

    def _raise_if_task_cancelled(self):
        if self._event.is_set() or self._is_current_task_cancelled():
            raise UserInterruptException("用户中断当前任务")

    @staticmethod
    def __subtitle_lang_suffix(source_lang: Any, output_mode: str = "bilingual") -> str:
        lang = str(source_lang or "").strip().lower().replace("_", "-")
        primary = lang.split("-")[0]
        aliases = {
            "zh": "chi",
            "zho": "chi",
            "chi": "chi",
            "cmn": "chi",
            "cn": "chi",
            "ja": "jp",
            "jpn": "jp",
            "jp": "jp",
            "en": "eng",
            "eng": "eng",
            "ko": "kr",
            "kor": "kr",
            "kr": "kr",
        }
        source_suffix = aliases.get(primary) or aliases.get(lang) or primary[:3] or "und"
        if output_mode == "chinese_only" or source_suffix in {"chi", "und"}:
            return "chi"
        return f"chi&{source_suffix}"

    @classmethod
    def __translated_subtitle_path(cls, file_path: str, source_lang: Any = "", output_mode: str = "bilingual") -> str:
        return f"{file_path}.{cls.__subtitle_lang_suffix(source_lang, output_mode)}.ai.srt"

    @staticmethod
    def _variant_for_source(resolved_source: Any) -> str:
        return {
            ResolvedSource.ASR.value: "aiasr",
            ResolvedSource.EMBEDDED.value: "aiembedded",
            ResolvedSource.MATCHED_EXTERNAL.value: "aimatch",
            ResolvedSource.LOCAL_EXTERNAL.value: "ailocal",
        }.get(str(resolved_source or ""), "ai")

    @classmethod
    def __translated_subtitle_path_with_variant(
        cls,
        file_path: str,
        source_lang: Any = "",
        output_mode: str = "bilingual",
        output_variant: str = "ai",
    ) -> str:
        variant = cls._normalize_text(output_variant) or "ai"
        return f"{file_path}.{cls.__subtitle_lang_suffix(source_lang, output_mode)}.{variant}.srt"

    def _prepare_output_path(
        self,
        file_path: str,
        source_lang: Any,
        output_mode: str,
        resolved_source: str,
        overwrite_policy: str,
        inherited_variant: str = "",
    ) -> Tuple[str, str]:
        policy = self._normalize_overwrite_policy(overwrite_policy)
        variant = self._normalize_text(inherited_variant)
        if not variant and policy == OverwritePolicy.NEW_VARIANT.value:
            variant = self._variant_for_source(resolved_source)
        if not variant:
            variant = "ai"
        return self.__translated_subtitle_path_with_variant(file_path, source_lang, output_mode, variant), variant

    @staticmethod
    def _backup_existing_file(path: str, suffix: str = ".mp-ai-bk") -> str:
        if not path or not os.path.exists(path):
            return ""
        backup_path = f"{path}{suffix}"
        if os.path.exists(backup_path):
            return backup_path
        shutil.copy2(path, backup_path)
        return backup_path

    def _copy_source_asset(self, task_id: str, source_path: str, source_name: str = "") -> str:
        source = self._normalize_text(source_path)
        if not source:
            return ""
        src = Path(source)
        if not src.exists() or src.suffix.lower() != ".srt":
            raise ValueError("指定字幕文件不存在或不是 SRT")
        safe_name = self._normalize_text(source_name) or src.name
        safe_name = re.sub(r"[\\/:*?\"<>|]+", "_", safe_name)
        asset_dir = Path(self.get_data_path()) / "task_assets" / task_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        dest = asset_dir / safe_name
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        return str(dest)

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
    ) -> TaskStatus:
        if not video_file:
            logger.error(f"[Step 0] video_file 为空")
            return TaskStatus.FAILED
        logger.info(f"[Step 1] 检查文件大小：{video_file}")
        # 如果文件大小小于指定大小， 则不处理
        if os.path.getsize(video_file) < self._file_size * 1024 * 1024:
            logger.info(f"[Step 1] 文件小于最小大小 {self._file_size}MB，跳过")
            return TaskStatus.IGNORED
        logger.info(f"[Step 2] 检查是否已标记为无声音跳过")
        # 检查是否已标记为无声音跳过
        if self.is_video_skipped(video_file):
            logger.info(f"[Step 2] 视频已标记为无声音跳过：{video_file}")
            return TaskStatus.NO_AUDIO
        logger.info(f"[Step 3] 开始正式处理")
        start_time = time.time()
        file_path, file_ext = os.path.splitext(video_file)
        file_name = os.path.basename(video_file)
        linked_force_generate = force_generate or self._is_subtitle_manual_upload_source(source)
        if self._skip_chinese and self.is_video_skip_chinese(video_file):
            if linked_force_generate:
                logger.info(f"[Step 3] 联动强制生成：跳过中文视频历史忽略记录")
            else:
                logger.info(f"[Step 3] 视频已标记为中文跳过翻译：{video_file}")
                message = f" 媒体: {file_name}\n 中文视频跳过翻译"
                if self._send_notify:
                    self.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                return TaskStatus.IGNORED

        try:
            self._raise_if_task_cancelled()
            logger.info(f"[Step 4] 判断目的字幕是否已存在：{video_file}")
            # 字幕匹配来源是用户显式触发，允许绕过已有外挂/内嵌字幕检查；监控规则保持原样。
            if not linked_force_generate and self.__target_subtitle_exists(video_file):
                logger.warn(f"[Step 4] 字幕文件已经存在，不进行处理")
                return TaskStatus.IGNORED
            if linked_force_generate:
                logger.info(f"[Step 4] 联动强制生成：跳过已有外挂/内嵌字幕检查 source={source.value if isinstance(source, TaskSource) else source}")
            logger.info(f"[Step 5] 生成字幕")
            # 生成字幕
            ret, lang, gen_sub_path = self.__generate_subtitle(
                video_file,
                file_path,
                self._enable_asr,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                source_policy=source_policy,
            )
            resolved_source = ResolvedSource.AUTO.value
            if isinstance(gen_sub_path, tuple):
                gen_sub_path, resolved_source = gen_sub_path
            if self._current_processing_task:
                self._current_processing_task.resolved_source = resolved_source or ""
                self._current_processing_task.source_lang = lang or ""
            self._raise_if_task_cancelled()
            if not ret:
                # 检查是否是无声音跳过（刚记录的）
                if self.is_video_skipped(video_file):
                    message = f" 媒体: {file_name}\n 无声音跳过"
                    if self._send_notify:
                        self.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                    return TaskStatus.NO_AUDIO
                if lang == "skip_chinese" or self.is_video_skip_chinese(video_file):
                    message = f" 媒体: {file_name}\n 中文视频跳过翻译"
                    if self._send_notify:
                        self.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                    return TaskStatus.IGNORED
                message = f" 媒体: {file_name}\n 生成字幕失败，跳过后续处理"
                if self._send_notify:
                    self.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                return TaskStatus.FAILED

            logger.info(f"[Step 6] 翻译字幕（如果需要）")
            translated_to_zh = False
            if self._translate_zh:
                # 翻译字幕（即使源语言是中文，也过LLM处理病句、繁转简、去空格）
                logger.info(f"开始翻译字幕为中文 ...")
                translated_subtitle, output_variant = self._prepare_output_path(
                    file_path,
                    lang,
                    self._subtitle_output_mode,
                    resolved_source,
                    overwrite_policy,
                    inherited_variant=output_variant,
                )
                normalized_overwrite = self._normalize_overwrite_policy(overwrite_policy)
                if os.path.exists(translated_subtitle):
                    if normalized_overwrite == OverwritePolicy.SKIP.value:
                        logger.info(f"目标字幕已存在，按覆盖策略跳过：{translated_subtitle}")
                        if self._current_processing_task:
                            self._current_processing_task.output_path = translated_subtitle
                            self._current_processing_task.output_variant = output_variant
                        return TaskStatus.IGNORED
                    if normalized_overwrite == OverwritePolicy.BACKUP_REPLACE.value:
                        backup_path = self._backup_existing_file(translated_subtitle)
                        logger.info(f"覆盖前备份 AI 字幕：{backup_path}")
                self.__translate_zh_subtitle(lang, gen_sub_path, translated_subtitle,
                                              output_mode=self._subtitle_output_mode)
                self._raise_if_task_cancelled()
                logger.info(f"翻译字幕完成：{os.path.basename(translated_subtitle)}")
                if self._current_processing_task:
                    self._current_processing_task.output_path = translated_subtitle
                    self._current_processing_task.output_variant = output_variant
                translated_to_zh = True

            end_time = time.time()
            message = f" 媒体: {file_name}\n 处理完成\n 字幕原始语言: {lang}\n "
            if translated_to_zh:
                message += f"字幕翻译语言: zh\n "
            message += f"耗时：{round(end_time - start_time, 2)}秒"
            logger.info(f"自动字幕生成 处理完成：{message}")
            logger.info("")  # 空行分隔
            logger.info("")  # 空行分隔
            if self._send_notify:
                self.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
            return TaskStatus.COMPLETED
        except UserInterruptException:
            logger.info(f"用户中断当前任务：{video_file}")
            logger.info("")  # 空行分隔
            logger.info("")  # 空行分隔
            return TaskStatus.CANCELLED
        except Exception as e:
            logger.error(f"自动字幕生成 处理异常：{e}")
            end_time = time.time()
            message = f" 媒体: {file_name}\n 处理失败\n 耗时：{round(end_time - start_time, 2)}秒"
            if self._send_notify:
                self.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
            # 打印调用栈
            logger.error(traceback.format_exc())
            logger.info("")  # 空行分隔
            logger.info("")  # 空行分隔
            return TaskStatus.FAILED

    def __do_speech_recognition(self, audio_lang, audio_file, video_file=None):
        """
        语音识别, 生成字幕
        :param audio_lang:
        :param audio_file:
        :param video_file: 视频文件路径（用于日志显示）
        :return:
        """
        lang = audio_lang
        video_name = os.path.basename(video_file) if video_file else os.path.basename(audio_file)
        logger.info(f"[Whisper音频提取文本] 开始处理: {video_name}")
        try:
            from faster_whisper import WhisperModel, download_model
            logger.info(f"[Whisper音频提取文本] {video_name} - 加载模型中...")
            # 设置缓存目录, 防止缓存同目录出现 cross-device 错误
            cache_dir = os.path.join(self._faster_whisper_model_path, "cache")
            if not os.path.exists(cache_dir):
                os.mkdir(cache_dir)
            os.environ["HF_HUB_CACHE"] = cache_dir
            if self._huggingface_proxy:
                os.environ["HTTP_PROXY"] = settings.PROXY['http']
                os.environ["HTTPS_PROXY"] = settings.PROXY['https']

            # 模型下载重试机制
            max_retries = 3
            model = None
            for attempt in range(max_retries):
                try:
                    model_path = download_model(self._faster_whisper_model, local_files_only=False, cache_dir=cache_dir)
                    if model_path is None:
                        raise ValueError("模型下载返回空路径")
                    model = WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=psutil.cpu_count(logical=False))
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warn(f"[Whisper音频提取文本] {video_name} - 模型下载失败（第{attempt+1}次），30秒后重试... 错误: {e}")
                        time.sleep(30)
                    else:
                        logger.error(f"[Whisper音频提取文本] {video_name} - 模型下载失败，已重试{max_retries}次。请检查：1) 网络连接 2) 代理配置 3) HuggingFace访问。错误: {e}")
                        return False, None

            try:
                segments, info = model.transcribe(audio_file,
                                                  language=lang if lang != 'auto' else None,
                                                  word_timestamps=True,
                                                  vad_filter=True,
                                                  temperature=0,
                                                  beam_size=5)
                logger.info(f"[Whisper音频提取文本] {video_name} - 检测到语言：{info.language}（置信度 {info.language_probability:.2%}）")

                detected_lang = info.language
                if lang == 'auto':
                    lang = detected_lang

                if self._skip_chinese and self.__is_chinese_lang(lang):
                    logger.info(f"[Whisper音频提取文本] {video_name} - 检测到中文且已开启中文视频不翻译，立即跳过后续字幕提取")
                    return "skip_chinese", lang

                logger.info(f"[Whisper音频提取文本] {video_name} - 开始提取字幕内容，语言：{lang}")
                extract_start_time = time.time()
            except ValueError as e:
                if "max() iterable argument is empty" in str(e):
                    logger.info(f"[Whisper音频提取文本] {video_name} - 音频文件中未检测到任何语言内容，标记为无声音")
                    # 返回 None 表示无声音，不生成空字幕文件
                    return None, None
                else:
                    raise e

            # 先遍历一次获取总时长，用于百分比进度显示
            seg_list = list(segments)
            total_duration = seg_list[-1].end if seg_list else 0
            total_count = len(seg_list)
            subs = []
            idx = 0
            last_pct = 0
            for segment in seg_list:
                if self._event.is_set() or self._is_current_task_cancelled():
                    logger.info(f"[Whisper音频提取文本] {video_name} - 用户中断，停止提取")
                    raise UserInterruptException(f"用户中断当前任务")
                pct = int(segment.end / total_duration * 100) if total_duration > 0 else 0
                if pct >= last_pct + 10:
                    logger.info(f"[Whisper音频提取文本] {video_name} - 提取进度：{pct}%（{segment.end:.1f}s / {total_duration:.1f}s）")
                    last_pct = pct
                if segment.words:
                    for word in segment.words:
                        idx += 1
                        subs.append(srt.Subtitle(index=idx,
                                                 start=timedelta(seconds=word.start),
                                                 end=timedelta(seconds=word.end),
                                                 content=word.word))
                else:
                    idx += 1
                    subs.append(srt.Subtitle(index=idx,
                                             start=timedelta(seconds=segment.start),
                                             end=timedelta(seconds=segment.end),
                                             content=segment.text))
            # 按最大时长和最大字数合并
            subs = self.__merge_srt(subs)

            # 计算提取耗时
            extract_elapsed = time.time() - extract_start_time
            logger.info(f"[Whisper音频提取文本] {video_name} - 提取完成，共处理 {total_count} 段，合并后 {idx} 条字幕，耗时 {extract_elapsed:.1f} 秒")

            # 性能警告（基于提取时长与视频时长的比例）
            if total_duration > 0:
                ratio = extract_elapsed / total_duration
                if ratio >= 0.8:
                    logger.warning(f"[Whisper音频提取文本] {video_name} - 提取耗时过长（{extract_elapsed:.1f}秒 / 视频{total_duration:.1f}秒 = {ratio:.0%}），强烈建议：1) 使用更快模型（tiny/base）2) 启用GPU加速 3) 检查CPU负载")
                elif ratio >= 0.6:
                    logger.warning(f"[Whisper音频提取文本] {video_name} - 提取耗时较长（{extract_elapsed:.1f}秒 / 视频{total_duration:.1f}秒 = {ratio:.0%}），建议：1) 使用更快模型（tiny/base）2) 启用GPU加速")
                elif ratio >= 0.3:
                    logger.info(f"[Whisper音频提取文本] {video_name} - 提取速度可优化（{extract_elapsed:.1f}秒 / 视频{total_duration:.1f}秒 = {ratio:.0%}），可考虑使用更快模型（tiny/base）")

            # 检查是否提取到了有效字幕内容
            if not subs:
                logger.info(f"[Whisper音频提取文本] {video_name} - 提取的字幕内容为空，标记为无声音")
                return None, None

            self._raise_if_task_cancelled()
            self.__save_srt(f"{audio_file}.srt", subs)
            logger.info(f"[Whisper音频提取文本] {video_name} - 音轨转字幕完成")
            return True, lang
        except ImportError:
            logger.warn(f"[Whisper音频提取文本] faster-whisper 未安装，不进行处理")
            return False, None
        except UserInterruptException:
            raise
        except Exception as e:
            traceback.print_exc()
            logger.error(f"[Whisper音频提取文本] {video_name} - 处理异常：{e}")
            return False, None

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
            inner_sub_lang = iso639.to_iso639_1(inner_sub_lang) \
                if (inner_sub_lang and iso639.find(inner_sub_lang) and iso639.to_iso639_1(inner_sub_lang)) else 'und'
            extracted_sub_path = f"{subtitle_file}.{inner_sub_lang}.srt"
            Ffmpeg().extract_subtitle_from_video(video_file, extracted_sub_path, subtitle_index)
            logger.info(f"提取字幕完成：{extracted_sub_path}")
            return True, inner_sub_lang, (extracted_sub_path, ResolvedSource.EMBEDDED.value)
        # 使用asr音轨识别字幕
        if audio_lang != 'auto':
            audio_lang = iso639.to_iso639_1(audio_lang)

        if not enable_asr and policy != SourcePolicy.ASR.value:
            logger.info(f"未开启语音识别，且无已有字幕文件，跳过后续处理")
            return False, None, None
        if policy == SourcePolicy.ASR.value and not self.__check_asr():
            logger.info("已指定音轨 ASR，但 ASR 依赖或 Whisper 配置不可用")
            return False, None, None

        # 清理异常退出的临时文件
        tempdir = tempfile.gettempdir()
        for file in os.listdir(tempdir):
            if file.startswith('autosub-'):
                os.remove(os.path.join(tempdir, file))

        with tempfile.NamedTemporaryFile(prefix='autosub-', suffix='.wav', delete=True) as audio_file:
            # 提取音频
            logger.info(f"[GenSub Step 5a] 提取音频：{audio_file.name}")
            Ffmpeg().extract_wav_from_video(video_file, audio_file.name, audio_index)
            logger.info(f"[GenSub Step 5a] 提取音频完成")
            logger.info(f"[GenSub Step 5b] 开始Whisper识别")

            # 生成字幕
            logger.info(f"[GenSub Step 5] 开始Whisper识别, 语言 {audio_lang}")
            ret, lang = self.__do_speech_recognition(audio_lang, audio_file.name, video_file)
            if ret == "skip_chinese":
                logger.info(f"视频识别为中文且已开启中文视频不翻译，跳过字幕生成：{video_file}")
                self.add_skip_chinese_video(video_file)
                return False, "skip_chinese", None
            elif ret:
                logger.info(f"生成字幕成功，原始语言：{lang}")
                # 复制字幕文件
                self._raise_if_task_cancelled()
                SystemUtils.copy(Path(f"{audio_file.name}.srt"), Path(f"{subtitle_file}.{lang}.srt"))
                logger.info(f"复制字幕文件：{subtitle_file}.{lang}.srt")
                # 删除临时文件
                os.remove(f"{audio_file.name}.srt")
                return ret, lang, (Path(f"{subtitle_file}.{lang}.srt"), ResolvedSource.ASR.value)
            elif ret is None:
                # 无声音，跳过并记录
                logger.info(f"视频无声音，跳过字幕生成：{video_file}")
                self.add_skipped_video(video_file)
                return False, None, None
            else:
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
        """
        加载字幕文件
        :param file_path: 字幕文件路径
        :return:
        """
        with open(file_path, 'r', encoding="utf8") as f:
            srt_text = f.read()
        return list(srt.parse(srt_text))

    @staticmethod
    def __save_srt(file_path, srt_data):
        """
        保存字幕文件
        :param file_path: 字幕文件路径
        :param srt_data: 字幕数据
        :return:
        """
        with open(file_path, 'w', encoding="utf8") as f:
            f.write(srt.compose(srt_data))

    def __merge_srt(self, subtitle_data, max_duration=None, max_chars=None):
        """
        将单词级字幕按句子合并，并强制按最大时长/字数切分
        :param subtitle_data: 单词级字幕列表
        :param max_duration: 每段最大时长（秒），默认用 self._max_segment_duration
        :param max_chars: 每段最大字符数，默认用 self._max_segment_chars
        :return:
        """
        if max_duration is None:
            max_duration = self._max_segment_duration or 8.0
        if max_chars is None:
            max_chars = self._max_segment_chars or 30

        subtitle_data = copy.deepcopy(subtitle_data)
        merged_subtitle = []
        sentence_end = True
        end_tokens = ['.', '!', '?', '。', '！', '？', '。"', '！"', '？"', '."', '!"', '?"']
        for index, item in enumerate(subtitle_data):
            content = item.content.replace('\n', ' ').strip()
            parse = etree.HTML(content)
            if parse is not None:
                content = parse.xpath('string(.)')
            if content == '':
                continue
            item.content = content

            if self.__is_noisy_subtitle(content):
                merged_subtitle.append(item)
                sentence_end = True
                continue

            # 计算当前字幕时长（秒）
            item_duration = (item.end - item.start).total_seconds()

            if not merged_subtitle or sentence_end:
                merged_subtitle.append(item)
                sentence_end = False
            else:
                # 强制切分条件：当前内容 + 新内容超过字数限制，或者累计时长超过最大时长
                existing_len = len(merged_subtitle[-1].content)
                force_split = False
                if existing_len + len(content) > max_chars:
                    force_split = True
                elif item_duration > max_duration:
                    force_split = True
                if force_split:
                    merged_subtitle.append(item)
                    sentence_end = False
                else:
                    merged_subtitle[-1].content = f"{merged_subtitle[-1].content} {content}"
                    merged_subtitle[-1].end = item.end

            if content.endswith(tuple(end_tokens)):
                sentence_end = True
            elif len(merged_subtitle[-1].content) > 80:
                sentence_end = True
            else:
                sentence_end = False

        return merged_subtitle

    @staticmethod
    def __get_video_prefer_audio(video_meta, prefer_lang=None):
        """
        获取视频的首选音轨，如果有多音轨， 优先指定语言音轨，否则获取默认音轨
        :param video_meta
        :return:
        """
        if type(prefer_lang) == str and prefer_lang:
            prefer_lang = [prefer_lang]

        # 获取首选音轨
        audio_lang = None
        audio_index = None
        audio_stream = filter(lambda x: x.get('codec_type') == 'audio', video_meta.get('streams', []))
        for index, stream in enumerate(audio_stream):
            if not audio_index:
                audio_index = index
                audio_lang = stream.get('tags', {}).get('language', 'und')
            # 获取默认音轨
            if stream.get('disposition', {}).get('default'):
                audio_index = index
                audio_lang = stream.get('tags', {}).get('language', 'und')
            # 获取指定语言音轨
            if prefer_lang and stream.get('tags', {}).get('language') in prefer_lang:
                audio_index = index
                audio_lang = stream.get('tags', {}).get('language', 'und')
                break

        # 如果没有音轨， 则不处理
        if audio_index is None:
            logger.warn(f"没有音轨，不进行处理")
            return False, None, None

        logger.info(f"选中音轨信息：{audio_index}, {audio_lang}")
        return True, audio_index, audio_lang

    @staticmethod
    def __get_video_prefer_subtitle(video_meta, prefer_lang=None, strict=False, only_srt=True):
        """
        获取视频的首选字幕。优先级：1.字幕为偏好语言 2.默认字幕 3.第一个字幕
        :param video_meta: 视频元数据
        :param prefer_lang: 字幕偏好语言
        :param strict: 是否严格模式。如果指定了偏好语言，严格模式下必须返回偏好语言的字幕。
        :return: (是否命中字幕，字幕index，字幕语言)
        """
        # from https://wiki.videolan.org/Subtitles_codecs/
        """
        https://trac.ffmpeg.org/wiki/ExtractSubtitles
        ffmpeg -codecs | grep subtitle
         DES... ass                  ASS (Advanced SSA) subtitle (decoders: ssa ass ) (encoders: ssa ass )
         DES... dvb_subtitle         DVB subtitles (decoders: dvbsub ) (encoders: dvbsub )
         DES... dvd_subtitle         DVD subtitles (decoders: dvdsub ) (encoders: dvdsub )
         D.S... hdmv_pgs_subtitle    HDMV Presentation Graphic Stream subtitles (decoders: pgssub )
         ..S... hdmv_text_subtitle   HDMV Text subtitle
         D.S... jacosub              JACOsub subtitle
         D.S... microdvd             MicroDVD subtitle
         D.S... mpl2                 MPL2 subtitle
         D.S... pjs                  PJS (Phoenix Japanimation Society) subtitle
         D.S... realtext             RealText subtitle
         D.S... sami                 SAMI subtitle
         ..S... srt                  SubRip subtitle with embedded timing
         ..S... ssa                  SSA (SubStation Alpha) subtitle
         D.S... stl                  Spruce subtitle format
         DES... subrip               SubRip subtitle (decoders: srt subrip ) (encoders: srt subrip )
         D.S... subviewer            SubViewer subtitle
         D.S... subviewer1           SubViewer v1 subtitle
         D.S... vplayer              VPlayer subtitle
         DES... webvtt               WebVTT subtitle
        """
        image_based_subtitle_codecs = (
            'dvd_subtitle',
            'dvb_subtitle',
            'hdmv_pgs_subtitle',
        )

        if prefer_lang is str and prefer_lang:
            prefer_lang = [prefer_lang]

        # 获取首选字幕
        subtitle_lang = None
        subtitle_index = None
        subtitle_score = 0
        subtitle_stream = filter(lambda x: x.get('codec_type') == 'subtitle', video_meta.get('streams', []))
        for index, stream in enumerate(subtitle_stream):
            # 如果是强制字幕，则跳过
            if stream.get('disposition', {}).get('forced'):
                continue
            # image-based 字幕，跳过
            if only_srt and (
                    'width' in stream
                    or stream.get('codec_name') in image_based_subtitle_codecs
            ):
                continue
            cur_is_default = stream.get('disposition', {}).get('default')
            cur_lang = stream.get('tags', {}).get('language')
            # 计算当前字幕得分：1.字幕为偏好语言*4 2.默认字幕*2 3.第一个字幕*1
            cur_score = 0
            if prefer_lang and cur_lang in prefer_lang:
                cur_score += 4
            if cur_is_default:
                cur_score += 2
            if subtitle_index is None:
                cur_score += 1
                # 第一个字幕初始化为默认字幕
                subtitle_lang, subtitle_index, subtitle_score = cur_lang, index, cur_score
            if cur_score > subtitle_score:
                subtitle_lang, subtitle_index, subtitle_score = cur_lang, index, cur_score

        # 未找到字幕
        if subtitle_index is None:
            logger.debug(f"没有内嵌字幕")
            return False, None, None
        if strict and prefer_lang and subtitle_lang not in prefer_lang:
            logger.warn(f"严格模式,没有偏好语言的字幕")
            return False, None, None
        logger.debug(f"命中内嵌字幕信息：{subtitle_index}, {subtitle_lang}, score:{subtitle_score}")
        return True, subtitle_index, subtitle_lang

    @staticmethod
    def __is_noisy_subtitle(content):
        """
        判断是否为背景音等字幕
        :param content:
        :return:
        """
        noisy_tokens = [('(', ')'), ('[', ']'), ('{', '}'), ('【', '】'), ('♪', '♪'), ('♫', '♫'), ('♪♪', '♪♪')]
        return any(content.startswith(t[0]) and content.endswith(t[1]) for t in noisy_tokens)

    @staticmethod
    def __normalize_subtitle_text_line(value: Any) -> str:
        text = str(value or "")
        text = text.replace("\\N", " ").replace("\\n", " ").replace("\r", "\n")
        text = re.sub(r"\s*\n+\s*", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def __format_translated_content(self, original: Any, translated: Any) -> str:
        trans = self.__normalize_subtitle_text_line(translated)
        origin = self.__normalize_subtitle_text_line(original)
        if self._subtitle_output_mode == 'chinese_only':
            return trans
        if not origin:
            return trans
        if not trans:
            return origin
        return f"{trans}\n{origin}"

    def __get_context(self, all_subs: list, target_indices: List[int], is_batch: bool) -> str:
        """通用上下文获取方法"""
        min_idx = max(0, min(target_indices) - self._context_window)
        max_idx = min(len(all_subs) - 1, max(target_indices) + self._context_window) if is_batch else min(
            target_indices)

        context = []
        for idx in range(min_idx, max_idx + 1):
            status = "[待译]" if idx in target_indices else ""
            content = all_subs[idx].content.replace('\n', ' ').strip()
            context.append(f"{status}{content}")

        return "\n".join(context)

    def __process_items(self, all_subs: list, items: list) -> list:
        """统一处理入口（支持批量和单条）"""
        if self._enable_batch and len(items) > 1:
            return self.__process_batch(all_subs, items)
        return [self.__process_single(all_subs, item) for item in items]

    def __translate_to_zh(self, text: str, context: str = None, max_retries: int = None) -> str:
        self._raise_if_task_cancelled()
        if max_retries is None:
            max_retries = self._max_retries
        return self._openai.translate_to_zh(text, context, max_retries=max_retries)

    def __process_batch(self, all_subs: list, batch: list) -> list:
        """批量处理逻辑"""
        indices = [all_subs.index(item) for item in batch]
        context = self.__get_context(all_subs, indices, is_batch=True) if self._context_window > 0 else None
        batch_text = '\n'.join([item.content for item in batch])

        try:
            ret, result = self.__translate_to_zh(batch_text, context)
            if not ret:
                raise Exception(result)

            translated = [line.strip() for line in result.split('\n') if line.strip()]
            if len(translated) != len(batch):
                raise Exception(f"批次行数不匹配 {len(translated)}/{len(batch)}")

            for item, trans in zip(batch, translated):
                item.content = self.__format_translated_content(item.content, trans)
            self._stats['batch_success'] += 1
            self._stats['translated'] += len(batch)
            return batch
        except UserInterruptException:
            raise
        except Exception as e:
            logger.warning(f"[翻译] 批量翻译失败：{e}，降级逐行翻译")
            self._stats['batch_fail'] += 1
            return [self.__process_single(all_subs, item) for item in batch]

    def __process_single(self, all_subs: List[srt.Subtitle], item: srt.Subtitle) -> srt.Subtitle:
        """单条处理逻辑"""
        idx = all_subs.index(item)
        context = self.__get_context(all_subs, [idx], is_batch=False) if self._context_window > 0 else None
        success, trans = self.__translate_to_zh(item.content, context)

        if success:
            item.content = self.__format_translated_content(item.content, trans)
            self._stats['line_fallback'] += 1
            self._stats['translated'] += 1
            return item
        else:
            if self._subtitle_output_mode == 'chinese_only':
                item.content = f"[翻译失败]"
            else:
                item.content = self.__format_translated_content(item.content, "[翻译失败]")
            self._stats['failed'] += 1
            return item

    def __enforce_translation_quality(self) -> Tuple[int, int, float]:
        total = int(self._stats.get('total') or 0)
        if total <= 0:
            return 0, 0, 0.0
        translated = int(self._stats.get('translated') or self._stats.get('line_fallback') or 0)
        translated = max(0, min(translated, total))
        failed = total - translated
        failure_rate = failed / total
        if failure_rate > self._max_translation_failure_rate:
            message = (
                f"翻译失败率过高：失败 {failed}/{total} 条（{failure_rate:.0%}），"
                f"超过阈值 {self._max_translation_failure_rate:.0%}，已停止输出字幕文件"
            )
            logger.error(f"[翻译] {message}")
            raise TranslationQualityException(message)
        return translated, failed, failure_rate

    def __translate_zh_subtitle(self, source_lang: str, source_subtitle: str, dest_subtitle: str,
                                  output_mode: str = None):
        """
        翻译字幕为中文
        :param source_lang: 源语言
        :param source_subtitle: 源字幕文件路径
        :param dest_subtitle: 目标字幕文件路径
        :param output_mode: 输出模式，'bilingual'=双语（翻译+原文），'chinese_only'=纯中文
        """
        self._stats = {'total': 0, 'batch_success': 0, 'batch_fail': 0, 'line_fallback': 0, 'translated': 0, 'failed': 0}
        subs = self.__load_srt(source_subtitle)
        valid_subs = subs  # ASR阶段已统一做word-level合并，翻译时不再重复合并
        configured_output_mode = output_mode or self._subtitle_output_mode or 'bilingual'
        effective_output_mode = configured_output_mode
        chinese_source = self.__is_chinese_lang(source_lang) or self.__subtitle_content_looks_chinese(valid_subs)
        if not self._skip_chinese and chinese_source:
            logger.info(f"检测字幕内容为中文，强制使用纯中文字幕输出模式")
            effective_output_mode = 'chinese_only'
        previous_output_mode = self._subtitle_output_mode
        self._subtitle_output_mode = effective_output_mode

        try:
            if not valid_subs:
                logger.warning("字幕文件为空或没有有效的字幕条目，跳过翻译")
                # 创建一个空的字幕文件
                self.__save_srt(dest_subtitle, [])
                return

            self._stats['total'] = len(valid_subs)
            translate_start_time = time.time()
            if self._enable_batch:
                processed = self.__translate_parallel(valid_subs)
            else:
                logger.info(f"[翻译] 逐条模式 - 共 {len(valid_subs)} 条（效果更好，速度较慢）")
                processed = [self.__process_single(valid_subs, item) for item in valid_subs]
            self._raise_if_task_cancelled()
            translated_count, failed_count, failure_rate = self.__enforce_translation_quality()
            self.__save_srt(dest_subtitle, processed)

            # 计算翻译耗时和速度
            translate_elapsed = time.time() - translate_start_time
            speed = len(valid_subs) / translate_elapsed if translate_elapsed > 0 else 0

            # 统计报告
            batch_success_count = self._stats['batch_success']
            batch_fail_count = self._stats['batch_fail']
            line_fallback_count = self._stats['line_fallback']

            # 构建日志消息
            log_msg = f"[翻译] 完成 - 总计 {self._stats['total']} 条，耗时 {translate_elapsed:.1f} 秒，速度 {speed:.1f} 条/秒"
            if self._enable_batch:
                log_msg += f"，批量成功 {batch_success_count} 批"
                if batch_fail_count > 0:
                    log_msg += f"，批量失败 {batch_fail_count} 批（降级成功 {line_fallback_count} 条）"
            log_msg += f"，翻译成功 {translated_count} 条，失败 {failed_count} 条，失败率 {failure_rate:.0%}"

            logger.info(log_msg)

            # 批量失败次数过多时警告
            if self._enable_batch and batch_fail_count > 0:
                fail_rate = batch_fail_count / (batch_success_count + batch_fail_count) if (batch_success_count + batch_fail_count) > 0 else 0
                if fail_rate > 0.5:
                    logger.warning(f"[翻译] 批量失败率过高（{fail_rate:.0%}），建议检查：1) LLM API稳定性 2) 降低batch_size 3) 检查prompt格式")
        finally:
            self._subtitle_output_mode = previous_output_mode

    def __translate_parallel(self, valid_subs: list):
        """
        并行翻译字幕，使用 ThreadPoolExecutor 多线程并发处理批次
        批次按原始索引排序合并，保证顺序正确
        """
        total = len(valid_subs)
        batch_size = self._batch_size
        workers = self._parallel_workers

        # 将字幕拆分为批次，每批包含 (全局索引, 字幕对象)
        batches = []
        for i in range(0, total, batch_size):
            batch_items = valid_subs[i:i + batch_size]
            # 建立 全局索引->字幕对象 的映射
            batch_map = {}
            for j, item in enumerate(batch_items):
                batch_map[i + j] = item  # 用全局索引 i+j
            batches.append((i, batch_map))

        logger.info(f"[翻译] 并行模式 - 共 {len(batches)} 批次，每批 {batch_size} 条，并发 {workers} 线程")

        results = {}  # 最终结果：全局idx -> 处理后的字幕对象

        def process_batch(batch_start_idx, batch_map, stats):
            """在子线程中执行：尝试批量翻译，失败则降级单行"""
            self._raise_if_task_cancelled()
            batch_list = list(batch_map.values())
            indices = list(batch_map.keys())

            # 尝试批量翻译（JSON结构化输出，按id校验）
            try:
                batch_texts = [item.content.strip() for item in batch_list]
                ret, translations = self._openai.translate_batch_to_zh(batch_texts)
                self._raise_if_task_cancelled()
                # 严格检查：ret=True 且 translations 不为空 且 所有条目均非 None
                if ret and translations and all(t is not None for t in translations):
                    for item, trans in zip(batch_list, translations):
                        item.content = self.__format_translated_content(item.content, trans)
                    stats["batch_ok"] += 1
                    stats["line_ok"] += len(translations)
                    return {gidx: batch_map[gidx] for gidx in indices}
            except UserInterruptException:
                raise
            except Exception as e:
                logger.debug(f"批次 {batch_start_idx} 批量翻译异常，降级单行：{e}")

            # 降级：逐行翻译（fallback单条，仅在批次失败后执行）
            # 逐条调用翻译（不走批量），失败时最多再重试1次，避免对已失败的条目无限重试
            line_ok_count = 0
            for gidx in indices:
                self._raise_if_task_cancelled()
                item = batch_map[gidx]
                context = self.__get_context(valid_subs, [gidx], is_batch=False) if self._context_window > 0 else None
                # 单条翻译，max_retries=1（只重试1次，避免过度调用）
                success, trans = self.__translate_to_zh(item.content, context, max_retries=1)
                if success:
                    line_ok_count += 1
                    item.content = self.__format_translated_content(item.content, trans)
                else:
                    # 单条翻译失败，不重试（避免浪费调用次数）
                    if self._subtitle_output_mode == 'chinese_only':
                        item.content = "[翻译失败]"
                    else:
                        item.content = self.__format_translated_content(item.content, "[翻译失败]")
            stats["line_ok"] += line_ok_count
            stats["batch_fail"] += 1
            logger.info(f"[翻译] 批次 {batch_start_idx} 降级逐行完成：{line_ok_count}/{len(indices)} 条成功")
            return {gidx: batch_map[gidx] for gidx in indices}

        # 统计计数器（在多线程间安全共享）
        stats = {"batch_ok": 0, "batch_fail": 0, "line_ok": 0}
        last_report_pct = -10  # 上次报告进度百分比，初始-10确保第一条打印

        # 并行执行
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_batch, start_idx, bmap, stats): start_idx
                       for start_idx, bmap in batches}

            for future in as_completed(futures):
                self._raise_if_task_cancelled()
                batch_results = future.result()
                results.update(batch_results)
                done_count = len(results)
                # 每10%打印一次进度
                pct = int(done_count / total * 100) if total > 0 else 0
                if pct >= last_report_pct + 10:
                    logger.info(f"[翻译] 进度: {pct}% ({done_count}/{total}) - 已完成 {done_count} 条")
                    last_report_pct = pct

        # 按索引排序返回
        processed = [results[i] for i in sorted(results.keys())]
        self._stats['batch_success'] = stats["batch_ok"]
        self._stats['batch_fail'] = stats["batch_fail"]
        self._stats['line_fallback'] = stats["line_ok"]
        self._stats['translated'] = stats["line_ok"]
        self._stats['failed'] = max(0, total - stats["line_ok"])
        return processed

    @staticmethod
    def __external_subtitle_exists(video_file, prefer_langs=None, only_srt=False, strict=True):
        """
        外部字幕文件是否存在,支持多种格式及扩展需求。
        :param video_file: 视频文件路径
        :param prefer_langs: 偏好语言列表，支持单个语言字符串或列表
        :param only_srt: 是否只匹配srt格式的字幕
        :param strict: 是否严格匹配偏好语言.当不存在偏好语言字幕但存在其他语言字幕时,是否返回其他字幕
        :return: 元组 (是否存在, 检测到的语言, 文件名)
        """
        video_dir, video_name = os.path.split(video_file)
        video_name, video_ext = os.path.splitext(video_name)

        if prefer_langs and type(prefer_langs) == str:
            prefer_langs = [prefer_langs]

        metadata_flags = ["default", "forced", "foreign", "sdh", "cc", "hi", "机翻", "ai"]
        language_aliases = {
            "chs": "zh",
            "zhs": "zh",
            "zh-cn": "zh",
            "zh-hans": "zh",
            "chi": "zh",
            "zho": "zh",
            "cn": "zh",
            "eng": "en",
            "jp": "ja",
            "jpn": "ja",
            "kr": "ko",
            "kor": "ko",
        }
        if only_srt:
            subtitle_extensions = [".srt"]
        else:
            subtitle_extensions = [".srt", ".sub", ".ass", ".ssa", ".vtt"]

        def parse_props(props):
            """
            解析字幕属性信息，提取语言和元数据标记。
            :param props: 属性字符串
            :return: (语言, 元数据列表)
            """
            parts = props.split(".")
            if len(parts) < 1:
                return None, []

            cur_subtitle_lang = None
            cur_metadata = []
            # 倒序遍历文件名中的标记
            for i in range(len(parts) - 1, -1, -1):
                part = parts[i].strip()
                lower_part = part.lower()
                if lower_part in metadata_flags:
                    cur_metadata.append(lower_part)
                elif cur_subtitle_lang is None:
                    composite_langs = [
                        language_aliases.get(item.strip().lower()) or item.strip().lower()
                        for item in re.split(r"[&+]", lower_part)
                        if item.strip()
                    ]
                    if any(item == "zh" for item in composite_langs):
                        cur_subtitle_lang = "zh"
                        continue
                    normalized = language_aliases.get(lower_part)
                    if normalized:
                        cur_subtitle_lang = normalized
                        continue
                    try:
                        iso639.to_iso639_1(part)
                    except Exception:
                        continue
                    else:
                        cur_subtitle_lang = iso639.to_iso639_1(part)  # 记录最后一个语言标记

            return cur_subtitle_lang, cur_metadata

        # 备选的字幕语言.当strict=False时生效, 用于在未找到偏好语言时返回其他语言
        second_lang = None
        second_file = None
        # 检查字幕文件
        for file in os.listdir(video_dir):
            if not file.startswith(video_name):
                continue

            # 检查扩展名是否在支持范围内
            _, ext = os.path.splitext(file)
            if ext.lower() not in subtitle_extensions:
                continue

            # 提取文件名中的语言和元数据信息
            props_str = file[len(video_name) + 1: -len(ext)] if file.startswith(video_name + ".") else ""
            subtitle_lang, metadata = parse_props(props_str)

            # 如果没有语言标记，跳过
            if not subtitle_lang:
                continue

            # 如果指定了偏好语言
            if prefer_langs:
                if subtitle_lang in prefer_langs:
                    return True, subtitle_lang, file
                else:
                    second_lang = subtitle_lang
                    second_file = file
            else:
                # 未指定偏好语言，找到的第一个字幕即返回
                return True, subtitle_lang, file
        if not strict and second_lang:
            return True, second_lang, second_file
        return False, None, None

    def __target_subtitle_exists(self, video_file):
        """
        目标字幕文件是否存在
        :param video_file:
        :return:
        """
        if self._translate_zh:
            prefer_langs = ['zh', 'chi', 'zh-CN', 'chs', 'zhs', 'zh-Hans', 'zhong', 'simp', 'cn']
            strict = True
        else:
            if self._translate_preference == "english_first":
                prefer_langs = ['en', 'eng']
                strict = False
            elif self._translate_preference == "english_only":
                prefer_langs = ['en', 'eng']
                strict = True
            else:
                prefer_langs = None
                strict = False

        exist, lang, _ = self.__external_subtitle_exists(video_file, prefer_langs, strict=strict)
        if exist:
            return True

        video_meta = Ffmpeg().get_video_metadata(video_file)
        if not video_meta:
            return False
        ret, subtitle_index, subtitle_lang = self.__get_video_prefer_subtitle(video_meta, prefer_lang=prefer_langs,
                                                                              only_srt=False)
        if ret and subtitle_lang in prefer_langs:
            return True

        return False

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        form = [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件", "color": "primary"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "send_notify", "label": "发送通知"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "clear_history", "label": "清理历史记录"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "path_whitelist",
                                            "label": "监控路径（每行一个）",
                                            "rows": 3,
                                            "placeholder": "/mnt/media/movies\n/downloads",
                                            "hint": "目录变化时自动触发字幕生成",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "generation_mode",
                                            "label": "启用独立入库监控",
                                            "true-value": "monitor",
                                            "false-value": "fallback",
                                            "hint": "关闭后仍可接收字幕匹配联动任务和手动任务",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [{"component": "VSwitch", "props": {"model": "process_new_only", "label": "仅处理新增视频", "hint": "关闭则处理路径下所有视频"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [{"component": "VSwitch", "props": {"model": "run_now", "label": "手动执行一次", "color": "secondary"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [{"component": "VSwitch", "props": {"model": "translate_zh", "label": "外语翻译成中文", "hint": "使用 OpenAI 兼容大模型翻译"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 2},
                                "content": [{"component": "VSwitch", "props": {"model": "skip_chinese", "label": "中文视频不翻译", "hint": "Whisper 检测到中文时跳过翻译"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "path_list",
                                            "label": "媒体路径（手动执行时使用）",
                                            "rows": 3,
                                            "placeholder": "绝对路径，每行一个，支持文件和文件夹",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "faster_whisper_model",
                                            "label": "Whisper 模型",
                                            "hint": "模型越大效果越好，耗时越久",
                                            "items": [
                                                {"title": "tiny", "value": "tiny"},
                                                {"title": "base", "value": "base"},
                                                {"title": "small", "value": "small"},
                                                {"title": "medium", "value": "medium"},
                                                {"title": "large-v3", "value": "large-v3"},
                                                {"title": "large-v3-turbo", "value": "deepdml/faster-whisper-large-v3-turbo-ct2"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "subtitle_output_mode",
                                            "label": "字幕输出模式",
                                            "items": [
                                                {"title": "双语字幕（翻译+原文）", "value": "bilingual"},
                                                {"title": "纯中文字幕", "value": "chinese_only"},
                                            ],
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "max_segment_duration", "label": "每段字幕最大时长（秒）", "placeholder": "8"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "max_segment_chars", "label": "每段字幕最大字符数", "placeholder": "50"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "file_size", "label": "文件最小大小（MB）", "placeholder": "默认10"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VSwitch", "props": {"model": "enable_asr", "label": "允许 ASR 生成字幕"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VSwitch", "props": {"model": "auto_detect_language", "label": "自动检测语言", "hint": "由 Whisper 自动识别，而非视频元数据"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "translate_preference",
                                            "label": "字幕源语言偏好",
                                            "items": [
                                                {"title": "仅英文", "value": "english_only"},
                                                {"title": "英文优先", "value": "english_first"},
                                                {"title": "原音优先", "value": "origin_first"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VSwitch", "props": {"model": "proxy", "label": "使用代理下载模型", "hint": "需配置 MP PROXY 环境变量"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "context_window", "label": "上下文窗口大小", "placeholder": "5"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "max_retries", "label": "LLM 请求重试次数", "placeholder": "3"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "enable_batch", "label": "启用批量翻译", "hint": "开启后速度更快"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VTextField", "props": {"model": "batch_size", "label": "每批翻译行数", "placeholder": "20 (建议不超过30)"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VTextField", "props": {"model": "parallel_workers", "label": "并发线程数", "placeholder": "5"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VSwitch", "props": {"model": "openai_proxy", "label": "使用代理服务器"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VSwitch", "props": {"model": "compatible", "label": "兼容模式"}}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "openai_url", "label": "API URL", "placeholder": "https://api.siliconflow.cn"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "openai_key", "label": "API 密钥", "type": "password", "placeholder": "sk-xxx"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "openai_model", "label": "自定义模型", "placeholder": "inclusionAI/Ling-mini-2.0"}}],
                            },
                        ],
                    },
                ],
            }
        ]
        defaults = {
            "enabled": False,
            "clear_history": False,
            "send_notify": False,
            "listen_transfer_event": True,
            "generation_mode": "monitor",
            "process_new_only": True,
            "path_whitelist": "",
            "run_now": False,
            "path_list": "",
            "file_size": "10",
            "translate_preference": "english_first",
            "translate_zh": True,
            "enable_asr": True,
            "auto_detect_language": False,
            "skip_chinese": False,
            "max_segment_duration": 8.0,
            "max_segment_chars": 50,
            "faster_whisper_model": "base",
            "proxy": True,
            "openai_proxy": False,
            "compatible": False,
            "openai_url": "https://api.siliconflow.cn",
            "openai_key": "",
            "openai_model": "inclusionAI/Ling-flash-2.0",
            "context_window": 5,
            "max_retries": 3,
            "enable_merge": False,
            "subtitle_output_mode": "bilingual",
            "enable_batch": True,
            "batch_size": 20,
            "parallel_workers": 10,
        }
        return form, defaults
    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 AI 字幕生成联动状态",
            },
            {
                "path": "/submit",
                "endpoint": self.api_submit,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "提交 AI 字幕生成任务",
            },
            {
                "path": "/tasks",
                "endpoint": self.api_tasks,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取 AI 字幕生成任务状态",
            },
            {
                "path": "/cancel",
                "endpoint": self.api_cancel,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消 AI 字幕生成任务",
            },
            {
                "path": "/delete",
                "endpoint": self.api_delete,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除 AI 字幕任务记录",
            },
            {
                "path": "/restart",
                "endpoint": self.api_restart,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重新生成 AI 字幕任务",
            },
        ]

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_page(self) -> List[dict]:
        # 加载任务并按添加时间倒序排列
        tasks: Dict[str, TaskItem] = self.load_tasks()
        sorted_tasks = sorted(
            tasks.items(),
            key=lambda x: x[1].add_time,
            reverse=True
        )

        status_classes = {
            TaskStatus.PENDING: "text-info",
            TaskStatus.IN_PROGRESS: "text-warning",
            TaskStatus.COMPLETED: "text-success",
            TaskStatus.IGNORED: "text-muted",
            TaskStatus.NO_AUDIO: "text-muted",
            TaskStatus.FAILED: "text-error",
            TaskStatus.CANCELLED: "text-muted"
        }

        rows = []
        for task_id, task in sorted_tasks:
            source_label = {
                TaskSource.MANUAL: "手动添加",
                TaskSource.EVENT: "入库触发",
                TaskSource.SUBTITLE_MANUAL_UPLOAD: "字幕匹配联动",
            }.get(task.source, task.source)

            status_text = {
                TaskStatus.PENDING: "等待中",
                TaskStatus.IN_PROGRESS: "处理中",
                TaskStatus.COMPLETED: "已完成",
                TaskStatus.IGNORED: "已忽略",
                TaskStatus.NO_AUDIO: "无声音跳过",
                TaskStatus.FAILED: "失败",
                TaskStatus.CANCELLED: "已取消"
            }.get(task.status, task.status)

            status_class = status_classes.get(task.status, "")

            add_time_str = task.add_time.strftime("%Y-%m-%d %H:%M:%S")
            complete_time_str = (
                task.complete_time.strftime("%Y-%m-%d %H:%M:%S")
                if task.complete_time else "-"
            )

            rows.append({
                "component": "tr",
                "props": {"class": "text-sm"},
                "content": [
                    {"component": "td", "text": add_time_str},
                    {"component": "td", "text": task.video_file},
                    {"component": "td", "text": source_label},
                    {"component": "td", "text": complete_time_str},
                    {
                        "component": "td",
                        "props": {"class": status_class},
                        "text": status_text
                    },
                ],
            })

        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTable",
                                "props": {"hover": True},
                                "content": [
                                    {
                                        "component": "thead",
                                        "content": [
                                            {
                                                "component": "th",
                                                "props": {"class": "text-start ps-4"},
                                                "text": "添加时间"
                                            },
                                            {
                                                "component": "th",
                                                "props": {"class": "text-start ps-4"},
                                                "text": "视频文件"
                                            },
                                            {
                                                "component": "th",
                                                "props": {"class": "text-start ps-4"},
                                                "text": "来源"
                                            },
                                            {
                                                "component": "th",
                                                "props": {"class": "text-start ps-4"},
                                                "text": "完成时间"
                                            },
                                            {
                                                "component": "th",
                                                "props": {"class": "text-start ps-4"},
                                                "text": "状态"
                                            },
                                        ]
                                    },
                                    {"component": "tbody", "content": rows}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

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
        if self._consumer_thread and self._consumer_thread.is_alive():
            logger.info("正在停止当前任务...")
            # self._consumer_thread.join(timeout=3)
            self._consumer_thread.join()

        if self._task_queue:
            while not self._task_queue.empty():
                self._task_queue.get_nowait()
                self._task_queue.task_done()
            logger.info("任务队列已清空")
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
