from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.db.models.transferhistory import TransferHistory
from app.log import logger
from app.plugins import _PluginBase

try:
    from app.core.plugin import PluginManager
except Exception:
    PluginManager = None

try:
    from app.chain.tmdb import TmdbChain
except Exception:
    TmdbChain = None

try:
    from app.schemas.types import MediaType
except Exception:
    class _NoopMediaType:
        MOVIE = "movie"
        TV = "tv"

    MediaType = _NoopMediaType

try:
    from app.core.event import eventmanager, Event as MPEvent
    from app.schemas.types import EventType
except Exception:
    class _NoopEventManager:
        @staticmethod
        def register(_event_type):
            def decorator(func):
                return func

            return decorator

    class _NoopEventType:
        TransferComplete = "transfer.complete"

    eventmanager = _NoopEventManager()
    MPEvent = Any
    EventType = _NoopEventType

from .online_subtitle import (
    CaptchaRequiredError,
    OnlineSubtitleSearchService,
    build_search_keywords,
    extract_title_aliases,
)
from .config_schema import (
    AUTO_MULTI_SUBTITLE_MODES,
    AUTO_TRANSFER_SUBTITLE_STRATEGIES,
    AUTO_TRANSFER_SUBTITLE_STRATEGY_ALIASES,
    AVAILABLE_ONLINE_PROVIDER_IDS,
    DEFAULT_ASSRT_API_URL,
    DEFAULT_ENGINE,
    DEFAULT_ONLINE_PROVIDER_IDS,
    DEFAULT_OPENSUBTITLES_API_URL,
    DEFAULT_PROVIDER_ROOTS,
    DEFAULT_RAR_TOOL_PATH,
    MANUAL_ONLINE_PROVIDER_IDS,
    RAR_DEPENDENCY_MODES,
    build_config_form,
    host_from_url,
    normalize_auto_multi_subtitle_mode,
    normalize_auto_transfer_subtitle_strategy,
    normalize_online_site_urls,
    normalize_plugin_config,
    normalize_provider_ids,
    normalize_rar_dependency_mode,
    normalize_root_url,
    normalize_timeline_max_offset,
    normalize_timeline_min_offset,
    normalize_timeline_vad_mode,
)
from .subtitle_language import (
    DEFAULT_AUTO_FORMAT_PRIORITY,
    DEFAULT_AUTO_LANGUAGE_PRIORITY,
    LANGUAGE_SUFFIX_ALIASES,
    auto_language_bucket,
    auto_subtitle_sort_key,
    autosub_lang_from_suffix,
    detect_language_profile,
    is_chinese_language_suffix,
    language_suffix_from_filename,
    normalize_auto_format_priority,
    normalize_auto_language_key,
    normalize_auto_language_priority,
    normalize_language_suffix,
)
from .autosub_bridge import AutoSubBridge, autosub_task_summary as bridge_autosub_task_summary
from .subtitle_history import SubtitleHistory
from .subtitle_writer import (
    SubtitleWriter,
    backup_subtitle_if_needed as writer_backup_subtitle_if_needed,
    build_destination_name as writer_build_destination_name,
    build_write_operations as writer_build_write_operations,
    subtitle_backup_path as writer_subtitle_backup_path,
    timeline_rejection_message as writer_timeline_rejection_message,
    timeline_result_blocks_auto_write as writer_timeline_result_blocks_auto_write,
)
from .timeline_fixer import TimelineFixResult, check_timeline_fixer_dependencies, fix_subtitle_timeline
from .tongwen import convert_subtitle_file_to_simplified
from .target_resolver import (
    LocalMediaCatalog,
    MediaTargetResolver,
    SubtitleInventory,
    entry_filesystem_signature as target_entry_filesystem_signature,
    entry_matches_keyword as target_entry_matches_keyword,
    entry_path_is_valid as target_entry_path_is_valid,
    event_value as target_event_value,
    history_type_text as target_history_type_text,
    is_local_video_path as target_is_local_video_path,
    is_stream_path as target_is_stream_path,
    media_type_text as target_media_type_text,
    number_from_tag as target_number_from_tag,
    poster_url as target_poster_url,
)
from .upload_session import (
    DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ArchiveResourceLimits,
    UploadSessionService,
    archive_suffix_from_content as upload_archive_suffix_from_content,
    extract_7z_subtitle_files as upload_extract_7z_subtitle_files,
    extract_command_archive_subtitle_files as upload_extract_command_archive_subtitle_files,
    extract_rar_subtitle_files as upload_extract_rar_subtitle_files,
    extract_rar_subtitle_files_with_rarfile as upload_extract_rar_subtitle_files_with_rarfile,
    find_rar_tool as upload_find_rar_tool,
    find_sevenzip_tool as upload_find_sevenzip_tool,
    is_executable_file as upload_is_executable_file,
    list_rar_members as upload_list_rar_members,
    normalize_online_download_name as normalize_upload_download_name,
    rar_python_available as upload_rar_python_available,
    rarfile_module as upload_rarfile_module,
    read_rar_member as upload_read_rar_member,
    run_archive_command as upload_run_archive_command,
)
from .online_ai import OnlineAiService
from .auto_transfer import AutoTransferService


