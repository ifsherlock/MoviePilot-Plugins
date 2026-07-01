from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Optional

from .target_resolver import (
    apply_tmdb_detail as target_apply_tmdb_detail,
    entry_filesystem_signature as target_entry_filesystem_signature,
    entry_matches_keyword as target_entry_matches_keyword,
    entry_path_is_valid as target_entry_path_is_valid,
    extract_episode_hint as target_extract_episode_hint,
    is_stream_path as target_is_stream_path,
    media_type_text as target_media_type_text,
    poster_url as target_poster_url,
    tmdb_aliases as target_tmdb_aliases,
    tmdb_detail_payload as target_tmdb_detail_payload,
)


def ok_response(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def hash_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def brief_ids(values: Iterable[Any], limit: int = 5) -> str:
    items = [normalize_text(item)[:8] for item in values if normalize_text(item)]
    if len(items) > limit:
        return f"{','.join(items[:limit])},+{len(items) - limit}"
    return ",".join(items)


def decode_preview_bytes(raw_bytes: bytes) -> str:
    if not raw_bytes:
        return ""
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def timestamp_iso(ts: Any) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")
    except Exception:
        return ""


def cache_loaded_at(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    text = normalize_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def entry_path_is_valid(
    entry: dict[str, Any],
    *,
    trust_transfer_history_paths: bool,
) -> bool:
    return target_entry_path_is_valid(
        entry,
        normalize_text=normalize_text,
        trust_transfer_history_paths=trust_transfer_history_paths,
    )


def entry_filesystem_signature(entry: dict[str, Any]) -> str:
    return target_entry_filesystem_signature(entry, normalize_text=normalize_text)


def extract_episode_hint(file_name: str) -> Optional[dict[str, int]]:
    return target_extract_episode_hint(file_name, safe_int=safe_int)


def media_type_text(value: Any) -> str:
    return target_media_type_text(value)


def poster_url(
    poster_path: Any,
    prefix: str = "w500",
    *,
    settings_obj: Any,
) -> str:
    return target_poster_url(
        poster_path,
        prefix,
        settings_obj=settings_obj,
        normalize_text=normalize_text,
    )


def entry_matches_keyword(entry: dict[str, Any], keyword: str) -> bool:
    return target_entry_matches_keyword(
        entry,
        keyword,
        normalize_text=normalize_text,
    )


def tmdb_detail_payload(
    detail: Any,
    *,
    extract_title_aliases_func: Any,
) -> dict[str, Any]:
    return target_tmdb_detail_payload(
        detail,
        extract_title_aliases_func=extract_title_aliases_func,
        normalize_text=normalize_text,
    )


def tmdb_aliases(*values: Any, extract_title_aliases_func: Any) -> list[str]:
    return target_tmdb_aliases(
        *values,
        extract_title_aliases_func=extract_title_aliases_func,
    )


def apply_tmdb_detail(target: dict[str, Any], detail: dict[str, Any]) -> None:
    target_apply_tmdb_detail(target, detail)


def is_stream_path(path: Any, *, stream_exts: Iterable[str]) -> bool:
    return target_is_stream_path(path, normalize_text=normalize_text, stream_exts=stream_exts)


def is_upload_file(value: Any, *, upload_file_type: Any) -> bool:
    return isinstance(value, upload_file_type)
