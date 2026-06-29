"""Legacy private API compatibility shell for SubtitleManualUpload.

New runtime behavior belongs in domain services or API modules; this mixin is
kept only while existing source paths and legacy tests still reference private
``_xxx`` helpers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from .compat_core import install_compat_core_methods
from .compat_services import (
    LEGACY_INSTANCE_SERVICE_DELEGATES,
    install_compat_archive_methods,
    install_compat_service_factories,
    install_legacy_service_delegates,
)
from .subtitle_language import (
    auto_subtitle_sort_key,
    is_chinese_language_suffix,
)
from .subtitle_writer import (
    build_destination_name as writer_build_destination_name,
    build_write_operations as writer_build_write_operations,
)
from .target_resolver import (
    auto_fill_missing_targets as target_auto_fill_missing_targets,
    auto_media_for_entry as target_auto_media_for_entry,
    is_chinese_transfer_media as target_is_chinese_transfer_media,
    suggest_target as target_suggest_target,
)
from .timeline_fixer import TimelineFixResult
from .upload_session import normalize_online_download_name as normalize_upload_download_name


class SubtitleManualUploadCompatMixin:
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


install_compat_core_methods(SubtitleManualUploadCompatMixin)
install_compat_service_factories(SubtitleManualUploadCompatMixin)
install_compat_archive_methods(SubtitleManualUploadCompatMixin)
install_legacy_service_delegates(SubtitleManualUploadCompatMixin, LEGACY_INSTANCE_SERVICE_DELEGATES)
