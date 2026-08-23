from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional


NormalizeText = Callable[[Any], str]
SafeInt = Callable[[Any, int], int]
HashText = Callable[[str], str]
EpisodeHint = Callable[[str], Optional[Dict[str, int]]]


def _default_normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _default_safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def media_type_text(value: Any) -> str:
    raw = str(getattr(value, "value", value) or "").strip().lower()
    if raw in {"movie", "电影", "mediatype.movie"}:
        return "movie"
    if raw in {"tv", "电视剧", "series", "mediatype.tv"}:
        return "tv"
    return ""


def poster_url(
    poster_path: Any,
    prefix: str = "w500",
    *,
    settings_obj: Any = None,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    poster = normalize_text(poster_path)
    if not poster:
        return ""
    if poster.startswith(("http://", "https://")):
        if prefix:
            return re.sub(r"(/t/p/)[^/]+/", rf"\g<1>{prefix}/", poster, count=1)
        return poster
    if not poster.startswith("/"):
        poster = f"/{poster}"
    domain = normalize_text(getattr(settings_obj, "TMDB_IMAGE_DOMAIN", "")) or "image.tmdb.org"
    return f"https://{domain}/t/p/{prefix}{poster}"


def history_type_text(
    value: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    normalized = media_type_text(value)
    if normalized == "movie":
        return "电影"
    if normalized == "tv":
        return "电视剧"
    return normalize_text(value)


def number_from_tag(
    value: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    safe_int: SafeInt = _default_safe_int,
) -> int:
    match = re.search(r"\d+", normalize_text(value))
    return safe_int(match.group(0), 0) if match else 0


def extract_episode_hint(
    file_name: str,
    *,
    safe_int: SafeInt = _default_safe_int,
) -> Optional[Dict[str, int]]:
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
        season = safe_int(match.groupdict().get("season"), 0)
        episode = safe_int(match.groupdict().get("episode"), 0)
        if episode:
            return {"season": season, "episode": episode}
    return None


def is_local_video_path(
    storage: str,
    path: str,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    settings_obj: Any = None,
    stream_exts: Iterable[str] = (),
    trust_transfer_history_paths: bool = False,
) -> bool:
    if normalize_text(storage) != "local" or not path:
        return False
    suffix = Path(path).suffix.lower()
    configured_exts = getattr(settings_obj, "RMT_MEDIAEXT", set()) or set()
    allowed_exts = {
        ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in configured_exts
    }
    allowed_exts.update(stream_exts)
    if suffix and allowed_exts and suffix not in allowed_exts:
        return False
    if trust_transfer_history_paths:
        return True
    try:
        return Path(path).is_file()
    except Exception:
        return False


def event_value(obj: Any, *names: str, default: Any = "") -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def is_stream_path(
    path: Any,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    stream_exts: Iterable[str] = (),
) -> bool:
    return Path(normalize_text(path)).suffix.lower() in set(stream_exts)


def entry_path_is_valid(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText = _default_normalize_text,
    trust_transfer_history_paths: bool = False,
) -> bool:
    storage = normalize_text(entry.get("storage")) or "local"
    if storage != "local":
        return True
    path = normalize_text(entry.get("path"))
    if not path:
        return False
    if trust_transfer_history_paths:
        return True
    try:
        return Path(path).is_file()
    except Exception:
        return False


def entry_filesystem_signature(
    entry: Dict[str, Any],
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> str:
    storage = normalize_text(entry.get("storage")) or "local"
    path_text = normalize_text(entry.get("path"))
    if storage != "local" or not path_text:
        return f"{storage}|{path_text}|remote"
    path = Path(path_text)
    normalized_path = path_text.lower().replace("\\", "/")
    try:
        stat = path.stat()
        parent_mtime = path.parent.stat().st_mtime_ns if path.parent.exists() else 0
        return "|".join(
            [
                "local",
                normalized_path,
                "1",
                str(stat.st_size),
                str(stat.st_mtime_ns),
                str(parent_mtime),
            ]
        )
    except FileNotFoundError:
        return f"local|{normalized_path}|0"
    except Exception as exc:
        return f"local|{normalized_path}|error:{type(exc).__name__}"


def entry_matches_keyword(
    entry: Dict[str, Any],
    keyword: str,
    *,
    normalize_text: NormalizeText = _default_normalize_text,
) -> bool:
    clean_keyword = normalize_text(keyword).lower()
    if not clean_keyword:
        return True
    haystack = " ".join(
        normalize_text(entry.get(key)).lower()
        for key in ("title", "filename", "basename", "relative_path")
    )
    return all(part in haystack for part in re.split(r"\s+", clean_keyword) if part)


__all__ = [name for name in globals() if not name.startswith("__")]
