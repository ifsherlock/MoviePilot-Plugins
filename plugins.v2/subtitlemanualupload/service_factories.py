from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any

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
    ArchiveSubtitleExtractor,
    UploadSessionService,
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


def archive_subtitle_extractor(owner_cls) -> ArchiveSubtitleExtractor:
    return ArchiveSubtitleExtractor(
        archive_dependency_service=archive_dependency_service(owner_cls),
        subtitle_exts=owner_cls._subtitle_exts,
        hash_text=owner_cls._hash_text,
        rar_python_package=owner_cls._rar_python_package,
        logger_warning=logger.warning,
    )


def upload_session_service_for_path(owner_cls, data_path: Path) -> UploadSessionService:
    extractor = archive_subtitle_extractor(owner_cls)
    return UploadSessionService(
        data_path=data_path,
        subtitle_exts=owner_cls._subtitle_exts,
        archive_exts=owner_cls._archive_exts,
        rar_exts=owner_cls._rar_exts,
        sevenzip_exts=owner_cls._sevenzip_exts,
        default_session_hours=owner_cls._default_session_hours,
        hash_text=owner_cls._hash_text,
        extract_rar_subtitle_files=extractor.extract_rar_subtitle_files,
        extract_7z_subtitle_files=extractor.extract_7z_subtitle_files,
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
