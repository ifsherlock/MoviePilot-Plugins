from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Tuple

from fastapi import HTTPException

from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.db.models.transferhistory import TransferHistory
from app.log import logger

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

from .auto_transfer import AutoTransferCollaborators, AutoTransferService
from .autosub_bridge import AutoSubBridge
from .online_ai import OnlineAiService
from .online_subtitle import OnlineSubtitleSearchService, extract_title_aliases
from .subtitle_history import SubtitleHistory
from .subtitle_language import is_chinese_language_suffix
from .subtitle_writer import SubtitleWriter, subtitle_backup_path as writer_subtitle_backup_path
from .target_resolver import (
    LocalMediaCatalog,
    MediaMetadataService,
    MediaTargetResolver,
    SubtitleInventory,
    TargetEntryCache,
)
from .timeline_fixer import TimelineFixResult, check_timeline_fixer_dependencies, fix_subtitle_timeline
from .timeline_tasks import TimelineTaskStore
from .tongwen import convert_subtitle_file_to_simplified
from .upload_session import (
    ArchiveDependencyService,
    ArchiveResourceLimits,
    DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    UploadSessionService,
    extract_7z_subtitle_files as upload_extract_7z_subtitle_files,
    extract_command_archive_subtitle_files as upload_extract_command_archive_subtitle_files,
    extract_rar_subtitle_files as upload_extract_rar_subtitle_files,
    extract_rar_subtitle_files_with_rarfile as upload_extract_rar_subtitle_files_with_rarfile,
    list_rar_members as upload_list_rar_members,
    read_rar_member as upload_read_rar_member,
)


def _make_service_delegate(service_name: str, target_name: str):
    def _delegate(self, *args, **kwargs):
        return getattr(getattr(self, service_name)(), target_name)(*args, **kwargs)

    return _delegate


def install_legacy_service_delegates(cls, specs: Tuple[Tuple[str, str, str], ...]) -> None:
    for legacy_name, service_name, target_name in specs:
        method = _make_service_delegate(service_name, target_name)
        method.__name__ = legacy_name
        setattr(cls, legacy_name, method)


def install_compat_archive_methods(cls) -> None:
    cls._rar_tool = classmethod(lambda owner_cls: archive_dependency_service(owner_cls).rar_tool())
    cls._sevenzip_tool = classmethod(lambda owner_cls: archive_dependency_service(owner_cls).sevenzip_tool())
    cls._rar_python_available = classmethod(lambda owner_cls: archive_dependency_service(owner_cls).rar_python_available())
    cls._rarfile_module = classmethod(lambda owner_cls: archive_dependency_service(owner_cls).rarfile_module())
    cls._run_archive_command = classmethod(lambda owner_cls, args, timeout=120: archive_dependency_service(owner_cls).run_archive_command(args, timeout=timeout))
    cls._list_rar_members = classmethod(list_rar_members)
    cls._read_rar_member = classmethod(read_rar_member)
    cls._extract_rar_subtitle_files_with_rarfile = classmethod(extract_rar_subtitle_files_with_rarfile)
    cls._extract_rar_subtitle_files = classmethod(extract_rar_subtitle_files)
    cls._extract_7z_subtitle_files = classmethod(extract_7z_subtitle_files)
    cls._extract_command_archive_subtitle_files = classmethod(extract_command_archive_subtitle_files)
    cls._extract_subtitle_files = classmethod(extract_subtitle_files)