class SubtitleManualUpload(_PluginBase):
    plugin_name = "字幕匹配"
    plugin_desc = "手动上传字幕、ZIP 或 RAR，匹配电影/剧集并按媒体文件名落盘，可选智能调轴。"
    plugin_icon = "https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/icons/subtitle-match.png"
    plugin_version = "0.1.70"
    plugin_author = "ifsherlock"
    author_url = "https://github.com/ifsherlock"
    plugin_config_prefix = "subtitlemanualupload_"
    plugin_order = 48
    auth_level = 1

    _enabled = False
    _show_sidebar_nav = True
    _rar_dependency_mode = "none"
    _rar_tool_path = DEFAULT_RAR_TOOL_PATH
    _default_online_provider_ids = list(DEFAULT_ONLINE_PROVIDER_IDS)
    _available_online_provider_ids = list(AVAILABLE_ONLINE_PROVIDER_IDS)
    _manual_online_provider_ids = list(MANUAL_ONLINE_PROVIDER_IDS)
    _online_provider_ids = ["assrt", "opensubtitles"]
    _online_engine = DEFAULT_ENGINE
    _online_use_proxy = False
    _online_site_urls = dict(DEFAULT_PROVIDER_ROOTS)
    _online_rate_records: Dict[str, List[float]] = {}
    _online_rate_limit_per_minute = 5
    _auto_transfer_queue_debounce_seconds = 3
    _auto_transfer_queue_history_limit = 200
    _transfer_auto_dedupe_seconds = 300
    _transfer_auto_recent: Dict[str, float] = {}
    _transfer_auto_lock = threading.Lock()
    _auto_transfer_tasks: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _auto_transfer_worker: Optional[threading.Thread] = None
    _auto_transfer_stopping = False
    _auto_season_package_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _embedded_subtitle_probe_cache: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    _embedded_subtitle_probe_cache_max_size = 500
    _embedded_subtitle_text_codecs = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text"}
    _embedded_subtitle_image_codecs = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub", "dvb_teletext", "eia_608"}
    _assrt_api_key = ""
    _assrt_api_url = DEFAULT_ASSRT_API_URL
    _opensubtitles_api_key = ""
    _opensubtitles_api_url = DEFAULT_OPENSUBTITLES_API_URL
    _opensubtitles_username = ""
    _opensubtitles_password = ""
    _ai_link_enabled = True
    _traditional_to_simplified = False
    _auto_search_on_transfer = False
    _auto_skip_chinese_media_on_transfer = True
    _auto_transfer_subtitle_strategy = "online_then_ai_source"
    _auto_search_min_score = 20
    _trust_transfer_history_paths = False
    _timeline_max_offset_seconds = 120
    _timeline_min_offset_seconds = 0.2
    _timeline_vad_mode = "webrtc"
    _timeline_allow_risky_offset = False
    _cache_ttl_seconds = 1800
    _cache_max_entries = 5000
    _entry_map_max_size = 2000
    _media_index_cache_max_keys = 20
    _match_history_cache_ttl_seconds = 86400
    _timeline_task_ttl_seconds = 86400
    _rar_dependency_status: Dict[str, Any] = {
        "mode": "none",
        "state": "idle",
        "message": "",
        "checked_at": "",
    }
    _entry_map: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _media_index_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _cache_refreshing = False
    _cache_refresh_started_at = ""
    _cache_refresh_completed_at = ""
    _cache_refresh_error = ""
    _local_entries_cache: Dict[str, Any] = {
        "loaded_at": None,
        "entries": [],
        "media_count": 0,
        "persisted": False,
    }
    _match_history_cache: Dict[str, Any] = {
        "loaded_at": None,
        "signature": "",
        "items": [],
        "entry_count": 0,
        "persisted": False,
    }
    _timeline_tasks: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _tmdb_detail_cache: Dict[str, Dict[str, Any]] = {}

    _subtitle_exts = {".ass", ".srt", ".ssa", ".sbv", ".sub", ".vtt", ".webvtt"}
    _archive_exts = {".zip", ".rar", ".7z"}
    _rar_exts = {".rar"}
    _sevenzip_exts = {".7z"}
    _rar_tools = ("unrar", "bsdtar", "7z", "7za", "7zz")
    _sevenzip_tools = ("7z", "7za", "7zz", "bsdtar")
    _rar_python_package = "rarfile"
    _rar_dependency_modes = set(RAR_DEPENDENCY_MODES)
    _auto_transfer_subtitle_strategies = set(AUTO_TRANSFER_SUBTITLE_STRATEGIES)
    _auto_multi_subtitle_modes = set(AUTO_MULTI_SUBTITLE_MODES)
    _default_auto_language_priority = list(DEFAULT_AUTO_LANGUAGE_PRIORITY)
    _default_auto_format_priority = list(DEFAULT_AUTO_FORMAT_PRIORITY)
    _auto_transfer_subtitle_strategy_aliases = dict(AUTO_TRANSFER_SUBTITLE_STRATEGY_ALIASES)
    _chinese_media_language_codes = {"zh", "cn", "zho", "cmn", "yue"}
    _chinese_media_country_codes = {"cn", "hk", "tw", "sg"}
    _chinese_media_region_names = {
        "china",
        "hong kong",
        "taiwan",
        "singapore",
        "中国",
        "大陆",
        "香港",
        "台湾",
        "新加坡",
    }
    _chinese_media_category_pattern = re.compile(r"华语|国产|大陆|内地|香港|台湾|港剧|台剧|港片|台片|港台|中国")
    _stream_exts = {".strm"}
    _default_session_hours = 24
    _language_suffix_aliases = dict(LANGUAGE_SUFFIX_ALIASES)

    def init_plugin(self, config: dict = None):
        normalized_config = normalize_plugin_config(
            config,
            subtitle_exts=self._subtitle_exts,
            default_auto_language_priority=self._default_auto_language_priority,
            default_auto_format_priority=self._default_auto_format_priority,
            available_provider_ids=self._available_online_provider_ids,
            default_provider_ids=self._default_online_provider_ids,
        )
        self._enabled = normalized_config["enabled"]
        self._show_sidebar_nav = normalized_config["show_sidebar_nav"]
        self._rar_dependency_mode = normalized_config["rar_dependency_mode"]
        self._rar_tool_path = normalized_config["rar_tool_path"]
        self._online_provider_ids = normalized_config["online_providers"]
        self._online_engine = normalized_config["online_engine"]
        self._online_use_proxy = normalized_config["online_use_proxy"]
        self._online_site_urls = normalized_config["online_site_urls"]
        self._assrt_api_key = normalized_config["assrt_api_key"]
        self._assrt_api_url = normalized_config["assrt_api_url"]
        self._opensubtitles_api_key = normalized_config["opensubtitles_api_key"]
        self._opensubtitles_api_url = normalized_config["opensubtitles_api_url"]
        self._opensubtitles_username = normalized_config["opensubtitles_username"]
        if (config or {}).get("opensubtitles_username") and "@" in self._normalize_text((config or {}).get("opensubtitles_username")):
            logger.warning("[SubtitleManualUpload] OpenSubtitles 用户名疑似邮箱，已忽略下载认证用户名")
        self._opensubtitles_password = normalized_config["opensubtitles_password"]
        self._ai_link_enabled = normalized_config["ai_link_enabled"]
        self._traditional_to_simplified = normalized_config["traditional_to_simplified"]
        self._auto_search_on_transfer = normalized_config["auto_search_on_transfer"]
        self._auto_skip_chinese_media_on_transfer = normalized_config["auto_skip_chinese_media_on_transfer"]
        self._auto_transfer_subtitle_strategy = normalized_config["auto_transfer_subtitle_strategy"]
        self._trust_transfer_history_paths = normalized_config["trust_transfer_history_paths"]
        self._auto_multi_subtitle_mode = normalized_config["auto_multi_subtitle_mode"]
        self._auto_subtitle_language_priority = normalized_config["auto_subtitle_language_priority"]
        self._auto_subtitle_format_priority = normalized_config["auto_subtitle_format_priority"]
        self._auto_ass_to_srt_for_ai = normalized_config["auto_ass_to_srt_for_ai"]
        self._timeline_max_offset_seconds = normalized_config["timeline_max_offset_seconds"]
        self._timeline_min_offset_seconds = normalized_config["timeline_min_offset_seconds"]
        self._timeline_vad_mode = normalized_config["timeline_vad_mode"]
        self._timeline_allow_risky_offset = normalized_config["timeline_allow_risky_offset"]
        type(self)._rar_dependency_mode = self._rar_dependency_mode
        type(self)._rar_tool_path = self._rar_tool_path
        type(self)._traditional_to_simplified = self._traditional_to_simplified
        type(self)._auto_search_on_transfer = self._auto_search_on_transfer
        type(self)._auto_skip_chinese_media_on_transfer = self._auto_skip_chinese_media_on_transfer
        type(self)._auto_transfer_subtitle_strategy = self._auto_transfer_subtitle_strategy
        type(self)._trust_transfer_history_paths = self._trust_transfer_history_paths
        type(self)._auto_multi_subtitle_mode = self._auto_multi_subtitle_mode
        type(self)._auto_subtitle_language_priority = self._auto_subtitle_language_priority
        type(self)._auto_subtitle_format_priority = self._auto_subtitle_format_priority
        type(self)._auto_ass_to_srt_for_ai = self._auto_ass_to_srt_for_ai
        type(self)._timeline_max_offset_seconds = self._timeline_max_offset_seconds
        type(self)._timeline_min_offset_seconds = self._timeline_min_offset_seconds
        type(self)._timeline_vad_mode = self._timeline_vad_mode
        type(self)._timeline_allow_risky_offset = self._timeline_allow_risky_offset
        self._entry_map = OrderedDict()
        self._media_index_cache = OrderedDict()
        self._match_history_cache = {"loaded_at": None, "signature": "", "items": [], "entry_count": 0, "persisted": False}
        self._timeline_tasks = OrderedDict()
        self._transfer_auto_recent = {}
        self._transfer_auto_lock = threading.Lock()
        self._auto_transfer_tasks = OrderedDict()
        self._auto_transfer_worker = None
        self._auto_transfer_stopping = False
        self._auto_season_package_cache = OrderedDict()
        self._cache_refreshing = False
        self._cache_refresh_started_at = ""
        self._cache_refresh_completed_at = ""
        self._cache_refresh_error = ""
        self._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
        self._restore_persisted_local_cache()
        self._restore_persisted_match_history_cache()
        self._save_config()
        self._prepare_rar_dependency()
        self._cleanup_old_sessions()

    def get_state(self) -> bool:
        return bool(self._enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取字幕匹配插件状态",
            },
            {
                "path": "/refresh_index",
                "endpoint": self.api_refresh_index,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "兼容旧版刷新索引入口",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "搜索 MoviePilot 本地资源候选",
            },
            {
                "path": "/targets",
                "endpoint": self.api_targets,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取选中媒体的本地文件目标",
            },
            {
                "path": "/match_history",
                "endpoint": self.api_match_history,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取字幕匹配历史",
            },
            {
                "path": "/timeline_tasks",
                "endpoint": self.api_timeline_tasks,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "查询智能调轴任务状态",
            },
            {
                "path": "/timeline_fix_existing",
                "endpoint": self.api_timeline_fix_existing,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "对匹配历史中的外挂字幕执行智能调轴",
            },
            {
                "path": "/auto_transfer_queue",
                "endpoint": self.api_auto_transfer_queue,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询入库自动字幕处理队列",
            },
            {
                "path": "/prepare_upload",
                "endpoint": self.api_prepare_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "上传字幕并生成匹配预览",
            },
            {
                "path": "/apply_upload",
                "endpoint": self.api_apply_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "应用字幕匹配结果并写入目标目录",
            },
            {
                "path": "/clear_subtitles",
                "endpoint": self.api_clear_subtitles,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空选中目标视频的外挂字幕",
            },
            {
                "path": "/delete_subtitle",
                "endpoint": self.api_delete_subtitle,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除单个已匹配外挂字幕",
            },
            {
                "path": "/restore_subtitle_backup",
                "endpoint": self.api_restore_subtitle_backup,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "恢复智能调轴前的字幕备份",
            },
            {
                "path": "/ai_submit",
                "endpoint": self.api_ai_submit,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "提交 AI 字幕生成任务",
            },
            {
                "path": "/ai_tasks",
                "endpoint": self.api_ai_tasks,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "查询当前资源的 AI 字幕生成任务状态",
            },
            {
                "path": "/ai_cancel",
                "endpoint": self.api_ai_cancel,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消 AI 字幕生成任务",
            },
            {
                "path": "/ai_restart",
                "endpoint": self.api_ai_restart,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重新生成 AI 字幕任务",
            },
            {
                "path": "/online_status",
                "endpoint": self.api_online_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取在线字幕源状态",
            },
            {
                "path": "/online_manual_links",
                "endpoint": self.api_online_manual_links,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "生成在线字幕站手动搜索链接",
            },
            {
                "path": "/online_search",
                "endpoint": self.api_online_search,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "搜索在线字幕",
            },
            {
                "path": "/online_search_provider",
                "endpoint": self.api_online_search_provider,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "搜索单个在线字幕源",
            },
            {
                "path": "/online_ai_submit",
                "endpoint": self.api_online_ai_submit,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "提交在线外语字幕到 AI 翻译状态队列",
            },
            {
                "path": "/online_download_preview",
                "endpoint": self.api_online_download_preview,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "下载在线字幕并生成匹配预览",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return build_config_form(
            default_auto_language_priority=self._default_auto_language_priority,
            default_auto_format_priority=self._default_auto_format_priority,
            default_online_provider_ids=self._default_online_provider_ids,
        )

    def get_page(self) -> List[dict]:
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self.get_state() or not self._show_sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "字幕匹配",
                "icon": "mdi-file-upload-outline",
                "section": "organize",
                "permission": "manage",
                "order": 48,
            }
        ]

    def stop_service(self):
        self._auto_transfer_service().stop()

    @eventmanager.register(EventType.TransferComplete)
    def listen_transfer_complete(self, event: MPEvent):
        if not self.get_state() or not self._auto_search_on_transfer:
            return
        event_data = getattr(event, "event_data", None) or {}
        if not isinstance(event_data, dict):
            return
        entries = self._entries_from_transfer_event(event_data)
        if not entries:
            logger.info("[SubtitleManualUpload] 入库事件未解析到本地视频目标，跳过自动字幕搜索")
            return
        self._merge_local_entries_cache(entries)
        queued, skipped = self._enqueue_transfer_auto_entries(entries)
        if skipped:
            logger.info("[SubtitleManualUpload] 入库自动字幕处理去重跳过重复目标 count=%s", skipped)
        if queued:
            logger.info("[SubtitleManualUpload] 入库自动字幕任务已入队 count=%s", queued)

    def _save_config(self) -> None:
        self.update_config(
            {
                "enabled": self._enabled,
                "show_sidebar_nav": self._show_sidebar_nav,
                "rar_dependency_mode": self._rar_dependency_mode,
                "rar_tool_path": self._rar_tool_path,
                "traditional_to_simplified": self._traditional_to_simplified,
                "auto_search_on_transfer": self._auto_search_on_transfer,
                "auto_skip_chinese_media_on_transfer": self._auto_skip_chinese_media_on_transfer,
                "auto_transfer_subtitle_strategy": self._auto_transfer_subtitle_strategy,
                "trust_transfer_history_paths": self._trust_transfer_history_paths,
                "timeline_max_offset_seconds": self._timeline_max_offset_seconds,
                "timeline_min_offset_seconds": self._timeline_min_offset_seconds,
                "timeline_vad_mode": self._timeline_vad_mode,
                "timeline_allow_risky_offset": self._timeline_allow_risky_offset,
                "online_providers": self._online_provider_ids,
                "online_engine": self._online_engine,
                "online_use_proxy": self._online_use_proxy,
                "online_proxy_migrated": True,
                "assrt_provider_migrated": True,
                "subhd_url": self._online_site_urls["subhd"],
                "zimuku_url": self._online_site_urls["zimuku"],
                "assrt_url": self._online_site_urls["assrt"],
                "assrt_api_key": self._assrt_api_key,
                "assrt_api_url": self._assrt_api_url,
                "opensubtitles_url": self._online_site_urls["opensubtitles"],
                "opensubtitles_api_key": self._opensubtitles_api_key,
                "opensubtitles_api_url": self._opensubtitles_api_url,
                "opensubtitles_username": self._opensubtitles_username,
                "opensubtitles_password": self._opensubtitles_password,
                "ai_link_enabled": self._ai_link_enabled,
                "auto_multi_subtitle_mode": self._auto_multi_subtitle_mode,
                "auto_subtitle_language_priority": list(self._auto_subtitle_language_priority),
                "auto_subtitle_format_priority": list(self._auto_subtitle_format_priority),
                "auto_ass_to_srt_for_ai": self._auto_ass_to_srt_for_ai,
            }
        )

    def _ok(self, data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @classmethod
    def _normalize_timeline_max_offset(cls, value: Any) -> int:
        return normalize_timeline_max_offset(value)

    @classmethod
    def _normalize_timeline_min_offset(cls, value: Any) -> float:
        return normalize_timeline_min_offset(value)

    @classmethod
    def _normalize_timeline_vad_mode(cls, value: Any) -> str:
        return normalize_timeline_vad_mode(value)

    @classmethod
    def _normalize_auto_multi_subtitle_mode(cls, value: Any) -> str:
        return normalize_auto_multi_subtitle_mode(value)

    @classmethod
    def _normalize_auto_language_key(cls, value: Any) -> str:
        return normalize_auto_language_key(value)

    @classmethod
    def _normalize_auto_language_priority(cls, value: Any) -> List[str]:
        return normalize_auto_language_priority(value, cls._default_auto_language_priority)

    @classmethod
    def _normalize_auto_format_priority(cls, value: Any) -> List[str]:
        return normalize_auto_format_priority(value, cls._subtitle_exts, cls._default_auto_format_priority)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _normalize_root_url(cls, value: Any, default: str) -> str:
        return normalize_root_url(value, default)

    @classmethod
    def _host_from_url(cls, value: Any) -> str:
        return host_from_url(value)

    @classmethod
    def _site_hosts(cls, site: Any) -> List[str]:
        hosts: List[str] = []
        for attr in ("url", "domain"):
            host = cls._normalize_site_host(getattr(site, attr, ""))
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    @classmethod
    def _normalize_site_host(cls, value: Any) -> str:
        text = cls._normalize_text(value)
        if not text:
            return ""
        host = cls._host_from_url(text)
        if not host:
            text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text, flags=re.I)
            host = re.split(r"[/?#]", text, maxsplit=1)[0]
        if "@" in host:
            host = host.rsplit("@", 1)[-1]
        if ":" in host:
            host = host.split(":", 1)[0]
        return host.strip(".").lower()

    @staticmethod
    def _site_host_matches(site_host: str, target_host: str) -> bool:
        site_host = site_host.lower().removeprefix("www.")
        target_host = target_host.lower().removeprefix("www.")
        return site_host == target_host or site_host.endswith(f".{target_host}") or target_host.endswith(f".{site_host}")

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    @classmethod
    def _brief_ids(cls, values: Iterable[Any], limit: int = 5) -> str:
        items = [cls._normalize_text(item)[:8] for item in values if cls._normalize_text(item)]
        if len(items) > limit:
            return f"{','.join(items[:limit])},+{len(items) - limit}"
        return ",".join(items)

    @staticmethod
    def _decode_preview_bytes(raw_bytes: bytes) -> str:
        if not raw_bytes:
            return ""
        for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
            try:
                return raw_bytes.decode(encoding)
            except Exception:
                continue
        return raw_bytes.decode("utf-8", errors="ignore")

    @classmethod
    def _normalize_rar_dependency_mode(cls, value: Any) -> str:
        return normalize_rar_dependency_mode(value)

    @classmethod
    def _normalize_auto_transfer_subtitle_strategy(cls, value: Any) -> str:
        return normalize_auto_transfer_subtitle_strategy(value)

    @classmethod
    def _normalize_provider_ids(cls, value: Any, *, fallback: bool = True) -> List[str]:
        return normalize_provider_ids(
            value,
            fallback=fallback,
            available_provider_ids=cls._available_online_provider_ids,
            default_provider_ids=cls._default_online_provider_ids,
        )

    @classmethod
    def _normalize_online_site_urls(cls, config: Dict[str, Any]) -> Dict[str, str]:
        return normalize_online_site_urls(config)

    def _check_online_rate_limit(self, providers: Iterable[str]) -> None:
        now = time.time()
        provider_ids = sorted({self._normalize_text(provider_id).lower() for provider_id in providers if self._normalize_text(provider_id)})
        blocked = []
        active_records: Dict[str, List[float]] = {}
        for provider_id in provider_ids:
            records = [item for item in self._online_rate_records.get(provider_id, []) if now - item < 60]
            active_records[provider_id] = records
            if len(records) >= self._online_rate_limit_per_minute:
                blocked.append(provider_id)
        if blocked:
            raise HTTPException(
                status_code=429,
                detail=f"在线字幕源请求过于频繁：{','.join(blocked)} 每分钟最多 {self._online_rate_limit_per_minute} 次，请稍后再试",
            )
        for provider_id, records in active_records.items():
            records.append(now)
            self._online_rate_records[provider_id] = records

    @classmethod
    def _entry_path_is_valid(cls, entry: Dict[str, Any]) -> bool:
        return target_entry_path_is_valid(
            entry,
            normalize_text=cls._normalize_text,
            trust_transfer_history_paths=getattr(cls, "_trust_transfer_history_paths", False),
        )

    @classmethod
    def _entry_filesystem_signature(cls, entry: Dict[str, Any]) -> str:
        return target_entry_filesystem_signature(entry, normalize_text=cls._normalize_text)

    def _filter_existing_local_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._local_media_catalog().filter_existing_local_entries(entries)

    def _prune_local_entries_cache(self) -> None:
        self._local_media_catalog().prune_local_entries_cache()

    def _transfer_auto_key(self, entry: Dict[str, Any]) -> str:
        return self._auto_transfer_service().transfer_auto_key(entry)

    def _claim_transfer_auto_entries(self, entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        return self._auto_transfer_service().claim_transfer_auto_entries(entries)

    @staticmethod
    def _timestamp_iso(ts: Any) -> str:
        try:
            return datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")
        except Exception:
            return ""

    def _auto_transfer_entry_key(self, entry: Dict[str, Any]) -> str:
        return self._auto_transfer_service().auto_transfer_entry_key(entry)

    def _auto_transfer_group_key(self, entry: Dict[str, Any]) -> str:
        return self._auto_transfer_service().auto_transfer_group_key(entry)

    def _trim_auto_transfer_tasks_locked(self) -> None:
        self._auto_transfer_service().trim_auto_transfer_tasks_locked()

    def _enqueue_transfer_auto_entries(self, entries: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self._auto_transfer_service().enqueue_transfer_auto_entries(entries)

    def _ensure_transfer_auto_worker(self) -> None:
        self._auto_transfer_service().ensure_transfer_auto_worker()

    def _update_auto_transfer_task(self, task_id: str, **updates: Any) -> None:
        self._auto_transfer_service().update_auto_transfer_task(task_id, **updates)

    def _claim_next_auto_transfer_batch(self) -> Tuple[List[Dict[str, Any]], float]:
        return self._auto_transfer_service().claim_next_auto_transfer_batch()

    def _auto_wait_online_rate_limit(self, providers: Iterable[str], task_ids: Optional[List[str]] = None) -> None:
        self._auto_transfer_service().auto_wait_online_rate_limit(providers, task_ids=task_ids)

    def _auto_transfer_rate_status(self) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_transfer_rate_status()

    def _auto_transfer_queue_summary(self) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_transfer_queue_summary()

    def _auto_transfer_queue_snapshot(self, limit: int = 100) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_transfer_queue_snapshot(limit=limit)

    def _auto_transfer_queue_loop(self) -> None:
        self._auto_transfer_service().auto_transfer_queue_loop()

    @staticmethod
    def _is_executable_file(path: Path) -> bool:
        return upload_is_executable_file(path)

    def _set_rar_dependency_status(self, state: str, message: str) -> None:
        self._rar_dependency_status = {
            "mode": self._rar_dependency_mode,
            "state": state,
            "message": message,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "tool_path": self._rar_tool_path,
        }

    def _prepare_rar_dependency(self) -> None:
        if self._rar_dependency_mode == "none":
            self._set_rar_dependency_status("skipped", "未启用 RAR 解压器自动处理")
            return

        if self._rar_tool():
            self._set_rar_dependency_status("ready", "已检测到可用 RAR 解压器")
            return

        if self._rar_dependency_mode == "mapped_binary":
            self._set_rar_dependency_status(
                "missing",
                f"未检测到映射文件，请把宿主机 7zz 映射到容器 {self._rar_tool_path}",
            )
            logger.info(
                "[SubtitleManualUpload] RAR 映射模式未检测到工具 path=%s",
                self._rar_tool_path,
            )
            return

        if self._rar_dependency_mode == "container_install":
            self._install_container_rar_tool()
            return

        self._set_rar_dependency_status("skipped", "未知 RAR 依赖处理方式")

    def _install_container_rar_tool(self) -> None:
        logger.info("[SubtitleManualUpload] 开始尝试在容器内安装 RAR 解压器")
        install_script = r"""
set -eu
if command -v unrar >/dev/null 2>&1 || command -v bsdtar >/dev/null 2>&1 || command -v 7z >/dev/null 2>&1 || command -v 7za >/dev/null 2>&1 || command -v 7zz >/dev/null 2>&1; then
  exit 0
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "当前容器没有 apt-get，无法自动安装，请使用宿主机静态 7zz 映射" >&2
  exit 78
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends p7zip-full unrar-free || apt-get install -y --no-install-recommends 7zip unrar-free libarchive-tools
"""
        try:
            completed = subprocess.run(
                ["sh", "-lc", install_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            self._set_rar_dependency_status("failed", "容器内安装 RAR 解压器超时")
            logger.warning("[SubtitleManualUpload] 容器内安装 RAR 解压器超时")
            return
        except subprocess.CalledProcessError as exc:
            stderr = self._decode_preview_bytes(exc.stderr or b"").strip()
            message = stderr[-500:] if stderr else str(exc)
            self._set_rar_dependency_status("failed", f"容器内安装失败: {message}")
            logger.warning(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器失败 returncode=%s error=%s",
                exc.returncode,
                message,
            )
            return

        stdout = self._decode_preview_bytes(completed.stdout or b"").strip()
        tool_path = self._rar_tool()
        if tool_path:
            self._set_rar_dependency_status("ready", f"容器内安装完成，当前工具: {Path(tool_path).name}")
            logger.info(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器完成 tool=%s output_tail=%s",
                Path(tool_path).name,
                stdout[-300:],
            )
            return

        self._set_rar_dependency_status("failed", "安装命令结束，但仍未检测到 unrar、bsdtar、7z、7za 或 7zz")
        logger.warning("[SubtitleManualUpload] 容器内安装后仍未检测到 RAR 解压器")

    @classmethod
    def _normalize_language_suffix(cls, value: Any) -> str:
        return normalize_language_suffix(value)

    @classmethod
    def _language_suffix_from_filename(cls, file_name: str) -> Dict[str, str]:
        return language_suffix_from_filename(file_name, cls._subtitle_exts)

    @classmethod
    def _detect_language_profile(cls, file_name: str, raw_bytes: bytes) -> Dict[str, str]:
        return detect_language_profile(file_name, raw_bytes, cls._subtitle_exts)

    @classmethod
    def _extract_episode_hint(cls, file_name: str) -> Optional[Dict[str, int]]:
        cleaned = str(file_name or "")
        patterns = [
            re.compile(r"(?i)\bS(?P<season>\d{1,2})[\s._-]*E(?P<episode>\d{1,3})\b"),
            re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b"),
            re.compile(r"第\s*(?P<season>\d{1,2})\s*季.*?第\s*(?P<episode>\d{1,3})\s*[集话話]"),
            re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]"),
        ]

        for pattern in patterns:
            match = pattern.search(cleaned)
            if not match:
                continue
            season = cls._safe_int(match.groupdict().get("season"), 0)
            episode = cls._safe_int(match.groupdict().get("episode"), 0)
            if episode:
                return {"season": season, "episode": episode}
        return None

    @classmethod
    def _upload_session_service_for_path(cls, data_path: Path) -> UploadSessionService:
        return UploadSessionService(
            data_path=data_path,
            subtitle_exts=cls._subtitle_exts,
            archive_exts=cls._archive_exts,
            rar_exts=cls._rar_exts,
            sevenzip_exts=cls._sevenzip_exts,
            default_session_hours=cls._default_session_hours,
            hash_text=cls._hash_text,
            extract_rar_subtitle_files=cls._extract_rar_subtitle_files,
            extract_7z_subtitle_files=cls._extract_7z_subtitle_files,
            logger_warning=logger.warning,
            normalize_text=cls._normalize_text,
            decode_preview_bytes=cls._decode_preview_bytes,
        )

    def _upload_session_service(self) -> UploadSessionService:
        return self._upload_session_service_for_path(self.get_data_path())

    @classmethod
    def _subtitle_inventory(cls) -> SubtitleInventory:
        return SubtitleInventory(
            subtitle_exts=cls._subtitle_exts,
            stream_exts=cls._stream_exts,
            embedded_text_codecs=cls._embedded_subtitle_text_codecs,
            embedded_image_codecs=cls._embedded_subtitle_image_codecs,
            embedded_probe_cache=cls._embedded_subtitle_probe_cache,
            embedded_probe_cache_max_size=cls._embedded_subtitle_probe_cache_max_size,
            trust_transfer_history_paths=getattr(cls, "_trust_transfer_history_paths", False),
            normalize_text=cls._normalize_text,
            normalize_language_suffix=cls._normalize_language_suffix,
            detect_language_profile=cls._detect_language_profile,
            is_chinese_language_suffix=cls._is_chinese_language_suffix,
            safe_int=cls._safe_int,
            subtitle_backup_path=cls._subtitle_backup_path,
            subprocess_module=subprocess,
            logger_warning=logger.warning,
        )

    def _subtitle_writer(self) -> SubtitleWriter:
        return SubtitleWriter(
            self,
            http_exception=HTTPException,
            logger=logger,
            timeline_result_type=TimelineFixResult,
            timeline_fix_func=fix_subtitle_timeline,
            convert_subtitle_file_to_simplified=convert_subtitle_file_to_simplified,
        )

    def _subtitle_history(self) -> SubtitleHistory:
        return SubtitleHistory(
            self,
            http_exception=HTTPException,
            logger=logger,
        )

    def _autosub_bridge(self) -> AutoSubBridge:
        return AutoSubBridge(
            self,
            plugin_manager=PluginManager,
            http_exception=HTTPException,
            logger=logger,
        )

    def _online_ai_service(self) -> OnlineAiService:
        return OnlineAiService(
            self,
            http_exception=HTTPException,
            logger=logger,
            check_timeline_fixer_dependencies=check_timeline_fixer_dependencies,
        )

    def _auto_transfer_service(self) -> AutoTransferService:
        return AutoTransferService(
            self,
            logger=logger,
            threading_module=threading,
            time_module=time,
            http_exception=HTTPException,
        )

    def _target_resolver(self) -> MediaTargetResolver:
        return MediaTargetResolver(
            settings_obj=settings,
            meta_info_path=MetaInfoPath,
            stream_exts=self._stream_exts,
            trust_transfer_history_paths=getattr(self, "_trust_transfer_history_paths", False),
            normalize_text=self._normalize_text,
            safe_int=self._safe_int,
            hash_text=self._hash_text,
            extract_episode_hint=self._extract_episode_hint,
            subtitle_files_for_target=self._subtitle_files_for_target,
            load_local_entries=self._load_local_entries,
            group_entries_as_media=self._group_entries_as_media,
            tmdb_detail_for_media=self._tmdb_detail_for_media,
            apply_tmdb_detail=self._apply_tmdb_detail,
            remember_targets=self._remember_targets,
        )

    def _local_media_catalog(self) -> LocalMediaCatalog:
        return LocalMediaCatalog(
            self,
            transfer_history=TransferHistory,
            http_exception=HTTPException,
            logger=logger,
        )

    def _get_session_root(self) -> Path:
        return self._upload_session_service().get_session_root()

    def _cleanup_old_sessions(self) -> None:
        self._upload_session_service().cleanup_old_sessions()

    @classmethod
    def _media_type_text(cls, value: Any) -> str:
        return target_media_type_text(value)

    @classmethod
    def _poster_url(cls, poster_path: Any, prefix: str = "w500") -> str:
        return target_poster_url(
            poster_path,
            prefix,
            settings_obj=settings,
            normalize_text=cls._normalize_text,
        )

    @classmethod
    def _history_type_text(cls, media_type: Any) -> str:
        return target_history_type_text(media_type, normalize_text=cls._normalize_text)

    @classmethod
    def _number_from_tag(cls, value: Any) -> int:
        return target_number_from_tag(value, normalize_text=cls._normalize_text, safe_int=cls._safe_int)

    @classmethod
    def _is_local_video_path(cls, storage: str, path: str) -> bool:
        return target_is_local_video_path(
            storage,
            path,
            normalize_text=cls._normalize_text,
            settings_obj=settings,
            stream_exts=cls._stream_exts,
            trust_transfer_history_paths=getattr(cls, "_trust_transfer_history_paths", False),
        )

    def _build_entry_from_history(self, history: Any) -> Optional[Dict[str, Any]]:
        return self._target_resolver().build_entry_from_history(history)

    @classmethod
    def _event_value(cls, obj: Any, *names: str, default: Any = "") -> Any:
        return target_event_value(obj, *names, default=default)

    def _transfer_event_paths(self, transferinfo: Any) -> List[str]:
        return self._target_resolver().transfer_event_paths(transferinfo)

    def _entries_from_transfer_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._target_resolver().entries_from_transfer_event(event_data)

    def _merge_local_entries_cache(self, entries: List[Dict[str, Any]]) -> None:
        if not entries:
            return
        entries = self._filter_existing_local_entries(entries)
        if not entries:
            return
        cache = self._local_entries_cache or {}
        existing = self._filter_existing_local_entries([item for item in cache.get("entries") or [] if isinstance(item, dict)])
        by_path = {entry.get("path"): entry for entry in entries if entry.get("path")}
        merged = list(entries)
        for entry in existing:
            if entry.get("path") not in by_path:
                merged.append(entry)
            if len(merged) >= self._cache_max_entries:
                break
        media_count = len({entry.get("media_key") for entry in merged if entry.get("media_key")})
        self._local_entries_cache = {
            "loaded_at": datetime.now(),
            "entries": merged[: self._cache_max_entries],
            "media_count": media_count,
            "persisted": False,
        }
        self._remember_targets(entries)
        self._reset_media_index_cache()
        self._invalidate_match_history_cache()
        self._persist_local_cache()

    def _local_cache_file(self) -> Path:
        return self._local_media_catalog().local_cache_file()

    def _match_history_cache_file(self) -> Path:
        return self._subtitle_history().match_history_cache_file()

    @classmethod
    def _cache_loaded_at(cls, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        text = cls._normalize_text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _persist_local_cache(self) -> None:
        self._local_media_catalog().persist_local_cache()

    def _restore_persisted_local_cache(self) -> bool:
        return self._local_media_catalog().restore_persisted_local_cache()

    @classmethod
    def _json_clone(cls, value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False))

    def _match_history_signature(self, entries: List[Dict[str, Any]]) -> str:
        return self._subtitle_history().match_history_signature(entries)

    def _persist_match_history_cache(self) -> None:
        self._subtitle_history().persist_match_history_cache()

    def _restore_persisted_match_history_cache(self) -> bool:
        return self._subtitle_history().restore_persisted_match_history_cache()

    def _invalidate_match_history_cache(self) -> None:
        self._subtitle_history().invalidate_match_history_cache()

    def _filter_match_history_items(
        self,
        items: List[Dict[str, Any]],
        *,
        keyword: str = "",
        media_type: str = "all",
    ) -> List[Dict[str, Any]]:
        return self._subtitle_history().filter_match_history_items(
            items,
            keyword=keyword,
            media_type=media_type,
        )

    @staticmethod
    def _timeline_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "skipped": 0,
            "failed": 0,
            "active": 0,
            "total": len(tasks),
        }
        for task in tasks:
            status = task.get("status")
            if status in counts:
                counts[status] += 1
            if task.get("active") or status in {"pending", "in_progress"}:
                counts["active"] += 1
        return counts

    def _cleanup_timeline_tasks(self) -> None:
        tasks = self._timeline_tasks or OrderedDict()
        cutoff = datetime.now() - timedelta(seconds=self._timeline_task_ttl_seconds)
        for key in list(tasks.keys()):
            updated_at = self._cache_loaded_at((tasks.get(key) or {}).get("updated_at"))
            if updated_at and updated_at < cutoff:
                tasks.pop(key, None)
        self._timeline_tasks = tasks

    def _timeline_task_for_target_id(self, target_id: Any) -> Optional[Dict[str, Any]]:
        self._cleanup_timeline_tasks()
        clean_id = self._normalize_text(target_id)
        if not clean_id:
            return None
        task = (self._timeline_tasks or {}).get(clean_id)
        return self._json_clone(task) if task else None

    def _set_timeline_task(
        self,
        operation: Dict[str, Any],
        *,
        status: str,
        message: str = "",
        timeline_result: Optional[TimelineFixResult] = None,
    ) -> None:
        target_entry = operation.get("target_entry") or {}
        target_id = self._normalize_text(target_entry.get("id"))
        if not target_id:
            return
        now = datetime.now().isoformat(timespec="seconds")
        timeline = timeline_result.to_dict() if timeline_result else None
        active = status in {"pending", "in_progress"}
        task = {
            "target_id": target_id,
            "target_label": target_entry.get("target_label") or target_entry.get("filename") or Path(self._normalize_text(target_entry.get("path"))).name,
            "source_name": (operation.get("upload_info") or {}).get("source_name", ""),
            "output_name": operation.get("destination_name", ""),
            "status": status,
            "active": active,
            "message": message or status,
            "status_label": {
                "pending": "等待调轴",
                "in_progress": "智能调轴中",
                "completed": "调轴完成",
                "skipped": "已跳过",
                "failed": "调轴失败",
            }.get(status, status),
            "timeline": timeline,
            "updated_at": now,
        }
        existing = (self._timeline_tasks or OrderedDict()).get(target_id) or {}
        if existing.get("created_at"):
            task["created_at"] = existing.get("created_at")
        else:
            task["created_at"] = now
        self._timeline_tasks[target_id] = task
        self._timeline_tasks.move_to_end(target_id)
        while len(self._timeline_tasks) > self._entry_map_max_size:
            self._timeline_tasks.popitem(last=False)

    def _timeline_tasks_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        tasks: List[Dict[str, Any]] = []
        task_by_target: Dict[str, Any] = {}
        for entry in target_entries:
            target_id = self._normalize_text(entry.get("id"))
            task = self._timeline_task_for_target_id(target_id)
            if task:
                task_by_target[target_id] = task
                tasks.append(task)
            else:
                task_by_target[target_id] = None
        return {
            "summary": self._timeline_task_summary(tasks),
            "tasks": tasks,
            "task_by_target": task_by_target,
        }

    def _start_background_cache_refresh(self) -> None:
        if self._cache_refreshing:
            return
        self._cache_refreshing = True
        self._cache_refresh_started_at = datetime.now().isoformat(timespec="seconds")
        self._cache_refresh_completed_at = ""
        self._cache_refresh_error = ""

        def worker():
            try:
                self._load_local_entries(force=True)
                self._cache_refresh_completed_at = datetime.now().isoformat(timespec="seconds")
                self._cache_refresh_error = ""
            except Exception as exc:
                self._cache_refresh_error = str(exc)
                logger.warning("[SubtitleManualUpload] 后台刷新本地资源缓存失败: %s", exc)
            finally:
                self._cache_refreshing = False

        threading.Thread(
            target=worker,
            name="SubtitleManualUploadCacheRefresh",
            daemon=True,
        ).start()

    def _load_local_entries(self, *, force: bool = False, allow_stale: bool = False) -> List[Dict[str, Any]]:
        return self._local_media_catalog().load_local_entries(force=force, allow_stale=allow_stale)

    def _refresh_local_cache(self) -> List[Dict[str, Any]]:
        return self._local_media_catalog().refresh_local_cache()

    def _cache_status(self) -> Dict[str, Any]:
        return self._local_media_catalog().cache_status()

    def _autosub_plugin(self) -> Tuple[Any, str]:
        return self._autosub_bridge().autosub_plugin()

    def _autosub_status(self) -> Dict[str, Any]:
        return self._autosub_bridge().autosub_status()

    @staticmethod
    def _autosub_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        return bridge_autosub_task_summary(tasks)

    def _autosub_tasks_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._autosub_bridge().autosub_tasks_for_entries(target_entries)

    @classmethod
    def _entry_matches_keyword(cls, entry: Dict[str, Any], keyword: str) -> bool:
        return target_entry_matches_keyword(entry, keyword, normalize_text=cls._normalize_text)

    def _reset_media_index_cache(self) -> None:
        self._local_media_catalog().reset_media_index_cache()

    def _media_index_cache_key(self, keyword: str, media_type: str) -> str:
        return self._local_media_catalog().media_index_cache_key(keyword, media_type)

    def _media_index_cache_get(self, key: str, entries: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        return self._local_media_catalog().media_index_cache_get(key, entries)

    def _media_index_cache_set(self, key: str, entries: List[Dict[str, Any]], medias: List[Dict[str, Any]]) -> None:
        self._local_media_catalog().media_index_cache_set(key, entries, medias)

    async def _search_media_candidates(self, keyword: str, media_type: str, limit: int, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        return await self._local_media_catalog().search_media_candidates(keyword, media_type, limit, offset)

    def _group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        return self._local_media_catalog().group_entries_as_media(entries, limit)

    def _match_history_items(self, *, keyword: str = "", media_type: str = "all") -> List[Dict[str, Any]]:
        return self._subtitle_history().match_history_items(keyword=keyword, media_type=media_type)

    def _merge_seasons(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._target_resolver().merge_seasons(entries)

    def _targets_for_media(
        self,
        media_type: str,
        tmdb_id: Any = None,
        douban_id: Any = None,
        title: str = "",
        year: str = "",
        season: Any = None,
    ) -> Dict[str, Any]:
        return self._target_resolver().targets_for_media(
            media_type=media_type,
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            title=title,
            year=year,
            season=season,
        )

    def _tmdb_detail_for_media(self, media: Dict[str, Any]) -> Dict[str, Any]:
        tmdb_id = self._safe_int(media.get("tmdb_id"), 0)
        media_type = self._media_type_text(media.get("media_type"))
        if not tmdb_id or TmdbChain is None:
            return {}
        cache_key = f"{media_type}:{tmdb_id}"
        if cache_key in self._tmdb_detail_cache:
            return dict(self._tmdb_detail_cache[cache_key])
        try:
            mp_type = MediaType.TV if media_type == "tv" else MediaType.MOVIE
            detail = TmdbChain().tmdb_info(tmdbid=tmdb_id, mtype=mp_type)
        except TypeError:
            try:
                mp_type = MediaType.TV if media_type == "tv" else MediaType.MOVIE
                detail = TmdbChain().tmdb_info(tmdb_id=tmdb_id, mtype=mp_type)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 读取 TMDB 详情失败 tmdb=%s type=%s error=%s", tmdb_id, media_type, exc)
                return {}
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 读取 TMDB 详情失败 tmdb=%s type=%s error=%s", tmdb_id, media_type, exc)
            return {}
        payload = self._tmdb_detail_payload(detail)
        self._tmdb_detail_cache[cache_key] = payload
        return dict(payload)

    @classmethod
    def _tmdb_detail_payload(cls, detail: Any) -> Dict[str, Any]:
        if not detail:
            return {}

        def value(*keys: str) -> Any:
            for key in keys:
                if isinstance(detail, dict) and key in detail:
                    return detail.get(key)
                if hasattr(detail, key):
                    return getattr(detail, key)
            return None

        translations = value("translations")
        alternative_titles = value("alternative_titles")
        aliases = cls._tmdb_aliases(translations, alternative_titles)
        return {
            "original_language": value("original_language") or "",
            "origin_country": value("origin_country") or [],
            "production_countries": value("production_countries") or [],
            "original_title": value("original_title", "original_name") or "",
            "en_title": cls._english_title_from_tmdb_values(translations, alternative_titles)
            or cls._english_title_from_aliases(aliases),
            "tmdb_aliases": aliases,
        }

    @classmethod
    def _english_title_from_tmdb_values(cls, *values: Any) -> str:
        candidates: List[str] = []

        def add_title(value: Any) -> None:
            for item in extract_title_aliases(value):
                if item and re.search(r"[A-Za-z]", item) and not re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", item):
                    candidates.append(item)

        def walk(value: Any) -> None:
            if isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
                return
            if not isinstance(value, dict):
                return
            lang = cls._normalize_text(value.get("iso_639_1")).lower()
            country = cls._normalize_text(value.get("iso_3166_1")).lower()
            if lang == "en" or country in {"us", "gb", "uk"}:
                data = value.get("data")
                if isinstance(data, dict):
                    add_title({key: data.get(key) for key in ("title", "name")})
                add_title({key: value.get(key) for key in ("title", "name")})
            for key in ["data", "titles", "results", "translations", "alternative_titles", "aliases"]:
                walk(value.get(key))

        for value in values:
            walk(value)
        seen = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            return item
        return ""

    @classmethod
    def _tmdb_aliases(cls, *values: Any) -> List[str]:
        aliases: List[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
                return
            aliases.extend(extract_title_aliases(value))

        for value in values:
            walk(value)
        result: List[str] = []
        seen = set()
        for item in aliases:
            key = item.lower()
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result[:80]

    @classmethod
    def _english_title_from_aliases(cls, aliases: List[str]) -> str:
        for item in aliases or []:
            if re.search(r"[A-Za-z]", item) and not re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", item):
                return item
        return ""

    @classmethod
    def _apply_tmdb_detail(cls, target: Dict[str, Any], detail: Dict[str, Any]) -> None:
        for key in ["original_language", "origin_country", "production_countries", "original_title", "tmdb_aliases"]:
            value = detail.get(key)
            if value and not target.get(key):
                target[key] = value
        if detail.get("en_title") and not target.get("en_title"):
            target["en_title"] = detail["en_title"]

    @classmethod
    def _flatten_media_values(cls, value: Any, keys: Tuple[str, ...] = ()) -> List[str]:
        values: List[str] = []

        def walk(item: Any) -> None:
            if item is None:
                return
            if isinstance(item, dict):
                for key in keys or ("iso_3166_1", "iso_639_1", "code", "value", "name", "english_name"):
                    if key in item:
                        walk(item.get(key))
                return
            if isinstance(item, (list, tuple, set)):
                for child in item:
                    walk(child)
                return
            text = cls._normalize_text(item)
            if not text:
                return
            for part in re.split(r"[,/|]+", text):
                clean = cls._normalize_text(part).lower().replace("_", "-")
                if clean:
                    values.append(clean)

        walk(value)
        return values

    @classmethod
    def _is_chinese_language_code(cls, value: Any) -> bool:
        code = cls._normalize_text(value).lower().replace("_", "-")
        base = re.split(r"[-\s]+", code, maxsplit=1)[0] if code else ""
        return code in cls._chinese_media_language_codes or base in cls._chinese_media_language_codes

    @classmethod
    def _is_chinese_country_value(cls, value: Any) -> bool:
        text = cls._normalize_text(value).lower().replace("_", "-")
        base = re.split(r"[-\s]+", text, maxsplit=1)[0] if text else ""
        return (
            text in cls._chinese_media_country_codes
            or base in cls._chinese_media_country_codes
            or text in cls._chinese_media_region_names
        )

    @classmethod
    def _chinese_category_evidence(cls, entry: Dict[str, Any]) -> str:
        values = []
        for key in [
            "library_name",
            "media_category",
            "media_category_name",
            "category",
            "category_name",
            "type_name",
        ]:
            raw = entry.get(key)
            if isinstance(raw, (list, tuple, set)):
                values.extend(cls._normalize_text(item) for item in raw)
            else:
                values.append(cls._normalize_text(raw))
        text = " ".join(item for item in values if item)
        if text and cls._chinese_media_category_pattern.search(text):
            return "MP 分类/库名包含华语标识"
        return ""

    def _auto_media_for_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        media = {
            "media_type": entry.get("media_type"),
            "title": entry.get("title"),
            "year": entry.get("year"),
            "tmdb_id": entry.get("tmdb_id"),
            "douban_id": entry.get("douban_id"),
            "original_language": entry.get("original_language"),
            "origin_country": entry.get("origin_country"),
            "production_countries": entry.get("production_countries"),
            "original_title": entry.get("original_title") or entry.get("original_name"),
            "en_title": entry.get("en_title"),
            "tmdb_aliases": entry.get("tmdb_aliases"),
        }
        tmdb_detail = self._tmdb_detail_for_media(media)
        if tmdb_detail:
            self._apply_tmdb_detail(media, tmdb_detail)
            self._apply_tmdb_detail(entry, tmdb_detail)
        return media

    def _is_chinese_transfer_media(self, entry: Dict[str, Any]) -> Tuple[bool, str]:
        category_reason = self._chinese_category_evidence(entry)
        if category_reason:
            return True, category_reason

        media = self._auto_media_for_entry(entry)
        languages = self._flatten_media_values(
            media.get("original_language"),
            ("iso_639_1", "code", "value", "name", "english_name"),
        )
        for language in languages:
            if self._is_chinese_language_code(language):
                return True, f"TMDB original_language={language}"

        country_values = [
            *self._flatten_media_values(
                media.get("origin_country"),
                ("iso_3166_1", "code", "value", "name", "english_name"),
            ),
            *self._flatten_media_values(
                media.get("production_countries"),
                ("iso_3166_1", "code", "value", "name", "english_name"),
            ),
        ]
        for country in country_values:
            if self._is_chinese_country_value(country):
                return True, f"TMDB country={country}"

        if media.get("tmdb_id"):
            return False, "TMDB 未提供中文语种/地区证据"
        return False, "中文识别证据不足"

    @classmethod
    def _is_stream_path(cls, path: Any) -> bool:
        return target_is_stream_path(
            path,
            normalize_text=cls._normalize_text,
            stream_exts=cls._stream_exts,
        )

    def _target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return self._target_resolver().target_from_entry(entry)

    def _remember_targets(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if target_id:
                if target_id in self._entry_map:
                    self._entry_map.move_to_end(target_id)
                self._entry_map[target_id] = entry
        while len(self._entry_map) > self._entry_map_max_size:
            self._entry_map.popitem(last=False)

    def _resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        return self._local_media_catalog().resolve_targets(target_ids)

    def _cached_unlocked_targets(self, locked_ids: set) -> List[Dict[str, Any]]:
        return self._local_media_catalog().cached_unlocked_targets(locked_ids)

    @classmethod
    def _build_destination_name(
        cls,
        target_entry: Dict[str, Any],
        subtitle_info: Dict[str, Any],
    ) -> str:
        return writer_build_destination_name(
            target_entry,
            subtitle_info,
            normalize_text=cls._normalize_text,
            normalize_language_suffix=cls._normalize_language_suffix,
        )

    @classmethod
    def _subtitle_files_for_target(cls, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        return cls._subtitle_inventory().subtitle_files_for_target(target_entry)

    @classmethod
    def _embedded_subtitle_tracks_for_target(cls, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        return cls._subtitle_inventory().embedded_subtitle_tracks_for_target(target_entry)

    @classmethod
    def _embedded_subtitle_language_suffix(cls, language: Any, title: Any = "") -> str:
        return cls._subtitle_inventory().embedded_subtitle_language_suffix(language, title)

    @classmethod
    def _embedded_subtitle_probe_cache_key(cls, video_path: Path) -> str:
        return cls._subtitle_inventory().embedded_subtitle_probe_cache_key(video_path)

    @classmethod
    def _embedded_subtitle_track_is_usable(cls, codec: Any, title: Any = "", disposition: Optional[Dict[str, Any]] = None) -> bool:
        return cls._subtitle_inventory().embedded_subtitle_track_is_usable(codec, title, disposition)

    @classmethod
    def _embedded_subtitle_sample_language_suffix(cls, video_path: Path, stream_index: Any, codec_name: Any) -> str:
        return cls._subtitle_inventory().embedded_subtitle_sample_language_suffix(video_path, stream_index, codec_name)

    def _remove_ext_marks(self, video_path: Path) -> None:
        self._subtitle_inventory().remove_ext_marks(video_path)

    @staticmethod
    def _is_upload_file(value: Any) -> bool:
        return isinstance(value, UploadFile)

    @classmethod
    def _rar_tool(cls) -> str:
        return upload_find_rar_tool(
            configured_tool_path=getattr(cls, "_rar_tool_path", ""),
            normalize_text=cls._normalize_text,
            rar_tools=cls._rar_tools,
        )

    @classmethod
    def _sevenzip_tool(cls) -> str:
        return upload_find_sevenzip_tool(
            configured_tool_path=getattr(cls, "_rar_tool_path", ""),
            normalize_text=cls._normalize_text,
            sevenzip_tools=cls._sevenzip_tools,
        )

    @classmethod
    def _rar_python_available(cls) -> bool:
        return upload_rar_python_available(cls._rar_python_package)

    @classmethod
    def _rarfile_module(cls) -> Any:
        return upload_rarfile_module(cls._rar_python_package)

    @classmethod
    def _run_archive_command(cls, args: List[str], timeout: int = 120) -> bytes:
        return upload_run_archive_command(args, decode_preview_bytes=cls._decode_preview_bytes, timeout=timeout)

    @classmethod
    def _list_rar_members(cls, archive_path: Path, tool_path: str) -> List[str]:
        return upload_list_rar_members(
            archive_path,
            tool_path,
            decode_preview_bytes=cls._decode_preview_bytes,
            run_command=cls._run_archive_command,
        )

    @classmethod
    def _read_rar_member(cls, archive_path: Path, member: str, tool_path: str) -> bytes:
        return upload_read_rar_member(
            archive_path,
            member,
            tool_path,
            run_command=cls._run_archive_command,
        )

    @classmethod
    def _extract_rar_subtitle_files_with_rarfile(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ) -> List[Dict[str, Any]]:
        return upload_extract_rar_subtitle_files_with_rarfile(
            source_name,
            archive_path,
            session_dir,
            rarfile_module_factory=cls._rarfile_module,
            rar_python_package=cls._rar_python_package,
            subtitle_exts=cls._subtitle_exts,
            hash_text=cls._hash_text,
            resource_limits=resource_limits,
        )

    @classmethod
    def _extract_rar_subtitle_files(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ) -> List[Dict[str, Any]]:
        return upload_extract_rar_subtitle_files(
            source_name,
            archive_path,
            session_dir,
            rar_python_available_func=cls._rar_python_available,
            extract_with_rarfile=cls._extract_rar_subtitle_files_with_rarfile,
            rar_tool_func=cls._rar_tool,
            extract_command_archive_subtitle_files_func=cls._extract_command_archive_subtitle_files,
            rar_python_package=cls._rar_python_package,
            logger_warning=logger.warning,
            resource_limits=resource_limits,
        )

    @classmethod
    def _extract_7z_subtitle_files(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ) -> List[Dict[str, Any]]:
        return upload_extract_7z_subtitle_files(
            source_name,
            archive_path,
            session_dir,
            sevenzip_tool_func=cls._sevenzip_tool,
            extract_command_archive_subtitle_files_func=cls._extract_command_archive_subtitle_files,
            resource_limits=resource_limits,
        )

    @classmethod
    def _extract_command_archive_subtitle_files(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        tool_path: str,
        resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ) -> List[Dict[str, Any]]:
        return upload_extract_command_archive_subtitle_files(
            source_name,
            archive_path,
            session_dir,
            tool_path,
            subtitle_exts=cls._subtitle_exts,
            hash_text=cls._hash_text,
            list_members=cls._list_rar_members,
            read_member=cls._read_rar_member,
            resource_limits=resource_limits,
        )

    @classmethod
    def _extract_subtitle_files(
        cls,
        upload_name: str,
        raw_bytes: bytes,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        return cls._upload_session_service_for_path(session_dir.parent).extract_subtitle_files(
            upload_name,
            raw_bytes,
            session_dir,
        )

    @classmethod
    def _suggest_target(
        cls,
        subtitle_info: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not targets:
            return None
        if len(targets) == 1:
            return targets[0]["id"]

        hint = cls._extract_episode_hint(subtitle_info.get("source_name"))
        if not hint:
            return None

        season = hint.get("season", 0)
        episode = hint.get("episode", 0)

        for target in targets:
            if target.get("season", 0) == season and target.get("episode", 0) == episode:
                return target["id"]

        if season == 0:
            candidate_seasons = {target.get("season", 0) for target in targets if target.get("season", 0)}
            if len(candidate_seasons) == 1:
                only_season = next(iter(candidate_seasons))
                for target in targets:
                    if target.get("season", 0) == only_season and target.get("episode", 0) == episode:
                        return target["id"]
        return None

    @classmethod
    def _auto_fill_missing_targets(
        cls,
        preview_items: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> None:
        unresolved = [item for item in preview_items if not item.get("target_id")]
        if not unresolved:
            return
        used_target_ids = {
            item.get("target_id")
            for item in preview_items
            if item.get("target_id")
        }
        remaining_targets = [
            target for target in targets if target.get("id") not in used_target_ids
        ]
        if len(unresolved) != len(remaining_targets):
            return
        sorted_targets = sorted(
            remaining_targets,
            key=lambda item: (
                item.get("season", 0),
                item.get("episode", 0),
                item.get("label", ""),
            ),
        )
        sorted_items = sorted(
            unresolved,
            key=lambda item: (
                cls._extract_episode_hint(item.get("source_name") or "") or {}
            ).get("episode", 0),
        )
        for item, target in zip(sorted_items, sorted_targets):
            item["target_id"] = target["id"]

    @classmethod
    def _build_write_operations(
        cls,
        items: List[Dict[str, Any]],
        upload_map: Dict[str, Dict[str, Any]],
        target_entries: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return writer_build_write_operations(
            items,
            upload_map,
            target_entries,
            normalize_text=cls._normalize_text,
            normalize_language_suffix=cls._normalize_language_suffix,
            build_destination_name_func=cls._build_destination_name,
            http_exception=HTTPException,
        )

    @classmethod
    def _is_chinese_language_suffix(cls, suffix: Any) -> bool:
        return is_chinese_language_suffix(suffix)

    @classmethod
    def _target_has_chinese_subtitle(cls, target: Dict[str, Any]) -> bool:
        subtitles = target.get("subtitles") or []
        if any(
            cls._is_chinese_language_suffix((item or {}).get("language_suffix") or (item or {}).get("language"))
            for item in subtitles
            if isinstance(item, dict)
        ):
            return True
        embedded_subtitles = target.get("embedded_subtitles") or []
        return any(
            bool((item or {}).get("is_chinese"))
            or cls._is_chinese_language_suffix((item or {}).get("language_suffix") or (item or {}).get("language"))
            for item in embedded_subtitles
            if isinstance(item, dict)
        )

    def _auto_target_has_chinese_subtitle(self, entry: Dict[str, Any], target: Dict[str, Any]) -> bool:
        if self._target_has_chinese_subtitle(target):
            return True
        embedded_subtitles = self._embedded_subtitle_tracks_for_target(entry)
        if embedded_subtitles:
            target["has_embedded_subtitle"] = True
            target["embedded_subtitle_count"] = len(embedded_subtitles)
            target["embedded_subtitles"] = embedded_subtitles
        return self._target_has_chinese_subtitle(target)

    def _maybe_convert_operation_to_simplified(self, operation: Dict[str, Any], output_dir: Path) -> None:
        self._subtitle_writer().maybe_convert_operation_to_simplified(operation, output_dir)

    def _write_operations_to_disk(
        self,
        *,
        session_dir: Path,
        operations: List[Dict[str, Any]],
        fix_timeline: bool = False,
        allow_risky_offset: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        return self._subtitle_writer().write_operations_to_disk(
            session_dir=session_dir,
            operations=operations,
            fix_timeline=fix_timeline,
            allow_risky_offset=allow_risky_offset,
        )

    def _write_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        self._upload_session_service().write_session(session_id, payload)

    def _load_session(self, session_id: str) -> Tuple[Path, Dict[str, Any]]:
        return self._upload_session_service().load_session(session_id, normalize_text=self._normalize_text)

    def _timeline_cache_dir(self) -> Path:
        return self.get_data_path() / "timeline_cache"

    @staticmethod
    def _timeline_result_blocks_auto_write(timeline_result: Optional[TimelineFixResult]) -> bool:
        return writer_timeline_result_blocks_auto_write(timeline_result)

    @staticmethod
    def _timeline_rejection_message(timeline_result: TimelineFixResult) -> str:
        return writer_timeline_rejection_message(timeline_result)

    @classmethod
    def _subtitle_backup_path(cls, subtitle_path: Path) -> Path:
        return writer_subtitle_backup_path(subtitle_path)

    @classmethod
    def _backup_subtitle_if_needed(cls, subtitle_path: Path) -> Optional[Path]:
        return writer_backup_subtitle_if_needed(subtitle_path)

    def _run_timeline_fix(
        self,
        *,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        allow_risky_offset: Optional[bool] = None,
    ) -> TimelineFixResult:
        return self._subtitle_writer().run_timeline_fix(
            video_path=video_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            allow_risky_offset=allow_risky_offset,
        )

    def _online_service(self) -> OnlineSubtitleSearchService:
        return OnlineSubtitleSearchService(
            engine=self._online_engine,
            use_proxy=self._online_use_proxy,
            provider_roots=self._online_site_urls,
            assrt_api_key=self._assrt_api_key,
            assrt_api_url=self._assrt_api_url,
            opensubtitles_api_key=self._opensubtitles_api_key,
            opensubtitles_api_url=self._opensubtitles_api_url,
            opensubtitles_username=self._opensubtitles_username,
            opensubtitles_password=self._opensubtitles_password,
        )

    @classmethod
    def _target_ids_from_body(cls, body: Dict[str, Any]) -> List[str]:
        target_ids = body.get("target_ids") or []
        if isinstance(target_ids, str):
            try:
                target_ids = json.loads(target_ids)
            except Exception:
                target_ids = [target_ids]
        if not isinstance(target_ids, list):
            return []
        return [cls._normalize_text(item) for item in target_ids if cls._normalize_text(item)]

    @classmethod
    def _locked_target_ids_from_body(cls, body: Dict[str, Any]) -> set:
        locked_ids = body.get("locked_target_ids") or []
        if isinstance(locked_ids, str):
            try:
                locked_ids = json.loads(locked_ids)
            except Exception:
                locked_ids = [locked_ids]
        if not isinstance(locked_ids, list):
            return set()
        return {cls._normalize_text(item) for item in locked_ids if cls._normalize_text(item)}

    @classmethod
    def _filter_unlocked_target_ids(cls, target_ids: Iterable[str], locked_ids: set) -> Tuple[List[str], List[Dict[str, str]]]:
        unlocked: List[str] = []
        skipped: List[Dict[str, str]] = []
        for target_id in target_ids:
            clean_id = cls._normalize_text(target_id)
            if not clean_id:
                continue
            if clean_id in locked_ids:
                skipped.append({"target_id": clean_id, "reason": "目标已锁定"})
                continue
            unlocked.append(clean_id)
        return unlocked, skipped

    @classmethod
    def _ensure_target_not_locked(cls, target_id: str, locked_ids: set) -> None:
        if cls._normalize_text(target_id) in locked_ids:
            raise HTTPException(status_code=423, detail="目标已锁定，不能执行该操作")

    @classmethod
    def _results_from_body(cls, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = body.get("results") or body.get("selected_results") or []
        if isinstance(results, dict):
            results = [results]
        if not isinstance(results, list):
            return []
        return [item for item in results if isinstance(item, dict)]

    def _online_keywords(
        self,
        body: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> List[str]:
        manual_keyword = self._normalize_text(body.get("keyword"))
        media = body.get("media") if isinstance(body.get("media"), dict) else {}
        scope = self._normalize_text(body.get("scope")) or "auto"
        keywords = build_search_keywords(media, targets, scope)
        if manual_keyword:
            keywords = [manual_keyword, *[item for item in keywords if item != manual_keyword]]
        return keywords[:8]

    def _auto_search_keywords_for_entry(self, entry: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
        return self._auto_transfer_service().auto_search_keywords_for_entry(entry, target)
    def _auto_search_providers(self) -> List[str]:
        return self._auto_transfer_service().auto_search_providers()
    def _auto_search_write_subtitle(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_search_write_subtitle(
            entry,
            target,
            queue_rate_limited=queue_rate_limited,
            task_ids=task_ids,
        )
    def _auto_search_and_write_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_search_and_write_entry(entry)
    def _call_auto_search_write_subtitle(
        self,
        entry: Dict[str, Any],
        target: Dict[str, Any],
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            return self._auto_search_write_subtitle(
                entry,
                target,
                queue_rate_limited=queue_rate_limited,
                task_ids=task_ids,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return self._auto_search_write_subtitle(entry, target)

    def _auto_submit_ai_for_entry(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_submit_ai_for_entry(entry, target, reason)
    def _auto_process_transfer_entry(
        self,
        entry: Dict[str, Any],
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_process_transfer_entry(
            entry,
            queue_rate_limited=queue_rate_limited,
            task_ids=task_ids,
        )
    def _auto_task_result_key(self, entry: Dict[str, Any]) -> str:
        return self._normalize_text(entry.get("id")) or self._auto_transfer_entry_key(entry)

    def _auto_season_cache_key(self, entry: Dict[str, Any]) -> str:
        media_key = self._normalize_text(entry.get("media_key") or entry.get("tmdb_id") or entry.get("title"))
        season = self._safe_int(entry.get("season"), 0)
        if not media_key or not season:
            return ""
        return self._hash_text(f"{media_key}|s{season:02d}")[:20]

    def _auto_season_cache_dir(self, cache_key: str) -> Path:
        return self.get_data_path() / "auto_season_packages" / cache_key

    def _auto_prepared_items_for_targets(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._auto_transfer_service().auto_prepared_items_for_targets(prepared_uploads, targets)
    @classmethod
    def _auto_language_bucket(cls, suffix: Any) -> str:
        return auto_language_bucket(suffix)

    def _auto_subtitle_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, int, str]:
        language_priority = list(getattr(self, "_auto_subtitle_language_priority", None) or self._default_auto_language_priority)
        format_priority = list(getattr(self, "_auto_subtitle_format_priority", None) or self._default_auto_format_priority)
        return auto_subtitle_sort_key(
            item,
            language_priority=language_priority,
            format_priority=format_priority,
        )

    def _select_auto_subtitle_items(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._auto_transfer_service().select_auto_subtitle_items(prepared_uploads, targets)
    def _auto_write_prepared_uploads_for_entries(
        self,
        *,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        session_dir: Path,
        selected_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_write_prepared_uploads_for_entries(
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            session_dir=session_dir,
            selected_result=selected_result,
        )
    def _store_auto_season_package_cache(
        self,
        entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        selected_result: Dict[str, Any],
    ) -> None:
        return self._auto_transfer_service().store_auto_season_package_cache(
            entries,
            prepared_uploads,
            selected_result,
        )
    def _load_auto_season_package_cache(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._auto_transfer_service().load_auto_season_package_cache(entry)
    def _auto_write_from_season_cache(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_write_from_season_cache(entries)
    def _auto_search_write_season_package(
        self,
        entries: List[Dict[str, Any]],
        *,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._auto_transfer_service().auto_search_write_season_package(entries, task_ids=task_ids)
    def _auto_process_transfer_group(self, entries: List[Dict[str, Any]], task_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        return self._auto_transfer_service().auto_process_transfer_group(entries, task_ids=task_ids)
    def _process_transfer_auto_task_batch(self, tasks: List[Dict[str, Any]]) -> None:
        self._auto_transfer_service().process_transfer_auto_task_batch(tasks)

    def _process_transfer_auto_subtitles(self, entries: List[Dict[str, Any]]) -> None:
        self._auto_transfer_service().process_transfer_auto_subtitles(entries)

    @classmethod
    def _normalize_online_download_name(cls, name: str, content: bytes, result: Dict[str, Any]) -> str:
        return normalize_upload_download_name(
            name,
            content,
            result,
            subtitle_exts=cls._subtitle_exts,
            archive_exts=cls._archive_exts,
            normalize_text=cls._normalize_text,
            decode_preview_bytes=cls._decode_preview_bytes,
        )

    @staticmethod
    def _archive_suffix_from_content(content: bytes) -> str:
        return upload_archive_suffix_from_content(content)

    def _build_preview_response_from_uploads(
        self,
        *,
        session_id: str,
        target_ids: List[str],
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        unsupported_files: Optional[List[str]] = None,
        invalid_files: Optional[List[Dict[str, str]]] = None,
        source: str = "upload",
    ) -> Dict[str, Any]:
        unsupported_files = unsupported_files or []
        invalid_files = invalid_files or []
        targets = [self._target_from_entry(item) for item in target_entries]
        preview_items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            file_path = Path(prepared["stored_path"])
            raw_bytes = file_path.read_bytes()
            language_profile = self._detect_language_profile(prepared["source_name"], raw_bytes)
            preview_item = {
                "upload_id": prepared["upload_id"],
                "source_name": prepared["source_name"],
                "archive_name": prepared.get("archive_name", ""),
                "ext": prepared["ext"],
                "target_id": self._suggest_target(prepared, targets),
                "detected_label": language_profile["label"],
                "language_suffix": language_profile["suffix"],
                "online_source": prepared.get("online_source", ""),
            }
            preview_items.append(preview_item)

        self._auto_fill_missing_targets(preview_items, targets)
        target_lookup = {item["id"]: item for item in targets if item.get("id")}
        for item in preview_items:
            target = target_lookup.get(item.get("target_id"))
            item["output_name"] = self._build_destination_name(target, item) if target else ""

        session_payload = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_ids": list(target_ids),
            "targets": target_entries,
            "uploads": prepared_uploads,
            "source": source,
        }
        self._write_session(session_id, session_payload)

        resolved_count = len([item for item in preview_items if item.get("target_id")])
        message = f"已解析 {len(preview_items)} 个字幕文件，自动匹配 {resolved_count} 个。"
        if unsupported_files:
            message += f" 已忽略 {len(unsupported_files)} 个不支持的文件。"
        if invalid_files:
            message += f" 有 {len(invalid_files)} 个压缩包解析失败。"

        logger.info(
            "[SubtitleManualUpload] 预览生成完成 source=%s session=%s subtitles=%s resolved=%s unsupported=%s invalid=%s",
            source,
            session_id,
            len(preview_items),
            resolved_count,
            len(unsupported_files),
            len(invalid_files),
        )
        return self._ok(
            {
                "session_id": session_id,
                "source": source,
                "targets": targets,
                "items": preview_items,
                "unsupported_files": unsupported_files,
                "invalid_files": invalid_files,
            },
            message=message,
        )
    def api_status(self) -> Dict[str, Any]:
        rar_tool = self._rar_tool()
        rar_python = self._rar_python_available()
        return self._ok(
            {
                "enabled": self.get_state(),
                "auto_search_on_transfer": bool(self._auto_search_on_transfer),
                "auto_skip_chinese_media_on_transfer": bool(self._auto_skip_chinese_media_on_transfer),
                "auto_transfer_subtitle_strategy": self._auto_transfer_subtitle_strategy,
                "traditional_to_simplified": bool(self._traditional_to_simplified),
                "source": "MoviePilot 本地整理记录",
                "index": self._cache_status(),
                "archive_support": {
                    "zip": True,
                    "rar": bool(rar_tool),
                    "rar_tool": Path(rar_tool).name if rar_tool else "",
                    "rar_tool_path": rar_tool or self._rar_tool_path,
                    "rar_python": rar_python,
                    "rar_python_package": self._rar_python_package,
                    "dependency_mode": self._rar_dependency_mode,
                    "dependency_status": self._rar_dependency_status,
                },
                "timeline_fixer": {
                    **check_timeline_fixer_dependencies(),
                    "configured_max_offset_seconds": self._timeline_max_offset_seconds,
                    "configured_min_offset_seconds": self._timeline_min_offset_seconds,
                    "vad_mode": self._timeline_vad_mode,
                    "allow_risky_offset": bool(self._timeline_allow_risky_offset),
                },
                "online_search": {
                    "enabled_providers": self._online_provider_ids,
                    "assrt_api_configured": bool(self._assrt_api_key),
                    "assrt_api_host": self._host_from_url(self._assrt_api_url),
                    "opensubtitles_api_configured": bool(self._opensubtitles_api_key),
                    "opensubtitles_api_host": self._host_from_url(self._opensubtitles_api_url),
                    "opensubtitles_download_configured": bool(
                        self._opensubtitles_username and self._opensubtitles_password
                    ),
                },
                "auto_transfer_queue": self._auto_transfer_queue_summary(),
                "ai_subtitle": self._autosub_status(),
            }
        )

    def api_refresh_index(self) -> Dict[str, Any]:
        self._start_background_cache_refresh()
        cache_status = self._cache_status()
        has_cache = bool((self._local_entries_cache or {}).get("entries"))
        message = "媒体库资源清单已在后台刷新"
        if has_cache:
            message += "，当前页面先使用已有缓存"
        else:
            message += "，首次刷新完成前列表可能暂时为空"
        return self._ok(
            {
                "realtime": False,
                "background": True,
                "index": cache_status,
            },
            message=message,
        )

    def _existing_timeline_operations(
        self,
        requested_items: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self._subtitle_history().existing_timeline_operations(requested_items)

    def _run_existing_timeline_fix(
        self,
        session_dir: Path,
        operations: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> None:
        self._subtitle_writer().run_existing_timeline_fix(
            session_dir,
            operations,
            allow_risky_offset=allow_risky_offset,
        )

    async def api_timeline_fix_existing(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        requested_items = body.get("items") if isinstance(body, dict) else []
        allow_risky_offset = bool(body.get("allow_risky_offset")) if isinstance(body, dict) else False
        if not isinstance(requested_items, list) or not requested_items:
            raise HTTPException(status_code=400, detail="请先选择要调轴的历史字幕")
        locked_ids = self._locked_target_ids_from_body(body if isinstance(body, dict) else {})
        locked_skipped: List[Dict[str, str]] = []
        if locked_ids:
            filtered_items = []
            for item in requested_items:
                target_id = self._normalize_text((item or {}).get("target_id")) if isinstance(item, dict) else ""
                if target_id in locked_ids:
                    locked_skipped.append({"target_id": target_id, "reason": "目标已锁定"})
                    continue
                filtered_items.append(item)
            requested_items = filtered_items
        if not requested_items:
            return self._ok(
                {
                    "accepted": 0,
                    "skipped": locked_skipped,
                    "failed": [],
                    "summary": self._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                },
                message="没有可提交智能调轴的历史字幕，锁定项已跳过",
            )
        timeline_status = check_timeline_fixer_dependencies()
        if not timeline_status.get("available"):
            missing = [
                key
                for key, value in {
                    "ffmpeg": timeline_status.get("ffmpeg"),
                    "ffprobe": timeline_status.get("ffprobe"),
                    **(timeline_status.get("modules") or {}),
                }.items()
                if not value and key != "webrtcvad"
            ]
            raise HTTPException(status_code=409, detail=f"智能调轴不可用：缺少 {', '.join(missing) or '依赖'}")
        operations, skipped, failed = self._existing_timeline_operations(requested_items)
        skipped = [*locked_skipped, *skipped]
        if not operations:
            return self._ok(
                {
                    "accepted": 0,
                    "skipped": skipped,
                    "failed": failed,
                    "summary": self._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                },
                message="没有可提交智能调轴的历史字幕",
            )
        for operation in operations:
            self._set_timeline_task(operation, status="pending", message="等待历史字幕智能调轴")
        session_id = self._hash_text(f"existing-timeline|{datetime.now().isoformat()}|{len(operations)}")[:16]
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(
            target=self._run_existing_timeline_fix,
            args=(session_dir, operations, allow_risky_offset),
            name="SubtitleManualUploadExistingTimelineFix",
            daemon=True,
        ).start()
        target_entries = [operation["target_entry"] for operation in operations]
        task_data = self._timeline_tasks_for_entries(target_entries)
        return self._ok(
            {
                "accepted": len(operations),
                "skipped": skipped,
                "failed": failed,
                **task_data,
            },
            message=f"已提交 {len(operations)} 个历史字幕智能调轴任务，跳过 {len(skipped)} 个，失败 {len(failed)} 个",
        )

    async def api_ai_submit(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        locked_ids = self._locked_target_ids_from_body(body)
        target_ids, locked_skipped = self._filter_unlocked_target_ids(target_ids, locked_ids)
        if not target_ids:
            if locked_skipped:
                return self._ok(
                    {"added": [], "skipped": locked_skipped, "failed": [], "targets": [], "tasks": {}},
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有提交 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="请先选择要生成 AI 字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        autosub_bridge = self._autosub_bridge()
        source_policy = self._normalize_text(body.get("source_policy")) or "auto"
        if source_policy == "reuse":
            source_policy = "auto"
        source_subtitle_path = self._normalize_text(body.get("source_subtitle_path") or body.get("subtitle_path"))
        source_subtitle_lang = self._normalize_text(body.get("source_subtitle_lang") or body.get("lang"))
        overwrite_policy = self._normalize_text(body.get("overwrite_policy")) or ("new_variant" if source_policy != "auto" else "skip")
        if source_policy == "matched_external":
            if not source_subtitle_path:
                raise HTTPException(status_code=400, detail="请选择要用于 AI 生成的外挂 SRT 字幕")
            subtitle_overrides = autosub_bridge.selected_external_subtitle_override_for_entries(
                target_entries,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                overwrite_policy=overwrite_policy,
            )
            result = autosub_bridge.submit_autosub_for_entries(
                target_entries,
                subtitle_overrides=subtitle_overrides,
                trigger="manual",
                source_policy="matched_external",
                overwrite_policy=overwrite_policy,
            )
        else:
            result = autosub_bridge.submit_autosub_for_entries(
                target_entries,
                trigger="manual",
                source_policy=source_policy,
                overwrite_policy=overwrite_policy,
            )
        if locked_skipped:
            result["skipped"] = [*(result.get("skipped") or []), *locked_skipped]
        return self._ok(
            result,
            message=f"已提交 {len(result.get('added') or [])} 个 AI 字幕生成任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    async def api_online_ai_submit(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        locked_ids = self._locked_target_ids_from_body(body)
        allow_risky_offset = bool(body.get("allow_risky_offset")) if isinstance(body, dict) else False
        target_ids, locked_skipped = self._filter_unlocked_target_ids(target_ids, locked_ids)
        if not target_ids:
            if locked_skipped:
                raise HTTPException(status_code=423, detail="选中的目标均已锁定，不能提交在线字幕 AI 翻译")
            raise HTTPException(status_code=400, detail="请先选择要生成 AI 字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries or len(target_entries) != len(set(target_ids)):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        selected_results = self._results_from_body(body)
        if not selected_results:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕结果")
        online_ai_service = self._online_ai_service()
        return await run_in_threadpool(
            online_ai_service.submit_online_ai_translate,
            target_entries,
            selected_results,
            allow_risky_offset,
        )

    def _download_online_results_to_uploads(
        self,
        selected_results: List[Dict[str, Any]],
        session_dir: Path,
        upload_session: Optional[UploadSessionService] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, str]]]:
        upload_session = upload_session or self._upload_session_service()
        prepared_uploads: List[Dict[str, Any]] = []
        unsupported_files: List[str] = []
        invalid_files: List[Dict[str, str]] = []
        downloads = self._online_service().download(selected_results)
        for downloaded in downloads:
            result = downloaded.get("result") or {}
            source_name = upload_session.normalize_online_download_name(
                downloaded.get("source_name", ""),
                downloaded.get("content") or b"",
                result,
            )
            try:
                extracted = upload_session.extract_subtitle_files(
                    source_name,
                    downloaded.get("content") or b"",
                    session_dir,
                )
            except ValueError as exc:
                invalid_files.append({"name": source_name, "reason": str(exc)})
                continue
            if not extracted:
                unsupported_files.append(source_name)
                continue
            for item in extracted:
                item["online_source"] = downloaded.get("provider")
                item["online_title"] = result.get("title", "")
                if not item.get("archive_name") and source_name != item.get("source_name"):
                    item["archive_name"] = source_name
            prepared_uploads.extend(extracted)
        return prepared_uploads, unsupported_files, invalid_files

    @classmethod
    def _autosub_lang_from_suffix(cls, suffix: Any) -> str:
        return autosub_lang_from_suffix(suffix)

    def _online_ai_candidate_items(
        self,
        *,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._online_ai_service().online_ai_candidate_items(
            prepared_uploads=prepared_uploads,
            targets=targets,
        )

    @classmethod
    def _load_pysubs2_file(cls, path: Path):
        return OnlineAiService.load_pysubs2_file(path)

    def _convert_ass_to_ai_srt(
        self,
        *,
        session_dir: Path,
        prepared: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return self._online_ai_service().convert_ass_to_ai_srt(
            session_dir=session_dir,
            prepared=prepared,
        )

    def _ai_ready_prepared_uploads(
        self,
        *,
        session_dir: Path,
        prepared_uploads: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._online_ai_service().ai_ready_prepared_uploads(
            session_dir=session_dir,
            prepared_uploads=prepared_uploads,
        )

    def _prepare_online_ai_subtitle_overrides(
        self,
        *,
        session_dir: Path,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, Any]]]:
        return self._online_ai_service().prepare_online_ai_subtitle_overrides(
            session_dir=session_dir,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            allow_risky_offset=allow_risky_offset,
        )

    def _submit_online_ai_translate(
        self,
        target_entries: List[Dict[str, Any]],
        selected_results: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> Dict[str, Any]:
        return self._online_ai_service().submit_online_ai_translate(
            target_entries,
            selected_results,
            allow_risky_offset,
        )

    def _submit_autosub_for_entries(
        self,
        target_entries: List[Dict[str, Any]],
        subtitle_overrides: Optional[Dict[str, Dict[str, str]]] = None,
        *,
        trigger: str = "manual",
        source_policy: str = "auto",
        overwrite_policy: str = "skip",
    ) -> Dict[str, Any]:
        return self._autosub_bridge().submit_autosub_for_entries(
            target_entries,
            subtitle_overrides=subtitle_overrides,
            trigger=trigger,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
        )

    async def api_ai_cancel(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        locked_ids = self._locked_target_ids_from_body(body)
        target_ids, locked_skipped = self._filter_unlocked_target_ids(target_ids, locked_ids)
        if not target_ids:
            if locked_skipped:
                return self._ok(
                    {"cancelled": [], "skipped": locked_skipped, "targets": [], "tasks": {}},
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有取消 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="请先选择要取消的 AI 字幕任务")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        result = self._autosub_bridge().cancel_autosub_for_entries(target_entries)
        if locked_skipped:
            result["skipped"] = [*(result.get("skipped") or []), *locked_skipped]
        return self._ok(
            result,
            message=f"已取消 {len(result.get('cancelled') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    async def api_ai_restart(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        requested_target_ids = list(target_ids)
        task_ids = body.get("task_ids") or []
        if isinstance(task_ids, str):
            task_ids = [task_ids]
        task_ids = [self._normalize_text(item) for item in task_ids if self._normalize_text(item)] if isinstance(task_ids, list) else []
        locked_ids = self._locked_target_ids_from_body(body)
        target_ids, locked_skipped = self._filter_unlocked_target_ids(target_ids, locked_ids)
        if not target_ids and not task_ids:
            if locked_skipped:
                return self._ok(
                    {"added": [], "skipped": locked_skipped, "failed": [], "targets": [], "tasks": {}},
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有重新生成 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="请先选择要重新生成 AI 字幕的本地视频")
        if target_ids:
            target_entries = list(self._resolve_targets(target_ids).values())
        elif requested_target_ids:
            target_entries = []
        else:
            target_entries = self._cached_unlocked_targets(locked_ids)
        if requested_target_ids and not target_ids and locked_skipped:
            skipped = [
                {"task_id": task_id, "reason": "任务不属于当前可操作目标或目标已锁定"}
                for task_id in task_ids
            ]
            return self._ok(
                {
                    "added": [],
                    "skipped": [*locked_skipped, *skipped],
                    "failed": [],
                    "targets": [],
                    "tasks": {},
                },
                message=f"已跳过 {len(locked_skipped) + len(skipped)} 个锁定或不可操作的 AI 字幕任务",
            )
        if requested_target_ids and (not target_entries or len(target_entries) != len(set(target_ids))):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        if not target_entries:
            if task_ids:
                return self._ok(
                    {
                        "added": [],
                        "skipped": [{"task_id": task_id, "reason": "任务不属于当前可操作目标或目标已锁定"} for task_id in task_ids],
                        "failed": [],
                        "targets": [],
                        "tasks": {},
                    },
                    message=f"已跳过 {len(task_ids)} 个无法确认目标归属的 AI 字幕任务",
                )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        result = self._autosub_bridge().restart_autosub_for_entries(
            target_entries,
            source_policy=self._normalize_text(body.get("source_policy")) or "reuse",
            overwrite_policy=self._normalize_text(body.get("overwrite_policy")) or "backup_replace",
            source_subtitle_path=self._normalize_text(body.get("source_subtitle_path") or body.get("subtitle_path")),
            source_subtitle_lang=self._normalize_text(body.get("source_subtitle_lang") or body.get("lang")),
            task_ids=task_ids,
        )
        if locked_skipped:
            result["skipped"] = [*(result.get("skipped") or []), *locked_skipped]
        return self._ok(
            result,
            message=f"已重新提交 {len(result.get('added') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    def _cancel_autosub_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._autosub_bridge().cancel_autosub_for_entries(target_entries)

    def _restart_autosub_for_entries(
        self,
        target_entries: List[Dict[str, Any]],
        *,
        source_policy: str = "reuse",
        overwrite_policy: str = "backup_replace",
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._autosub_bridge().restart_autosub_for_entries(
            target_entries,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            task_ids=task_ids,
        )

    def _filter_restart_task_ids_by_targets(
        self,
        task_ids: List[str],
        tasks_data: Dict[str, Any],
        target_entries: List[Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        return self._autosub_bridge().filter_restart_task_ids_by_targets(
            task_ids,
            tasks_data,
            target_entries,
        )

    def _selected_external_subtitle_override_for_entries(
        self,
        target_entries: List[Dict[str, Any]],
        *,
        source_subtitle_path: str,
        source_subtitle_lang: str = "",
        overwrite_policy: str = "new_variant",
    ) -> Dict[str, Dict[str, Any]]:
        return self._autosub_bridge().selected_external_subtitle_override_for_entries(
            target_entries,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            overwrite_policy=overwrite_policy,
        )

    async def api_ai_tasks(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        autosub_bridge = self._autosub_bridge()
        if not target_ids:
            return self._ok(
                {
                    "status": autosub_bridge.autosub_status(),
                    "summary": bridge_autosub_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                    "tasks_by_target": {},
                }
            )
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        if len(target_entries) != len(set(target_ids)):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        return self._ok(autosub_bridge.autosub_tasks_for_entries(target_entries))

    async def api_timeline_tasks(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            return self._ok(
                {
                    "summary": self._timeline_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                }
            )
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        return self._ok(self._timeline_tasks_for_entries(target_entries))

    def api_auto_transfer_queue(self, request: Request) -> Dict[str, Any]:
        limit = min(max(self._safe_int(request.query_params.get("limit"), 100), 1), 200)
        return self._ok(self._auto_transfer_queue_snapshot(limit=limit))

    async def api_search(self, request: Request) -> Dict[str, Any]:
        keyword = self._normalize_text(request.query_params.get("keyword"))
        media_type = self._normalize_text(request.query_params.get("media_type")) or "all"
        page = max(self._safe_int(request.query_params.get("page"), 1), 1)
        page_size = min(max(self._safe_int(request.query_params.get("page_size") or request.query_params.get("limit"), 20), 1), 80)
        medias, total = await self._local_media_catalog().search_media_candidates(
            keyword=keyword,
            media_type=media_type,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        logger.info(
            "[SubtitleManualUpload] 本地资源搜索完成 keyword=%s media_type=%s page=%s size=%s result=%s total=%s",
            keyword or "<recent>",
            media_type,
            page,
            page_size,
            len(medias),
            total,
        )
        return self._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": page * page_size < total,
                "medias": medias,
            }
        )

    def api_match_history(self, request: Request) -> Dict[str, Any]:
        keyword = self._normalize_text(request.query_params.get("keyword"))
        media_type = self._normalize_text(request.query_params.get("media_type")) or "all"
        page = max(self._safe_int(request.query_params.get("page"), 1), 1)
        page_size = min(max(self._safe_int(request.query_params.get("page_size"), 20), 5), 80)
        items = self._match_history_items(keyword=keyword, media_type=media_type)
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return self._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": end < total,
                "items": items[start:end],
            }
        )

    def api_targets(self, request: Request) -> Dict[str, Any]:
        media_type = self._normalize_text(request.query_params.get("media_type"))
        tmdb_id = self._normalize_text(request.query_params.get("tmdb_id"))
        douban_id = self._normalize_text(request.query_params.get("douban_id"))
        title = self._normalize_text(request.query_params.get("title"))
        year = self._normalize_text(request.query_params.get("year"))
        season = self._normalize_text(request.query_params.get("season"))
        result = self._target_resolver().targets_for_media(
            media_type=media_type,
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            title=title,
            year=year,
            season=season,
        )
        logger.info(
            "[SubtitleManualUpload] 本地目标读取完成 media=%s year=%s type=%s season=%s targets=%s all_targets=%s",
            title or tmdb_id or douban_id,
            year or "-",
            media_type or "-",
            result.get("selected_season"),
            result.get("target_count"),
            result.get("all_target_count"),
        )
        return self._ok(result)

    def api_online_status(self) -> Dict[str, Any]:
        status = self._online_service().status()
        status["enabled_providers"] = self._online_provider_ids
        status["online_engine"] = self._online_engine
        status["provider_roots"] = self._online_site_urls
        status["assrt_api_configured"] = bool(self._assrt_api_key)
        status["assrt_api_host"] = self._host_from_url(self._assrt_api_url)
        status["opensubtitles_api_configured"] = bool(self._opensubtitles_api_key)
        status["opensubtitles_api_host"] = self._host_from_url(self._opensubtitles_api_url)
        status["opensubtitles_download_configured"] = bool(
            self._opensubtitles_username and self._opensubtitles_password
        )
        status["rate_limit_per_minute"] = self._online_rate_limit_per_minute
        return self._ok(status)

    async def api_online_manual_links(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [self._target_from_entry(item) for item in target_entries]
        keywords = self._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        providers = list(self._manual_online_provider_ids)
        links = self._online_service().manual_links(keywords, providers=providers)
        logger.info(
            "[SubtitleManualUpload] 在线字幕手动链接生成 target_count=%s keywords=%s providers=%s",
            len(targets),
            len(keywords),
            ",".join(providers),
        )
        return self._ok(
            {
                "keywords": keywords,
                "links": links,
            }
        )

    async def api_online_search(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [self._target_from_entry(item) for item in target_entries]
        keywords = self._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        requested_providers = body.get("providers") if isinstance(body.get("providers"), list) else self._online_provider_ids
        providers = self._normalize_provider_ids(requested_providers, fallback=not isinstance(body.get("providers"), list))
        if not providers:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕源")
        self._check_online_rate_limit(providers)
        scope = self._normalize_text(body.get("scope")) or "auto"
        service = self._online_service()
        search_result = await run_in_threadpool(
            service.search,
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope=scope,
        )
        manual_links = service.manual_links(keywords, providers=providers)
        logger.info(
            "[SubtitleManualUpload] 在线字幕搜索完成 scope=%s providers=%s targets=%s results=%s",
            scope,
            ",".join(providers),
            len(targets),
            len(search_result.get("results") or []),
        )
        return self._ok(
            {
                "keywords": keywords,
                "providers": providers,
                "targets": targets,
                "results": search_result.get("results") or [],
                "messages": search_result.get("messages") or [],
                "manual_links": manual_links,
            }
        )

    async def api_online_search_provider(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [self._target_from_entry(item) for item in target_entries]
        keywords = self._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        provider_id = self._normalize_text(body.get("provider"))
        providers = self._normalize_provider_ids([provider_id], fallback=False)
        if not providers:
            raise HTTPException(status_code=400, detail="未知或未启用的在线字幕源")
        self._check_online_rate_limit(providers)
        scope = self._normalize_text(body.get("scope")) or "auto"
        service = self._online_service()
        search_result = await run_in_threadpool(
            service.search,
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope=scope,
        )
        logger.info(
            "[SubtitleManualUpload] 在线字幕单源搜索完成 scope=%s provider=%s targets=%s results=%s",
            scope,
            providers[0],
            len(targets),
            len(search_result.get("results") or []),
        )
        return self._ok(
            {
                "keywords": keywords,
                "provider": providers[0],
                "providers": providers,
                "targets": targets,
                "results": search_result.get("results") or [],
                "messages": search_result.get("messages") or [],
            }
        )

    async def api_online_download_preview(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        locked_ids = self._locked_target_ids_from_body(body)
        target_ids, locked_skipped = self._filter_unlocked_target_ids(target_ids, locked_ids)
        if not target_ids:
            if locked_skipped:
                raise HTTPException(status_code=423, detail="选中的目标均已锁定，不能下载写入在线字幕")
            raise HTTPException(status_code=400, detail="请先选择要写入字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        if len(target_entries) != len(set(target_ids)):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        selected_results = self._results_from_body(body)
        if not selected_results:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕结果")
        submit_ai_translate = bool(body.get("submit_ai_translate"))
        allow_risky_offset = bool(body.get("allow_risky_offset")) if isinstance(body, dict) else False
        if submit_ai_translate:
            online_ai_service = self._online_ai_service()
            return await run_in_threadpool(
                online_ai_service.submit_online_ai_translate,
                target_entries,
                selected_results,
                allow_risky_offset,
            )
        self._check_online_rate_limit([item.get("provider") for item in selected_results if isinstance(item, dict)])

        upload_session = self._upload_session_service()
        session_id = self._hash_text(f"online|{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = upload_session.get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        try:
            prepared_uploads, unsupported_files, invalid_files = await run_in_threadpool(
                self._download_online_results_to_uploads,
                selected_results,
                session_dir,
                upload_session,
            )
        except CaptchaRequiredError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.warning("[SubtitleManualUpload] 在线字幕自动仿真下载失败 provider=%s message=%s", exc.provider, exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.warning("[SubtitleManualUpload] 在线字幕下载预览失败：%s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.error("[SubtitleManualUpload] 在线字幕下载预览异常: %s", exc)
            raise HTTPException(status_code=500, detail=f"在线字幕下载失败: {exc}") from exc

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{invalid_files[0]['reason']}")
            raise HTTPException(status_code=400, detail="没有解析到可用的在线字幕文件")

        logger.info(
            "[SubtitleManualUpload] 在线字幕下载完成 selected=%s prepared=%s unsupported=%s invalid=%s",
            len(selected_results),
            len(prepared_uploads),
            len(unsupported_files),
            len(invalid_files),
        )
        response = self._build_preview_response_from_uploads(
            session_id=session_id,
            target_ids=target_ids,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            unsupported_files=unsupported_files,
            invalid_files=invalid_files,
            source="online",
        )
        return response

    async def api_prepare_upload(self, request: Request) -> Dict[str, Any]:
        form = await request.form()
        target_ids_raw = self._normalize_text(form.get("target_ids"))
        if not target_ids_raw:
            logger.warning("[SubtitleManualUpload] 上传预览失败：未提供目标 target_ids")
            raise HTTPException(status_code=400, detail="请先选择目标电影或剧集")

        try:
            target_ids = json.loads(target_ids_raw)
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标参数格式错误 %s", exc)
            raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc
        if not isinstance(target_ids, list) or not target_ids:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：目标视频已失效 target_ids=%s",
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        upload_files = [item for item in form.getlist("files") if self._is_upload_file(item)]
        if not upload_files:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：未收到字幕文件 target_count=%s target_ids=%s",
                len(target_entries),
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="请至少上传一个字幕文件、ZIP 或 RAR")

        logger.info(
            "[SubtitleManualUpload] 开始上传预览 target_count=%s upload_files=%s target_ids=%s",
            len(target_entries),
            len(upload_files),
            self._brief_ids(target_ids),
        )

        upload_session = self._upload_session_service()
        session_id = self._hash_text(f"{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = upload_session.get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        prepared_uploads: List[Dict[str, Any]] = []
        unsupported_files: List[str] = []
        invalid_files: List[Dict[str, str]] = []
        for upload in upload_files:
            file_name = Path(self._normalize_text(upload.filename)).name
            if not file_name:
                continue
            raw_bytes = await upload.read()
            try:
                extracted = upload_session.extract_subtitle_files(file_name, raw_bytes, session_dir)
            except ValueError as exc:
                invalid_files.append(
                    {
                        "name": file_name,
                        "reason": str(exc),
                    }
                )
                continue
            if not extracted:
                unsupported_files.append(file_name)
                continue
            prepared_uploads.extend(extracted)

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                first_reason = invalid_files[0]["reason"]
                logger.warning(
                    "[SubtitleManualUpload] 上传预览失败：压缩包解析失败 invalid=%s unsupported=%s reason=%s",
                    len(invalid_files),
                    len(unsupported_files),
                    first_reason,
                )
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{first_reason}")
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：没有可用字幕 unsupported=%s",
                len(unsupported_files),
            )
            raise HTTPException(status_code=400, detail="没有解析到可用的字幕文件，请检查文件格式")

        return self._build_preview_response_from_uploads(
            session_id=session_id,
            target_ids=target_ids,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            unsupported_files=unsupported_files,
            invalid_files=invalid_files,
            source="upload",
        )

    async def api_apply_upload(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        session_id = self._normalize_text(body.get("session_id"))
        items = body.get("items") or []
        fix_timeline = bool(body.get("fix_timeline"))
        allow_risky_offset = bool(body.get("allow_risky_offset"))
        if not session_id or not isinstance(items, list) or not items:
            logger.warning("[SubtitleManualUpload] 写入失败：缺少会话或匹配结果 session=%s", session_id or "-")
            raise HTTPException(status_code=400, detail="缺少上传会话或匹配结果")
        locked_ids = self._locked_target_ids_from_body(body)
        locked_skipped: List[Dict[str, str]] = []
        if locked_ids:
            filtered_items = []
            for item in items:
                target_id = self._normalize_text((item or {}).get("target_id")) if isinstance(item, dict) else ""
                if target_id in locked_ids:
                    locked_skipped.append({"target_id": target_id, "reason": "目标已锁定"})
                    continue
                filtered_items.append(item)
            items = filtered_items
        if not items:
            return self._ok(
                {
                    "count": 0,
                    "written": [],
                    "skipped": locked_skipped,
                },
                message="没有写入字幕，锁定项已跳过",
            )

        payload, message = self._subtitle_writer().apply_upload_session(
            session_id=session_id,
            items=items,
            locked_skipped=locked_skipped,
            fix_timeline=fix_timeline,
            allow_risky_offset=allow_risky_offset,
        )

        return self._ok(payload, message=message)

    async def api_clear_subtitles(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        locked_ids = self._locked_target_ids_from_body(body)
        target_ids, locked_skipped = self._filter_unlocked_target_ids(target_ids, locked_ids)

        if not target_ids:
            if locked_skipped:
                return self._ok(
                    {
                        "count": 0,
                        "deleted": [],
                        "failed": locked_skipped,
                    },
                    message=f"已跳过 {len(locked_skipped)} 个锁定目标，没有删除外挂字幕",
                )
            logger.warning("[SubtitleManualUpload] 清空外挂字幕失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = self._resolve_targets(target_ids)
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 清空外挂字幕失败：目标视频已失效 target_ids=%s",
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        payload, message = self._subtitle_writer().clear_subtitles(
            target_ids,
            target_entries,
            locked_skipped,
        )

        logger.info(
            "[SubtitleManualUpload] 清空外挂字幕完成 targets=%s deleted=%s failed=%s",
            len(target_ids),
            len(payload.get("deleted") or []),
            len(payload.get("failed") or []),
        )

        return self._ok(payload, message=message)

    async def api_delete_subtitle(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_id = self._normalize_text(body.get("target_id"))
        subtitle_path_raw = self._normalize_text(body.get("subtitle_path"))
        subtitle_name = self._normalize_text(body.get("subtitle_name"))
        self._ensure_target_not_locked(target_id, self._locked_target_ids_from_body(body))
        if not target_id:
            raise HTTPException(status_code=400, detail="请先选择目标视频")
        if not subtitle_path_raw and not subtitle_name:
            raise HTTPException(status_code=400, detail="请指定要删除的字幕")

        target_entries = self._resolve_targets([target_id])
        target_entry = target_entries.get(target_id)
        if not target_entry:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        payload, message = self._subtitle_writer().delete_subtitle(
            target_id=target_id,
            target_entry=target_entry,
            subtitle_path_raw=subtitle_path_raw,
            subtitle_name=subtitle_name,
        )

        logger.info(
            "[SubtitleManualUpload] 删除单个外挂字幕完成 target=%s subtitle=%s",
            target_id[:8],
            (payload.get("deleted") or {}).get("name"),
        )
        return self._ok(payload, message=message)

    async def api_restore_subtitle_backup(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_id = self._normalize_text(body.get("target_id"))
        subtitle_path_raw = self._normalize_text(body.get("subtitle_path"))
        subtitle_name = self._normalize_text(body.get("subtitle_name"))
        self._ensure_target_not_locked(target_id, self._locked_target_ids_from_body(body))
        if not target_id:
            raise HTTPException(status_code=400, detail="请先选择目标视频")
        if not subtitle_path_raw and not subtitle_name:
            raise HTTPException(status_code=400, detail="请指定要恢复的字幕")

        target_entries = self._resolve_targets([target_id])
        target_entry = target_entries.get(target_id)
        if not target_entry:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        payload, message = self._subtitle_writer().restore_subtitle_backup(
            target_id=target_id,
            target_entry=target_entry,
            subtitle_path_raw=subtitle_path_raw,
            subtitle_name=subtitle_name,
        )
        return self._ok(payload, message=message)
