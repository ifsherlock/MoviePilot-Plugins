from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.core.config import settings

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

from .online_subtitle import OnlineSubtitleSearchService, build_search_keywords, check_online_rate_limit, extract_title_aliases
from .config_schema import normalize_auto_transfer_subtitle_strategy
from .subtitle_language import auto_subtitle_sort_key, detect_language_profile, is_chinese_language_suffix, normalize_language_suffix
from .autosub_bridge import autosub_task_summary as bridge_autosub_task_summary
from .subtitle_writer import (
    build_destination_name as writer_build_destination_name,
    build_write_operations as writer_build_write_operations,
    subtitle_backup_path as writer_subtitle_backup_path,
    timeline_rejection_message as writer_timeline_rejection_message,
    timeline_result_blocks_auto_write as writer_timeline_result_blocks_auto_write,
)
from .timeline_fixer import TimelineFixResult
from .timeline_tasks import timeline_task_summary
from .target_resolver import (
    apply_tmdb_detail as target_apply_tmdb_detail,
    auto_media_for_entry as target_auto_media_for_entry,
    auto_fill_missing_targets as target_auto_fill_missing_targets,
    entry_filesystem_signature as target_entry_filesystem_signature,
    entry_matches_keyword as target_entry_matches_keyword,
    entry_path_is_valid as target_entry_path_is_valid,
    extract_episode_hint as target_extract_episode_hint,
    is_chinese_transfer_media as target_is_chinese_transfer_media,
    is_stream_path as target_is_stream_path,
    media_type_text as target_media_type_text,
    poster_url as target_poster_url,
    suggest_target as target_suggest_target,
    tmdb_aliases as target_tmdb_aliases,
    tmdb_detail_payload as target_tmdb_detail_payload,
)
from .upload_session import normalize_online_download_name as normalize_upload_download_name
from .compat_services import (
    LEGACY_INSTANCE_SERVICE_DELEGATES,
    install_compat_archive_methods,
    install_compat_service_factories,
    install_legacy_service_delegates,
)




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
        return target_entry_path_is_valid(
            entry,
            normalize_text=cls._normalize_text,
            trust_transfer_history_paths=getattr(cls, "_trust_transfer_history_paths", False),
        )

    @classmethod
    def _entry_filesystem_signature(cls, entry: Dict[str, Any]) -> str:
        return target_entry_filesystem_signature(entry, normalize_text=cls._normalize_text)

    @staticmethod
    def _timestamp_iso(ts: Any) -> str:
        try:
            return datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")
        except Exception:
            return ""


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
        return target_extract_episode_hint(file_name, safe_int=cls._safe_int)

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

    @classmethod
    def _json_clone(cls, value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False))


    @staticmethod
    def _timeline_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
        return timeline_task_summary(tasks)

    @staticmethod
    def _autosub_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        return bridge_autosub_task_summary(tasks)

    @classmethod
    def _entry_matches_keyword(cls, entry: Dict[str, Any], keyword: str) -> bool:
        return target_entry_matches_keyword(entry, keyword, normalize_text=cls._normalize_text)

    @classmethod
    def _tmdb_detail_payload(cls, detail: Any) -> Dict[str, Any]:
        return target_tmdb_detail_payload(
            detail,
            extract_title_aliases_func=extract_title_aliases,
            normalize_text=cls._normalize_text,
        )

    @classmethod
    def _tmdb_aliases(cls, *values: Any) -> List[str]:
        return target_tmdb_aliases(*values, extract_title_aliases_func=extract_title_aliases)

    @classmethod
    def _apply_tmdb_detail(cls, target: Dict[str, Any], detail: Dict[str, Any]) -> None:
        target_apply_tmdb_detail(target, detail)

    def _auto_media_for_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return target_auto_media_for_entry(
            entry,
            tmdb_detail_for_media_func=self._tmdb_detail_for_media,
        )

    def _is_chinese_transfer_media(self, entry: Dict[str, Any]) -> Tuple[bool, str]:
        return target_is_chinese_transfer_media(
            entry,
            auto_media_for_entry_func=self._auto_media_for_entry,
            normalize_text=self._normalize_text,
            chinese_language_codes=self._chinese_media_language_codes,
            chinese_country_codes=self._chinese_media_country_codes,
            chinese_region_names=self._chinese_media_region_names,
            chinese_category_pattern=self._chinese_media_category_pattern,
        )

    @classmethod
    def _is_stream_path(cls, path: Any) -> bool:
        return target_is_stream_path(
            path,
            normalize_text=cls._normalize_text,
            stream_exts=cls._stream_exts,
        )

    def _remember_targets(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if target_id:
                if target_id in self._entry_map:
                    self._entry_map.move_to_end(target_id)
                self._entry_map[target_id] = entry
        while len(self._entry_map) > self._entry_map_max_size:
            self._entry_map.popitem(last=False)

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





    @staticmethod
    def _is_upload_file(value: Any) -> bool:
        return isinstance(value, UploadFile)

    @classmethod
    def _suggest_target(
        cls,
        subtitle_info: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> Optional[str]:
        return target_suggest_target(
            subtitle_info,
            targets,
            extract_episode_hint=cls._extract_episode_hint,
        )

    @classmethod
    def _auto_fill_missing_targets(
        cls,
        preview_items: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> None:
        target_auto_fill_missing_targets(
            preview_items,
            targets,
            extract_episode_hint=cls._extract_episode_hint,
        )

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


    def _online_service(self) -> OnlineSubtitleSearchService:
        return build_online_service(self)

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

    def _auto_subtitle_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, int, str]:
        language_priority = list(getattr(self, "_auto_subtitle_language_priority", None) or self._default_auto_language_priority)
        format_priority = list(getattr(self, "_auto_subtitle_format_priority", None) or self._default_auto_format_priority)
        return auto_subtitle_sort_key(
            item,
            language_priority=language_priority,
            format_priority=format_priority,
        )

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


install_compat_service_factories(SubtitleManualUploadCompatMixin)
install_compat_archive_methods(SubtitleManualUploadCompatMixin)
install_legacy_service_delegates(SubtitleManualUploadCompatMixin, LEGACY_INSTANCE_SERVICE_DELEGATES)
