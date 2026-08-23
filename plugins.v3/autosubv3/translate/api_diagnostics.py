from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def safe_api_url(value: Any) -> str:
    """Return a log-safe API URL without credentials, query, or fragment."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
        hostname = parts.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        port = f":{parts.port}" if parts.port else ""
        netloc = f"{hostname}{port}" if hostname else ""
        return urlunsplit((parts.scheme, netloc, parts.path, "", "")) or _fallback_url(text)
    except (TypeError, ValueError):
        return _fallback_url(text)


def _fallback_url(value: str) -> str:
    text = value.split("?", 1)[0].split("#", 1)[0]
    if "://" not in text:
        return text
    scheme, remainder = text.split("://", 1)
    return f"{scheme}://{remainder.rsplit('@', 1)[-1]}"


def sanitize_api_error(value: Any, *secrets: Any, limit: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    secret_values = sorted(
        {str(secret or "").strip() for secret in secrets if str(secret or "").strip()},
        key=len,
        reverse=True,
    )
    for secret_text in secret_values:
        text = text.replace(secret_text, "***")
    return text[:limit] or "请求失败，接口未返回具体原因"
