from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

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


class MediaTargetResolver:
    def __init__(
        self,
        *,
        settings_obj: Any,
        meta_info_path: Optional[Callable[[Path], Any]],
        stream_exts: Iterable[str],
        trust_transfer_history_paths: bool,
        normalize_text: NormalizeText,
        safe_int: SafeInt,
        hash_text: HashText,
        extract_episode_hint: EpisodeHint,
        subtitle_files_provider: SubtitleFilesForTarget,
        load_local_entries: Callable[..., List[Dict[str, Any]]],
        group_entries_as_media: Callable[[List[Dict[str, Any]], int], List[Dict[str, Any]]],
        tmdb_detail_for_media: Callable[[Dict[str, Any]], Dict[str, Any]],
        apply_tmdb_detail: Callable[[Dict[str, Any], Dict[str, Any]], None],
        target_entry_cache: TargetEntryCache,
    ) -> None:
        self._settings = settings_obj
        self._meta_info_path = meta_info_path
        self._stream_exts = set(stream_exts)
        self._trust_transfer_history_paths = trust_transfer_history_paths
        self._normalize_text = normalize_text
        self._safe_int = safe_int
        self._hash_text = hash_text
        self._extract_episode_hint = extract_episode_hint
        self._subtitle_files_provider = subtitle_files_provider
        self._load_local_entries = load_local_entries
        self._group_entries_as_media = group_entries_as_media
        self._tmdb_detail_for_media = tmdb_detail_for_media
        self._apply_tmdb_detail = apply_tmdb_detail
        self._target_entry_cache = target_entry_cache

    def media_type_text(self, value: Any) -> str:
        return media_type_text(value)

    def poster_url(self, poster_path: Any, prefix: str = "w500") -> str:
        return poster_url(
            poster_path,
            prefix,
            settings_obj=self._settings,
            normalize_text=self._normalize_text,
        )

    def history_type_text(self, value: Any) -> str:
        return history_type_text(value, normalize_text=self._normalize_text)

    def number_from_tag(self, value: Any) -> int:
        return number_from_tag(value, normalize_text=self._normalize_text, safe_int=self._safe_int)

    def is_local_video_path(self, storage: str, path: str) -> bool:
        return is_local_video_path(
            storage,
            path,
            normalize_text=self._normalize_text,
            settings_obj=self._settings,
            stream_exts=self._stream_exts,
            trust_transfer_history_paths=self._trust_transfer_history_paths,
        )

    def build_entry_from_history(self, history: Any) -> Optional[Dict[str, Any]]:
        if not getattr(history, "status", False):
            return None

        raw_fileitem = getattr(history, "dest_fileitem", None)
        fileitem = raw_fileitem if isinstance(raw_fileitem, dict) else {}
        storage = self._normalize_text(fileitem.get("storage") or getattr(history, "dest_storage", "")) or "local"
        path = self._normalize_text(fileitem.get("path") or getattr(history, "dest", ""))
        if not self.is_local_video_path(storage, path):
            return None

        file_path = Path(path)
        filename = self._normalize_text(fileitem.get("name")) or file_path.name
        basename = self._normalize_text(fileitem.get("basename")) or file_path.stem
        media_type = self.media_type_text(getattr(history, "type", ""))
        if not media_type:
            return None

        title = self._normalize_text(getattr(history, "title", ""))
        year = self._normalize_text(getattr(history, "year", ""))
        season = self.number_from_tag(getattr(history, "seasons", ""))
        episode = self.number_from_tag(getattr(history, "episodes", ""))
        if not season or not episode:
            try:
                meta = self._meta_info_path(file_path) if self._meta_info_path else None
                season = season or self._safe_int(
                    getattr(meta, "begin_season", None) or getattr(meta, "season", None),
                    0,
                )
                episode = episode or self._safe_int(
                    getattr(meta, "begin_episode", None) or getattr(meta, "episode", None),
                    0,
                )
            except Exception:
                pass
        episode_hint = self._extract_episode_hint(filename or basename)
        if episode_hint:
            season = season or episode_hint.get("season", 0)
            episode = episode or episode_hint.get("episode", 0)
        if media_type == "tv" and episode and not season:
            season = 1

        tmdb_id = self._safe_int(getattr(history, "tmdbid", 0), 0)
        douban_id = self._normalize_text(getattr(history, "doubanid", ""))
        media_key = self._hash_text(f"{media_type}|{tmdb_id}|{douban_id}|{title}|{year}")
        entry_id = self._hash_text(f"{storage}|{path}")
        if media_type == "tv":
            prefix = f"S{season:02d}E{episode:02d}" if season and episode else basename
            target_label = f"{prefix} · {filename}"
        else:
            target_label = filename or (f"{title} ({year})" if year else title)

        return {
            "id": entry_id,
            "media_key": media_key,
            "media_type": media_type,
            "title": title,
            "year": year,
            "tmdb_id": tmdb_id,
            "douban_id": douban_id,
            "poster_url": self.poster_url(getattr(history, "image", "")),
            "poster_thumb_url": self.poster_url(getattr(history, "image", ""), "w185"),
            "season": season,
            "episode": episode,
            "path": path,
            "basename": basename,
            "filename": filename,
            "storage": storage,
            "library_name": "MoviePilot 媒体库",
            "relative_path": path.replace("\\", "/"),
            "target_label": target_label,
            "writable": True,
            "date": self._normalize_text(getattr(history, "date", "")),
        }

    def transfer_event_paths(self, transferinfo: Any) -> List[str]:
        raw_paths = event_value(transferinfo, "file_list_new", default=[]) or []
        if isinstance(raw_paths, (str, Path)):
            raw_paths = [raw_paths]
        paths = [self._normalize_text(item) for item in raw_paths if self._normalize_text(item)]
        if not paths:
            target_path = self._normalize_text(event_value(transferinfo, "target_path", default=""))
            if target_path:
                paths = [target_path]
        result = []
        for path in paths:
            if self.is_local_video_path("local", path):
                result.append(path)
        return result

    def entries_from_transfer_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        meta = event_data.get("meta") if isinstance(event_data, dict) else None
        mediainfo = event_data.get("mediainfo") if isinstance(event_data, dict) else None
        transferinfo = event_data.get("transferinfo") if isinstance(event_data, dict) else None
        paths = self.transfer_event_paths(transferinfo)
        if not paths:
            return []

        media_type = self.media_type_text(event_value(mediainfo, "type", default=""))
        title = self._normalize_text(
            event_value(mediainfo, "title", "name", default="")
            or event_value(meta, "name", "title", default="")
        )
        year = self._normalize_text(event_value(mediainfo, "year", "release_year", default=""))
        tmdb_id = self._safe_int(event_value(mediainfo, "tmdb_id", "tmdbid", default=0), 0)
        douban_id = self._normalize_text(event_value(mediainfo, "douban_id", "doubanid", default=""))
        season = self._safe_int(
            event_value(meta, "begin_season", "season", default=0)
            or event_value(mediainfo, "season", default=0),
            0,
        )
        episode = self._safe_int(
            event_value(meta, "begin_episode", "episode", default=0)
            or event_value(mediainfo, "episode", default=0),
            0,
        )
        episode_list = event_value(meta, "episode_list", default=[]) or []
        if not episode and isinstance(episode_list, list) and len(episode_list) == 1:
            episode = self._safe_int(episode_list[0], 0)
        if not media_type:
            media_type = "tv" if season or episode else "movie"

        entries: List[Dict[str, Any]] = []
        for path in paths:
            video_path = Path(path)
            basename = video_path.stem
            filename = video_path.name
            hint = self._extract_episode_hint(filename) or {}
            item_season = season or self._safe_int(hint.get("season"), 0)
            item_episode = episode or self._safe_int(hint.get("episode"), 0)
            item_title = title or basename
            media_key = self._hash_text(f"{media_type}|{tmdb_id}|{douban_id}|{item_title}|{year}")
            target_label = (
                f"S{item_season:02d}E{item_episode:02d} · {filename}"
                if media_type == "tv" and item_season and item_episode
                else filename
            )
            entries.append(
                {
                    "id": self._hash_text(f"local|{path}"),
                    "media_key": media_key,
                    "media_type": media_type,
                    "title": item_title,
                    "year": year,
                    "tmdb_id": tmdb_id,
                    "douban_id": douban_id,
                    "poster_url": self.poster_url(event_value(mediainfo, "poster_path", "image", default="")),
                    "poster_thumb_url": self.poster_url(
                        event_value(mediainfo, "poster_path", "image", default=""),
                        "w185",
                    ),
                    "season": item_season,
                    "episode": item_episode,
                    "path": path,
                    "basename": basename,
                    "filename": filename,
                    "storage": "local",
                    "library_name": "MoviePilot 入库事件",
                    "relative_path": path.replace("\\", "/"),
                    "target_label": target_label,
                    "writable": True,
                    "date": datetime.now().isoformat(timespec="seconds"),
                }
            )
        return entries

    def merge_seasons(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seasons: Dict[int, Dict[str, Any]] = {}
        for entry in entries:
            season = self._safe_int(entry.get("season"), 0)
            episode = self._safe_int(entry.get("episode"), 0)
            if not season:
                continue
            item = seasons.setdefault(
                season,
                {
                    "season": season,
                    "name": f"第 {season} 季",
                    "episode_count": 0,
                    "poster_url": "",
                    "local_count": 0,
                    "episodes": [],
                    "available": False,
                },
            )
            item["local_count"] += 1
            item["available"] = True
            if episode and episode not in item["episodes"]:
                item["episodes"].append(episode)

        result = list(seasons.values())
        for item in result:
            item["episodes"] = sorted(item.get("episodes") or [])
            item["episode_count"] = len(item["episodes"])
        result.sort(key=lambda item: item.get("season", 0))
        return result

    def targets_for_media(
        self,
        media_type: str,
        tmdb_id: Any = None,
        douban_id: Any = None,
        title: str = "",
        year: str = "",
        season: Any = None,
    ) -> Dict[str, Any]:
        clean_type = self.media_type_text(media_type)
        clean_tmdb_id = self._safe_int(tmdb_id, 0)
        clean_title = self._normalize_text(title)
        clean_year = self._normalize_text(year)
        clean_douban_id = self._normalize_text(douban_id)

        entries = []
        seen_paths = set()
        for entry in self._load_local_entries(allow_stale=True):
            if clean_type and entry.get("media_type") != clean_type:
                continue
            if clean_tmdb_id and self._safe_int(entry.get("tmdb_id"), 0) != clean_tmdb_id:
                continue
            if clean_douban_id and self._normalize_text(entry.get("douban_id")) != clean_douban_id:
                continue
            if not clean_tmdb_id and not clean_douban_id and clean_title and entry.get("title") != clean_title:
                continue
            if clean_year and entry.get("year") != clean_year:
                continue
            if entry["path"] not in seen_paths:
                seen_paths.add(entry["path"])
                entries.append(entry)

        entries.sort(key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("filename", "")))
        media_groups = self._group_entries_as_media(entries, 1)
        media = media_groups[0] if media_groups else {
            "id": self._hash_text(f"{clean_type}|{clean_tmdb_id}|{douban_id}|{clean_title}|{clean_year}"),
            "media_id": "",
            "media_type": clean_type,
            "title": clean_title,
            "year": clean_year,
            "tmdb_id": clean_tmdb_id,
            "douban_id": self._normalize_text(douban_id),
            "poster_url": "",
            "poster_thumb_url": "",
            "local_count": 0,
            "season_count": 0,
        }
        tmdb_detail = self._tmdb_detail_for_media(media)
        if tmdb_detail:
            self._apply_tmdb_detail(media, tmdb_detail)
        seasons = self.merge_seasons(entries) if media.get("media_type") == "tv" else []

        season_value = self._normalize_text(season)
        selected_season: Any = "all"
        if media.get("media_type") == "tv" and season_value not in {"", "all", "0"}:
            selected_season = self._safe_int(season_value, 0) or "all"

        visible_entries = entries
        if media.get("media_type") == "tv" and selected_season != "all":
            visible_entries = [entry for entry in entries if self._safe_int(entry.get("season"), 0) == selected_season]

        self._target_entry_cache.remember(visible_entries)
        targets = [self.target_from_entry(entry) for entry in visible_entries]
        if tmdb_detail:
            for target in targets:
                self._apply_tmdb_detail(target, tmdb_detail)

        return {
            "media": media,
            "seasons": seasons,
            "selected_season": selected_season,
            "targets": targets,
            "target_count": len(visible_entries),
            "all_target_count": len(entries),
        }

    def is_stream_path(self, path: Any) -> bool:
        return is_stream_path(path, normalize_text=self._normalize_text, stream_exts=self._stream_exts)

    def target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        subtitles = self._subtitle_files_provider(entry)
        path = self._normalize_text(entry.get("path"))
        return {
            "id": entry.get("id"),
            "label": entry.get("target_label"),
            "basename": entry.get("basename"),
            "path": path,
            "media_type": entry.get("media_type"),
            "title": entry.get("title"),
            "tmdb_id": entry.get("tmdb_id"),
            "douban_id": entry.get("douban_id"),
            "season": entry.get("season", 0),
            "episode": entry.get("episode", 0),
            "year": entry.get("year", ""),
            "library_name": entry.get("library_name"),
            "relative_path": entry.get("relative_path"),
            "original_language": entry.get("original_language"),
            "origin_country": entry.get("origin_country"),
            "production_countries": entry.get("production_countries"),
            "original_title": entry.get("original_title"),
            "original_name": entry.get("original_name"),
            "en_title": entry.get("en_title"),
            "tmdb_aliases": entry.get("tmdb_aliases"),
            "storage": entry.get("storage", "local"),
            "writable": entry.get("writable", True),
            "is_stream": self.is_stream_path(path),
            "has_subtitle": bool(subtitles),
            "subtitle_count": len(subtitles),
            "subtitles": subtitles,
        }


