from __future__ import annotations

import hashlib
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
    ArchiveDependencyService,
    ArchiveResourceLimits,
    UploadSessionService,
    archive_suffix_from_content as upload_archive_suffix_from_content,
    extract_7z_subtitle_files as upload_extract_7z_subtitle_files,
    extract_command_archive_subtitle_files as upload_extract_command_archive_subtitle_files,
    extract_rar_subtitle_files as upload_extract_rar_subtitle_files,
    extract_rar_subtitle_files_with_rarfile as upload_extract_rar_subtitle_files_with_rarfile,
    list_rar_members as upload_list_rar_members,
    normalize_online_download_name as normalize_upload_download_name,
    read_rar_member as upload_read_rar_member,
)
from .online_ai import OnlineAiService
from .auto_transfer import AutoTransferService




class SubtitleManualUploadCompatMixin:
    @classmethod
    def _host_module_value(cls, name: str, default: Any) -> Any:
        module = sys.modules.get(cls.__module__)
        return getattr(module, name, default) if module is not None else default

    def _ok(self, data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default








    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()




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
    def _normalize_auto_transfer_subtitle_strategy(cls, value: Any) -> str:
        return normalize_auto_transfer_subtitle_strategy(value)



    def _check_online_rate_limit(self, providers: Iterable[str]) -> None:
        now = self._host_module_value("time", time).time()
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


    def _auto_transfer_queue_loop(self) -> None:
        self._auto_transfer_service().auto_transfer_queue_loop()


    @classmethod
    def _archive_dependency_service(
        cls,
        status_setter: Optional[Any] = None,
    ) -> ArchiveDependencyService:
        return ArchiveDependencyService(
            rar_dependency_mode=getattr(cls, "_rar_dependency_mode", "none"),
            rar_tool_path=getattr(cls, "_rar_tool_path", ""),
            rar_python_package=getattr(cls, "_rar_python_package", "rarfile"),
            rar_tools=cls._rar_tools,
            sevenzip_tools=cls._sevenzip_tools,
            normalize_text=cls._normalize_text,
            decode_preview_bytes=cls._decode_preview_bytes,
            subprocess_module=cls._host_module_value("subprocess", subprocess),
            logger_info=logger.info,
            logger_warning=logger.warning,
            status_setter=status_setter,
        )

    def _set_rar_dependency_status(self, state: str, message: str) -> None:
        self._rar_dependency_status = type(self)._archive_dependency_service().dependency_status(state, message)

    def _prepare_rar_dependency(self) -> None:
        type(self)._archive_dependency_service(self._set_rar_dependency_status).prepare_rar_dependency()

    @classmethod
    def _normalize_language_suffix(cls, value: Any) -> str:
        return normalize_language_suffix(value)


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
            subprocess_module=cls._host_module_value("subprocess", subprocess),
            logger_warning=logger.warning,
        )

    def _subtitle_writer(self) -> SubtitleWriter:
        return SubtitleWriter(
            self,
            http_exception=HTTPException,
            logger=logger,
            timeline_result_type=self._host_module_value("TimelineFixResult", TimelineFixResult),
            timeline_fix_func=self._host_module_value("fix_subtitle_timeline", fix_subtitle_timeline),
            convert_subtitle_file_to_simplified=self._host_module_value(
                "convert_subtitle_file_to_simplified",
                convert_subtitle_file_to_simplified,
            ),
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
            plugin_manager=self._host_module_value("PluginManager", PluginManager),
            http_exception=HTTPException,
            logger=logger,
        )

    def _online_ai_service(self) -> OnlineAiService:
        return OnlineAiService(
            self,
            http_exception=HTTPException,
            logger=logger,
            check_timeline_fixer_dependencies=self._host_module_value(
                "check_timeline_fixer_dependencies",
                check_timeline_fixer_dependencies,
            ),
        )

    def _auto_transfer_service(self) -> AutoTransferService:
        return AutoTransferService(
            self,
            logger=logger,
            threading_module=self._host_module_value("threading", threading),
            time_module=self._host_module_value("time", time),
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




    def _build_entry_from_history(self, history: Any) -> Optional[Dict[str, Any]]:
        return self._target_resolver().build_entry_from_history(history)



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



    def _restore_persisted_match_history_cache(self) -> bool:
        return self._subtitle_history().restore_persisted_match_history_cache()

    def _invalidate_match_history_cache(self) -> None:
        self._subtitle_history().invalidate_match_history_cache()


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

        self._host_module_value("threading", threading).Thread(
            target=worker,
            name="SubtitleManualUploadCacheRefresh",
            daemon=True,
        ).start()

    def _load_local_entries(self, *, force: bool = False, allow_stale: bool = False) -> List[Dict[str, Any]]:
        return self._local_media_catalog().load_local_entries(force=force, allow_stale=allow_stale)



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





    def _group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        return self._local_media_catalog().group_entries_as_media(entries, limit)

    def _match_history_items(self, *, keyword: str = "", media_type: str = "all") -> List[Dict[str, Any]]:
        return self._subtitle_history().match_history_items(keyword=keyword, media_type=media_type)

    def _merge_seasons(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._target_resolver().merge_seasons(entries)


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





    def _remove_ext_marks(self, video_path: Path) -> None:
        self._subtitle_inventory().remove_ext_marks(video_path)

    @staticmethod
    def _is_upload_file(value: Any) -> bool:
        return isinstance(value, UploadFile)

    @classmethod
    def _rar_tool(cls) -> str:
        return cls._archive_dependency_service().rar_tool()

    @classmethod
    def _sevenzip_tool(cls) -> str:
        return cls._archive_dependency_service().sevenzip_tool()

    @classmethod
    def _rar_python_available(cls) -> bool:
        return cls._archive_dependency_service().rar_python_available()

    @classmethod
    def _rarfile_module(cls) -> Any:
        return cls._archive_dependency_service().rarfile_module()

    @classmethod
    def _run_archive_command(cls, args: List[str], timeout: int = 120) -> bytes:
        return cls._archive_dependency_service().run_archive_command(args, timeout=timeout)

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
