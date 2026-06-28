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
from .compat import SubtitleManualUploadCompatMixin


class SubtitleManualUpload(SubtitleManualUploadCompatMixin, _PluginBase):
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
        queued, skipped = self._auto_transfer_service().enqueue_transfer_auto_entries(entries)
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
        return self._ok(self._auto_transfer_service().auto_transfer_queue_snapshot(limit=limit))

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
