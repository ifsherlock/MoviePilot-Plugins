from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
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
    check_online_rate_limit,
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
from .config_runtime import (
    apply_runtime_config,
    build_save_config_payload,
    reset_runtime_state,
    sync_class_runtime_config,
)
from .runtime_helpers import (
    apply_tmdb_detail as runtime_apply_tmdb_detail,
    brief_ids as runtime_brief_ids,
    cache_loaded_at as runtime_cache_loaded_at,
    decode_preview_bytes as runtime_decode_preview_bytes,
    entry_filesystem_signature as runtime_entry_filesystem_signature,
    entry_matches_keyword as runtime_entry_matches_keyword,
    entry_path_is_valid as runtime_entry_path_is_valid,
    extract_episode_hint as runtime_extract_episode_hint,
    hash_text as runtime_hash_text,
    is_stream_path as runtime_is_stream_path,
    is_upload_file as runtime_is_upload_file,
    json_clone as runtime_json_clone,
    media_type_text as runtime_media_type_text,
    normalize_text as runtime_normalize_text,
    ok_response,
    poster_url as runtime_poster_url,
    safe_int as runtime_safe_int,
    timestamp_iso as runtime_timestamp_iso,
    tmdb_aliases as runtime_tmdb_aliases,
    tmdb_detail_payload as runtime_tmdb_detail_payload,
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
)
from .timeline_tasks import timeline_task_summary
from .auto_transfer import AutoTransferService
from .service_registry import SubtitleManualUploadServices
from .api.routes import build_api_routes


