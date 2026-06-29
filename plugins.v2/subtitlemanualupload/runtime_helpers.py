from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Optional


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
