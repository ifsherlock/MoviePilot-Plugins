from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


class ManualStrmCatalog:
    """扫描用户明确配置的本地 STRM 根目录，不读取 STRM 内容或远端媒体。"""

    def __init__(
        self,
        *,
        normalize_text: Callable[[Any], str],
        safe_int: Callable[[Any, int], int],
        hash_text: Callable[[str], str],
        extract_episode_hint: Callable[[str], Optional[Dict[str, int]]],
        meta_info_path: Optional[Callable[[Path], Any]],
        logger_warning: Callable[..., None],
    ) -> None:
        self._normalize_text = normalize_text
        self._safe_int = safe_int
        self._hash_text = hash_text
        self._extract_episode_hint = extract_episode_hint
        self._meta_info_path = meta_info_path
        self._logger_warning = logger_warning

    def scan(self, roots: Iterable[str], *, max_entries: int = 5000) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        seen_paths: set[str] = set()
        for root_text in roots:
            root = self._resolve_root(root_text)
            if not root:
                continue
            for path in self._iter_strm_files(root):
                path_key = str(path)
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                entry = self._entry_from_path(root, path)
                if entry:
                    entries.append(entry)
                    if len(entries) >= max_entries:
                        return entries
        return entries

    def _resolve_root(self, value: Any) -> Optional[Path]:
        raw = self._normalize_text(value)
        if not raw:
            return None
        try:
            root = Path(raw).expanduser()
            if not root.is_absolute() or str(root) in {"", "/", "\\"}:
                return None
            root = root.resolve()
            return root if root.is_dir() else None
        except Exception as exc:
            self._logger_warning("[SubtitleManualUpload] 手动 STRM 根目录不可用 path=%s error=%s", raw, exc)
            return None

    def _iter_strm_files(self, root: Path):
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as iterator:
                    for item in iterator:
                        try:
                            if item.is_symlink():
                                continue
                            if item.is_dir(follow_symlinks=False):
                                stack.append(Path(item.path))
                            elif item.is_file(follow_symlinks=False) and item.name.lower().endswith(".strm"):
                                yield Path(item.path)
                        except OSError:
                            continue
            except OSError as exc:
                self._logger_warning("[SubtitleManualUpload] 扫描手动 STRM 目录失败 directory=%s error=%s", current, exc)

    def _entry_from_path(self, root: Path, path: Path) -> Optional[Dict[str, Any]]:
        nfo = self._read_nfo(root, path)
        meta = self._path_meta(path)
        hint = self._extract_episode_hint(path.name) or {}
        root_tag = self._normalize_text(nfo.get("root_tag")).lower()
        media_type = "tv" if root_tag in {"tvshow", "episodedetails", "season"} else ""
        media_type = media_type or ("tv" if meta.get("is_tv") else "")
        media_type = media_type or ("tv" if hint.get("season") or hint.get("episode") else "movie")
        title = self._normalize_text(nfo.get("title") or nfo.get("showtitle"))
        title = title or self._normalize_text(meta.get("title"))
        title = title or self._title_from_path(path)
        year = self._normalize_text(nfo.get("year") or meta.get("year"))
        season = self._safe_int(nfo.get("season"), 0) or self._safe_int(meta.get("season"), 0) or self._safe_int(hint.get("season"), 0)
        episode = self._safe_int(nfo.get("episode"), 0) or self._safe_int(meta.get("episode"), 0) or self._safe_int(hint.get("episode"), 0)
        if media_type == "tv" and episode and not season:
            season = 1

        source = self._normalize_text(nfo.get("media_source")).lower()
        media_id = self._normalize_text(nfo.get("media_id"))
        tmdb_id = self._normalize_text(nfo.get("tmdb_id"))
        douban_id = self._normalize_text(nfo.get("douban_id"))
        if not source and tmdb_id:
            source, media_id = "themoviedb", tmdb_id
        elif not source and douban_id:
            source, media_id = "douban", douban_id
        identity_key = f"{source}:{media_id}" if source and media_id else f"{media_type}|{title}|{year}"
        media_key = self._hash_text(identity_key)
        filename = path.name
        basename = path.stem
        prefix = f"S{season:02d}E{episode:02d}" if media_type == "tv" and season and episode else basename
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            modified_at = 0
        return {
            "id": self._hash_text(f"manual-strm|{root}|{path.relative_to(root).as_posix()}"),
            "origin": "manual_strm",
            "media_key": media_key,
            "media_type": media_type,
            "title": title,
            "year": year,
            "media_source": source,
            "media_id": media_id,
            "tmdb_id": self._safe_int(tmdb_id or (media_id if source == "themoviedb" else 0), 0),
            "douban_id": douban_id or (media_id if source == "douban" else ""),
            "season": season,
            "episode": episode,
            "path": str(path),
            "basename": basename,
            "filename": filename,
            "storage": "local",
            "library_name": "手动 STRM 目录",
            "relative_path": str(path.relative_to(root)).replace("\\", "/"),
            "target_label": f"{prefix} · {filename}" if media_type == "tv" else filename,
            "writable": True,
            "date": datetime.fromtimestamp(modified_at).isoformat(timespec="seconds") if modified_at else "",
            "identity_confidence": "nfo" if media_id else ("path" if title else "unresolved"),
            "nfo_path": self._normalize_text(nfo.get("path")),
        }

    def _path_meta(self, path: Path) -> Dict[str, Any]:
        if not self._meta_info_path:
            return {}
        try:
            meta = self._meta_info_path(path)
            type_value = self._normalize_text(getattr(getattr(meta, "type", None), "value", getattr(meta, "type", "")))
            return {
                "title": self._normalize_text(getattr(meta, "name", "")) or self._normalize_text(getattr(meta, "title", "")),
                "year": self._normalize_text(getattr(meta, "year", "")),
                "season": self._safe_int(getattr(meta, "begin_season", None) or getattr(meta, "season", None), 0),
                "episode": self._safe_int(getattr(meta, "begin_episode", None) or getattr(meta, "episode", None), 0),
                "is_tv": type_value.lower() in {"tv", "电视剧", "series"},
            }
        except Exception:
            return {}

    def _read_nfo(self, root: Path, path: Path) -> Dict[str, Any]:
        direct = self._read_nfo_file(path.with_suffix(".nfo"))
        season = self._read_nfo_file(path.parent / "season.nfo")
        show: Dict[str, Any] = {}
        parent = path.parent
        while True:
            candidate = self._read_nfo_file(parent / "tvshow.nfo")
            if candidate:
                show = candidate
                break
            if parent == root or parent.parent == parent:
                break
            parent = parent.parent
        is_tv = bool(show) or self._normalize_text(direct.get("root_tag")).lower() in {"tvshow", "episodedetails"}
        if is_tv:
            return {
                "path": show.get("path") or direct.get("path") or season.get("path") or "",
                "root_tag": show.get("root_tag") or direct.get("root_tag") or "",
                "title": show.get("title") or direct.get("showtitle") or direct.get("title") or "",
                "showtitle": direct.get("showtitle") or show.get("title") or "",
                "year": show.get("year") or direct.get("year") or "",
                "season": direct.get("season") or season.get("season") or "",
                "episode": direct.get("episode") or "",
                "tmdb_id": show.get("tmdb_id") or "",
                "douban_id": show.get("douban_id") or "",
                "media_source": show.get("media_source") or direct.get("media_source") or "",
                "media_id": show.get("media_id") or direct.get("media_id") or "",
            }
        return direct or season or show

    def _read_nfo_file(self, candidate: Path) -> Dict[str, Any]:
        if not candidate.is_file():
            return {}
        try:
            root = ET.parse(candidate).getroot()
            values = {child.tag.lower(): self._normalize_text(child.text) for child in root}
            unique_ids = {
                self._normalize_text(item.attrib.get("type")).lower(): self._normalize_text(item.text)
                for item in root.findall("uniqueid")
            }
            return {
                "path": str(candidate),
                "root_tag": root.tag,
                "title": values.get("title") or values.get("name"),
                "showtitle": values.get("showtitle"),
                "year": values.get("year"),
                "season": values.get("season") or values.get("seasonnumber"),
                "episode": values.get("episode") or values.get("episodenumber"),
                "tmdb_id": values.get("tmdbid") or unique_ids.get("tmdb") or unique_ids.get("themoviedb"),
                "douban_id": values.get("doubanid") or unique_ids.get("douban"),
                "media_source": values.get("mediasource") or values.get("source"),
                "media_id": values.get("mediaid") or values.get("media_id"),
            }
        except (OSError, ET.ParseError):
            return {}

    def _title_from_path(self, path: Path) -> str:
        candidates = [path.parent.name, path.parent.parent.name]
        for value in candidates:
            text = re.sub(r"\s*\([^)]{4}\)\s*$", "", value).strip()
            if text and not text.lower().startswith("season "):
                return text
        return path.stem


__all__ = ["ManualStrmCatalog"]