class SubtitleManualUpload(_PluginBase):
    plugin_name = "字幕匹配"
    plugin_desc = "手动上传字幕、ZIP 或 RAR，匹配电影/剧集并按媒体文件名落盘，可选智能调轴。"
    plugin_icon = "https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/icons/subtitle-match.png"
    plugin_version = "0.1.73"
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
        apply_runtime_config(self, normalized_config)
        if (config or {}).get("opensubtitles_username") and "@" in self._normalize_text((config or {}).get("opensubtitles_username")):
            logger.warning("[SubtitleManualUpload] OpenSubtitles 用户名疑似邮箱，已忽略下载认证用户名")
        sync_class_runtime_config(type(self), self)
        reset_runtime_state(self)
        self.services.local_media_catalog().restore_persisted_local_cache()
        self.services.history().restore_persisted_match_history_cache()
        self._save_config()
        self._prepare_rar_dependency()
        self.services.upload_session().cleanup_old_sessions()

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

    @classmethod
    def _host_module_value(cls, name: str, default: Any) -> Any:
        module = sys.modules.get(cls.__module__)
        return getattr(module, name, default) if module is not None else default

    def _ok(self, data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return ok_response(data, message)

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        return runtime_safe_int(value, default)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return runtime_normalize_text(value)

    @staticmethod
    def _hash_text(value: str) -> str:
        return runtime_hash_text(value)

    @classmethod
    def _brief_ids(cls, values: Iterable[Any], limit: int = 5) -> str:
        return runtime_brief_ids(values, limit)

    @staticmethod
    def _decode_preview_bytes(raw_bytes: bytes) -> str:
        return runtime_decode_preview_bytes(raw_bytes)

    @classmethod
    def _normalize_auto_transfer_subtitle_strategy(cls, value: Any) -> str:
        return normalize_auto_transfer_subtitle_strategy(value)

    def _check_online_rate_limit(self, providers: Iterable[str]) -> None:
        check_online_rate_limit(
            providers,
            records=self._online_rate_records,
            limit_per_minute=self._online_rate_limit_per_minute,
            now=self._host_module_value("time", time).time(),
            normalize_text=self._normalize_text,
            http_exception=HTTPException,
        )

    @classmethod
    def _entry_path_is_valid(cls, entry: Dict[str, Any]) -> bool:
        return runtime_entry_path_is_valid(
            entry,
            trust_transfer_history_paths=getattr(cls, "_trust_transfer_history_paths", False),
        )

    @classmethod
    def _entry_filesystem_signature(cls, entry: Dict[str, Any]) -> str:
        return runtime_entry_filesystem_signature(entry)

    @staticmethod
    def _timestamp_iso(ts: Any) -> str:
        return runtime_timestamp_iso(ts)

    def _set_rar_dependency_status(self, state: str, message: str) -> None:
        self._rar_dependency_status = type(self)._archive_dependency_service().dependency_status(state, message)

    def _prepare_rar_dependency(self) -> None:
        type(self)._archive_dependency_service(self._set_rar_dependency_status).prepare_rar_dependency()

    @classmethod
    def _normalize_language_suffix(cls, value: Any) -> str:
        return normalize_language_suffix(value)

    @classmethod
    def _detect_language_profile(cls, file_name: str, raw_bytes: bytes) -> Dict[str, Any]:
        return detect_language_profile(file_name, raw_bytes, cls._subtitle_exts)

    @classmethod
    def _extract_episode_hint(cls, file_name: str) -> Optional[Dict[str, int]]:
        return runtime_extract_episode_hint(file_name)

    @classmethod
    def _media_type_text(cls, value: Any) -> str:
        return runtime_media_type_text(value)

    @classmethod
    def _poster_url(cls, poster_path: Any, prefix: str = "w500") -> str:
        return runtime_poster_url(
            poster_path,
            prefix,
            settings_obj=settings,
        )

    @classmethod
    def _cache_loaded_at(cls, value: Any) -> Optional[datetime]:
        return runtime_cache_loaded_at(value)

    @staticmethod
    def _json_clone(value: Any) -> Any:
        return runtime_json_clone(value)

    @staticmethod
    def _timeline_task_summary(tasks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        return timeline_task_summary(tasks)

    @staticmethod
    def _autosub_task_summary(tasks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        return bridge_autosub_task_summary(tasks)

    @classmethod
    def _entry_matches_keyword(cls, entry: Dict[str, Any], keyword: str) -> bool:
        return runtime_entry_matches_keyword(
            entry,
            keyword,
        )

    @classmethod
    def _tmdb_detail_payload(cls, detail: Any) -> Dict[str, Any]:
        return runtime_tmdb_detail_payload(
            detail,
            extract_title_aliases_func=extract_title_aliases,
        )

    @classmethod
    def _tmdb_aliases(cls, *values: Any) -> List[str]:
        return runtime_tmdb_aliases(*values, extract_title_aliases_func=extract_title_aliases)

    @classmethod
    def _apply_tmdb_detail(cls, target: Dict[str, Any], detail: Dict[str, Any]) -> None:
        runtime_apply_tmdb_detail(target, detail)

    @classmethod
    def _is_stream_path(cls, path: Any) -> bool:
        return runtime_is_stream_path(path, stream_exts=cls._stream_exts)

    @staticmethod
    def _is_upload_file(value: Any) -> bool:
        return runtime_is_upload_file(value, upload_file_type=UploadFile)

    @staticmethod
    def _timeline_result_blocks_auto_write(result: TimelineFixResult) -> bool:
        return writer_timeline_result_blocks_auto_write(result)

    @staticmethod
    def _timeline_rejection_message(result: TimelineFixResult) -> str:
        return writer_timeline_rejection_message(result)

    @classmethod
    def _subtitle_backup_path(cls, subtitle_path: Path) -> Path:
        return writer_subtitle_backup_path(subtitle_path)

    @property
    def services(self) -> SubtitleManualUploadServices:
        registry = getattr(self, "_services_registry", None)
        if registry is None:
            registry = SubtitleManualUploadServices(self)
            self._services_registry = registry
        return registry

    @classmethod
    def _archive_dependency_service(cls, status_setter=None):
        return SubtitleManualUploadServices(cls).archive_dependency(status_setter=status_setter)

    @classmethod
    def _upload_session_service_for_path(cls, data_path: Path):
        return SubtitleManualUploadServices(cls).upload_session_for_path(data_path)

    @classmethod
    def _subtitle_inventory(cls):
        return SubtitleManualUploadServices(cls).subtitle_inventory()

    def _upload_session_service(self):
        return self.services.upload_session()

    def _subtitle_writer(self):
        return self.services.writer()

    def _subtitle_history(self):
        return self.services.history()

    def _autosub_bridge(self):
        return self.services.autosub_bridge()

    def _online_ai_service(self):
        return self.services.online_ai()

    def _auto_transfer_service(self):
        return self.services.auto_transfer()

    def _target_resolver(self):
        return self.services.target_resolver()

    def _local_media_catalog(self):
        return self.services.local_media_catalog()

    def _media_metadata_service(self):
        return self.services.media_metadata()

    def _timeline_task_store(self):
        return self.services.timeline_tasks()

    def _online_service(self):
        return self.services.online_subtitles()

    def _build_entry_from_history(self, *args, **kwargs):
        return self._target_resolver().build_entry_from_history(*args, **kwargs)

    def _merge_seasons(self, *args, **kwargs):
        return self._target_resolver().merge_seasons(*args, **kwargs)

    def _target_from_entry(self, *args, **kwargs):
        return self._target_resolver().target_from_entry(*args, **kwargs)

    def _tmdb_detail_for_media(self, *args, **kwargs):
        return self._media_metadata_service().tmdb_detail_for_media(*args, **kwargs)

    def _restore_persisted_match_history_cache(self, *args, **kwargs):
        return self._subtitle_history().restore_persisted_match_history_cache(*args, **kwargs)

    def _invalidate_match_history_cache(self, *args, **kwargs):
        return self._subtitle_history().invalidate_match_history_cache(*args, **kwargs)

    def _set_timeline_task(self, *args, **kwargs):
        return self._timeline_task_store().set_task(*args, **kwargs)

    def _timeline_tasks_for_entries(self, *args, **kwargs):
        return self._timeline_task_store().tasks_for_entries(*args, **kwargs)

    def _autosub_plugin(self, *args, **kwargs):
        return self._autosub_bridge().autosub_plugin(*args, **kwargs)

    def _autosub_tasks_for_entries(self, *args, **kwargs):
        return self._autosub_bridge().autosub_tasks_for_entries(*args, **kwargs)

    def _cleanup_old_sessions(self, *args, **kwargs):
        return self._upload_session_service().cleanup_old_sessions(*args, **kwargs)

    def _write_session(self, *args, **kwargs):
        return self._upload_session_service().write_session(*args, **kwargs)

    def _remove_ext_marks(self, *args, **kwargs):
        return self._subtitle_inventory().remove_ext_marks(*args, **kwargs)

    def _run_timeline_fix(self, *args, **kwargs):
        return self._subtitle_writer().run_timeline_fix(*args, **kwargs)

    def _transfer_auto_key(self, *args, **kwargs):
        return self._auto_transfer_service().transfer_auto_key(*args, **kwargs)

    def _claim_transfer_auto_entries(self, *args, **kwargs):
        return self._auto_transfer_service().claim_transfer_auto_entries(*args, **kwargs)

    def _auto_transfer_entry_key(self, *args, **kwargs):
        return self._auto_transfer_service().auto_transfer_entry_key(*args, **kwargs)

    def _auto_transfer_group_key(self, *args, **kwargs):
        return self._auto_transfer_service().auto_transfer_group_key(*args, **kwargs)

    def _trim_auto_transfer_tasks_locked(self, *args, **kwargs):
        return self._auto_transfer_service().trim_auto_transfer_tasks_locked(*args, **kwargs)

    def _ensure_transfer_auto_worker(self, *args, **kwargs):
        return self._auto_transfer_service().ensure_transfer_auto_worker(*args, **kwargs)

    def _update_auto_transfer_task(self, *args, **kwargs):
        return self._auto_transfer_service().update_auto_transfer_task(*args, **kwargs)

    def _claim_next_auto_transfer_batch(self, *args, **kwargs):
        return self._auto_transfer_service().claim_next_auto_transfer_batch(*args, **kwargs)

    def _auto_wait_online_rate_limit(self, *args, **kwargs):
        return self._auto_transfer_service().auto_wait_online_rate_limit(*args, **kwargs)

    def _auto_transfer_rate_status(self, *args, **kwargs):
        return self._auto_transfer_service().auto_transfer_rate_status(*args, **kwargs)

    def _auto_transfer_queue_loop(self, *args, **kwargs):
        return self._auto_transfer_service().auto_transfer_queue_loop(*args, **kwargs)

    def _auto_search_keywords_for_entry(self, *args, **kwargs):
        return self._auto_transfer_service().auto_search_keywords_for_entry(*args, **kwargs)

    def _auto_search_providers(self, *args, **kwargs):
        return self._auto_transfer_service().auto_search_providers(*args, **kwargs)

    def _auto_search_write_subtitle(self, *args, **kwargs):
        return self._auto_transfer_service().auto_search_write_subtitle(*args, **kwargs)

    def _auto_submit_ai_for_entry(self, *args, **kwargs):
        return self._auto_transfer_service().auto_submit_ai_for_entry(*args, **kwargs)

    def _auto_process_transfer_entry(self, *args, **kwargs):
        return self._auto_transfer_service().auto_process_transfer_entry(*args, **kwargs)

    def _auto_prepared_items_for_targets(self, *args, **kwargs):
        return self._auto_transfer_service().auto_prepared_items_for_targets(*args, **kwargs)

    def _select_auto_subtitle_items(self, *args, **kwargs):
        return self._auto_transfer_service().select_auto_subtitle_items(*args, **kwargs)

    def _auto_write_prepared_uploads_for_entries(self, *args, **kwargs):
        return self._auto_transfer_service().auto_write_prepared_uploads_for_entries(*args, **kwargs)

    def _store_auto_season_package_cache(self, *args, **kwargs):
        return self._auto_transfer_service().store_auto_season_package_cache(*args, **kwargs)

    def _load_auto_season_package_cache(self, *args, **kwargs):
        return self._auto_transfer_service().load_auto_season_package_cache(*args, **kwargs)

    def _auto_write_from_season_cache(self, *args, **kwargs):
        return self._auto_transfer_service().auto_write_from_season_cache(*args, **kwargs)

    def _auto_search_write_season_package(self, *args, **kwargs):
        return self._auto_transfer_service().auto_search_write_season_package(*args, **kwargs)

    def _auto_process_transfer_group(self, *args, **kwargs):
        return self._auto_transfer_service().auto_process_transfer_group(*args, **kwargs)

    def _process_transfer_auto_task_batch(self, *args, **kwargs):
        return self._auto_transfer_service().process_transfer_auto_task_batch(*args, **kwargs)

    def stop_service(self):
        self.services.auto_transfer().stop()

    @eventmanager.register(EventType.TransferComplete)
    def listen_transfer_complete(self, event: MPEvent):
        if not self.get_state() or not self._auto_search_on_transfer:
            return
        self.services.auto_transfer().handle_transfer_complete(event)

    def _save_config(self) -> None:
        self.update_config(build_save_config_payload(self))

    @classmethod
    def _autosub_lang_from_suffix(cls, suffix: Any) -> str:
        return autosub_lang_from_suffix(suffix)

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
