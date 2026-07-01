from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from .target_normalizers import (
    EpisodeHint,
    HashText,
    NormalizeText,
    SafeInt,
    event_value,
    history_type_text,
    is_local_video_path,
    is_stream_path,
    media_type_text,
    number_from_tag,
    poster_url,
)

SubtitleFilesForTarget = Callable[[Dict[str, Any]], List[Dict[str, Any]]]


class TargetEntryCacheProtocol(Protocol):
    def remember(self, entries: List[Dict[str, Any]]) -> None:
        ...


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
        target_entry_cache: TargetEntryCacheProtocol,
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



__all__ = [name for name in globals() if not name.startswith("__")]
