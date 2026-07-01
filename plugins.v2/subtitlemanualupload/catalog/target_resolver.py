from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from . import local_media_catalog as _local_media_catalog
from . import media_target_resolver as _media_target_resolver
from . import media_metadata as _media_metadata
from . import subtitle_inventory as _subtitle_inventory
from . import target_normalizers as _target_normalizers
from .target_normalizers import (
    EpisodeHint,
    HashText,
    NormalizeText,
    SafeInt,
    _default_normalize_text,
    _default_safe_int,
)

SubtitleFilesForTarget = Callable[[Dict[str, Any]], List[Dict[str, Any]]]
DetectLanguageProfile = Callable[[str, bytes], Dict[str, Any]]
NormalizeLanguageSuffix = Callable[[Any], str]
LanguageSuffixCheck = Callable[[Any], bool]
SubtitleBackupPath = Callable[[Path], Path]
TitleAliasExtractor = Callable[[Any], List[str]]


class TargetEntryCache:
    def __init__(
        self,
        entry_map: OrderedDict[str, Dict[str, Any]],
        *,
        max_size: int,
        normalize_text: NormalizeText,
    ) -> None:
        self._entry_map = entry_map
        self._max_size = max_size
        self._normalize_text = normalize_text

    def remember(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if not target_id:
                continue
            if target_id in self._entry_map:
                self._entry_map.move_to_end(target_id)
            self._entry_map[target_id] = entry
        while len(self._entry_map) > self._max_size:
            self._entry_map.popitem(last=False)

    def clear(self) -> None:
        self._entry_map.clear()

    def prune(self, entry_is_valid: Callable[[Dict[str, Any]], bool]) -> None:
        for target_id, entry in list(self._entry_map.items()):
            if not entry_is_valid(entry):
                self._entry_map.pop(target_id, None)

    def get(self, target_id: str) -> Optional[Dict[str, Any]]:
        return self._entry_map.get(self._normalize_text(target_id))

    def discard(self, target_id: str) -> None:
        self._entry_map.pop(self._normalize_text(target_id), None)

    def items(self) -> List[Tuple[str, Dict[str, Any]]]:
        return list(self._entry_map.items())

    def count(self) -> int:
        return len(self._entry_map)


def media_type_text(value: Any) -> str:
    return _target_normalizers.media_type_text(value)


def poster_url(
    poster_path: Any,
    prefix: str = "w500",
    *,
    settings_obj: Any = None,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    return _target_normalizers.poster_url(
        poster_path,
        prefix,
        settings_obj=settings_obj,
        normalize_text=normalize_text,
    )


def history_type_text(
    value: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    return _target_normalizers.history_type_text(value, normalize_text=normalize_text)


def number_from_tag(
    value: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    safe_int: SafeInt = _default_safe_int,
) -> int:
    return _target_normalizers.number_from_tag(
        value,
        normalize_text=normalize_text,
        safe_int=safe_int,
    )


def extract_episode_hint(
    file_name: str,
    *,
    safe_int: SafeInt = _default_safe_int,
) -> Optional[Dict[str, int]]:
    return _target_normalizers.extract_episode_hint(file_name, safe_int=safe_int)


def is_local_video_path(
    storage: str,
    path: str,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    settings_obj: Any = None,
    stream_exts: Iterable[str] = (),
    trust_transfer_history_paths: bool = False,
) -> bool:
    return _target_normalizers.is_local_video_path(
        storage,
        path,
        normalize_text=normalize_text,
        settings_obj=settings_obj,
        stream_exts=stream_exts,
        trust_transfer_history_paths=trust_transfer_history_paths,
    )


def event_value(obj: Any, *names: str, default: Any = "") -> Any:
    return _target_normalizers.event_value(obj, *names, default=default)


def is_stream_path(
    path: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    stream_exts: Iterable[str] = (),
) -> bool:
    return _target_normalizers.is_stream_path(
        path,
        normalize_text=normalize_text,
        stream_exts=stream_exts,
    )


def entry_path_is_valid(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    trust_transfer_history_paths: bool = False,
) -> bool:
    return _target_normalizers.entry_path_is_valid(
        entry,
        normalize_text=normalize_text,
        trust_transfer_history_paths=trust_transfer_history_paths,
    )


def entry_filesystem_signature(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    return _target_normalizers.entry_filesystem_signature(
        entry,
        normalize_text=normalize_text,
    )


def entry_matches_keyword(
    entry: Dict[str, Any],
    keyword: str,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> bool:
    return _target_normalizers.entry_matches_keyword(
        entry,
        keyword,
        normalize_text=normalize_text,
    )


def _latin_title(text: str) -> bool:
    return _media_metadata._latin_title(text)


def english_title_from_aliases(aliases: List[str]) -> str:
    return _media_metadata.english_title_from_aliases(aliases)


def tmdb_aliases(
    *values: Any,
    extract_title_aliases_func: TitleAliasExtractor,
) -> List[str]:
    return _media_metadata.tmdb_aliases(
        *values,
        extract_title_aliases_func=extract_title_aliases_func,
    )


def english_title_from_tmdb_values(
    *values: Any,
    extract_title_aliases_func: TitleAliasExtractor,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    return _media_metadata.english_title_from_tmdb_values(
        *values,
        extract_title_aliases_func=extract_title_aliases_func,
        normalize_text=normalize_text,
    )


def tmdb_detail_payload(
    detail: Any,
    *,
    extract_title_aliases_func: TitleAliasExtractor,
    normalize_text: NormalizeText = _default_normalize_text,
) -> Dict[str, Any]:
    return _media_metadata.tmdb_detail_payload(
        detail,
        extract_title_aliases_func=extract_title_aliases_func,
        normalize_text=normalize_text,
    )


def apply_tmdb_detail(target: Dict[str, Any], detail: Dict[str, Any]) -> None:
    _media_metadata.apply_tmdb_detail(target, detail)


def flatten_media_values(
    value: Any,
    keys: Tuple[str, ...] = (),
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> List[str]:
    return _media_metadata.flatten_media_values(
        value,
        keys,
        normalize_text=normalize_text,
    )


def is_chinese_language_code(
    value: Any,
    *,
    normalize_text: NormalizeText,
    chinese_language_codes: Iterable[str],
) -> bool:
    return _media_metadata.is_chinese_language_code(
        value,
        normalize_text=normalize_text,
        chinese_language_codes=chinese_language_codes,
    )


def is_chinese_country_value(
    value: Any,
    *,
    normalize_text: NormalizeText,
    chinese_country_codes: Iterable[str],
    chinese_region_names: Iterable[str],
) -> bool:
    return _media_metadata.is_chinese_country_value(
        value,
        normalize_text=normalize_text,
        chinese_country_codes=chinese_country_codes,
        chinese_region_names=chinese_region_names,
    )


def chinese_category_evidence(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText,
    chinese_category_pattern: Any,
) -> str:
    return _media_metadata.chinese_category_evidence(
        entry,
        normalize_text=normalize_text,
        chinese_category_pattern=chinese_category_pattern,
    )


def auto_media_for_entry(
    entry: Dict[str, Any],
    *,
    tmdb_detail_for_media_func: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    return _media_metadata.auto_media_for_entry(
        entry,
        tmdb_detail_for_media_func=tmdb_detail_for_media_func,
    )


def is_chinese_transfer_media(
    entry: Dict[str, Any],
    *,
    auto_media_for_entry_func: Callable[[Dict[str, Any]], Dict[str, Any]],
    normalize_text: NormalizeText,
    chinese_language_codes: Iterable[str],
    chinese_country_codes: Iterable[str],
    chinese_region_names: Iterable[str],
    chinese_category_pattern: Any,
) -> Tuple[bool, str]:
    return _media_metadata.is_chinese_transfer_media(
        entry,
        auto_media_for_entry_func=auto_media_for_entry_func,
        normalize_text=normalize_text,
        chinese_language_codes=chinese_language_codes,
        chinese_country_codes=chinese_country_codes,
        chinese_region_names=chinese_region_names,
        chinese_category_pattern=chinese_category_pattern,
    )


def suggest_target(
    subtitle_info: Dict[str, Any],
    targets: List[Dict[str, Any]],
    *,
    extract_episode_hint: EpisodeHint,
) -> Optional[str]:
    if not targets:
        return None
    if len(targets) == 1:
        return targets[0]["id"]

    hint = extract_episode_hint(subtitle_info.get("source_name"))
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


def auto_fill_missing_targets(
    preview_items: List[Dict[str, Any]],
    targets: List[Dict[str, Any]],
    *,
    extract_episode_hint: EpisodeHint,
) -> None:
    unresolved = [item for item in preview_items if not item.get("target_id")]
    if not unresolved:
        return
    used_target_ids = {item.get("target_id") for item in preview_items if item.get("target_id")}
    remaining_targets = [target for target in targets if target.get("id") not in used_target_ids]
    if len(unresolved) != len(remaining_targets):
        return
    sorted_targets = sorted(
        remaining_targets,
        key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("label", "")),
    )
    sorted_items = sorted(
        unresolved,
        key=lambda item: (extract_episode_hint(item.get("source_name") or "") or {}).get("episode", 0),
    )
    for item, target in zip(sorted_items, sorted_targets):
        item["target_id"] = target["id"]


class MediaMetadataService(_media_metadata.MediaMetadataService):
    pass


class SubtitleInventory(_subtitle_inventory.SubtitleInventory):
    pass


class MediaTargetResolver(_media_target_resolver.MediaTargetResolver):
    pass


class LocalMediaCatalog(_local_media_catalog.LocalMediaCatalog):
    pass
