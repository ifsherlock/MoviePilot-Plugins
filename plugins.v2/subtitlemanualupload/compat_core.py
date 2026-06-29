from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.core.config import settings

from .autosub_bridge import autosub_task_summary as bridge_autosub_task_summary
from .config_schema import normalize_auto_transfer_subtitle_strategy
from .online_subtitle import check_online_rate_limit, extract_title_aliases
from .subtitle_language import detect_language_profile, normalize_language_suffix
from .subtitle_writer import (
    subtitle_backup_path as writer_subtitle_backup_path,
    timeline_rejection_message as writer_timeline_rejection_message,
    timeline_result_blocks_auto_write as writer_timeline_result_blocks_auto_write,
)
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
from .timeline_tasks import timeline_task_summary


def host_module_value(owner_cls, name: str, default: Any) -> Any:
    module = sys.modules.get(owner_cls.__module__)
    return getattr(module, name, default) if module is not None else default


def ok(_owner, data: Any = None, message: str = "ok") -> Dict[str, Any]:
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


def brief_ids(owner_cls, values: Iterable[Any], limit: int = 5) -> str:
    items = [owner_cls._normalize_text(item)[:8] for item in values if owner_cls._normalize_text(item)]
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


def check_online_rate_limit_compat(owner, providers: Iterable[str]) -> None:
    check_online_rate_limit(
        providers,
        records=owner._online_rate_records,
        limit_per_minute=owner._online_rate_limit_per_minute,
        now=owner._host_module_value("time", time).time(),
        normalize_text=owner._normalize_text,
        http_exception=HTTPException,
    )


def entry_path_is_valid(owner_cls, entry: Dict[str, Any]) -> bool:
    return target_entry_path_is_valid(
        entry,
        normalize_text=owner_cls._normalize_text,
        trust_transfer_history_paths=getattr(owner_cls, "_trust_transfer_history_paths", False),
    )


def timestamp_iso(ts: Any) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")
    except Exception:
        return ""


def cache_loaded_at(owner_cls, value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    text = owner_cls._normalize_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def poster_url(owner_cls, poster_path: Any, prefix: str = "w500") -> str:
    return target_poster_url(
        poster_path,
        prefix,
        settings_obj=settings,
        normalize_text=owner_cls._normalize_text,
    )


def tmdb_detail_payload(owner_cls, detail: Any) -> Dict[str, Any]:
    return target_tmdb_detail_payload(
        detail,
        extract_title_aliases_func=extract_title_aliases,
        normalize_text=owner_cls._normalize_text,
    )


def is_stream_path(owner_cls, path: Any) -> bool:
    return target_is_stream_path(
        path,
        normalize_text=owner_cls._normalize_text,
        stream_exts=owner_cls._stream_exts,
    )


def subtitle_backup_path(_owner_cls, subtitle_path: Path) -> Path:
    return writer_subtitle_backup_path(subtitle_path)
