from __future__ import annotations

try:
    from ..online_subtitles.core import *  # noqa: F401,F403
except ImportError:
    import importlib.util
    import types
    import sys
    from pathlib import Path

    package_path = Path(__file__).resolve().parents[1] / "online_subtitles"
    package_name = "_subtitlemanualupload_online_subtitles"
    module_path = package_path / "core.py"
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules.setdefault(package_name, package)
    spec = importlib.util.spec_from_file_location(f"{package_name}.core", module_path)
    if spec is None or spec.loader is None:
        raise
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    globals().update(
        {
            name: value
            for name, value in vars(module).items()
            if not (name.startswith("__") and name.endswith("__"))
        }
    )


def check_online_rate_limit(
    providers,
    *,
    records,
    limit_per_minute,
    now,
    normalize_text,
    http_exception,
) -> None:
    provider_ids = sorted({normalize_text(provider_id).lower() for provider_id in providers if normalize_text(provider_id)})
    blocked = []
    active_records = {}
    for provider_id in provider_ids:
        recent = [item for item in records.get(provider_id, []) if now - item < 60]
        active_records[provider_id] = recent
        if len(recent) >= limit_per_minute:
            blocked.append(provider_id)
    if blocked:
        raise http_exception(
            status_code=429,
            detail=f"在线字幕源请求过于频繁：{','.join(blocked)} 每分钟最多 {limit_per_minute} 次，请稍后再试",
        )
    for provider_id, recent in active_records.items():
        recent.append(now)
        records[provider_id] = recent