class LocalMediaCatalog:
    def __init__(
        self,
        owner: Any,
        *,
        transfer_history: Any,
        http_exception: Any,
        logger: Any,
        target_entry_cache: TargetEntryCache,
        threading_module: Any = None,
    ) -> None:
        self._owner = owner
        self._transfer_history = transfer_history
        self._http_exception = http_exception
        self._logger = logger
        self._target_entry_cache = target_entry_cache
        self._threading = threading_module

    def filter_existing_local_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        owner = self._owner
        filtered = [entry for entry in entries if isinstance(entry, dict) and owner._entry_path_is_valid(entry)]
        dropped = len(entries or []) - len(filtered)
        if dropped:
            self._logger.info("[SubtitleManualUpload] 已剔除失效本地视频目标 count=%s", dropped)
        return filtered

    def prune_local_entries_cache(self) -> None:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        entries = [entry for entry in cache.get("entries") or [] if isinstance(entry, dict)]
        if not entries:
            return
        filtered = self.filter_existing_local_entries(entries)
        if len(filtered) == len(entries):
            return
        media_count = len({entry.get("media_key") for entry in filtered if entry.get("media_key")})
        owner._local_entries_cache = {
            **cache,
            "entries": filtered,
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.prune(owner._entry_path_is_valid)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()

    def merge_local_entries_cache(self, entries: List[Dict[str, Any]]) -> None:
        owner = self._owner
        if not entries:
            return
        entries = self.filter_existing_local_entries(entries)
        if not entries:
            return
        cache = owner._local_entries_cache or {}
        existing = self.filter_existing_local_entries(
            [item for item in cache.get("entries") or [] if isinstance(item, dict)]
        )
        by_path = {entry.get("path"): entry for entry in entries if entry.get("path")}
        merged = list(entries)
        for entry in existing:
            if entry.get("path") not in by_path:
                merged.append(entry)
            if len(merged) >= owner._cache_max_entries:
                break
        media_count = len({entry.get("media_key") for entry in merged if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": datetime.now(),
            "entries": merged[: owner._cache_max_entries],
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.remember(entries)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()

    def local_cache_file(self) -> Path:
        return self._owner.get_data_path() / "local_entries_cache.json"

    def persist_local_cache(self) -> None:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        payload = {
            "loaded_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entries": cache.get("entries") or [],
            "media_count": int(cache.get("media_count") or 0),
        }
        try:
            cache_file = self.local_cache_file()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 写入本地资源持久化缓存失败: %s", exc)

    def restore_persisted_local_cache(self) -> bool:
        owner = self._owner
        try:
            cache_file = self.local_cache_file()
            if not cache_file.exists():
                return False
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取本地资源持久化缓存失败: %s", exc)
            return False
        entries = payload.get("entries") if isinstance(payload, dict) else []
        loaded_at = owner._cache_loaded_at(payload.get("loaded_at")) if isinstance(payload, dict) else None
        if not loaded_at or not isinstance(entries, list):
            return False
        valid_entries = self.filter_existing_local_entries([entry for entry in entries if isinstance(entry, dict)])
        media_count = len({entry.get("media_key") for entry in valid_entries if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": loaded_at,
            "entries": valid_entries,
            "media_count": media_count,
            "persisted": True,
        }
        self._target_entry_cache.remember(owner._local_entries_cache["entries"])
        self.reset_media_index_cache()
        self._logger.info(
            "[SubtitleManualUpload] 已恢复本地资源持久化缓存 entries=%s medias=%s",
            len(owner._local_entries_cache["entries"]),
            media_count,
        )
        return True

    def load_local_entries(self, *, force: bool = False, allow_stale: bool = False) -> List[Dict[str, Any]]:
        owner = self._owner
        self.prune_local_entries_cache()
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        now = datetime.now()
        if not force and loaded_at and (now - loaded_at).total_seconds() < owner._cache_ttl_seconds:
            return list(cache.get("entries") or [])
        if not force and not loaded_at and self.restore_persisted_local_cache():
            cache = owner._local_entries_cache or {}
            loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
            if loaded_at and (now - loaded_at).total_seconds() < owner._cache_ttl_seconds:
                return list(cache.get("entries") or [])
        if not force and allow_stale and cache.get("entries"):
            self.start_background_cache_refresh()
            return list(cache.get("entries") or [])

        try:
            histories = self._transfer_history.list_by_page(
                db=None,
                page=1,
                count=owner._cache_max_entries,
                status=True,
            ) or []
        except Exception as exc:
            raise self._http_exception(status_code=500, detail=f"读取 MoviePilot 本地整理记录失败: {exc}") from exc

        entries: List[Dict[str, Any]] = []
        seen_paths = set()
        for history in histories:
            entry = owner._build_entry_from_history(history)
            if not entry:
                continue
            if not owner._entry_path_is_valid(entry):
                continue
            path = entry.get("path")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            entries.append(entry)
            if len(entries) >= owner._cache_max_entries:
                break

        media_count = len({entry.get("media_key") for entry in entries if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": now,
            "entries": entries,
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.remember(entries)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()
        self._logger.info(
            "[SubtitleManualUpload] 本地资源缓存已刷新 entries=%s medias=%s",
            len(entries),
            media_count,
        )
        return list(entries)

    def start_background_cache_refresh(self) -> None:
        owner = self._owner
        if owner._cache_refreshing:
            return
        owner._cache_refreshing = True
        owner._cache_refresh_started_at = datetime.now().isoformat(timespec="seconds")
        owner._cache_refresh_completed_at = ""
        owner._cache_refresh_error = ""

        def worker():
            try:
                self.load_local_entries(force=True)
                owner._cache_refresh_completed_at = datetime.now().isoformat(timespec="seconds")
                owner._cache_refresh_error = ""
            except Exception as exc:
                owner._cache_refresh_error = str(exc)
                self._logger.warning("[SubtitleManualUpload] 后台刷新本地资源缓存失败: %s", exc)
            finally:
                owner._cache_refreshing = False

        self._threading.Thread(
            target=worker,
            name="SubtitleManualUploadCacheRefresh",
            daemon=True,
        ).start()

    def refresh_local_cache(self) -> List[Dict[str, Any]]:
        owner = self._owner
        self._target_entry_cache.clear()
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        owner._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
        return self.load_local_entries(force=True)

    def cache_status(self) -> Dict[str, Any]:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        expires_in = 0
        stale = False
        if loaded_at:
            age = (datetime.now() - loaded_at).total_seconds()
            expires_in = max(0, int(owner._cache_ttl_seconds - age))
            stale = age >= owner._cache_ttl_seconds
        return {
            "ready": bool(loaded_at),
            "persisted": bool(cache.get("persisted")),
            "stale": stale,
            "refreshing": bool(owner._cache_refreshing),
            "refresh_started_at": owner._cache_refresh_started_at,
            "refresh_completed_at": owner._cache_refresh_completed_at,
            "refresh_error": owner._cache_refresh_error,
            "trust_transfer_history_paths": bool(owner._trust_transfer_history_paths),
            "ttl_seconds": owner._cache_ttl_seconds,
            "expires_in": expires_in,
            "updated_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entry_count": len(cache.get("entries") or []),
            "media_count": int(cache.get("media_count") or 0),
            "media_index_count": len(owner._media_index_cache or {}),
            "target_cache_count": self._target_entry_cache.count(),
            "max_entries": owner._cache_max_entries,
        }

    def reset_media_index_cache(self) -> None:
        self._owner._media_index_cache = OrderedDict()

    def media_index_cache_key(self, keyword: str, media_type: str) -> str:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword).lower()
        expected_type = owner._media_type_text(media_type) or "all"
        return f"{expected_type}\0{clean_keyword}"

    def media_index_cache_get(self, key: str, entries: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        owner = self._owner
        cache = owner._media_index_cache or OrderedDict()
        item = cache.get(key)
        if not item:
            return None
        loaded_at = owner._cache_loaded_at((owner._local_entries_cache or {}).get("loaded_at"))
        cached_loaded_at = owner._cache_loaded_at(item.get("loaded_at"))
        if cached_loaded_at != loaded_at or int(item.get("entry_count") or 0) != len(entries):
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return [dict(media) for media in item.get("medias") or [] if isinstance(media, dict)]

    def media_index_cache_set(self, key: str, entries: List[Dict[str, Any]], medias: List[Dict[str, Any]]) -> None:
        owner = self._owner
        cache = owner._media_index_cache or OrderedDict()
        cache[key] = {
            "loaded_at": (owner._local_entries_cache or {}).get("loaded_at"),
            "entry_count": len(entries),
            "medias": [dict(media) for media in medias],
        }
        cache.move_to_end(key)
        while len(cache) > owner._media_index_cache_max_keys:
            cache.popitem(last=False)
        owner._media_index_cache = cache

    async def search_media_candidates(
        self,
        keyword: str,
        media_type: str,
        limit: int,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword)
        expected_type = owner._media_type_text(media_type)
        all_entries = self.load_local_entries(allow_stale=True)
        cache_key = self.media_index_cache_key(clean_keyword, media_type)
        all_candidates = self.media_index_cache_get(cache_key, all_entries)
        if all_candidates is None:
            entries: List[Dict[str, Any]] = []
            for entry in all_entries:
                if expected_type and entry.get("media_type") != expected_type:
                    continue
                if not owner._entry_matches_keyword(entry, clean_keyword):
                    continue
                entries.append(entry)
            all_candidates = self.group_entries_as_media(entries, 0)
            self.media_index_cache_set(cache_key, all_entries, all_candidates)
        total = len(all_candidates)
        candidates = all_candidates[offset: offset + limit]
        return candidates, total

    def group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        owner = self._owner
        groups: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            key = entry["media_key"]
            group = groups.setdefault(
                key,
                {
                    "id": key,
                    "media_id": key,
                    "media_type": entry.get("media_type"),
                    "title": entry.get("title"),
                    "en_title": "",
                    "year": entry.get("year"),
                    "tmdb_id": entry.get("tmdb_id"),
                    "douban_id": entry.get("douban_id"),
                    "poster_url": entry.get("poster_url"),
                    "poster_thumb_url": entry.get("poster_thumb_url") or owner._poster_url(entry.get("poster_url"), "w185"),
                    "backdrop_url": "",
                    "overview": "",
                    "vote_average": 0,
                    "local_count": 0,
                    "season_count": 0,
                    "latest_at": entry.get("date", ""),
                    "_entries": [],
                },
            )
            group["_entries"].append(entry)
            group["local_count"] += 1
            if entry.get("poster_url") and not group.get("poster_url"):
                group["poster_url"] = entry["poster_url"]
            if entry.get("poster_thumb_url") and not group.get("poster_thumb_url"):
                group["poster_thumb_url"] = entry["poster_thumb_url"]
            if entry.get("date") and entry["date"] > group.get("latest_at", ""):
                group["latest_at"] = entry["date"]

        result = []
        for group in groups.values():
            seasons = owner._merge_seasons(group.pop("_entries"))
            group["seasons"] = seasons
            group["season_count"] = len(seasons)
            result.append(group)
        result.sort(key=lambda item: (item.get("latest_at", ""), item.get("title", "")), reverse=True)
        return result[:limit] if limit else result

    def resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        target_id_list = [owner._normalize_text(item) for item in target_ids if owner._normalize_text(item)]
        target_id_set = set(target_id_list)
        result: Dict[str, Dict[str, Any]] = {}
        for target_id in target_id_list:
            entry = self._target_entry_cache.get(target_id)
            if entry and owner._entry_path_is_valid(entry):
                result[target_id] = entry
            elif entry:
                self._target_entry_cache.discard(target_id)
        missing_ids = target_id_set - set(result.keys())
        if not missing_ids:
            return result

        self._logger.info(
            "[SubtitleManualUpload] 目标缓存未命中，回查本地整理记录 target_ids=%s missing=%s",
            owner._brief_ids(target_id_list),
            len(missing_ids),
        )

        def take_matches(source_entries: List[Dict[str, Any]]) -> None:
            for entry in source_entries:
                target_id = owner._normalize_text(entry.get("id"))
                if target_id not in missing_ids:
                    continue
                self._target_entry_cache.remember([entry])
                result[target_id] = entry
                missing_ids.remove(target_id)
                if not missing_ids:
                    break

        try:
            take_matches(self.load_local_entries(allow_stale=True))
            if missing_ids:
                take_matches(self.load_local_entries(force=True))
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] 回查本地整理记录失败: %s", exc)
            return result

        if missing_ids:
            self._logger.warning(
                "[SubtitleManualUpload] 仍有目标无法解析 target_ids=%s missing=%s",
                owner._brief_ids(target_id_list),
                len(missing_ids),
            )
        return result

    def cached_unlocked_targets(self, locked_ids: set) -> List[Dict[str, Any]]:
        owner = self._owner
        entries: List[Dict[str, Any]] = []
        for target_id, entry in self._target_entry_cache.items():
            if owner._normalize_text(target_id) in locked_ids:
                continue
            if owner._entry_path_is_valid(entry):
                entries.append(entry)
        return entries
