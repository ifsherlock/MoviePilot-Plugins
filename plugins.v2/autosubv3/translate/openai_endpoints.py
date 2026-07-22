from __future__ import annotations

import ast
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .api_diagnostics import safe_api_url, sanitize_api_error
from .openai_translate import OpenAi


DEFAULT_API_URL = "https://api.siliconflow.cn"
DEFAULT_MODEL = "inclusionAI/Ling-flash-2.0"
LEGACY_ENDPOINT_ID = "default"


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_openai_model(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("value", "id", "model", "title"):
            model = normalize_openai_model(value.get(key))
            if model:
                return model
        return ""
    if isinstance(value, (list, tuple)):
        return normalize_openai_model(value[0]) if value else ""
    text = _text(value)
    if text == "[object Object]":
        return ""
    if text.startswith(("{", "[")):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except (TypeError, ValueError, SyntaxError):
                continue
            if parsed != value:
                return normalize_openai_model(parsed)
    return text


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _raw_endpoint_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def normalize_openai_endpoints(config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, bool]:
    raw_items = _raw_endpoint_list((config or {}).get("openai_endpoints"))
    if not raw_items:
        raw_items = [
            {
                "id": LEGACY_ENDPOINT_ID,
                "name": "默认线路",
                "api_url": (config or {}).get("openai_url") or DEFAULT_API_URL,
                "api_key": (config or {}).get("openai_key") or "",
                "model": (config or {}).get("openai_model") or DEFAULT_MODEL,
                "use_proxy": (config or {}).get("openai_proxy", False),
                "compatible": (config or {}).get("compatible", False),
                "enabled": True,
            }
        ]

    endpoints: List[Dict[str, Any]] = []
    used_ids = set()
    for index, item in enumerate(raw_items, start=1):
        endpoint_id = _text(item.get("id")) or f"endpoint-{index}"
        if endpoint_id in used_ids:
            endpoint_id = f"{endpoint_id}-{index}"
        used_ids.add(endpoint_id)
        endpoints.append(
            {
                "id": endpoint_id,
                "name": _text(item.get("name")) or f"API 线路 {index}",
                "api_url": (_text(item.get("api_url") or item.get("openai_url")) or DEFAULT_API_URL).rstrip("/"),
                "api_key": _text(item.get("api_key") or item.get("openai_key")),
                "model": normalize_openai_model(item.get("model") or item.get("openai_model")) or DEFAULT_MODEL,
                "use_proxy": _bool(item.get("use_proxy", item.get("openai_proxy")), False),
                "compatible": _bool(item.get("compatible"), False),
                "enabled": _bool(item.get("enabled"), True),
            }
        )

    active_id = _text((config or {}).get("openai_active_endpoint"))
    available_ids = {item["id"] for item in endpoints if item["enabled"]}
    if active_id not in available_ids:
        active_id = next((item["id"] for item in endpoints if item["enabled"]), endpoints[0]["id"])
    fallback_enabled = _bool((config or {}).get("openai_fallback_enabled"), True)
    return endpoints, active_id, fallback_enabled


def active_openai_endpoint(endpoints: List[Dict[str, Any]], active_id: str) -> Dict[str, Any]:
    return next((item for item in endpoints if item.get("id") == active_id), endpoints[0] if endpoints else {})


def apply_openai_endpoint_compatibility_fields(
    config: Dict[str, Any],
    endpoints: List[Dict[str, Any]],
    active_id: str,
    fallback_enabled: bool,
) -> bool:
    active = active_openai_endpoint(endpoints, active_id)
    normalized_values = {
        "openai_endpoints": endpoints,
        "openai_active_endpoint": active_id,
        "openai_fallback_enabled": bool(fallback_enabled),
        "openai_url": active.get("api_url") or DEFAULT_API_URL,
        "openai_key": active.get("api_key") or "",
        "openai_model": active.get("model") or DEFAULT_MODEL,
        "openai_proxy": bool(active.get("use_proxy")),
        "compatible": bool(active.get("compatible")),
    }
    changed = any(config.get(key) != value for key, value in normalized_values.items())
    config.update(normalized_values)
    return changed


def configured_openai_endpoints(endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        item
        for item in endpoints
        if item.get("enabled") and item.get("api_url") and item.get("api_key") and item.get("model")
    ]


class OpenAiEndpointPool:
    def __init__(
        self,
        endpoints: List[Dict[str, Any]],
        *,
        active_id: str,
        fallback_enabled: bool,
        proxy: Optional[Dict[str, Any]],
        logger: Any,
        client_factory: Callable[..., OpenAi] = OpenAi,
        failure_cooldown_seconds: float = 30.0,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self._endpoints = configured_openai_endpoints(endpoints)
        self._active_id = active_id
        self._fallback_enabled = bool(fallback_enabled)
        self._proxy = proxy
        self._logger = logger
        self._failure_cooldown_seconds = max(0.0, float(failure_cooldown_seconds))
        self._time = time_func
        self._lock = threading.Lock()
        self._failed_at: Dict[str, float] = {}
        self._clients: Dict[str, OpenAi] = {}
        self._client_errors: Dict[str, str] = {}
        self._last_error = ""
        for endpoint in self._endpoints:
            try:
                self._clients[endpoint["id"]] = client_factory(
                    api_key=endpoint["api_key"],
                    api_url=endpoint["api_url"],
                    proxy=self._proxy if endpoint.get("use_proxy") else None,
                    model=endpoint["model"],
                    compatible=bool(endpoint.get("compatible")),
                    logger=logger,
                    endpoint_name=endpoint["name"],
                )
            except Exception as exc:
                error = self._error_text(endpoint, exc)
                self._client_errors[endpoint["id"]] = error
                logger.error(
                    "[AutoSubv3] AI API 客户端初始化失败 endpoint=%s url=%s model=%s error=%s",
                    endpoint["name"],
                    safe_api_url(endpoint["api_url"]),
                    endpoint["model"],
                    error,
                )

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    @property
    def model(self) -> str:
        primary = self._ordered_endpoints(include_cooling=True)
        return primary[0].get("model", "") if primary else ""

    @property
    def endpoint_count(self) -> int:
        return len(self._endpoints)

    def _ordered_endpoints(self, *, include_cooling: bool = False) -> List[Dict[str, Any]]:
        ordered = sorted(self._endpoints, key=lambda item: 0 if item["id"] == self._active_id else 1)
        if not self._fallback_enabled:
            ordered = ordered[:1]
        now = self._time()
        with self._lock:
            ready = [
                item
                for item in ordered
                if now - self._failed_at.get(item["id"], -self._failure_cooldown_seconds) >= self._failure_cooldown_seconds
            ]
        return ordered if include_cooling or not ready else ready

    @staticmethod
    def _error_text(endpoint: Dict[str, Any], value: Any) -> str:
        return sanitize_api_error(value, endpoint.get("api_key"), endpoint.get("api_url"), limit=500)

    def _record_failure(self, endpoint: Dict[str, Any], error: str) -> None:
        with self._lock:
            self._failed_at[endpoint["id"]] = self._time()
        self._logger.warning(
            "[AutoSubv3] AI API 请求失败 endpoint=%s url=%s model=%s error=%s",
            endpoint["name"],
            safe_api_url(endpoint["api_url"]),
            endpoint["model"],
            error,
        )

    def _record_success(self, endpoint: Dict[str, Any]) -> None:
        with self._lock:
            self._failed_at.pop(endpoint["id"], None)
            self._last_error = ""
        if endpoint["id"] != self._active_id:
            callback = getattr(self._logger, "debug", None)
            if callback:
                callback("[AutoSubv3] AI API 已切换到备用线路 endpoint=%s model=%s", endpoint["name"], endpoint["model"])

    def _all_failed(self, failures: List[str]) -> str:
        message = "；".join(failures) or "没有可用的 AI API 端点"
        with self._lock:
            self._last_error = message
        self._logger.error("[AutoSubv3] 所有 AI API 端点均失败：%s", message)
        return message

    def translate_to_zh(self, text: str, context: str = None, max_retries: int = 3):
        failures: List[str] = []
        for endpoint in self._ordered_endpoints():
            client = self._clients.get(endpoint["id"])
            if not client:
                failures.append(f"{endpoint['name']}：{self._client_errors[endpoint['id']]}")
                continue
            try:
                success, result = client.translate_to_zh(text, context, max_retries=max_retries)
            except Exception as exc:
                success, result = False, exc
            if success:
                self._record_success(endpoint)
                return True, result
            error = self._error_text(endpoint, getattr(client, "last_error", "") or result)
            failures.append(f"{endpoint['name']}：{error}")
            self._record_failure(endpoint, error)
        return False, self._all_failed(failures)

    def translate_batch_to_zh(self, texts: List[str], max_retries: int = 3):
        failures: List[str] = []
        for endpoint in self._ordered_endpoints():
            client = self._clients.get(endpoint["id"])
            if not client:
                failures.append(f"{endpoint['name']}：{self._client_errors[endpoint['id']]}")
                continue
            try:
                success, result = client.translate_batch_to_zh(texts, max_retries=max_retries)
            except Exception as exc:
                success, result = False, [None] * len(texts)
                client_error = exc
            else:
                client_error = getattr(client, "last_error", "")
            if success:
                self._record_success(endpoint)
                return True, result
            error = self._error_text(endpoint, client_error)
            failures.append(f"{endpoint['name']}：{error}")
            self._record_failure(endpoint, error)
        self._all_failed(failures)
        return False, [None] * len(texts)