LEGACY_INSTANCE_SERVICE_DELEGATES = (
    ("_filter_existing_local_entries", "_local_media_catalog", "filter_existing_local_entries"),
    ("_merge_local_entries_cache", "_local_media_catalog", "merge_local_entries_cache"),
    ("_restore_persisted_local_cache", "_local_media_catalog", "restore_persisted_local_cache"),
    ("_start_background_cache_refresh", "_local_media_catalog", "start_background_cache_refresh"),
    ("_load_local_entries", "_local_media_catalog", "load_local_entries"),
    ("_group_entries_as_media", "_local_media_catalog", "group_entries_as_media"),
    ("_resolve_targets", "_local_media_catalog", "resolve_targets"),
    ("_build_entry_from_history", "_target_resolver", "build_entry_from_history"),
    ("_entries_from_transfer_event", "_target_resolver", "entries_from_transfer_event"),
    ("_merge_seasons", "_target_resolver", "merge_seasons"),
    ("_target_from_entry", "_target_resolver", "target_from_entry"),
    ("_tmdb_detail_for_media", "_media_metadata_service", "tmdb_detail_for_media"),
    ("_restore_persisted_match_history_cache", "_subtitle_history", "restore_persisted_match_history_cache"),
    ("_invalidate_match_history_cache", "_subtitle_history", "invalidate_match_history_cache"),
    ("_match_history_items", "_subtitle_history", "match_history_items"),
    ("_timeline_task_for_target_id", "_timeline_task_store", "task_for_target_id"),
    ("_set_timeline_task", "_timeline_task_store", "set_task"),
    ("_timeline_tasks_for_entries", "_timeline_task_store", "tasks_for_entries"),
    ("_autosub_plugin", "_autosub_bridge", "autosub_plugin"),
    ("_autosub_status", "_autosub_bridge", "autosub_status"),
    ("_autosub_tasks_for_entries", "_autosub_bridge", "autosub_tasks_for_entries"),
    ("_get_session_root", "_upload_session_service", "get_session_root"),
    ("_cleanup_old_sessions", "_upload_session_service", "cleanup_old_sessions"),
    ("_write_session", "_upload_session_service", "write_session"),
    ("_remove_ext_marks", "_subtitle_inventory", "remove_ext_marks"),
    ("_write_operations_to_disk", "_subtitle_writer", "write_operations_to_disk"),
    ("_run_timeline_fix", "_subtitle_writer", "run_timeline_fix"),
    ("_transfer_auto_key", "_auto_transfer_service", "transfer_auto_key"),
    ("_claim_transfer_auto_entries", "_auto_transfer_service", "claim_transfer_auto_entries"),
    ("_auto_transfer_entry_key", "_auto_transfer_service", "auto_transfer_entry_key"),
    ("_auto_transfer_group_key", "_auto_transfer_service", "auto_transfer_group_key"),
    ("_trim_auto_transfer_tasks_locked", "_auto_transfer_service", "trim_auto_transfer_tasks_locked"),
    ("_ensure_transfer_auto_worker", "_auto_transfer_service", "ensure_transfer_auto_worker"),
    ("_update_auto_transfer_task", "_auto_transfer_service", "update_auto_transfer_task"),
    ("_claim_next_auto_transfer_batch", "_auto_transfer_service", "claim_next_auto_transfer_batch"),
    ("_auto_wait_online_rate_limit", "_auto_transfer_service", "auto_wait_online_rate_limit"),
    ("_auto_transfer_rate_status", "_auto_transfer_service", "auto_transfer_rate_status"),
    ("_auto_transfer_queue_summary", "_auto_transfer_service", "auto_transfer_queue_summary"),
    ("_auto_transfer_queue_loop", "_auto_transfer_service", "auto_transfer_queue_loop"),
    ("_auto_search_keywords_for_entry", "_auto_transfer_service", "auto_search_keywords_for_entry"),
    ("_auto_search_providers", "_auto_transfer_service", "auto_search_providers"),
    ("_auto_search_write_subtitle", "_auto_transfer_service", "auto_search_write_subtitle"),
    ("_auto_submit_ai_for_entry", "_auto_transfer_service", "auto_submit_ai_for_entry"),
    ("_auto_process_transfer_entry", "_auto_transfer_service", "auto_process_transfer_entry"),
    ("_auto_prepared_items_for_targets", "_auto_transfer_service", "auto_prepared_items_for_targets"),
    ("_select_auto_subtitle_items", "_auto_transfer_service", "select_auto_subtitle_items"),
    ("_auto_write_prepared_uploads_for_entries", "_auto_transfer_service", "auto_write_prepared_uploads_for_entries"),
    ("_store_auto_season_package_cache", "_auto_transfer_service", "store_auto_season_package_cache"),
    ("_load_auto_season_package_cache", "_auto_transfer_service", "load_auto_season_package_cache"),
    ("_auto_write_from_season_cache", "_auto_transfer_service", "auto_write_from_season_cache"),
    ("_auto_search_write_season_package", "_auto_transfer_service", "auto_search_write_season_package"),
    ("_auto_process_transfer_group", "_auto_transfer_service", "auto_process_transfer_group"),
    ("_process_transfer_auto_task_batch", "_auto_transfer_service", "process_transfer_auto_task_batch"),
)


