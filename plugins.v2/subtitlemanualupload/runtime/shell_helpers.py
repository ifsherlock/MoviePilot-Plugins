from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..integrations.autosub_bridge import autosub_task_summary as bridge_autosub_task_summary
from ..config.config_schema import normalize_auto_transfer_subtitle_strategy
from ..online.online_subtitle import check_online_rate_limit, extract_title_aliases
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
from .service_registry import SubtitleManualUploadServices
from ..matching.subtitle_language import detect_language_profile, normalize_language_suffix
from ..matching.subtitle_writer import (
    subtitle_backup_path as writer_subtitle_backup_path,
    timeline_rejection_message as writer_timeline_rejection_message,
    timeline_result_blocks_auto_write as writer_timeline_result_blocks_auto_write,
)
from ..timeline.timeline_tasks import timeline_task_summary


def _service_accessor(service_name: str):
    def accessor(self):
        return getattr(self.services, service_name)()

    return accessor


def _service_delegate(service_name: str, method_name: str):
    def delegate(self, *args, **kwargs):
        return getattr(getattr(self.services, service_name)(), method_name)(*args, **kwargs)

    return delegate


def install_shell_helpers(cls, *, upload_file_type: Any, http_exception: Any, settings_obj: Any) -> None:
    def host_module_value(owner_cls, name: str, default: Any) -> Any:
        module = sys.modules.get(owner_cls.__module__)
        return getattr(module, name, default) if module is not None else default

    def ok(self, data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return ok_response(data, message)

    def shell_check_online_rate_limit(self, providers: Iterable[str]) -> None:
        check_online_rate_limit(
            providers,
            records=self._online_rate_records,
            limit_per_minute=self._online_rate_limit_per_minute,
            now=self._host_module_value("time", time).time(),
            normalize_text=self._normalize_text,
            http_exception=http_exception,
        )

    def entry_path_is_valid(owner_cls, entry: Dict[str, Any]) -> bool:
        return runtime_entry_path_is_valid(
            entry,
            trust_transfer_history_paths=getattr(owner_cls, "_trust_transfer_history_paths", False),
        )

    def shell_detect_language_profile(owner_cls, file_name: str, raw_bytes: bytes) -> Dict[str, Any]:
        return detect_language_profile(file_name, raw_bytes, owner_cls._subtitle_exts)

    def poster_url(owner_cls, poster_path: Any, prefix: str = "w500") -> str:
        return runtime_poster_url(poster_path, prefix, settings_obj=settings_obj)

    def tmdb_detail_payload(owner_cls, detail: Any) -> Dict[str, Any]:
        return runtime_tmdb_detail_payload(detail, extract_title_aliases_func=extract_title_aliases)

    def tmdb_aliases(owner_cls, *values: Any) -> List[str]:
        return runtime_tmdb_aliases(*values, extract_title_aliases_func=extract_title_aliases)

    def is_stream_path(owner_cls, path: Any) -> bool:
        return runtime_is_stream_path(path, stream_exts=owner_cls._stream_exts)

    def is_upload_file(value: Any) -> bool:
        return runtime_is_upload_file(value, upload_file_type=upload_file_type)

    def set_rar_dependency_status(self, state: str, message: str) -> None:
        self._rar_dependency_status = type(self)._archive_dependency_service().dependency_status(state, message)

    def prepare_rar_dependency(self) -> None:
        type(self)._archive_dependency_service(self._set_rar_dependency_status).prepare_rar_dependency()

    def archive_dependency_service(owner_cls, status_setter=None):
        return SubtitleManualUploadServices(owner_cls).archive_dependency(status_setter=status_setter)

    def upload_session_service_for_path(owner_cls, data_path: Path):
        return SubtitleManualUploadServices(owner_cls).upload_session_for_path(data_path)

    def subtitle_inventory(owner_cls):
        return SubtitleManualUploadServices(owner_cls).subtitle_inventory()

    runtime_static_methods = {
        "_safe_int": runtime_safe_int,
        "_normalize_text": runtime_normalize_text,
        "_hash_text": runtime_hash_text,
        "_brief_ids": runtime_brief_ids,
        "_decode_preview_bytes": runtime_decode_preview_bytes,
        "_normalize_auto_transfer_subtitle_strategy": normalize_auto_transfer_subtitle_strategy,
        "_entry_filesystem_signature": runtime_entry_filesystem_signature,
        "_timestamp_iso": runtime_timestamp_iso,
        "_normalize_language_suffix": normalize_language_suffix,
        "_extract_episode_hint": runtime_extract_episode_hint,
        "_media_type_text": runtime_media_type_text,
        "_cache_loaded_at": runtime_cache_loaded_at,
        "_json_clone": runtime_json_clone,
        "_timeline_task_summary": timeline_task_summary,
        "_autosub_task_summary": bridge_autosub_task_summary,
        "_entry_matches_keyword": runtime_entry_matches_keyword,
        "_apply_tmdb_detail": runtime_apply_tmdb_detail,
        "_is_upload_file": is_upload_file,
        "_timeline_result_blocks_auto_write": writer_timeline_result_blocks_auto_write,
        "_timeline_rejection_message": writer_timeline_rejection_message,
        "_subtitle_backup_path": writer_subtitle_backup_path,
    }
    class_methods = {
        "_host_module_value": host_module_value,
        "_entry_path_is_valid": entry_path_is_valid,
        "_detect_language_profile": shell_detect_language_profile,
        "_poster_url": poster_url,
        "_tmdb_detail_payload": tmdb_detail_payload,
        "_tmdb_aliases": tmdb_aliases,
        "_is_stream_path": is_stream_path,
        "_archive_dependency_service": archive_dependency_service,
        "_upload_session_service_for_path": upload_session_service_for_path,
        "_subtitle_inventory": subtitle_inventory,
    }
    instance_methods = {
        "_ok": ok,
        "_check_online_rate_limit": shell_check_online_rate_limit,
        "_set_rar_dependency_status": set_rar_dependency_status,
        "_prepare_rar_dependency": prepare_rar_dependency,
    }
    service_accessors = {
        "_upload_session_service": "upload_session",
        "_subtitle_writer": "writer",
        "_subtitle_history": "history",
        "_autosub_bridge": "autosub_bridge",
        "_online_ai_service": "online_ai",
        "_auto_transfer_service": "auto_transfer",
        "_target_resolver": "target_resolver",
        "_local_media_catalog": "local_media_catalog",
        "_media_metadata_service": "media_metadata",
        "_timeline_task_store": "timeline_tasks",
        "_online_service": "online_subtitles",
    }
    service_delegates = {
        "_build_entry_from_history": ("target_resolver", "build_entry_from_history"),
        "_merge_seasons": ("target_resolver", "merge_seasons"),
        "_target_from_entry": ("target_resolver", "target_from_entry"),
        "_tmdb_detail_for_media": ("media_metadata", "tmdb_detail_for_media"),
        "_restore_persisted_match_history_cache": ("history", "restore_persisted_match_history_cache"),
        "_invalidate_match_history_cache": ("history", "invalidate_match_history_cache"),
        "_set_timeline_task": ("timeline_tasks", "set_task"),
        "_timeline_tasks_for_entries": ("timeline_tasks", "tasks_for_entries"),
        "_autosub_plugin": ("autosub_bridge", "autosub_plugin"),
        "_autosub_tasks_for_entries": ("autosub_bridge", "autosub_tasks_for_entries"),
        "_cleanup_old_sessions": ("upload_session", "cleanup_old_sessions"),
        "_write_session": ("upload_session", "write_session"),
        "_remove_ext_marks": ("subtitle_inventory", "remove_ext_marks"),
        "_run_timeline_fix": ("writer", "run_timeline_fix"),
        "_transfer_auto_key": ("auto_transfer", "transfer_auto_key"),
        "_claim_transfer_auto_entries": ("auto_transfer", "claim_transfer_auto_entries"),
        "_auto_transfer_entry_key": ("auto_transfer", "auto_transfer_entry_key"),
        "_auto_transfer_group_key": ("auto_transfer", "auto_transfer_group_key"),
        "_trim_auto_transfer_tasks_locked": ("auto_transfer", "trim_auto_transfer_tasks_locked"),
        "_ensure_transfer_auto_worker": ("auto_transfer", "ensure_transfer_auto_worker"),
        "_update_auto_transfer_task": ("auto_transfer", "update_auto_transfer_task"),
        "_claim_next_auto_transfer_batch": ("auto_transfer", "claim_next_auto_transfer_batch"),
        "_auto_wait_online_rate_limit": ("auto_transfer", "auto_wait_online_rate_limit"),
        "_auto_transfer_rate_status": ("auto_transfer", "auto_transfer_rate_status"),
        "_auto_transfer_queue_loop": ("auto_transfer", "auto_transfer_queue_loop"),
        "_auto_search_keywords_for_entry": ("auto_transfer", "auto_search_keywords_for_entry"),
        "_auto_search_providers": ("auto_transfer", "auto_search_providers"),
        "_auto_search_write_subtitle": ("auto_transfer", "auto_search_write_subtitle"),
        "_auto_submit_ai_for_entry": ("auto_transfer", "auto_submit_ai_for_entry"),
        "_auto_process_transfer_entry": ("auto_transfer", "auto_process_transfer_entry"),
        "_auto_prepared_items_for_targets": ("auto_transfer", "auto_prepared_items_for_targets"),
        "_select_auto_subtitle_items": ("auto_transfer", "select_auto_subtitle_items"),
        "_auto_write_prepared_uploads_for_entries": ("auto_transfer", "auto_write_prepared_uploads_for_entries"),
        "_store_auto_season_package_cache": ("auto_transfer", "store_auto_season_package_cache"),
        "_load_auto_season_package_cache": ("auto_transfer", "load_auto_season_package_cache"),
        "_auto_write_from_season_cache": ("auto_transfer", "auto_write_from_season_cache"),
        "_auto_search_write_season_package": ("auto_transfer", "auto_search_write_season_package"),
        "_auto_process_transfer_group": ("auto_transfer", "auto_process_transfer_group"),
        "_process_transfer_auto_task_batch": ("auto_transfer", "process_transfer_auto_task_batch"),
    }

    for name, func in runtime_static_methods.items():
        setattr(cls, name, staticmethod(func))
    for name, func in class_methods.items():
        setattr(cls, name, classmethod(func))
    for name, func in instance_methods.items():
        setattr(cls, name, func)
    for name, service_name in service_accessors.items():
        setattr(cls, name, _service_accessor(service_name))
    for name, (service_name, method_name) in service_delegates.items():
        setattr(cls, name, _service_delegate(service_name, method_name))
