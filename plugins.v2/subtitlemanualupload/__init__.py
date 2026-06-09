from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.db.models.transferhistory import TransferHistory
from app.log import logger
from app.plugins import _PluginBase

try:
    from app.core.plugin import PluginManager
except Exception:
    PluginManager = None

try:
    from app.core.event import eventmanager, Event as MPEvent
    from app.schemas.types import EventType
except Exception:
    class _NoopEventManager:
        @staticmethod
        def register(_event_type):
            def decorator(func):
                return func

            return decorator

    class _NoopEventType:
        TransferComplete = "transfer.complete"

    eventmanager = _NoopEventManager()
    MPEvent = Any
    EventType = _NoopEventType

from .online_subtitle import (
    CaptchaRequiredError,
    DEFAULT_ENGINE,
    DEFAULT_PROVIDER_ROOTS,
    OnlineSubtitleSearchService,
    build_search_keywords,
    normalize_online_engine,
    normalize_provider_roots,
)
from .timeline_fixer import TimelineFixResult, check_timeline_fixer_dependencies, fix_subtitle_timeline
from .tongwen import convert_subtitle_file_to_simplified


class SubtitleManualUpload(_PluginBase):
    plugin_name = "字幕匹配"
    plugin_desc = "手动上传字幕、ZIP 或 RAR，匹配电影/剧集并按媒体文件名落盘，可选智能调轴。"
    plugin_icon = "https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/icons/subtitle-match.png"
    plugin_version = "0.1.45"
    plugin_author = "jaysherlock"
    author_url = "https://github.com/jaysherlock"
    plugin_config_prefix = "subtitlemanualupload_"
    plugin_order = 48
    auth_level = 1

    _enabled = False
    _show_sidebar_nav = True
    _rar_dependency_mode = "none"
    _rar_tool_path = "/usr/local/bin/7z"
    _default_online_provider_ids = ["assrt", "opensubtitles"]
    _manual_online_provider_ids = ["subhd", "zimuku", "assrt", "opensubtitles"]
    _online_provider_ids = ["assrt", "opensubtitles"]
    _online_engine = DEFAULT_ENGINE
    _online_use_proxy = False
    _online_site_urls = dict(DEFAULT_PROVIDER_ROOTS)
    _online_rate_records: Dict[str, List[float]] = {}
    _online_rate_limit_per_minute = 5
    _assrt_api_key = ""
    _assrt_api_url = "https://api.assrt.net"
    _opensubtitles_api_key = ""
    _opensubtitles_api_url = "https://api.opensubtitles.com/api/v1"
    _opensubtitles_username = ""
    _opensubtitles_password = ""
    _ai_link_enabled = True
    _traditional_to_simplified = False
    _auto_search_on_transfer = False
    _auto_search_min_score = 20
    _cache_ttl_seconds = 90
    _cache_max_entries = 5000
    _entry_map_max_size = 2000
    _rar_dependency_status: Dict[str, Any] = {
        "mode": "none",
        "state": "idle",
        "message": "",
        "checked_at": "",
    }
    _entry_map: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _cache_refreshing = False
    _local_entries_cache: Dict[str, Any] = {
        "loaded_at": None,
        "entries": [],
        "media_count": 0,
        "persisted": False,
    }

    _subtitle_exts = {".ass", ".srt", ".ssa", ".sbv", ".sub", ".vtt", ".webvtt"}
    _archive_exts = {".zip", ".rar"}
    _rar_exts = {".rar"}
    _rar_tools = ("unrar", "bsdtar", "7z", "7za", "7zz")
    _rar_python_package = "rarfile"
    _rar_dependency_modes = {"none", "container_install", "mapped_binary"}
    _stream_exts = {".strm"}
    _default_session_hours = 24
    _language_suffix_aliases = {
        "zh": "chi",
        "zh-hans": "chi",
        "zh_hans": "chi",
        "zh-cn": "chi",
        "zh_cn": "chi",
        "zh-hant": "cht",
        "zh_hant": "cht",
        "zh-tw": "cht",
        "zh_tw": "cht",
        "chs": "chi",
        "cht": "cht",
        "tw": "cht",
        "hk": "cht",
        "zho": "chi",
        "cmn": "chi",
        "cn": "chi",
        "en": "eng",
        "ja": "jpn",
        "jp": "jpn",
        "ko": "kor",
        "kr": "kor",
        "fr": "fre",
        "fra": "fre",
        "de": "ger",
        "deu": "ger",
        "es": "spa",
        "pt": "por",
        "it": "ita",
        "ru": "rus",
    }

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._show_sidebar_nav = bool(config.get("show_sidebar_nav", True))
        self._rar_dependency_mode = self._normalize_rar_dependency_mode(config.get("rar_dependency_mode"))
        self._rar_tool_path = self._normalize_text(config.get("rar_tool_path")) or "/usr/local/bin/7z"
        self._online_provider_ids = self._normalize_provider_ids(config.get("online_providers"))
        self._online_engine = normalize_online_engine(config.get("online_engine"))
        legacy_proxy_default = "online_proxy_migrated" not in config and config.get("online_use_proxy") is True
        self._online_use_proxy = False if legacy_proxy_default else bool(config.get("online_use_proxy", False))
        self._online_site_urls = self._normalize_online_site_urls(config)
        self._assrt_api_key = self._normalize_text(config.get("assrt_api_key"))
        self._assrt_api_url = self._normalize_root_url(
            config.get("assrt_api_url"),
            "https://api.assrt.net",
        )
        self._opensubtitles_api_key = self._normalize_text(config.get("opensubtitles_api_key"))
        self._opensubtitles_api_url = self._normalize_root_url(
            config.get("opensubtitles_api_url"),
            "https://api.opensubtitles.com/api/v1",
        )
        self._opensubtitles_username = self._normalize_text(config.get("opensubtitles_username"))
        if "@" in self._opensubtitles_username:
            logger.warning("[SubtitleManualUpload] OpenSubtitles 用户名疑似邮箱，已忽略下载认证用户名")
            self._opensubtitles_username = ""
        self._opensubtitles_password = self._normalize_text(config.get("opensubtitles_password"))
        self._ai_link_enabled = bool(config.get("ai_link_enabled", True))
        self._traditional_to_simplified = bool(config.get("traditional_to_simplified", False))
        self._auto_search_on_transfer = bool(config.get("auto_search_on_transfer", False))
        if not config.get("assrt_provider_migrated") and not self._assrt_api_key:
            self._online_provider_ids = [item for item in self._online_provider_ids if item != "assrt"]
        if self._assrt_api_key and "assrt" not in self._online_provider_ids:
            self._online_provider_ids.append("assrt")
        if self._opensubtitles_api_key and "opensubtitles" not in self._online_provider_ids:
            self._online_provider_ids.append("opensubtitles")
        self._online_provider_ids = [
            item
            for item in self._online_provider_ids
            if item in self._default_online_provider_ids
            and (item != "assrt" or self._assrt_api_key)
            and (item != "opensubtitles" or self._opensubtitles_api_key)
        ]
        type(self)._rar_dependency_mode = self._rar_dependency_mode
        type(self)._rar_tool_path = self._rar_tool_path
        type(self)._traditional_to_simplified = self._traditional_to_simplified
        type(self)._auto_search_on_transfer = self._auto_search_on_transfer
        self._entry_map = OrderedDict()
        self._cache_refreshing = False
        self._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
        self._restore_persisted_local_cache()
        self._save_config()
        self._prepare_rar_dependency()
        self._cleanup_old_sessions()

    def get_state(self) -> bool:
        return bool(self._enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取字幕匹配插件状态",
            },
            {
                "path": "/refresh_index",
                "endpoint": self.api_refresh_index,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "兼容旧版刷新索引入口",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "搜索 MoviePilot 本地资源候选",
            },
            {
                "path": "/targets",
                "endpoint": self.api_targets,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取选中媒体的本地文件目标",
            },
            {
                "path": "/prepare_upload",
                "endpoint": self.api_prepare_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "上传字幕并生成匹配预览",
            },
            {
                "path": "/apply_upload",
                "endpoint": self.api_apply_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "应用字幕匹配结果并写入目标目录",
            },
            {
                "path": "/clear_subtitles",
                "endpoint": self.api_clear_subtitles,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空选中目标视频的外挂字幕",
            },
            {
                "path": "/ai_submit",
                "endpoint": self.api_ai_submit,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "提交 AI 字幕生成任务",
            },
            {
                "path": "/ai_tasks",
                "endpoint": self.api_ai_tasks,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "查询当前资源的 AI 字幕生成任务状态",
            },
            {
                "path": "/ai_cancel",
                "endpoint": self.api_ai_cancel,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消 AI 字幕生成任务",
            },
            {
                "path": "/online_status",
                "endpoint": self.api_online_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取在线字幕源状态",
            },
            {
                "path": "/online_manual_links",
                "endpoint": self.api_online_manual_links,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "生成在线字幕站手动搜索链接",
            },
            {
                "path": "/online_search",
                "endpoint": self.api_online_search,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "搜索在线字幕",
            },
            {
                "path": "/online_search_provider",
                "endpoint": self.api_online_search_provider,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "搜索单个在线字幕源",
            },
            {
                "path": "/online_download_preview",
                "endpoint": self.api_online_download_preview,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "下载在线字幕并生成匹配预览",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "show_sidebar_nav",
                                            "label": "显示侧边栏入口",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "traditional_to_simplified",
                                            "label": "写入前繁体转简体",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "auto_search_on_transfer",
                                            "label": "入库后自动搜索匹配字幕",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "online_providers",
                                            "label": "自动字幕源（API）",
                                            "multiple": True,
                                            "chips": True,
                                            "items": [
                                                {"title": "射手网(伪，需 API Key)", "value": "assrt"},
                                                {"title": "OpenSubtitles 多语言字幕", "value": "opensubtitles"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "online_use_proxy",
                                            "label": "API 搜索和下载使用 MoviePilot 系统代理（默认关闭）",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "subhd_url",
                                            "label": "SubHD 手动跳转地址",
                                            "placeholder": DEFAULT_PROVIDER_ROOTS["subhd"],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "zimuku_url",
                                            "label": "Zimuku 手动跳转地址",
                                            "placeholder": DEFAULT_PROVIDER_ROOTS["zimuku"],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "assrt_url",
                                            "label": "射手网(伪) 站点地址",
                                            "placeholder": DEFAULT_PROVIDER_ROOTS["assrt"],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "opensubtitles_url",
                                            "label": "OpenSubtitles 站点地址",
                                            "placeholder": DEFAULT_PROVIDER_ROOTS["opensubtitles"],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "assrt_api_url",
                                            "label": "射手网(伪) API 地址",
                                            "placeholder": "https://api.assrt.net",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "assrt_api_key",
                                            "label": "射手网(伪) API Key",
                                            "type": "password",
                                            "placeholder": "未填写时不参与自动搜索",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "opensubtitles_api_url",
                                            "label": "OpenSubtitles API 地址",
                                            "placeholder": "https://api.opensubtitles.com/api/v1",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "opensubtitles_api_key",
                                            "label": "OpenSubtitles API Key",
                                            "type": "password",
                                            "placeholder": "未填写时不参与自动搜索",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "opensubtitles_username",
                                            "label": "OpenSubtitles 用户名（可选）",
                                            "placeholder": "下载时用于后台登录换取 token",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "opensubtitles_password",
                                            "label": "OpenSubtitles 密码（可选）",
                                            "type": "password",
                                            "placeholder": "下载时用于后台登录换取 token",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "从 MoviePilot 本地整理记录中搜索已有视频资源；在线自动搜索仅使用射手网(伪) 和 OpenSubtitles API，SubHD/Zimuku 只保留手动跳转。",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "rar_dependency_mode",
                                            "label": "RAR 解压器处理方式",
                                            "items": [
                                                {"title": "不处理，仅检测", "value": "none"},
                                                {"title": "加载插件时尝试容器内安装", "value": "container_install"},
                                                {"title": "使用宿主机映射文件", "value": "mapped_binary"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "rar_tool_path",
                                            "label": "容器内映射路径",
                                            "placeholder": "/usr/local/bin/7z",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "show_sidebar_nav": True,
            "rar_dependency_mode": "none",
            "rar_tool_path": "/usr/local/bin/7z",
            "traditional_to_simplified": False,
            "auto_search_on_transfer": False,
            "online_providers": list(self._default_online_provider_ids),
            "online_engine": DEFAULT_ENGINE,
            "online_use_proxy": False,
            "subhd_url": DEFAULT_PROVIDER_ROOTS["subhd"],
            "zimuku_url": DEFAULT_PROVIDER_ROOTS["zimuku"],
            "assrt_url": DEFAULT_PROVIDER_ROOTS["assrt"],
            "assrt_api_key": "",
            "assrt_api_url": "https://api.assrt.net",
            "opensubtitles_url": DEFAULT_PROVIDER_ROOTS["opensubtitles"],
            "opensubtitles_api_key": "",
            "opensubtitles_api_url": "https://api.opensubtitles.com/api/v1",
            "opensubtitles_username": "",
            "opensubtitles_password": "",
            "ai_link_enabled": True,
        }

    def get_page(self) -> List[dict]:
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self.get_state() or not self._show_sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "字幕匹配",
                "icon": "mdi-file-upload-outline",
                "section": "organize",
                "permission": "manage",
                "order": 48,
            }
        ]

    def stop_service(self):
        pass

    @eventmanager.register(EventType.TransferComplete)
    def listen_transfer_complete(self, event: MPEvent):
        if not self.get_state() or not self._auto_search_on_transfer:
            return
        event_data = getattr(event, "event_data", None) or {}
        if not isinstance(event_data, dict):
            return
        entries = self._entries_from_transfer_event(event_data)
        if not entries:
            logger.info("[SubtitleManualUpload] 入库事件未解析到本地视频目标，跳过自动字幕搜索")
            return
        self._merge_local_entries_cache(entries)
        threading.Thread(
            target=self._process_transfer_auto_subtitles,
            args=(entries,),
            name="SubtitleManualUploadTransferAutoSearch",
            daemon=True,
        ).start()

    def _save_config(self) -> None:
        self.update_config(
            {
                "enabled": self._enabled,
                "show_sidebar_nav": self._show_sidebar_nav,
                "rar_dependency_mode": self._rar_dependency_mode,
                "rar_tool_path": self._rar_tool_path,
                "traditional_to_simplified": self._traditional_to_simplified,
                "auto_search_on_transfer": self._auto_search_on_transfer,
                "online_providers": self._online_provider_ids,
                "online_engine": self._online_engine,
                "online_use_proxy": self._online_use_proxy,
                "online_proxy_migrated": True,
                "assrt_provider_migrated": True,
                "subhd_url": self._online_site_urls["subhd"],
                "zimuku_url": self._online_site_urls["zimuku"],
                "assrt_url": self._online_site_urls["assrt"],
                "assrt_api_key": self._assrt_api_key,
                "assrt_api_url": self._assrt_api_url,
                "opensubtitles_url": self._online_site_urls["opensubtitles"],
                "opensubtitles_api_key": self._opensubtitles_api_key,
                "opensubtitles_api_url": self._opensubtitles_api_url,
                "opensubtitles_username": self._opensubtitles_username,
                "opensubtitles_password": self._opensubtitles_password,
                "ai_link_enabled": self._ai_link_enabled,
            }
        )

    def _ok(self, data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _normalize_root_url(cls, value: Any, default: str) -> str:
        url = cls._normalize_text(value).rstrip("/")
        if re.match(r"^https?://", url, flags=re.I):
            return url
        return default

    @classmethod
    def _host_from_url(cls, value: Any) -> str:
        match = re.match(r"^https?://([^/?#]+)", cls._normalize_text(value), flags=re.I)
        return match.group(1) if match else ""

    @classmethod
    def _site_hosts(cls, site: Any) -> List[str]:
        hosts: List[str] = []
        for attr in ("url", "domain"):
            host = cls._normalize_site_host(getattr(site, attr, ""))
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    @classmethod
    def _normalize_site_host(cls, value: Any) -> str:
        text = cls._normalize_text(value)
        if not text:
            return ""
        host = cls._host_from_url(text)
        if not host:
            text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text, flags=re.I)
            host = re.split(r"[/?#]", text, maxsplit=1)[0]
        if "@" in host:
            host = host.rsplit("@", 1)[-1]
        if ":" in host:
            host = host.split(":", 1)[0]
        return host.strip(".").lower()

    @staticmethod
    def _site_host_matches(site_host: str, target_host: str) -> bool:
        site_host = site_host.lower().removeprefix("www.")
        target_host = target_host.lower().removeprefix("www.")
        return site_host == target_host or site_host.endswith(f".{target_host}") or target_host.endswith(f".{site_host}")

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    @classmethod
    def _brief_ids(cls, values: Iterable[Any], limit: int = 5) -> str:
        items = [cls._normalize_text(item)[:8] for item in values if cls._normalize_text(item)]
        if len(items) > limit:
            return f"{','.join(items[:limit])},+{len(items) - limit}"
        return ",".join(items)

    @staticmethod
    def _decode_preview_bytes(raw_bytes: bytes) -> str:
        if not raw_bytes:
            return ""
        for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
            try:
                return raw_bytes.decode(encoding)
            except Exception:
                continue
        return raw_bytes.decode("utf-8", errors="ignore")

    @classmethod
    def _normalize_rar_dependency_mode(cls, value: Any) -> str:
        mode = cls._normalize_text(value).lower()
        if mode in cls._rar_dependency_modes:
            return mode
        return "none"

    @classmethod
    def _normalize_provider_ids(cls, value: Any, *, fallback: bool = True) -> List[str]:
        allowed = set(cls._default_online_provider_ids)
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = re.split(r"[,，\s]+", value)
        else:
            raw_items = cls._default_online_provider_ids
        providers = []
        for item in raw_items:
            provider_id = cls._normalize_text(item).lower()
            if provider_id in allowed and provider_id not in providers:
                providers.append(provider_id)
        return providers or (list(cls._default_online_provider_ids) if fallback else [])

    @classmethod
    def _normalize_online_site_urls(cls, config: Dict[str, Any]) -> Dict[str, str]:
        raw = config.get("online_site_urls") if isinstance(config.get("online_site_urls"), dict) else {}
        roots = {
            "subhd": raw.get("subhd") or config.get("subhd_url"),
            "zimuku": raw.get("zimuku") or config.get("zimuku_url"),
            "assrt": raw.get("assrt") or config.get("assrt_url"),
            "opensubtitles": raw.get("opensubtitles") or config.get("opensubtitles_url"),
        }
        return normalize_provider_roots(roots)

    def _check_online_rate_limit(self, providers: Iterable[str]) -> None:
        now = time.time()
        provider_ids = sorted({self._normalize_text(provider_id).lower() for provider_id in providers if self._normalize_text(provider_id)})
        blocked = []
        active_records: Dict[str, List[float]] = {}
        for provider_id in provider_ids:
            records = [item for item in self._online_rate_records.get(provider_id, []) if now - item < 60]
            active_records[provider_id] = records
            if len(records) >= self._online_rate_limit_per_minute:
                blocked.append(provider_id)
        if blocked:
            raise HTTPException(
                status_code=429,
                detail=f"在线字幕源请求过于频繁：{','.join(blocked)} 每分钟最多 {self._online_rate_limit_per_minute} 次，请稍后再试",
            )
        for provider_id, records in active_records.items():
            records.append(now)
            self._online_rate_records[provider_id] = records

    @staticmethod
    def _is_executable_file(path: Path) -> bool:
        try:
            return path.is_file() and os.access(path, os.X_OK)
        except Exception:
            return False

    def _set_rar_dependency_status(self, state: str, message: str) -> None:
        self._rar_dependency_status = {
            "mode": self._rar_dependency_mode,
            "state": state,
            "message": message,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "tool_path": self._rar_tool_path,
        }

    def _prepare_rar_dependency(self) -> None:
        if self._rar_dependency_mode == "none":
            self._set_rar_dependency_status("skipped", "未启用 RAR 解压器自动处理")
            return

        if self._rar_tool():
            self._set_rar_dependency_status("ready", "已检测到可用 RAR 解压器")
            return

        if self._rar_dependency_mode == "mapped_binary":
            self._set_rar_dependency_status(
                "missing",
                f"未检测到映射文件，请把宿主机 7zz 映射到容器 {self._rar_tool_path}",
            )
            logger.info(
                "[SubtitleManualUpload] RAR 映射模式未检测到工具 path=%s",
                self._rar_tool_path,
            )
            return

        if self._rar_dependency_mode == "container_install":
            self._install_container_rar_tool()
            return

        self._set_rar_dependency_status("skipped", "未知 RAR 依赖处理方式")

    def _install_container_rar_tool(self) -> None:
        logger.info("[SubtitleManualUpload] 开始尝试在容器内安装 RAR 解压器")
        install_script = r"""
set -eu
if command -v unrar >/dev/null 2>&1 || command -v bsdtar >/dev/null 2>&1 || command -v 7z >/dev/null 2>&1 || command -v 7za >/dev/null 2>&1 || command -v 7zz >/dev/null 2>&1; then
  exit 0
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "当前容器没有 apt-get，无法自动安装，请使用宿主机静态 7zz 映射" >&2
  exit 78
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends p7zip-full unrar-free || apt-get install -y --no-install-recommends 7zip unrar-free libarchive-tools
"""
        try:
            completed = subprocess.run(
                ["sh", "-lc", install_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            self._set_rar_dependency_status("failed", "容器内安装 RAR 解压器超时")
            logger.warning("[SubtitleManualUpload] 容器内安装 RAR 解压器超时")
            return
        except subprocess.CalledProcessError as exc:
            stderr = self._decode_preview_bytes(exc.stderr or b"").strip()
            message = stderr[-500:] if stderr else str(exc)
            self._set_rar_dependency_status("failed", f"容器内安装失败: {message}")
            logger.warning(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器失败 returncode=%s error=%s",
                exc.returncode,
                message,
            )
            return

        stdout = self._decode_preview_bytes(completed.stdout or b"").strip()
        tool_path = self._rar_tool()
        if tool_path:
            self._set_rar_dependency_status("ready", f"容器内安装完成，当前工具: {Path(tool_path).name}")
            logger.info(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器完成 tool=%s output_tail=%s",
                Path(tool_path).name,
                stdout[-300:],
            )
            return

        self._set_rar_dependency_status("failed", "安装命令结束，但仍未检测到 unrar、bsdtar、7z、7za 或 7zz")
        logger.warning("[SubtitleManualUpload] 容器内安装后仍未检测到 RAR 解压器")

    @classmethod
    def _normalize_language_suffix(cls, value: Any) -> str:
        suffix = cls._normalize_text(value).strip().lower()
        if not suffix:
            return "und"
        if any(separator in suffix for separator in ("&", "+", "/", ",")):
            parts = []
            for part in re.split(r"[&+/,]+", suffix):
                normalized = cls._language_suffix_aliases.get(part.strip(), part.strip())
                normalized = {"jpn": "jp", "kor": "kr"}.get(normalized, normalized)
                normalized = re.sub(r"[^a-z0-9-]", "", normalized)
                if normalized and normalized not in parts:
                    parts.append(normalized)
            return "&".join(parts) or "und"
        suffix = cls._language_suffix_aliases.get(suffix, suffix)
        return re.sub(r"[^a-z0-9-]", "", suffix) or "und"

    @classmethod
    def _detect_language_profile(cls, file_name: str, raw_bytes: bytes) -> Dict[str, str]:
        lowered = file_name.lower()
        preview = cls._decode_preview_bytes(raw_bytes[:16000])
        has_cjk = len(re.findall(r"[\u4e00-\u9fff]", preview)) >= 20
        has_kana = len(re.findall(r"[\u3040-\u30ff]", preview)) >= 20
        has_hangul = len(re.findall(r"[\uac00-\ud7af]", preview)) >= 20
        has_ascii = len(re.findall(r"[A-Za-z]{3,}", preview)) >= 20
        has_chinese_name = bool(
            re.search(r"(^|[\s._\-\[\]()])(?:zh|chi|chs|cht|zho|cmn)(?=$|[\s._\-\[\]()])", lowered)
            or any(token in lowered for token in ("中英", "中日", "中韩", "中文", "中字", "双语", "bilingual"))
        )
        has_english_name = bool(
            re.search(r"(^|[\s._\-\[\]()])(?:en|eng)(?=$|[\s._\-\[\]()])", lowered)
            or any(token in lowered for token in ("english", "英文", "英语", "中英"))
        )
        has_japanese_name = bool(
            re.search(r"(^|[\s._\-\[\]()])(?:ja|jp|jpn)(?=$|[\s._\-\[\]()])", lowered)
            or any(token in lowered for token in ("japanese", "日文", "日语", "中日"))
        )
        has_korean_name = bool(
            re.search(r"(^|[\s._\-\[\]()])(?:ko|kr|kor)(?=$|[\s._\-\[\]()])", lowered)
            or any(token in lowered for token in ("korean", "韩文", "韩语", "中韩"))
        )

        suffix = "und"
        label = "未知"

        if (has_chinese_name or has_cjk) and (has_japanese_name or has_kana):
            suffix = "chi&jp"
            label = "中日双语"
        elif (has_chinese_name or has_cjk) and (has_korean_name or has_hangul):
            suffix = "chi&kr"
            label = "中韩双语"
        elif has_chinese_name and (has_english_name or has_ascii):
            suffix = "chi&eng"
            label = "中英双语"
        elif any(token in lowered for token in ("zh-hant", "zh_tw", "zh-tw", "cht", "繁体", "繁中", "big5")) or re.search(
            r"(^|[\s._\-\[\]()])(?:tw|hk)(?=$|[\s._\-\[\]()])",
            lowered,
        ):
            suffix = "cht"
            label = "繁中"
        elif any(token in lowered for token in ("zh-hans", "zh_cn", "zh-cn", "chs", "简体", "简中", "gb")):
            suffix = "chi"
            label = "简中"
        elif any(token in lowered for token in ("zh", "chi", "zho", "cmn", "中文", "中字")) or (has_cjk and not has_kana):
            suffix = "chi"
            label = "中文"
        elif any(token in lowered for token in ("jpn", "japanese", "日文", "日语", ".ja.")) or has_kana:
            suffix = "jpn"
            label = "日文"
        elif any(token in lowered for token in ("kor", "korean", "韩文", "韩语", ".ko.")) or has_hangul:
            suffix = "kor"
            label = "韩文"
        elif any(token in lowered for token in ("eng", "english", "英文", "英语", ".en.")) or has_ascii:
            suffix = "eng"
            label = "英文"
        elif any(token in lowered for token in ("fre", "fra", "french", "français", ".fr.")):
            suffix = "fre"
            label = "法文"
        elif any(token in lowered for token in ("spa", "spanish", "español", ".es.")):
            suffix = "spa"
            label = "西文"
        elif any(token in lowered for token in ("ger", "deu", "german", "deutsch", ".de.")):
            suffix = "ger"
            label = "德文"
        elif any(token in lowered for token in ("por", "portuguese", "português", ".pt.")):
            suffix = "por"
            label = "葡文"
        elif any(token in lowered for token in ("ita", "italian", "italiano", ".it.")):
            suffix = "ita"
            label = "意文"
        elif any(token in lowered for token in ("rus", "russian", ".ru.")):
            suffix = "rus"
            label = "俄文"

        if suffix == "chi" and has_ascii:
            suffix = "chi&eng"
            label = f"{label}/双语"

        return {
            "suffix": cls._normalize_language_suffix(suffix),
            "label": label,
        }

    @classmethod
    def _extract_episode_hint(cls, file_name: str) -> Optional[Dict[str, int]]:
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
            season = cls._safe_int(match.groupdict().get("season"), 0)
            episode = cls._safe_int(match.groupdict().get("episode"), 0)
            if episode:
                return {"season": season, "episode": episode}
        return None

    def _get_session_root(self) -> Path:
        root = self.get_data_path() / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _cleanup_old_sessions(self) -> None:
        root = self._get_session_root()
        expire_before = datetime.now() - timedelta(hours=self._default_session_hours)
        for child in root.iterdir():
            try:
                if not child.is_dir():
                    continue
                if datetime.fromtimestamp(child.stat().st_mtime) < expire_before:
                    shutil.rmtree(child, ignore_errors=True)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 清理旧会话失败 %s: %s", child, exc)

    @classmethod
    def _media_type_text(cls, value: Any) -> str:
        raw = str(getattr(value, "value", value) or "").strip().lower()
        if raw in {"movie", "电影", "mediatype.movie"}:
            return "movie"
        if raw in {"tv", "电视剧", "series", "mediatype.tv"}:
            return "tv"
        return ""

    @classmethod
    def _poster_url(cls, poster_path: Any, prefix: str = "w500") -> str:
        poster = cls._normalize_text(poster_path)
        if not poster:
            return ""
        if poster.startswith(("http://", "https://")):
            return poster
        if not poster.startswith("/"):
            poster = f"/{poster}"
        domain = cls._normalize_text(getattr(settings, "TMDB_IMAGE_DOMAIN", "")) or "image.tmdb.org"
        return f"https://{domain}/t/p/{prefix}{poster}"

    @classmethod
    def _history_type_text(cls, media_type: Any) -> str:
        normalized = cls._media_type_text(media_type)
        if normalized == "movie":
            return "电影"
        if normalized == "tv":
            return "电视剧"
        return cls._normalize_text(media_type)

    @classmethod
    def _number_from_tag(cls, value: Any) -> int:
        match = re.search(r"\d+", cls._normalize_text(value))
        return cls._safe_int(match.group(0), 0) if match else 0

    @classmethod
    def _is_local_video_path(cls, storage: str, path: str) -> bool:
        if cls._normalize_text(storage) != "local" or not path:
            return False
        suffix = Path(path).suffix.lower()
        configured_exts = getattr(settings, "RMT_MEDIAEXT", set()) or set()
        allowed_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in configured_exts
        }
        allowed_exts.update(cls._stream_exts)
        if suffix and allowed_exts and suffix not in allowed_exts:
            return False
        try:
            return Path(path).is_file()
        except Exception:
            return False

    def _build_entry_from_history(self, history: Any) -> Optional[Dict[str, Any]]:
        if not getattr(history, "status", False):
            return None

        raw_fileitem = getattr(history, "dest_fileitem", None)
        fileitem = raw_fileitem if isinstance(raw_fileitem, dict) else {}
        storage = self._normalize_text(fileitem.get("storage") or getattr(history, "dest_storage", "")) or "local"
        path = self._normalize_text(fileitem.get("path") or getattr(history, "dest", ""))
        if not self._is_local_video_path(storage, path):
            return None

        file_path = Path(path)
        filename = self._normalize_text(fileitem.get("name")) or file_path.name
        basename = self._normalize_text(fileitem.get("basename")) or file_path.stem
        media_type = self._media_type_text(getattr(history, "type", ""))
        if not media_type:
            return None

        title = self._normalize_text(getattr(history, "title", ""))
        year = self._normalize_text(getattr(history, "year", ""))
        season = self._number_from_tag(getattr(history, "seasons", ""))
        episode = self._number_from_tag(getattr(history, "episodes", ""))
        if not season or not episode:
            try:
                meta = MetaInfoPath(file_path)
                season = season or self._safe_int(getattr(meta, "begin_season", None) or getattr(meta, "season", None), 0)
                episode = episode or self._safe_int(getattr(meta, "begin_episode", None) or getattr(meta, "episode", None), 0)
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
            "poster_url": self._poster_url(getattr(history, "image", "")),
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

    @classmethod
    def _event_value(cls, obj: Any, *names: str, default: Any = "") -> Any:
        for name in names:
            if isinstance(obj, dict) and name in obj:
                return obj.get(name)
            if hasattr(obj, name):
                return getattr(obj, name)
        return default

    def _transfer_event_paths(self, transferinfo: Any) -> List[str]:
        raw_paths = self._event_value(transferinfo, "file_list_new", default=[]) or []
        if isinstance(raw_paths, (str, Path)):
            raw_paths = [raw_paths]
        paths = [self._normalize_text(item) for item in raw_paths if self._normalize_text(item)]
        if not paths:
            target_path = self._normalize_text(self._event_value(transferinfo, "target_path", default=""))
            if target_path:
                paths = [target_path]
        result = []
        for path in paths:
            if self._is_local_video_path("local", path):
                result.append(path)
        return result

    def _entries_from_transfer_event(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        meta = event_data.get("meta") if isinstance(event_data, dict) else None
        mediainfo = event_data.get("mediainfo") if isinstance(event_data, dict) else None
        transferinfo = event_data.get("transferinfo") if isinstance(event_data, dict) else None
        paths = self._transfer_event_paths(transferinfo)
        if not paths:
            return []

        media_type = self._media_type_text(self._event_value(mediainfo, "type", default=""))
        title = self._normalize_text(
            self._event_value(mediainfo, "title", "name", default="")
            or self._event_value(meta, "name", "title", default="")
        )
        year = self._normalize_text(self._event_value(mediainfo, "year", "release_year", default=""))
        tmdb_id = self._safe_int(self._event_value(mediainfo, "tmdb_id", "tmdbid", default=0), 0)
        douban_id = self._normalize_text(self._event_value(mediainfo, "douban_id", "doubanid", default=""))
        season = self._safe_int(
            self._event_value(meta, "begin_season", "season", default=0)
            or self._event_value(mediainfo, "season", default=0),
            0,
        )
        episode = self._safe_int(
            self._event_value(meta, "begin_episode", "episode", default=0)
            or self._event_value(mediainfo, "episode", default=0),
            0,
        )
        episode_list = self._event_value(meta, "episode_list", default=[]) or []
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
                    "poster_url": self._poster_url(self._event_value(mediainfo, "poster_path", "image", default="")),
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

    def _merge_local_entries_cache(self, entries: List[Dict[str, Any]]) -> None:
        if not entries:
            return
        cache = self._local_entries_cache or {}
        existing = [item for item in cache.get("entries") or [] if isinstance(item, dict)]
        by_path = {entry.get("path"): entry for entry in entries if entry.get("path")}
        merged = list(entries)
        for entry in existing:
            if entry.get("path") not in by_path:
                merged.append(entry)
            if len(merged) >= self._cache_max_entries:
                break
        media_count = len({entry.get("media_key") for entry in merged if entry.get("media_key")})
        self._local_entries_cache = {
            "loaded_at": datetime.now(),
            "entries": merged[: self._cache_max_entries],
            "media_count": media_count,
            "persisted": False,
        }
        self._remember_targets(entries)
        self._persist_local_cache()

    def _local_cache_file(self) -> Path:
        return self.get_data_path() / "local_entries_cache.json"

    @classmethod
    def _cache_loaded_at(cls, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        text = cls._normalize_text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _persist_local_cache(self) -> None:
        cache = self._local_entries_cache or {}
        loaded_at = self._cache_loaded_at(cache.get("loaded_at"))
        payload = {
            "loaded_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entries": cache.get("entries") or [],
            "media_count": int(cache.get("media_count") or 0),
        }
        try:
            cache_file = self._local_cache_file()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 写入本地资源持久化缓存失败: %s", exc)

    def _restore_persisted_local_cache(self) -> bool:
        try:
            cache_file = self._local_cache_file()
            if not cache_file.exists():
                return False
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 读取本地资源持久化缓存失败: %s", exc)
            return False
        entries = payload.get("entries") if isinstance(payload, dict) else []
        loaded_at = self._cache_loaded_at(payload.get("loaded_at")) if isinstance(payload, dict) else None
        if not loaded_at or not isinstance(entries, list):
            return False
        media_count = int(payload.get("media_count") or len({entry.get("media_key") for entry in entries if isinstance(entry, dict) and entry.get("media_key")}))
        self._local_entries_cache = {
            "loaded_at": loaded_at,
            "entries": [entry for entry in entries if isinstance(entry, dict)],
            "media_count": media_count,
            "persisted": True,
        }
        self._remember_targets(self._local_entries_cache["entries"])
        logger.info(
            "[SubtitleManualUpload] 已恢复本地资源持久化缓存 entries=%s medias=%s",
            len(self._local_entries_cache["entries"]),
            media_count,
        )
        return True

    def _start_background_cache_refresh(self) -> None:
        if self._cache_refreshing:
            return
        self._cache_refreshing = True

        def worker():
            try:
                self._load_local_entries(force=True)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 后台刷新本地资源缓存失败: %s", exc)
            finally:
                self._cache_refreshing = False

        threading.Thread(
            target=worker,
            name="SubtitleManualUploadCacheRefresh",
            daemon=True,
        ).start()

    def _load_local_entries(self, *, force: bool = False, allow_stale: bool = False) -> List[Dict[str, Any]]:
        cache = self._local_entries_cache or {}
        loaded_at = self._cache_loaded_at(cache.get("loaded_at"))
        now = datetime.now()
        if not force and loaded_at and (now - loaded_at).total_seconds() < self._cache_ttl_seconds:
            return list(cache.get("entries") or [])
        if not force and not loaded_at and self._restore_persisted_local_cache():
            cache = self._local_entries_cache or {}
            loaded_at = self._cache_loaded_at(cache.get("loaded_at"))
            if loaded_at and (now - loaded_at).total_seconds() < self._cache_ttl_seconds:
                return list(cache.get("entries") or [])
        if not force and allow_stale and cache.get("entries"):
            self._start_background_cache_refresh()
            return list(cache.get("entries") or [])

        try:
            histories = TransferHistory.list_by_page(
                db=None,
                page=1,
                count=self._cache_max_entries,
                status=True,
            ) or []
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取 MoviePilot 本地整理记录失败: {exc}") from exc

        entries: List[Dict[str, Any]] = []
        seen_paths = set()
        for history in histories:
            entry = self._build_entry_from_history(history)
            if not entry:
                continue
            path = entry.get("path")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            entries.append(entry)
            if len(entries) >= self._cache_max_entries:
                break

        media_count = len({entry.get("media_key") for entry in entries if entry.get("media_key")})
        self._local_entries_cache = {
            "loaded_at": now,
            "entries": entries,
            "media_count": media_count,
            "persisted": False,
        }
        self._remember_targets(entries)
        self._persist_local_cache()
        logger.info(
            "[SubtitleManualUpload] 本地资源缓存已刷新 entries=%s medias=%s",
            len(entries),
            media_count,
        )
        return list(entries)

    def _refresh_local_cache(self) -> List[Dict[str, Any]]:
        self._entry_map = OrderedDict()
        self._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
        return self._load_local_entries(force=True)

    def _cache_status(self) -> Dict[str, Any]:
        cache = self._local_entries_cache or {}
        loaded_at = self._cache_loaded_at(cache.get("loaded_at"))
        expires_in = 0
        stale = False
        if loaded_at:
            age = (datetime.now() - loaded_at).total_seconds()
            expires_in = max(0, int(self._cache_ttl_seconds - age))
            stale = age >= self._cache_ttl_seconds
        return {
            "ready": bool(loaded_at),
            "persisted": bool(cache.get("persisted")),
            "stale": stale,
            "refreshing": bool(self._cache_refreshing),
            "ttl_seconds": self._cache_ttl_seconds,
            "expires_in": expires_in,
            "updated_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entry_count": len(cache.get("entries") or []),
            "media_count": int(cache.get("media_count") or 0),
            "target_cache_count": len(self._entry_map or {}),
            "max_entries": self._cache_max_entries,
        }

    def _autosub_plugin(self) -> Tuple[Any, str]:
        if not self._ai_link_enabled:
            return None, "字幕匹配未启用 AI 字幕联动"
        if PluginManager is None:
            return None, "MoviePilot 插件管理器不可用"
        try:
            running_plugins = PluginManager().running_plugins or {}
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 读取运行中插件失败: %s", exc)
            return None, "读取运行中插件失败"
        plugin = running_plugins.get("AutoSubv3") or running_plugins.get("autosubv3")
        if not plugin:
            for candidate in running_plugins.values():
                if candidate.__class__.__name__ == "AutoSubv3":
                    plugin = candidate
                    break
        if not plugin:
            return None, "请先安装并启用 AI字幕生成(联动版)"
        return plugin, ""

    def _autosub_status(self) -> Dict[str, Any]:
        status = {
            "enabled": bool(self._ai_link_enabled),
            "installed": False,
            "available": False,
            "running": False,
            "queue_ready": False,
            "plugin_name": "AI字幕生成(联动版)",
            "plugin_version": "",
            "message": "请先安装并启用 AI字幕生成(联动版)",
            "counts": {},
            "updated_at": "",
        }
        if not self._ai_link_enabled:
            status["message"] = "AI 字幕联动已关闭"
            return status
        plugin, reason = self._autosub_plugin()
        if not plugin:
            status["message"] = reason
            return status
        try:
            if hasattr(plugin, "_status_payload"):
                plugin_status = plugin._status_payload()
            else:
                running = bool(plugin.get_state()) if hasattr(plugin, "get_state") else False
                plugin_status = {
                    "available": running,
                    "running": running,
                    "queue_ready": running,
                    "plugin_name": getattr(plugin, "plugin_name", "AI字幕生成(联动版)"),
                    "plugin_version": getattr(plugin, "plugin_version", ""),
                    "message": "可提交 AI 字幕生成任务" if running else "AI 字幕插件未运行",
                    "counts": {},
                    "updated_at": "",
                }
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 读取 AI 字幕插件状态失败: %s", exc)
            status["installed"] = True
            status["message"] = "读取 AI 字幕插件状态失败"
            return status
        status.update(plugin_status)
        status["enabled"] = bool(self._ai_link_enabled)
        status["installed"] = True
        status["available"] = bool(plugin_status.get("available")) and bool(self._ai_link_enabled)
        return status

    @staticmethod
    def _autosub_task_summary(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        counts = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "ignored": 0,
            "no_audio": 0,
            "failed": 0,
            "cancelled": 0,
            "active": 0,
            "total": len(tasks),
        }
        for task in tasks:
            status = task.get("status")
            if status in counts:
                counts[status] += 1
            if task.get("active") or status in {"pending", "in_progress"}:
                counts["active"] += 1
        return counts

    def _autosub_tasks_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        status = self._autosub_status()
        paths = [self._normalize_text(entry.get("path")) for entry in target_entries if self._normalize_text(entry.get("path"))]
        task_by_target: Dict[str, Any] = {}
        if not status.get("available"):
            return {
                "status": status,
                "summary": self._autosub_task_summary([]),
                "tasks": [],
                "task_by_target": task_by_target,
            }
        plugin, reason = self._autosub_plugin()
        if not plugin or not hasattr(plugin, "tasks_payload"):
            status["available"] = False
            status["message"] = reason or "AI 字幕插件版本过旧，请更新到联动版"
            return {
                "status": status,
                "summary": self._autosub_task_summary([]),
                "tasks": [],
                "task_by_target": task_by_target,
            }
        try:
            payload = plugin.tasks_payload(paths=paths, limit=max(300, len(paths) * 20))
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 读取 AI 字幕任务失败: %s", exc)
            status["available"] = False
            status["message"] = "读取 AI 字幕任务失败"
            return {
                "status": status,
                "summary": self._autosub_task_summary([]),
                "tasks": [],
                "task_by_target": task_by_target,
            }
        status = {**status, **(payload.get("status") or {})}
        latest_by_path: Dict[str, Dict[str, Any]] = {}
        for task in payload.get("tasks") or []:
            path = self._normalize_text(task.get("video_file"))
            if path and path not in latest_by_path:
                latest_by_path[path] = task

        tasks: List[Dict[str, Any]] = []
        for entry in target_entries:
            target_id = self._normalize_text(entry.get("id"))
            path = self._normalize_text(entry.get("path"))
            task = dict(latest_by_path.get(path) or {})
            if task:
                task["target_id"] = target_id
                task["target_label"] = entry.get("target_label") or entry.get("filename") or Path(path).name
                task_by_target[target_id] = task
                tasks.append(task)
            else:
                task_by_target[target_id] = None
        return {
            "status": status,
            "summary": self._autosub_task_summary(tasks),
            "tasks": tasks,
            "task_by_target": task_by_target,
        }

    @classmethod
    def _entry_matches_keyword(cls, entry: Dict[str, Any], keyword: str) -> bool:
        clean_keyword = cls._normalize_text(keyword).lower()
        if not clean_keyword:
            return True
        haystack = " ".join(
            cls._normalize_text(entry.get(key)).lower()
            for key in ("title", "filename", "basename", "relative_path")
        )
        return all(part in haystack for part in re.split(r"\s+", clean_keyword) if part)

    async def _search_media_candidates(self, keyword: str, media_type: str, limit: int) -> List[Dict[str, Any]]:
        clean_keyword = self._normalize_text(keyword)
        expected_type = self._media_type_text(media_type)
        entries: List[Dict[str, Any]] = []
        for entry in self._load_local_entries(allow_stale=True):
            if expected_type and entry.get("media_type") != expected_type:
                continue
            if not self._entry_matches_keyword(entry, clean_keyword):
                continue
            entries.append(entry)
        candidates = self._group_entries_as_media(entries, limit)
        for media in candidates:
            detail = self._targets_for_media(
                media_type=media.get("media_type"),
                tmdb_id=media.get("tmdb_id"),
                douban_id=media.get("douban_id"),
                title=media.get("title"),
                year=media.get("year"),
                season="all",
            )
            detail_media = detail.get("media") or {}
            media["local_count"] = detail.get("all_target_count", media.get("local_count", 0))
            media["seasons"] = detail.get("seasons", media.get("seasons", []))
            media["season_count"] = len(media["seasons"])
            media["poster_url"] = detail_media.get("poster_url") or media.get("poster_url", "")
        return candidates

    def _group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            key = entry["media_key"]
            group = groups.setdefault(
                key,
                {
                    "id": key,
                    "media_id": key,
                    "media_type": entry.get("media_type"),
                    "title": entry.get("title"),
                    "en_title": "",
                    "year": entry.get("year"),
                    "tmdb_id": entry.get("tmdb_id"),
                    "douban_id": entry.get("douban_id"),
                    "poster_url": entry.get("poster_url"),
                    "backdrop_url": "",
                    "overview": "",
                    "vote_average": 0,
                    "local_count": 0,
                    "season_count": 0,
                    "latest_at": entry.get("date", ""),
                    "_entries": [],
                },
            )
            group["_entries"].append(entry)
            group["local_count"] += 1
            if entry.get("poster_url") and not group.get("poster_url"):
                group["poster_url"] = entry["poster_url"]
            if entry.get("date") and entry["date"] > group.get("latest_at", ""):
                group["latest_at"] = entry["date"]

        result = []
        for group in groups.values():
            seasons = self._merge_seasons(group.pop("_entries"))
            group["seasons"] = seasons
            group["season_count"] = len(seasons)
            result.append(group)
        result.sort(key=lambda item: (item.get("latest_at", ""), item.get("title", "")), reverse=True)
        return result[:limit]

    def _merge_seasons(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    def _targets_for_media(
        self,
        media_type: str,
        tmdb_id: Any = None,
        douban_id: Any = None,
        title: str = "",
        year: str = "",
        season: Any = None,
    ) -> Dict[str, Any]:
        clean_type = self._media_type_text(media_type)
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
            "local_count": 0,
            "season_count": 0,
        }
        seasons = self._merge_seasons(entries) if media.get("media_type") == "tv" else []

        season_value = self._normalize_text(season)
        selected_season: Any = "all"
        if media.get("media_type") == "tv" and season_value not in {"", "all", "0"}:
            selected_season = self._safe_int(season_value, 0) or "all"

        visible_entries = entries
        if media.get("media_type") == "tv" and selected_season != "all":
            visible_entries = [entry for entry in entries if self._safe_int(entry.get("season"), 0) == selected_season]

        self._remember_targets(visible_entries)
        return {
            "media": media,
            "seasons": seasons,
            "selected_season": selected_season,
            "targets": [self._target_from_entry(entry) for entry in visible_entries],
            "target_count": len(visible_entries),
            "all_target_count": len(entries),
        }

    def _target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        subtitles = self._subtitle_files_for_target(entry)
        return {
            "id": entry.get("id"),
            "label": entry.get("target_label"),
            "basename": entry.get("basename"),
            "media_type": entry.get("media_type"),
            "title": entry.get("title"),
            "season": entry.get("season", 0),
            "episode": entry.get("episode", 0),
            "year": entry.get("year", ""),
            "library_name": entry.get("library_name"),
            "relative_path": entry.get("relative_path"),
            "storage": entry.get("storage", "local"),
            "writable": entry.get("writable", True),
            "has_subtitle": bool(subtitles),
            "subtitle_count": len(subtitles),
            "subtitles": subtitles,
        }

    def _remember_targets(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if target_id:
                if target_id in self._entry_map:
                    self._entry_map.move_to_end(target_id)
                self._entry_map[target_id] = entry
        while len(self._entry_map) > self._entry_map_max_size:
            self._entry_map.popitem(last=False)

    def _resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        target_id_list = [self._normalize_text(item) for item in target_ids if self._normalize_text(item)]
        target_id_set = set(target_id_list)
        result: Dict[str, Dict[str, Any]] = {}
        for target_id in target_id_list:
            entry = self._entry_map.get(target_id)
            if entry:
                result[target_id] = entry
        missing_ids = target_id_set - set(result.keys())
        if not missing_ids:
            return result

        logger.info(
            "[SubtitleManualUpload] 目标缓存未命中，回查本地整理记录 target_ids=%s missing=%s",
            self._brief_ids(target_id_list),
            len(missing_ids),
        )

        def take_matches(source_entries: List[Dict[str, Any]]) -> None:
            for entry in source_entries:
                target_id = self._normalize_text(entry.get("id"))
                if target_id not in missing_ids:
                    continue
                self._remember_targets([entry])
                result[target_id] = entry
                missing_ids.remove(target_id)
                if not missing_ids:
                    break

        try:
            take_matches(self._load_local_entries(allow_stale=True))
            if missing_ids:
                take_matches(self._load_local_entries(force=True))
        except Exception as exc:
            logger.error("[SubtitleManualUpload] 回查本地整理记录失败: %s", exc)
            return result

        if missing_ids:
            logger.warning(
                "[SubtitleManualUpload] 仍有目标无法解析 target_ids=%s missing=%s",
                self._brief_ids(target_id_list),
                len(missing_ids),
            )
        return result

    @classmethod
    def _build_destination_name(
        cls,
        target_entry: Dict[str, Any],
        subtitle_info: Dict[str, Any],
    ) -> str:
        basename = cls._normalize_text(target_entry.get("basename")) or "subtitle"
        language_suffix = cls._normalize_language_suffix(subtitle_info.get("language_suffix"))
        ext = cls._normalize_text(subtitle_info.get("ext")) or ".srt"
        if not ext.startswith("."):
            ext = f".{ext}"
        return f"{basename}.{language_suffix}{ext.lower()}"

    @classmethod
    def _subtitle_files_for_target(cls, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        storage = cls._normalize_text(target_entry.get("storage")) or "local"
        if storage != "local":
            return []

        video_path_raw = cls._normalize_text(target_entry.get("path"))
        if not video_path_raw:
            return []

        video_path = Path(video_path_raw)
        media_dir = video_path.parent
        if not media_dir.exists() or not media_dir.is_dir():
            return []

        stem = video_path.stem
        subtitles: List[Dict[str, Any]] = []
        try:
            for sub_file in media_dir.iterdir():
                if not sub_file.is_file():
                    continue
                if sub_file.suffix.lower() not in cls._subtitle_exts:
                    continue
                if sub_file.stem != stem and not sub_file.name.startswith(f"{stem}."):
                    continue
                subtitles.append(
                    {
                        "name": sub_file.name,
                        "path": str(sub_file),
                        "relative_path": str(sub_file).replace("\\", "/"),
                        "ext": sub_file.suffix.lower(),
                        "size": sub_file.stat().st_size,
                        "modified_at": datetime.fromtimestamp(sub_file.stat().st_mtime).isoformat(timespec="seconds"),
                    }
                )
        except Exception as exc:
            logger.warning(
                "[SubtitleManualUpload] 读取外挂字幕失败 video=%s error=%s",
                video_path.name,
                exc,
            )
        subtitles.sort(key=lambda item: item.get("name", ""))
        return subtitles

    def _remove_ext_marks(self, video_path: Path) -> None:
        for sub_file in video_path.parent.iterdir():
            if not sub_file.is_file():
                continue
            if sub_file.suffix.lower() not in self._subtitle_exts:
                continue
            if not sub_file.name.startswith(f"{video_path.stem}."):
                continue
            new_name = sub_file.name.replace(".default.", ".").replace(".forced.", ".")
            if new_name == sub_file.name:
                continue
            target = sub_file.with_name(new_name)
            if target.exists():
                target.unlink()
            sub_file.rename(target)

    @staticmethod
    def _is_upload_file(value: Any) -> bool:
        return isinstance(value, UploadFile)

    @classmethod
    def _rar_tool(cls) -> str:
        configured = cls._normalize_text(getattr(cls, "_rar_tool_path", ""))
        if configured:
            configured_path = Path(configured)
            if cls._is_executable_file(configured_path):
                return str(configured_path)
        for tool in cls._rar_tools:
            found = shutil.which(tool)
            if found:
                return found
        return ""

    @classmethod
    def _rar_python_available(cls) -> bool:
        return importlib.util.find_spec(cls._rar_python_package) is not None

    @classmethod
    def _rarfile_module(cls) -> Any:
        try:
            return __import__(cls._rar_python_package)
        except Exception:
            return None

    @classmethod
    def _run_archive_command(cls, args: List[str], timeout: int = 120) -> bytes:
        try:
            completed = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=timeout,
            )
            return completed.stdout
        except subprocess.CalledProcessError as exc:
            stderr = cls._decode_preview_bytes(exc.stderr or b"").strip()
            raise ValueError(f"压缩包解压失败: {stderr or exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("压缩包解压超时") from exc

    @classmethod
    def _list_rar_members(cls, archive_path: Path, tool_path: str) -> List[str]:
        tool_name = Path(tool_path).name.lower()
        if tool_name == "unrar":
            output = cls._run_archive_command([tool_path, "lb", str(archive_path)])
            return [line.strip() for line in cls._decode_preview_bytes(output).splitlines() if line.strip()]
        if tool_name == "bsdtar":
            output = cls._run_archive_command([tool_path, "-tf", str(archive_path)])
            return [line.strip() for line in cls._decode_preview_bytes(output).splitlines() if line.strip()]
        if tool_name in {"7z", "7za", "7zz"}:
            output = cls._run_archive_command([tool_path, "l", "-slt", str(archive_path)])
            members = []
            for line in cls._decode_preview_bytes(output).splitlines():
                if not line.startswith("Path = "):
                    continue
                member = line.removeprefix("Path = ").strip()
                if member and member != str(archive_path):
                    members.append(member)
            return members
        return []

    @classmethod
    def _read_rar_member(cls, archive_path: Path, member: str, tool_path: str) -> bytes:
        tool_name = Path(tool_path).name.lower()
        if tool_name == "unrar":
            return cls._run_archive_command([tool_path, "p", "-inul", str(archive_path), member])
        if tool_name == "bsdtar":
            return cls._run_archive_command([tool_path, "-xOf", str(archive_path), member])
        if tool_name in {"7z", "7za", "7zz"}:
            return cls._run_archive_command([tool_path, "x", "-so", str(archive_path), member])
        raise ValueError("当前容器缺少可用的 RAR 解压工具")

    @classmethod
    def _extract_rar_subtitle_files_with_rarfile(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        rarfile_module = cls._rarfile_module()
        if not rarfile_module:
            raise ValueError(f"未安装 Python 依赖 {cls._rar_python_package}")

        prepared: List[Dict[str, Any]] = []
        try:
            with rarfile_module.RarFile(str(archive_path)) as archive:
                for member in archive.infolist():
                    if member.isdir():
                        continue
                    member_name = re.split(r"[\\/]", member.filename)[-1]
                    if not member_name or member_name.startswith("."):
                        continue
                    member_ext = Path(member_name).suffix.lower()
                    if member_ext not in cls._subtitle_exts:
                        continue
                    member_bytes = archive.read(member)
                    upload_id = cls._hash_text(
                        f"{source_name}|{member.filename}|{len(member_bytes)}|{datetime.now().timestamp()}"
                    )
                    stored_path = session_dir / f"{upload_id}{member_ext}"
                    stored_path.write_bytes(member_bytes)
                    prepared.append(
                        {
                            "upload_id": upload_id,
                            "source_name": member_name,
                            "archive_name": source_name,
                            "stored_path": str(stored_path),
                            "ext": member_ext,
                        }
                    )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return prepared

    @classmethod
    def _extract_rar_subtitle_files(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        if cls._rar_python_available():
            try:
                return cls._extract_rar_subtitle_files_with_rarfile(source_name, archive_path, session_dir)
            except ValueError as exc:
                logger.warning(
                    "[SubtitleManualUpload] rarfile 解析 RAR 失败，将尝试外部命令回退 archive=%s error=%s",
                    source_name,
                    exc,
                )

        tool_path = cls._rar_tool()
        if not tool_path:
            package_note = f"已声明 Python 依赖 {cls._rar_python_package}，但 RAR 内容解压仍需要外部解压程序"
            raise ValueError(f"{package_note}；请在容器安装 unrar、bsdtar、7z、7za 或映射静态 7zz")

        prepared: List[Dict[str, Any]] = []
        members = cls._list_rar_members(archive_path, tool_path)
        for member in members:
            member_name = re.split(r"[\\/]", member)[-1]
            if not member_name or member_name.startswith("."):
                continue
            member_ext = Path(member_name).suffix.lower()
            if member_ext not in cls._subtitle_exts:
                continue
            member_bytes = cls._read_rar_member(archive_path, member, tool_path)
            upload_id = cls._hash_text(
                f"{source_name}|{member}|{len(member_bytes)}|{datetime.now().timestamp()}"
            )
            stored_path = session_dir / f"{upload_id}{member_ext}"
            stored_path.write_bytes(member_bytes)
            prepared.append(
                {
                    "upload_id": upload_id,
                    "source_name": member_name,
                    "archive_name": source_name,
                    "stored_path": str(stored_path),
                    "ext": member_ext,
                }
            )
        return prepared

    @classmethod
    def _extract_subtitle_files(
        cls,
        upload_name: str,
        raw_bytes: bytes,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        source_name = Path(upload_name or "").name
        ext = Path(source_name).suffix.lower()
        prepared: List[Dict[str, Any]] = []

        if ext in cls._subtitle_exts:
            upload_id = cls._hash_text(f"{source_name}|{len(raw_bytes)}|{datetime.now().timestamp()}")
            stored_path = session_dir / f"{upload_id}{ext}"
            stored_path.write_bytes(raw_bytes)
            prepared.append(
                {
                    "upload_id": upload_id,
                    "source_name": source_name,
                    "archive_name": "",
                    "stored_path": str(stored_path),
                    "ext": ext,
                }
            )
            return prepared

        if ext not in cls._archive_exts:
            return prepared

        archive_path = session_dir / source_name
        archive_path.write_bytes(raw_bytes)
        if ext in cls._rar_exts:
            return cls._extract_rar_subtitle_files(source_name, archive_path, session_dir)

        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    member_name = Path(member.filename).name
                    if not member_name or member_name.startswith("."):
                        continue
                    member_ext = Path(member_name).suffix.lower()
                    if member_ext not in cls._subtitle_exts:
                        continue
                    member_bytes = archive.read(member)
                    upload_id = cls._hash_text(
                        f"{source_name}|{member.filename}|{len(member_bytes)}|{datetime.now().timestamp()}"
                    )
                    stored_path = session_dir / f"{upload_id}{member_ext}"
                    stored_path.write_bytes(member_bytes)
                    prepared.append(
                        {
                            "upload_id": upload_id,
                            "source_name": member_name,
                            "archive_name": source_name,
                            "stored_path": str(stored_path),
                            "ext": member_ext,
                        }
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError(f"压缩包损坏或格式不正确: {source_name}") from exc
        return prepared

    @classmethod
    def _suggest_target(
        cls,
        subtitle_info: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not targets:
            return None
        if len(targets) == 1:
            return targets[0]["id"]

        hint = cls._extract_episode_hint(subtitle_info.get("source_name"))
        if not hint:
            return None

        season = hint.get("season", 0)
        episode = hint.get("episode", 0)

        for target in targets:
            if target.get("season", 0) == season and target.get("episode", 0) == episode:
                return target["id"]

        if season == 0:
            candidate_seasons = {target.get("season", 0) for target in targets if target.get("season", 0)}
            if len(candidate_seasons) == 1:
                only_season = next(iter(candidate_seasons))
                for target in targets:
                    if target.get("season", 0) == only_season and target.get("episode", 0) == episode:
                        return target["id"]
        return None

    @classmethod
    def _auto_fill_missing_targets(
        cls,
        preview_items: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> None:
        unresolved = [item for item in preview_items if not item.get("target_id")]
        if not unresolved:
            return
        used_target_ids = {
            item.get("target_id")
            for item in preview_items
            if item.get("target_id")
        }
        remaining_targets = [
            target for target in targets if target.get("id") not in used_target_ids
        ]
        if len(unresolved) != len(remaining_targets):
            return
        sorted_targets = sorted(
            remaining_targets,
            key=lambda item: (
                item.get("season", 0),
                item.get("episode", 0),
                item.get("label", ""),
            ),
        )
        sorted_items = sorted(
            unresolved,
            key=lambda item: (
                cls._extract_episode_hint(item.get("source_name") or "") or {}
            ).get("episode", 0),
        )
        for item, target in zip(sorted_items, sorted_targets):
            item["target_id"] = target["id"]

    @classmethod
    def _build_write_operations(
        cls,
        items: List[Dict[str, Any]],
        upload_map: Dict[str, Dict[str, Any]],
        target_entries: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        destination_keys = set()
        operations: List[Dict[str, Any]] = []

        for item in items:
            upload_id = cls._normalize_text(item.get("upload_id"))
            target_id = cls._normalize_text(item.get("target_id"))
            if not upload_id or not target_id:
                raise HTTPException(status_code=400, detail="存在未完成目标选择的字幕项")

            upload_info = upload_map.get(upload_id)
            target_entry = target_entries.get(target_id)
            if not upload_info or not target_entry:
                raise HTTPException(status_code=400, detail="上传项或目标视频不存在，请重新上传")

            storage = cls._normalize_text(target_entry.get("storage")) or "local"
            if storage != "local":
                raise HTTPException(status_code=400, detail=f"当前仅支持写入本地媒体文件，目标存储为: {storage}")

            video_path = Path(target_entry["path"])
            if not video_path.exists():
                raise HTTPException(status_code=400, detail=f"目标视频不存在: {video_path}")

            source_path = Path(upload_info["stored_path"])
            if not source_path.exists():
                raise HTTPException(status_code=400, detail=f"上传缓存文件不存在: {upload_info.get('source_name')}")

            item_ext = cls._normalize_text(item.get("ext")) or upload_info.get("ext") or ".srt"
            item_suffix = cls._normalize_language_suffix(item.get("language_suffix"))
            destination_name = cls._build_destination_name(
                target_entry,
                {
                    "ext": item_ext,
                    "language_suffix": item_suffix,
                },
            )
            unique_key = f"{target_id}|{destination_name}"
            if unique_key in destination_keys:
                raise HTTPException(status_code=400, detail=f"重复映射到同一个目标字幕名: {destination_name}")
            destination_keys.add(unique_key)

            operations.append(
                {
                    "upload_info": upload_info,
                    "target_entry": target_entry,
                    "video_path": video_path,
                    "source_path": source_path,
                    "language_suffix": item_suffix,
                    "destination_name": destination_name,
                    "destination_path": video_path.parent / destination_name,
                }
            )
        return operations

    @classmethod
    def _is_chinese_language_suffix(cls, suffix: Any) -> bool:
        return any(part in {"chi", "cht"} for part in cls._normalize_language_suffix(suffix).split("&"))

    def _maybe_convert_operation_to_simplified(self, operation: Dict[str, Any], output_dir: Path) -> None:
        operation["simplified_result"] = {"enabled": False, "converted": False}
        if not self._traditional_to_simplified:
            return
        if not self._is_chinese_language_suffix(operation.get("language_suffix")):
            return
        source_path = Path(operation["write_source_path"])
        if source_path.suffix.lower() not in self._subtitle_exts:
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{operation['upload_info'].get('upload_id')}{source_path.suffix.lower()}"
        try:
            converted = convert_subtitle_file_to_simplified(source_path, output_path)
        except Exception as exc:
            logger.error(
                "[SubtitleManualUpload] 繁转简失败 %s -> %s: %s",
                operation["upload_info"].get("source_name"),
                operation["destination_name"],
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"繁转简失败: {operation['upload_info'].get('source_name')} - {exc}",
            ) from exc
        operation["write_source_path"] = output_path
        operation["simplified_result"] = {"enabled": True, "converted": converted}

    def _write_operations_to_disk(
        self,
        *,
        session_dir: Path,
        operations: List[Dict[str, Any]],
        fix_timeline: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        fixed_dir = session_dir / "timeline_fixed"
        simplified_dir = session_dir / "simplified"
        for operation in operations:
            operation["write_source_path"] = operation["source_path"]
            operation["timeline_result"] = None
            operation["simplified_result"] = {"enabled": False, "converted": False}
            if fix_timeline:
                fixed_dir.mkdir(parents=True, exist_ok=True)
                fixed_source_path = fixed_dir / f"{operation['upload_info'].get('upload_id')}{operation['source_path'].suffix}"
                if operation["video_path"].suffix.lower() in self._stream_exts:
                    shutil.copyfile(operation["source_path"], fixed_source_path)
                    operation["write_source_path"] = fixed_source_path
                    operation["timeline_result"] = TimelineFixResult(
                        enabled=True,
                        applied=False,
                        reason="stream target skipped",
                        base="strm",
                        offset_seconds=0.0,
                        scale_factor=1.0,
                        score=0.0,
                    )
                    logger.info(
                        "[SubtitleManualUpload] STRM 目标跳过智能调轴 %s -> %s",
                        operation["upload_info"].get("source_name"),
                        operation["destination_name"],
                    )
                    self._maybe_convert_operation_to_simplified(operation, simplified_dir)
                    continue
                try:
                    timeline_result = fix_subtitle_timeline(
                        video_path=operation["video_path"],
                        subtitle_path=operation["source_path"],
                        output_path=fixed_source_path,
                    )
                except Exception as exc:
                    logger.error(
                        "[SubtitleManualUpload] 智能调轴失败 %s -> %s: %s",
                        operation["upload_info"].get("source_name"),
                        operation["destination_name"],
                        exc,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"智能调轴失败: {operation['upload_info'].get('source_name')} - {exc}",
                    ) from exc
                operation["write_source_path"] = fixed_source_path
                operation["timeline_result"] = timeline_result
            self._maybe_convert_operation_to_simplified(operation, simplified_dir)

        written_results = []
        for operation in operations:
            destination_path = operation["destination_path"]
            temp_path = destination_path.with_name(f"{destination_path.name}.mp-uploading")
            if temp_path.exists():
                temp_path.unlink()

            shutil.copyfile(operation["write_source_path"], temp_path)
            temp_path.replace(destination_path)
            timeline_result = operation.get("timeline_result")
            written_results.append(
                {
                    "source_name": operation["upload_info"].get("source_name"),
                    "archive_name": operation["upload_info"].get("archive_name"),
                    "target_label": self._target_from_entry(operation["target_entry"]).get("label"),
                    "output_name": operation["destination_name"],
                    "output_path": str(destination_path),
                    "timeline": timeline_result.to_dict() if timeline_result else {"enabled": False},
                    "simplified": operation.get("simplified_result") or {"enabled": False, "converted": False},
                }
            )

        touched_videos: Dict[str, Path] = {
            str(operation["video_path"]): operation["video_path"]
            for operation in operations
        }
        for video_path in touched_videos.values():
            self._remove_ext_marks(video_path)

        fixed_count = len(
            [
                item
                for item in written_results
                if item.get("timeline", {}).get("enabled") and item.get("timeline", {}).get("applied")
            ]
        )
        simplified_count = len(
            [
                item
                for item in written_results
                if item.get("simplified", {}).get("enabled") and item.get("simplified", {}).get("converted")
            ]
        )
        return written_results, fixed_count, simplified_count

    def _write_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        session_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_session(self, session_id: str) -> Tuple[Path, Dict[str, Any]]:
        session_dir = self._get_session_root() / self._normalize_text(session_id)
        session_file = session_dir / "session.json"
        if not session_file.exists():
            raise HTTPException(status_code=404, detail="上传会话不存在或已过期")
        try:
            return session_dir, json.loads(session_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取上传会话失败: {exc}") from exc

    def _online_service(self) -> OnlineSubtitleSearchService:
        return OnlineSubtitleSearchService(
            engine=self._online_engine,
            use_proxy=self._online_use_proxy,
            provider_roots=self._online_site_urls,
            assrt_api_key=self._assrt_api_key,
            assrt_api_url=self._assrt_api_url,
            opensubtitles_api_key=self._opensubtitles_api_key,
            opensubtitles_api_url=self._opensubtitles_api_url,
            opensubtitles_username=self._opensubtitles_username,
            opensubtitles_password=self._opensubtitles_password,
        )

    @classmethod
    def _target_ids_from_body(cls, body: Dict[str, Any]) -> List[str]:
        target_ids = body.get("target_ids") or []
        if isinstance(target_ids, str):
            try:
                target_ids = json.loads(target_ids)
            except Exception:
                target_ids = [target_ids]
        if not isinstance(target_ids, list):
            return []
        return [cls._normalize_text(item) for item in target_ids if cls._normalize_text(item)]

    @classmethod
    def _results_from_body(cls, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = body.get("results") or body.get("selected_results") or []
        if isinstance(results, dict):
            results = [results]
        if not isinstance(results, list):
            return []
        return [item for item in results if isinstance(item, dict)]

    def _online_keywords(
        self,
        body: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> List[str]:
        manual_keyword = self._normalize_text(body.get("keyword"))
        media = body.get("media") if isinstance(body.get("media"), dict) else {}
        scope = self._normalize_text(body.get("scope")) or "auto"
        keywords = build_search_keywords(media, targets, scope)
        if manual_keyword:
            keywords = [manual_keyword, *[item for item in keywords if item != manual_keyword]]
        return keywords[:8]

    def _auto_search_keywords_for_entry(self, entry: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
        media = {
            "media_type": entry.get("media_type"),
            "title": entry.get("title"),
            "year": entry.get("year"),
        }
        return build_search_keywords(media, [target], "auto")[:8]

    def _auto_search_and_write_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        target = self._target_from_entry(entry)
        if target.get("has_subtitle"):
            return {"status": "skipped", "reason": "目标已有外挂字幕", "target": target.get("label")}
        providers = list(self._online_provider_ids or [])
        if not providers:
            return {"status": "skipped", "reason": "未配置可用 API 字幕源", "target": target.get("label")}
        keywords = self._auto_search_keywords_for_entry(entry, target)
        if not keywords:
            return {"status": "skipped", "reason": "没有可用搜索关键词", "target": target.get("label")}

        self._check_online_rate_limit(providers)
        service = self._online_service()
        search_result = service.search(
            keywords=keywords,
            providers=providers,
            targets=[target],
            scope="auto",
        )
        candidates = [
            item
            for item in search_result.get("results") or []
            if item.get("downloadable") is not False and self._safe_int(item.get("score"), 0) >= self._auto_search_min_score
        ]
        if len(candidates) != 1:
            return {
                "status": "skipped",
                "reason": f"高置信可下载结果数量为 {len(candidates)}",
                "target": target.get("label"),
                "results": len(search_result.get("results") or []),
            }

        selected = candidates[0]
        session_id = self._hash_text(f"auto|{datetime.now().isoformat()}|{entry.get('id')}")[:16]
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        try:
            downloads = service.download([selected])
            prepared_uploads: List[Dict[str, Any]] = []
            for downloaded in downloads:
                result = downloaded.get("result") or {}
                source_name = self._normalize_online_download_name(
                    downloaded.get("source_name", ""),
                    downloaded.get("content") or b"",
                    result,
                )
                extracted = self._extract_subtitle_files(
                    source_name,
                    downloaded.get("content") or b"",
                    session_dir,
                )
                for item in extracted:
                    item["online_source"] = downloaded.get("provider")
                    item["online_title"] = result.get("title", "")
                    if not item.get("archive_name") and source_name != item.get("source_name"):
                        item["archive_name"] = source_name
                prepared_uploads.extend(extracted)
            if len(prepared_uploads) != 1:
                return {
                    "status": "skipped",
                    "reason": f"下载包解析出 {len(prepared_uploads)} 个字幕，需人工确认",
                    "target": target.get("label"),
                }

            prepared = prepared_uploads[0]
            raw_bytes = Path(prepared["stored_path"]).read_bytes()
            language_profile = self._detect_language_profile(prepared["source_name"], raw_bytes)
            item = {
                "upload_id": prepared["upload_id"],
                "target_id": entry["id"],
                "ext": prepared["ext"],
                "language_suffix": language_profile["suffix"],
            }
            operations = self._build_write_operations(
                [item],
                {prepared["upload_id"]: prepared},
                {entry["id"]: entry},
            )
            written, _, simplified_count = self._write_operations_to_disk(
                session_dir=session_dir,
                operations=operations,
                fix_timeline=False,
            )
            if selected.get("language_category") == "english":
                try:
                    self._submit_autosub_for_entries([entry])
                except Exception as exc:
                    logger.warning("[SubtitleManualUpload] 自动入库英文字幕提交 AI 翻译失败: %s", exc)
            return {
                "status": "written",
                "target": target.get("label"),
                "result": selected.get("title"),
                "written": written,
                "simplified_count": simplified_count,
            }
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)

    def _process_transfer_auto_subtitles(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            try:
                result = self._auto_search_and_write_entry(entry)
                logger.info(
                    "[SubtitleManualUpload] 入库自动字幕处理完成 target=%s status=%s reason=%s",
                    result.get("target"),
                    result.get("status"),
                    result.get("reason", ""),
                )
            except Exception as exc:
                logger.warning(
                    "[SubtitleManualUpload] 入库自动字幕处理失败 target=%s error=%s",
                    entry.get("target_label") or entry.get("filename"),
                    exc,
                )

    @classmethod
    def _normalize_online_download_name(cls, name: str, content: bytes, result: Dict[str, Any]) -> str:
        safe_name = Path(cls._normalize_text(name)).name
        suffix = Path(safe_name).suffix.lower()
        magic_suffix = cls._archive_suffix_from_content(content)
        if magic_suffix:
            stem = Path(safe_name).stem if safe_name else ""
            if not stem:
                stem = re.sub(r"[\\/:*?\"<>|]+", " ", cls._normalize_text(result.get("title")) or "online-subtitle").strip()
            return f"{stem or 'online-subtitle'}{magic_suffix}"
        if suffix in cls._subtitle_exts or suffix in cls._archive_exts:
            return safe_name
        title = re.sub(r"[\\/:*?\"<>|]+", " ", cls._normalize_text(result.get("title")) or "online-subtitle").strip()
        if content.startswith(b"PK\x03\x04"):
            return f"{title}.zip"
        if content.startswith(b"Rar!\x1a\x07"):
            return f"{title}.rar"
        text_head = cls._decode_preview_bytes(content[:4096]).lstrip()
        if re.match(r"^\d+\s*\n\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->", text_head):
            return f"{title}.srt"
        if "[Script Info]" in text_head or "[V4+ Styles]" in text_head:
            return f"{title}.ass"
        return safe_name or f"{title}.zip"

    @staticmethod
    def _archive_suffix_from_content(content: bytes) -> str:
        head = (content or b"")[:8]
        if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
            return ".zip"
        if head.startswith(b"Rar!\x1a\x07"):
            return ".rar"
        return ""

    def _build_preview_response_from_uploads(
        self,
        *,
        session_id: str,
        target_ids: List[str],
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        unsupported_files: Optional[List[str]] = None,
        invalid_files: Optional[List[Dict[str, str]]] = None,
        source: str = "upload",
    ) -> Dict[str, Any]:
        unsupported_files = unsupported_files or []
        invalid_files = invalid_files or []
        targets = [self._target_from_entry(item) for item in target_entries]
        preview_items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            file_path = Path(prepared["stored_path"])
            raw_bytes = file_path.read_bytes()
            language_profile = self._detect_language_profile(prepared["source_name"], raw_bytes)
            preview_item = {
                "upload_id": prepared["upload_id"],
                "source_name": prepared["source_name"],
                "archive_name": prepared.get("archive_name", ""),
                "ext": prepared["ext"],
                "target_id": self._suggest_target(prepared, targets),
                "detected_label": language_profile["label"],
                "language_suffix": language_profile["suffix"],
                "online_source": prepared.get("online_source", ""),
            }
            preview_items.append(preview_item)

        self._auto_fill_missing_targets(preview_items, targets)
        target_lookup = {item["id"]: item for item in targets if item.get("id")}
        for item in preview_items:
            target = target_lookup.get(item.get("target_id"))
            item["output_name"] = self._build_destination_name(target, item) if target else ""

        session_payload = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_ids": list(target_ids),
            "targets": target_entries,
            "uploads": prepared_uploads,
            "source": source,
        }
        self._write_session(session_id, session_payload)

        resolved_count = len([item for item in preview_items if item.get("target_id")])
        message = f"已解析 {len(preview_items)} 个字幕文件，自动匹配 {resolved_count} 个。"
        if unsupported_files:
            message += f" 已忽略 {len(unsupported_files)} 个不支持的文件。"
        if invalid_files:
            message += f" 有 {len(invalid_files)} 个压缩包解析失败。"

        logger.info(
            "[SubtitleManualUpload] 预览生成完成 source=%s session=%s subtitles=%s resolved=%s unsupported=%s invalid=%s",
            source,
            session_id,
            len(preview_items),
            resolved_count,
            len(unsupported_files),
            len(invalid_files),
        )
        return self._ok(
            {
                "session_id": session_id,
                "source": source,
                "targets": targets,
                "items": preview_items,
                "unsupported_files": unsupported_files,
                "invalid_files": invalid_files,
            },
            message=message,
        )
    def api_status(self) -> Dict[str, Any]:
        rar_tool = self._rar_tool()
        rar_python = self._rar_python_available()
        return self._ok(
            {
                "enabled": self.get_state(),
                "auto_search_on_transfer": bool(self._auto_search_on_transfer),
                "traditional_to_simplified": bool(self._traditional_to_simplified),
                "source": "MoviePilot 本地整理记录",
                "index": self._cache_status(),
                "archive_support": {
                    "zip": True,
                    "rar": bool(rar_tool),
                    "rar_tool": Path(rar_tool).name if rar_tool else "",
                    "rar_tool_path": rar_tool or self._rar_tool_path,
                    "rar_python": rar_python,
                    "rar_python_package": self._rar_python_package,
                    "dependency_mode": self._rar_dependency_mode,
                    "dependency_status": self._rar_dependency_status,
                },
                "timeline_fixer": check_timeline_fixer_dependencies(),
                "online_search": {
                    "enabled_providers": self._online_provider_ids,
                    "assrt_api_configured": bool(self._assrt_api_key),
                    "assrt_api_host": self._host_from_url(self._assrt_api_url),
                    "opensubtitles_api_configured": bool(self._opensubtitles_api_key),
                    "opensubtitles_api_host": self._host_from_url(self._opensubtitles_api_url),
                    "opensubtitles_download_configured": bool(
                        self._opensubtitles_username and self._opensubtitles_password
                    ),
                },
                "ai_subtitle": self._autosub_status(),
            }
        )

    def api_refresh_index(self) -> Dict[str, Any]:
        entries = self._refresh_local_cache()
        cache_status = self._cache_status()
        return self._ok(
            {
                "realtime": False,
                "index": cache_status,
            },
            message=f"已刷新媒体库资源清单：{cache_status['media_count']} 个媒体，{len(entries)} 个本地视频目标",
        )

    async def api_ai_submit(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要生成 AI 字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        result = self._submit_autosub_for_entries(target_entries)
        return self._ok(
            result,
            message=f"已提交 {len(result.get('added') or [])} 个 AI 字幕生成任务，跳过 {len(result.get('skipped') or [])} 个，失败 {len(result.get('failed') or [])} 个",
        )

    def _submit_autosub_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        plugin, reason = self._autosub_plugin()
        if not plugin:
            raise HTTPException(status_code=409, detail=reason)
        if not hasattr(plugin, "submit_tasks"):
            raise HTTPException(status_code=409, detail="AI 字幕插件版本过旧，请更新到联动版")

        paths = [self._normalize_text(entry.get("path")) for entry in target_entries if self._normalize_text(entry.get("path"))]
        try:
            result = plugin.submit_tasks(paths, source="subtitle_manual_upload")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[SubtitleManualUpload] AI 字幕任务提交失败: %s", exc)
            raise HTTPException(status_code=500, detail=f"AI 字幕任务提交失败: {exc}") from exc

        tasks = self._autosub_tasks_for_entries(target_entries)
        logger.info(
            "[SubtitleManualUpload] AI 字幕任务提交完成 targets=%s added=%s skipped=%s failed=%s",
            len(target_entries),
            len(result.get("added") or []),
            len(result.get("skipped") or []),
            len(result.get("failed") or []),
        )
        return {
            **result,
            "targets": [self._target_from_entry(entry) for entry in target_entries],
            "tasks": tasks,
        }

    async def api_ai_cancel(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要取消的 AI 字幕任务")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        result = self._cancel_autosub_for_entries(target_entries)
        return self._ok(
            result,
            message=f"已取消 {len(result.get('cancelled') or [])} 个 AI 字幕任务，跳过 {len(result.get('skipped') or [])} 个",
        )

    def _cancel_autosub_for_entries(self, target_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        plugin, reason = self._autosub_plugin()
        if not plugin:
            raise HTTPException(status_code=409, detail=reason)
        if not hasattr(plugin, "cancel_tasks"):
            raise HTTPException(status_code=409, detail="AI 字幕插件版本过旧，请更新到支持取消任务的联动版")

        paths = [self._normalize_text(entry.get("path")) for entry in target_entries if self._normalize_text(entry.get("path"))]
        try:
            result = plugin.cancel_tasks(paths=paths)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[SubtitleManualUpload] AI 字幕任务取消失败: %s", exc)
            raise HTTPException(status_code=500, detail=f"AI 字幕任务取消失败: {exc}") from exc

        tasks = self._autosub_tasks_for_entries(target_entries)
        logger.info(
            "[SubtitleManualUpload] AI 字幕任务取消完成 targets=%s cancelled=%s skipped=%s",
            len(target_entries),
            len(result.get("cancelled") or []),
            len(result.get("skipped") or []),
        )
        return {
            **result,
            "targets": [self._target_from_entry(entry) for entry in target_entries],
            "tasks": tasks,
        }

    async def api_ai_tasks(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            return self._ok(
                {
                    "status": self._autosub_status(),
                    "summary": self._autosub_task_summary([]),
                    "tasks": [],
                    "task_by_target": {},
                }
            )
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        return self._ok(self._autosub_tasks_for_entries(target_entries))

    async def api_search(self, request: Request) -> Dict[str, Any]:
        keyword = self._normalize_text(request.query_params.get("keyword"))
        media_type = self._normalize_text(request.query_params.get("media_type")) or "all"
        limit = min(max(self._safe_int(request.query_params.get("limit"), 20), 1), 100)
        medias = await self._search_media_candidates(keyword=keyword, media_type=media_type, limit=limit)
        logger.info(
            "[SubtitleManualUpload] 本地资源搜索完成 keyword=%s media_type=%s result=%s",
            keyword or "<recent>",
            media_type,
            len(medias),
        )
        return self._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "medias": medias,
            }
        )

    def api_targets(self, request: Request) -> Dict[str, Any]:
        media_type = self._normalize_text(request.query_params.get("media_type"))
        tmdb_id = self._normalize_text(request.query_params.get("tmdb_id"))
        douban_id = self._normalize_text(request.query_params.get("douban_id"))
        title = self._normalize_text(request.query_params.get("title"))
        year = self._normalize_text(request.query_params.get("year"))
        season = self._normalize_text(request.query_params.get("season"))
        result = self._targets_for_media(
            media_type=media_type,
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            title=title,
            year=year,
            season=season,
        )
        logger.info(
            "[SubtitleManualUpload] 本地目标读取完成 media=%s year=%s type=%s season=%s targets=%s all_targets=%s",
            title or tmdb_id or douban_id,
            year or "-",
            media_type or "-",
            result.get("selected_season"),
            result.get("target_count"),
            result.get("all_target_count"),
        )
        return self._ok(result)

    def api_online_status(self) -> Dict[str, Any]:
        status = self._online_service().status()
        status["enabled_providers"] = self._online_provider_ids
        status["online_engine"] = self._online_engine
        status["provider_roots"] = self._online_site_urls
        status["assrt_api_configured"] = bool(self._assrt_api_key)
        status["assrt_api_host"] = self._host_from_url(self._assrt_api_url)
        status["opensubtitles_api_configured"] = bool(self._opensubtitles_api_key)
        status["opensubtitles_api_host"] = self._host_from_url(self._opensubtitles_api_url)
        status["opensubtitles_download_configured"] = bool(
            self._opensubtitles_username and self._opensubtitles_password
        )
        status["rate_limit_per_minute"] = self._online_rate_limit_per_minute
        return self._ok(status)

    async def api_online_manual_links(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [self._target_from_entry(item) for item in target_entries]
        keywords = self._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        providers = list(self._manual_online_provider_ids)
        links = self._online_service().manual_links(keywords, providers=providers)
        logger.info(
            "[SubtitleManualUpload] 在线字幕手动链接生成 target_count=%s keywords=%s providers=%s",
            len(targets),
            len(keywords),
            ",".join(providers),
        )
        return self._ok(
            {
                "keywords": keywords,
                "links": links,
            }
        )

    async def api_online_search(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [self._target_from_entry(item) for item in target_entries]
        keywords = self._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        requested_providers = body.get("providers") if isinstance(body.get("providers"), list) else self._online_provider_ids
        providers = self._normalize_provider_ids(requested_providers, fallback=not isinstance(body.get("providers"), list))
        if not providers:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕源")
        self._check_online_rate_limit(providers)
        scope = self._normalize_text(body.get("scope")) or "auto"
        service = self._online_service()
        search_result = await run_in_threadpool(
            service.search,
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope=scope,
        )
        manual_links = service.manual_links(keywords, providers=providers)
        logger.info(
            "[SubtitleManualUpload] 在线字幕搜索完成 scope=%s providers=%s targets=%s results=%s",
            scope,
            ",".join(providers),
            len(targets),
            len(search_result.get("results") or []),
        )
        return self._ok(
            {
                "keywords": keywords,
                "providers": providers,
                "targets": targets,
                "results": search_result.get("results") or [],
                "messages": search_result.get("messages") or [],
                "manual_links": manual_links,
            }
        )

    async def api_online_search_provider(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [self._target_from_entry(item) for item in target_entries]
        keywords = self._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        provider_id = self._normalize_text(body.get("provider"))
        providers = self._normalize_provider_ids([provider_id], fallback=False)
        if not providers:
            raise HTTPException(status_code=400, detail="未知或未启用的在线字幕源")
        self._check_online_rate_limit(providers)
        scope = self._normalize_text(body.get("scope")) or "auto"
        service = self._online_service()
        search_result = await run_in_threadpool(
            service.search,
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope=scope,
        )
        logger.info(
            "[SubtitleManualUpload] 在线字幕单源搜索完成 scope=%s provider=%s targets=%s results=%s",
            scope,
            providers[0],
            len(targets),
            len(search_result.get("results") or []),
        )
        return self._ok(
            {
                "keywords": keywords,
                "provider": providers[0],
                "providers": providers,
                "targets": targets,
                "results": search_result.get("results") or [],
                "messages": search_result.get("messages") or [],
            }
        )

    async def api_online_download_preview(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = self._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要写入字幕的本地视频")
        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        selected_results = self._results_from_body(body)
        if not selected_results:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕结果")
        self._check_online_rate_limit([item.get("provider") for item in selected_results if isinstance(item, dict)])
        submit_ai_translate = bool(body.get("submit_ai_translate"))
        if submit_ai_translate and any((item.get("language_category") or "").lower() == "chinese" for item in selected_results):
            raise HTTPException(status_code=400, detail="请只选择外语字幕结果后再提交 AI 翻译")

        session_id = self._hash_text(f"online|{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        prepared_uploads: List[Dict[str, Any]] = []
        unsupported_files: List[str] = []
        invalid_files: List[Dict[str, str]] = []
        try:
            downloads = await run_in_threadpool(
                self._online_service().download,
                selected_results,
            )
            for downloaded in downloads:
                result = downloaded.get("result") or {}
                source_name = self._normalize_online_download_name(
                    downloaded.get("source_name", ""),
                    downloaded.get("content") or b"",
                    result,
                )
                try:
                    extracted = self._extract_subtitle_files(
                        source_name,
                        downloaded.get("content") or b"",
                        session_dir,
                    )
                except ValueError as exc:
                    invalid_files.append({"name": source_name, "reason": str(exc)})
                    continue
                if not extracted:
                    unsupported_files.append(source_name)
                    continue
                for item in extracted:
                    item["online_source"] = downloaded.get("provider")
                    item["online_title"] = result.get("title", "")
                    if not item.get("archive_name") and source_name != item.get("source_name"):
                        item["archive_name"] = source_name
                prepared_uploads.extend(extracted)
        except CaptchaRequiredError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.warning("[SubtitleManualUpload] 在线字幕自动仿真下载失败 provider=%s message=%s", exc.provider, exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.warning("[SubtitleManualUpload] 在线字幕下载预览失败：%s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.error("[SubtitleManualUpload] 在线字幕下载预览异常: %s", exc)
            raise HTTPException(status_code=500, detail=f"在线字幕下载失败: {exc}") from exc

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{invalid_files[0]['reason']}")
            raise HTTPException(status_code=400, detail="没有解析到可用的在线字幕文件")

        logger.info(
            "[SubtitleManualUpload] 在线字幕下载完成 selected=%s prepared=%s unsupported=%s invalid=%s",
            len(selected_results),
            len(prepared_uploads),
            len(unsupported_files),
            len(invalid_files),
        )
        response = self._build_preview_response_from_uploads(
            session_id=session_id,
            target_ids=target_ids,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            unsupported_files=unsupported_files,
            invalid_files=invalid_files,
            source="online",
        )
        if submit_ai_translate:
            response["data"]["ai_translate"] = self._submit_autosub_for_entries(target_entries)
            response["message"] = f"{response.get('message') or ''} 已提交 AI 字幕翻译任务。".strip()
        return response

    async def api_prepare_upload(self, request: Request) -> Dict[str, Any]:
        form = await request.form()
        target_ids_raw = self._normalize_text(form.get("target_ids"))
        if not target_ids_raw:
            logger.warning("[SubtitleManualUpload] 上传预览失败：未提供目标 target_ids")
            raise HTTPException(status_code=400, detail="请先选择目标电影或剧集")

        try:
            target_ids = json.loads(target_ids_raw)
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标参数格式错误 %s", exc)
            raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc
        if not isinstance(target_ids, list) or not target_ids:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：目标视频已失效 target_ids=%s",
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        upload_files = [item for item in form.getlist("files") if self._is_upload_file(item)]
        if not upload_files:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：未收到字幕文件 target_count=%s target_ids=%s",
                len(target_entries),
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="请至少上传一个字幕文件、ZIP 或 RAR")

        logger.info(
            "[SubtitleManualUpload] 开始上传预览 target_count=%s upload_files=%s target_ids=%s",
            len(target_entries),
            len(upload_files),
            self._brief_ids(target_ids),
        )

        session_id = self._hash_text(f"{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        prepared_uploads: List[Dict[str, Any]] = []
        unsupported_files: List[str] = []
        invalid_files: List[Dict[str, str]] = []
        for upload in upload_files:
            file_name = Path(self._normalize_text(upload.filename)).name
            if not file_name:
                continue
            raw_bytes = await upload.read()
            try:
                extracted = self._extract_subtitle_files(file_name, raw_bytes, session_dir)
            except ValueError as exc:
                invalid_files.append(
                    {
                        "name": file_name,
                        "reason": str(exc),
                    }
                )
                continue
            if not extracted:
                unsupported_files.append(file_name)
                continue
            prepared_uploads.extend(extracted)

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                first_reason = invalid_files[0]["reason"]
                logger.warning(
                    "[SubtitleManualUpload] 上传预览失败：压缩包解析失败 invalid=%s unsupported=%s reason=%s",
                    len(invalid_files),
                    len(unsupported_files),
                    first_reason,
                )
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{first_reason}")
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：没有可用字幕 unsupported=%s",
                len(unsupported_files),
            )
            raise HTTPException(status_code=400, detail="没有解析到可用的字幕文件，请检查文件格式")

        return self._build_preview_response_from_uploads(
            session_id=session_id,
            target_ids=target_ids,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            unsupported_files=unsupported_files,
            invalid_files=invalid_files,
            source="upload",
        )

    async def api_apply_upload(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        session_id = self._normalize_text(body.get("session_id"))
        items = body.get("items") or []
        fix_timeline = bool(body.get("fix_timeline"))
        if not session_id or not isinstance(items, list) or not items:
            logger.warning("[SubtitleManualUpload] 写入失败：缺少会话或匹配结果 session=%s", session_id or "-")
            raise HTTPException(status_code=400, detail="缺少上传会话或匹配结果")

        session_dir, session_payload = self._load_session(session_id)
        upload_map = {
            item["upload_id"]: item
            for item in session_payload.get("uploads", [])
            if item.get("upload_id")
        }
        target_entries = {
            item["id"]: item
            for item in session_payload.get("targets", [])
            if item.get("id")
        }
        if not target_entries:
            logger.warning("[SubtitleManualUpload] 写入失败：会话目标为空 session=%s", session_id)
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并上传")

        logger.info(
            "[SubtitleManualUpload] 开始写入字幕 session=%s items=%s targets=%s fix_timeline=%s",
            session_id,
            len(items),
            len(target_entries),
            fix_timeline,
        )
        operations = self._build_write_operations(items, upload_map, target_entries)
        written_results, fixed_count, simplified_count = self._write_operations_to_disk(
            session_dir=session_dir,
            operations=operations,
            fix_timeline=fix_timeline,
        )

        shutil.rmtree(session_dir, ignore_errors=True)

        message = f"已写入 {len(written_results)} 个字幕文件"
        if fix_timeline:
            message += f"，智能调轴 {fixed_count} 个"
        if self._traditional_to_simplified:
            message += f"，繁转简 {simplified_count} 个"

        logger.info(
            "[SubtitleManualUpload] 字幕写入完成 session=%s count=%s fix_timeline=%s fixed=%s",
            session_id,
            len(written_results),
            fix_timeline,
            fixed_count,
        )

        return self._ok(
            {
                "count": len(written_results),
                "written": written_results,
            },
            message=message,
        )

    async def api_clear_subtitles(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = body.get("target_ids") or []
        if isinstance(target_ids, str):
            try:
                target_ids = json.loads(target_ids)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 清空外挂字幕失败：目标参数格式错误 %s", exc)
                raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc

        if not isinstance(target_ids, list) or not target_ids:
            logger.warning("[SubtitleManualUpload] 清空外挂字幕失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = self._resolve_targets(target_ids)
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 清空外挂字幕失败：目标视频已失效 target_ids=%s",
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        deleted: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []
        visited_paths = set()
        for target_id in target_ids:
            clean_target_id = self._normalize_text(target_id)
            target_entry = target_entries.get(clean_target_id)
            if not target_entry:
                failed.append({"target_id": clean_target_id, "reason": "目标视频已失效"})
                continue
            if self._normalize_text(target_entry.get("storage")) not in {"", "local"}:
                failed.append({"target_id": clean_target_id, "reason": "当前仅支持清空本地媒体文件的外挂字幕"})
                continue

            target_label = self._target_from_entry(target_entry).get("label")
            for subtitle in self._subtitle_files_for_target(target_entry):
                subtitle_path = Path(subtitle["path"])
                path_key = str(subtitle_path)
                if path_key in visited_paths:
                    continue
                visited_paths.add(path_key)
                try:
                    subtitle_path.unlink()
                    deleted.append(
                        {
                            "target_id": clean_target_id,
                            "target_label": target_label,
                            "name": subtitle_path.name,
                            "path": path_key,
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "[SubtitleManualUpload] 删除外挂字幕失败 target=%s subtitle=%s error=%s",
                        clean_target_id[:8],
                        subtitle_path.name,
                        exc,
                    )
                    failed.append({"target_id": clean_target_id, "reason": f"{subtitle_path.name}: {exc}"})

        logger.info(
            "[SubtitleManualUpload] 清空外挂字幕完成 targets=%s deleted=%s failed=%s",
            len(target_ids),
            len(deleted),
            len(failed),
        )

        message = f"已删除 {len(deleted)} 个外挂字幕"
        if failed:
            message += f"，{len(failed)} 个目标处理失败"

        return self._ok(
            {
                "count": len(deleted),
                "deleted": deleted,
                "failed": failed,
            },
            message=message,
        )