def archive_dependency_service(owner_cls, status_setter=None) -> ArchiveDependencyService:
    return ArchiveDependencyService(
        rar_dependency_mode=getattr(owner_cls, "_rar_dependency_mode", "none"),
        rar_tool_path=getattr(owner_cls, "_rar_tool_path", ""),
        rar_python_package=getattr(owner_cls, "_rar_python_package", "rarfile"),
        rar_tools=owner_cls._rar_tools,
        sevenzip_tools=owner_cls._sevenzip_tools,
        normalize_text=owner_cls._normalize_text,
        decode_preview_bytes=owner_cls._decode_preview_bytes,
        subprocess_module=owner_cls._host_module_value("subprocess", subprocess),
        logger_info=logger.info,
        logger_warning=logger.warning,
        status_setter=status_setter,
    )


def upload_session_service_for_path(owner_cls, data_path: Path) -> UploadSessionService:
    return UploadSessionService(
        data_path=data_path,
        subtitle_exts=owner_cls._subtitle_exts,
        archive_exts=owner_cls._archive_exts,
        rar_exts=owner_cls._rar_exts,
        sevenzip_exts=owner_cls._sevenzip_exts,
        default_session_hours=owner_cls._default_session_hours,
        hash_text=owner_cls._hash_text,
        extract_rar_subtitle_files=owner_cls._extract_rar_subtitle_files,
        extract_7z_subtitle_files=owner_cls._extract_7z_subtitle_files,
        logger_warning=logger.warning,
        normalize_text=owner_cls._normalize_text,
        decode_preview_bytes=owner_cls._decode_preview_bytes,
    )


def subtitle_inventory(owner_cls) -> SubtitleInventory:
    return SubtitleInventory(
        subtitle_exts=owner_cls._subtitle_exts,
        stream_exts=owner_cls._stream_exts,
        embedded_text_codecs=owner_cls._embedded_subtitle_text_codecs,
        embedded_image_codecs=owner_cls._embedded_subtitle_image_codecs,
        embedded_probe_cache=owner_cls._embedded_subtitle_probe_cache,
        embedded_probe_cache_max_size=owner_cls._embedded_subtitle_probe_cache_max_size,
        trust_transfer_history_paths=getattr(owner_cls, "_trust_transfer_history_paths", False),
        normalize_text=owner_cls._normalize_text,
        normalize_language_suffix=owner_cls._normalize_language_suffix,
        detect_language_profile=owner_cls._detect_language_profile,
        is_chinese_language_suffix=is_chinese_language_suffix,
        safe_int=owner_cls._safe_int,
        subtitle_backup_path=writer_subtitle_backup_path,
        subprocess_module=owner_cls._host_module_value("subprocess", subprocess),
        logger_warning=logger.warning,
    )


