from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..timeline_fixer import check_timeline_fixer_dependencies


class StatusApi:
    def __init__(self, owner: Any):
        self.owner = owner

    def status(self) -> Dict[str, Any]:
        owner = self.owner
        rar_tool = owner._rar_tool()
        rar_python = owner._rar_python_available()
        return owner._ok(
            {
                "enabled": owner.get_state(),
                "auto_search_on_transfer": bool(owner._auto_search_on_transfer),
                "auto_skip_chinese_media_on_transfer": bool(owner._auto_skip_chinese_media_on_transfer),
                "auto_transfer_subtitle_strategy": owner._auto_transfer_subtitle_strategy,
                "traditional_to_simplified": bool(owner._traditional_to_simplified),
                "source": "MoviePilot 本地整理记录",
                "index": owner._cache_status(),
                "archive_support": {
                    "zip": True,
                    "rar": bool(rar_tool),
                    "rar_tool": Path(rar_tool).name if rar_tool else "",
                    "rar_tool_path": rar_tool or owner._rar_tool_path,
                    "rar_python": rar_python,
                    "rar_python_package": owner._rar_python_package,
                    "dependency_mode": owner._rar_dependency_mode,
                    "dependency_status": owner._rar_dependency_status,
                },
                "timeline_fixer": {
                    **check_timeline_fixer_dependencies(),
                    "configured_max_offset_seconds": owner._timeline_max_offset_seconds,
                    "configured_min_offset_seconds": owner._timeline_min_offset_seconds,
                    "vad_mode": owner._timeline_vad_mode,
                    "allow_risky_offset": bool(owner._timeline_allow_risky_offset),
                },
                "online_search": {
                    "enabled_providers": owner._online_provider_ids,
                    "assrt_api_configured": bool(owner._assrt_api_key),
                    "assrt_api_host": owner._host_from_url(owner._assrt_api_url),
                    "opensubtitles_api_configured": bool(owner._opensubtitles_api_key),
                    "opensubtitles_api_host": owner._host_from_url(owner._opensubtitles_api_url),
                    "opensubtitles_download_configured": bool(
                        owner._opensubtitles_username and owner._opensubtitles_password
                    ),
                },
                "auto_transfer_queue": owner._auto_transfer_queue_summary(),
                "ai_subtitle": owner._autosub_status(),
            }
        )

    def refresh_index(self) -> Dict[str, Any]:
        owner = self.owner
        owner._start_background_cache_refresh()
        cache_status = owner._cache_status()
        has_cache = bool((owner._local_entries_cache or {}).get("entries"))
        message = "媒体库资源清单已在后台刷新"
        if has_cache:
            message += "，当前页面先使用已有缓存"
        else:
            message += "，首次刷新完成前列表可能暂时为空"
        return owner._ok(
            {
                "realtime": False,
                "background": True,
                "index": cache_status,
            },
            message=message,
        )

    def auto_transfer_queue(self, request: Any) -> Dict[str, Any]:
        owner = self.owner
        limit = min(max(owner._safe_int(request.query_params.get("limit"), 100), 1), 200)
        return owner._ok(owner._auto_transfer_service().auto_transfer_queue_snapshot(limit=limit))
