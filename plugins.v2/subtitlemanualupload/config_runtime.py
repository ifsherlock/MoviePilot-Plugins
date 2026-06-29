from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Mapping


RUNTIME_CONFIG_FIELDS = (
    ("_enabled", "enabled"),
    ("_show_sidebar_nav", "show_sidebar_nav"),
    ("_rar_dependency_mode", "rar_dependency_mode"),
    ("_rar_tool_path", "rar_tool_path"),
    ("_online_provider_ids", "online_providers"),
    ("_online_engine", "online_engine"),
    ("_online_use_proxy", "online_use_proxy"),
    ("_online_site_urls", "online_site_urls"),
    ("_assrt_api_key", "assrt_api_key"),
    ("_assrt_api_url", "assrt_api_url"),
    ("_opensubtitles_api_key", "opensubtitles_api_key"),
    ("_opensubtitles_api_url", "opensubtitles_api_url"),
    ("_opensubtitles_username", "opensubtitles_username"),
    ("_opensubtitles_password", "opensubtitles_password"),
    ("_ai_link_enabled", "ai_link_enabled"),
    ("_traditional_to_simplified", "traditional_to_simplified"),
    ("_auto_search_on_transfer", "auto_search_on_transfer"),
    ("_auto_skip_chinese_media_on_transfer", "auto_skip_chinese_media_on_transfer"),
    ("_auto_transfer_subtitle_strategy", "auto_transfer_subtitle_strategy"),
    ("_trust_transfer_history_paths", "trust_transfer_history_paths"),
    ("_auto_multi_subtitle_mode", "auto_multi_subtitle_mode"),
    ("_auto_subtitle_language_priority", "auto_subtitle_language_priority"),
    ("_auto_subtitle_format_priority", "auto_subtitle_format_priority"),
    ("_auto_ass_to_srt_for_ai", "auto_ass_to_srt_for_ai"),
    ("_timeline_max_offset_seconds", "timeline_max_offset_seconds"),
    ("_timeline_min_offset_seconds", "timeline_min_offset_seconds"),
    ("_timeline_vad_mode", "timeline_vad_mode"),
    ("_timeline_allow_risky_offset", "timeline_allow_risky_offset"),
)

CLASS_RUNTIME_CONFIG_FIELDS = (
    "_rar_dependency_mode",
    "_rar_tool_path",
    "_traditional_to_simplified",
    "_auto_search_on_transfer",
    "_auto_skip_chinese_media_on_transfer",
    "_auto_transfer_subtitle_strategy",
    "_trust_transfer_history_paths",
    "_auto_multi_subtitle_mode",
    "_auto_subtitle_language_priority",
    "_auto_subtitle_format_priority",
    "_auto_ass_to_srt_for_ai",
    "_timeline_max_offset_seconds",
    "_timeline_min_offset_seconds",
    "_timeline_vad_mode",
    "_timeline_allow_risky_offset",
)


def apply_runtime_config(owner: Any, normalized_config: Mapping[str, Any]) -> None:
    for attribute, key in RUNTIME_CONFIG_FIELDS:
        setattr(owner, attribute, normalized_config[key])


def sync_class_runtime_config(owner_cls: type, owner: Any) -> None:
    for attribute in CLASS_RUNTIME_CONFIG_FIELDS:
        setattr(owner_cls, attribute, getattr(owner, attribute))


def reset_runtime_state(owner: Any) -> None:
    owner._entry_map = OrderedDict()
    owner._media_index_cache = OrderedDict()
    owner._match_history_cache = {"loaded_at": None, "signature": "", "items": [], "entry_count": 0, "persisted": False}
    owner._timeline_tasks = OrderedDict()
    owner._transfer_auto_recent = {}
    owner._transfer_auto_lock = threading.Lock()
    owner._auto_transfer_tasks = OrderedDict()
    owner._auto_transfer_worker = None
    owner._auto_transfer_stopping = False
    owner._auto_season_package_cache = OrderedDict()
    owner._cache_refreshing = False
    owner._cache_refresh_started_at = ""
    owner._cache_refresh_completed_at = ""
    owner._cache_refresh_error = ""
    owner._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