def subtitle_writer(owner) -> SubtitleWriter:
    return SubtitleWriter(
        owner,
        http_exception=HTTPException,
        logger=logger,
        timeline_result_type=owner._host_module_value("TimelineFixResult", TimelineFixResult),
        timeline_fix_func=owner._host_module_value("fix_subtitle_timeline", fix_subtitle_timeline),
        convert_subtitle_file_to_simplified=owner._host_module_value(
            "convert_subtitle_file_to_simplified",
            convert_subtitle_file_to_simplified,
        ),
        load_session=lambda session_id: owner._upload_session_service().load_session(
            session_id,
            normalize_text=owner._normalize_text,
        ),
        timeline_cache_dir=lambda: owner.get_data_path() / "timeline_cache",
    )


def target_entry_cache(owner) -> TargetEntryCache:
    return TargetEntryCache(
        owner._entry_map,
        max_size=owner._entry_map_max_size,
        normalize_text=owner._normalize_text,
    )


def subtitle_history(owner) -> SubtitleHistory:
    return SubtitleHistory(
        owner,
        http_exception=HTTPException,
        logger=logger,
        target_entry_cache=target_entry_cache(owner),
    )


def autosub_bridge(owner) -> AutoSubBridge:
    return AutoSubBridge(
        owner,
        plugin_manager=owner._host_module_value("PluginManager", PluginManager),
        http_exception=HTTPException,
        logger=logger,
    )


def online_ai_service(owner) -> OnlineAiService:
    return OnlineAiService(
        owner,
        http_exception=HTTPException,
        logger=logger,
        check_timeline_fixer_dependencies=owner._host_module_value(
            "check_timeline_fixer_dependencies",
            check_timeline_fixer_dependencies,
        ),
    )


def auto_transfer_service(owner) -> AutoTransferService:
    threading_module = owner._host_module_value("threading", threading)
    time_module = owner._host_module_value("time", time)
    collaborators = AutoTransferCollaborators.from_owner(
        owner,
        logger=logger,
        threading_module=threading_module,
        time_module=time_module,
        http_exception=HTTPException,
    )
    return AutoTransferService(
        owner,
        logger=logger,
        threading_module=threading_module,
        time_module=time_module,
        http_exception=HTTPException,
        collaborators=collaborators,
    )


def target_resolver(owner) -> MediaTargetResolver:
    return MediaTargetResolver(
        settings_obj=settings,
        meta_info_path=MetaInfoPath,
        stream_exts=owner._stream_exts,
        trust_transfer_history_paths=getattr(owner, "_trust_transfer_history_paths", False),
        normalize_text=owner._normalize_text,
        safe_int=owner._safe_int,
        hash_text=owner._hash_text,
        extract_episode_hint=owner._extract_episode_hint,
        subtitle_files_provider=owner._subtitle_inventory().subtitle_files_for_target,
        load_local_entries=owner._load_local_entries,
        group_entries_as_media=owner._group_entries_as_media,
        tmdb_detail_for_media=owner._tmdb_detail_for_media,
        apply_tmdb_detail=owner._apply_tmdb_detail,
        target_entry_cache=target_entry_cache(owner),
    )


def local_media_catalog(owner) -> LocalMediaCatalog:
    return LocalMediaCatalog(
        owner,
        transfer_history=TransferHistory,
        http_exception=HTTPException,
        logger=logger,
        target_entry_cache=target_entry_cache(owner),
        threading_module=owner._host_module_value("threading", threading),
    )


def media_metadata_service(owner) -> MediaMetadataService:
    return MediaMetadataService(
        tmdb_chain_factory=TmdbChain,
        media_type_tv=MediaType.TV,
        media_type_movie=MediaType.MOVIE,
        tmdb_detail_cache=owner._tmdb_detail_cache,
        logger_warning=logger.warning,
        normalize_text=owner._normalize_text,
        safe_int=owner._safe_int,
        media_type_text_func=owner._media_type_text,
        extract_title_aliases_func=extract_title_aliases,
        chinese_language_codes=owner._chinese_media_language_codes,
        chinese_country_codes=owner._chinese_media_country_codes,
        chinese_region_names=owner._chinese_media_region_names,
        chinese_category_pattern=owner._chinese_media_category_pattern,
    )


