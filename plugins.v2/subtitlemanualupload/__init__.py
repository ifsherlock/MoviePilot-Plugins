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
from .autosub_bridge import AutoSubBridge
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
from .api.routes import build_api_routes


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
        return build_api_routes(self)

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