def timeline_task_store(owner) -> TimelineTaskStore:
    return TimelineTaskStore(
        owner,
        normalize_text=owner._normalize_text,
        cache_loaded_at=owner._cache_loaded_at,
        json_clone=owner._json_clone,
        timeline_task_ttl_seconds=owner._timeline_task_ttl_seconds,
        max_tasks=owner._entry_map_max_size,
    )


def online_service(owner) -> OnlineSubtitleSearchService:
    return OnlineSubtitleSearchService(
        engine=owner._online_engine,
        use_proxy=owner._online_use_proxy,
        provider_roots=owner._online_site_urls,
        assrt_api_key=owner._assrt_api_key,
        assrt_api_url=owner._assrt_api_url,
        opensubtitles_api_key=owner._opensubtitles_api_key,
        opensubtitles_api_url=owner._opensubtitles_api_url,
        opensubtitles_username=owner._opensubtitles_username,
        opensubtitles_password=owner._opensubtitles_password,
    )


def list_rar_members(owner_cls, archive_path: Path, tool_path: str):
    return upload_list_rar_members(
        archive_path,
        tool_path,
        decode_preview_bytes=owner_cls._decode_preview_bytes,
        run_command=owner_cls._run_archive_command,
    )


def read_rar_member(owner_cls, archive_path: Path, member: str, tool_path: str):
    return upload_read_rar_member(
        archive_path,
        member,
        tool_path,
        run_command=owner_cls._run_archive_command,
    )


def extract_rar_subtitle_files_with_rarfile(
    owner_cls,
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
):
    return upload_extract_rar_subtitle_files_with_rarfile(
        source_name,
        archive_path,
        session_dir,
        rarfile_module_factory=owner_cls._rarfile_module,
        rar_python_package=owner_cls._rar_python_package,
        subtitle_exts=owner_cls._subtitle_exts,
        hash_text=owner_cls._hash_text,
        resource_limits=resource_limits,
    )


def extract_rar_subtitle_files(
    owner_cls,
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
):
    return upload_extract_rar_subtitle_files(
        source_name,
        archive_path,
        session_dir,
        rar_python_available_func=owner_cls._rar_python_available,
        extract_with_rarfile=owner_cls._extract_rar_subtitle_files_with_rarfile,
        rar_tool_func=owner_cls._rar_tool,
        extract_command_archive_subtitle_files_func=owner_cls._extract_command_archive_subtitle_files,
        rar_python_package=owner_cls._rar_python_package,
        logger_warning=logger.warning,
        resource_limits=resource_limits,
    )


def extract_7z_subtitle_files(
    owner_cls,
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
):
    return upload_extract_7z_subtitle_files(
        source_name,
        archive_path,
        session_dir,
        sevenzip_tool_func=owner_cls._sevenzip_tool,
        extract_command_archive_subtitle_files_func=owner_cls._extract_command_archive_subtitle_files,
        resource_limits=resource_limits,
    )


def extract_command_archive_subtitle_files(
    owner_cls,
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    tool_path: str,
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
):
    return upload_extract_command_archive_subtitle_files(
        source_name,
        archive_path,
        session_dir,
        tool_path,
        subtitle_exts=owner_cls._subtitle_exts,
        hash_text=owner_cls._hash_text,
        list_members=owner_cls._list_rar_members,
        read_member=owner_cls._read_rar_member,
        resource_limits=resource_limits,
    )


def extract_subtitle_files(owner_cls, upload_name: str, raw_bytes: bytes, session_dir: Path):
    return upload_session_service_for_path(owner_cls, session_dir.parent).extract_subtitle_files(
        upload_name,
        raw_bytes,
        session_dir,
    )
