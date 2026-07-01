from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..online.online_subtitle import (
    DEFAULT_ASSRT_API_URL,
    DEFAULT_ENGINE,
    DEFAULT_OPENSUBTITLES_API_URL,
    DEFAULT_PROVIDER_ROOTS,
    normalize_online_engine,
    normalize_provider_roots,
)
from ..matching.subtitle_language import (
    DEFAULT_AUTO_FORMAT_PRIORITY,
    DEFAULT_AUTO_LANGUAGE_PRIORITY,
    normalize_auto_format_priority,
    normalize_auto_language_priority,
)


DEFAULT_RAR_TOOL_PATH = "/usr/bin/unar"
DEFAULT_ONLINE_PROVIDER_IDS = ["assrt", "opensubtitles"]
AVAILABLE_ONLINE_PROVIDER_IDS = ["subhd", "zimuku", "assrt", "opensubtitles"]
MANUAL_ONLINE_PROVIDER_IDS = ["subhd", "zimuku", "assrt", "opensubtitles"]

RAR_DEPENDENCY_MODES = {"none", "container_install", "mapped_binary"}
AUTO_TRANSFER_SUBTITLE_STRATEGIES = {"online_then_ai_source", "online_source_only", "ai_source_only"}
AUTO_MULTI_SUBTITLE_MODES = {"best", "chinese_all", "all"}
AUTO_TRANSFER_SUBTITLE_STRATEGY_ALIASES = {
    "search_first": "online_then_ai_source",
    "search_only": "online_source_only",
    "ai_only": "ai_source_only",
    "ai_first": "ai_source_only",
}
TIMELINE_VAD_MODES = {"webrtc", "rms"}

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "show_sidebar_nav": True,
    "rar_dependency_mode": "none",
    "rar_tool_path": DEFAULT_RAR_TOOL_PATH,
    "traditional_to_simplified": False,
    "auto_search_on_transfer": False,
    "auto_skip_chinese_media_on_transfer": True,
    "auto_transfer_subtitle_strategy": "online_then_ai_source",
    "trust_transfer_history_paths": False,
    "auto_multi_subtitle_mode": "best",
    "auto_subtitle_language_priority": list(DEFAULT_AUTO_LANGUAGE_PRIORITY),
    "auto_subtitle_format_priority": list(DEFAULT_AUTO_FORMAT_PRIORITY),
    "auto_ass_to_srt_for_ai": True,
    "timeline_max_offset_seconds": 120,
    "timeline_min_offset_seconds": 0.2,
    "timeline_vad_mode": "webrtc",
    "timeline_allow_risky_offset": False,
    "online_providers": list(DEFAULT_ONLINE_PROVIDER_IDS),
    "online_engine": DEFAULT_ENGINE,
    "online_use_proxy": False,
    "subhd_url": DEFAULT_PROVIDER_ROOTS["subhd"],
    "zimuku_url": DEFAULT_PROVIDER_ROOTS["zimuku"],
    "assrt_url": DEFAULT_PROVIDER_ROOTS["assrt"],
    "assrt_api_key": "",
    "assrt_api_url": DEFAULT_ASSRT_API_URL,
    "opensubtitles_url": DEFAULT_PROVIDER_ROOTS["opensubtitles"],
    "opensubtitles_api_key": "",
    "opensubtitles_api_url": DEFAULT_OPENSUBTITLES_API_URL,
    "opensubtitles_username": "",
    "opensubtitles_password": "",
    "ai_link_enabled": True,
}


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_root_url(value: Any, default: str) -> str:
    url = normalize_text(value).rstrip("/")
    if re.match(r"^https?://", url, flags=re.I):
        return url
    return default


def host_from_url(value: Any) -> str:
    match = re.match(r"^https?://([^/?#]+)", normalize_text(value), flags=re.I)
    return match.group(1) if match else ""


def normalize_timeline_max_offset(value: Any) -> int:
    seconds = safe_int(value, 120)
    if seconds <= 0:
        return 120
    return min(seconds, 300)


def normalize_timeline_min_offset(value: Any) -> float:
    try:
        seconds = float(value)
    except Exception:
        seconds = 0.2
    if seconds <= 0 or seconds > 1:
        return 0.2
    return seconds


def normalize_timeline_vad_mode(value: Any) -> str:
    mode = normalize_text(value).lower()
    return mode if mode in TIMELINE_VAD_MODES else "webrtc"


def normalize_auto_multi_subtitle_mode(value: Any) -> str:
    mode = normalize_text(value).lower()
    aliases = {
        "preferred": "best",
        "prefer": "best",
        "best_only": "best",
        "chinese": "chinese_all",
        "chinese_and_bilingual": "chinese_all",
        "all_chinese": "chinese_all",
        "everything": "all",
    }
    mode = aliases.get(mode, mode)
    return mode if mode in AUTO_MULTI_SUBTITLE_MODES else "best"


def normalize_rar_dependency_mode(value: Any) -> str:
    mode = normalize_text(value).lower()
    if mode in RAR_DEPENDENCY_MODES:
        return mode
    return "none"


def normalize_auto_transfer_subtitle_strategy(value: Any) -> str:
    strategy = normalize_text(value).lower()
    strategy = AUTO_TRANSFER_SUBTITLE_STRATEGY_ALIASES.get(strategy, strategy)
    if strategy in AUTO_TRANSFER_SUBTITLE_STRATEGIES:
        return strategy
    return "online_then_ai_source"


def normalize_provider_ids(
    value: Any,
    *,
    fallback: bool = True,
    available_provider_ids: Optional[Iterable[str]] = None,
    default_provider_ids: Optional[Iterable[str]] = None,
) -> List[str]:
    allowed = set(available_provider_ids or AVAILABLE_ONLINE_PROVIDER_IDS)
    defaults = list(default_provider_ids or DEFAULT_ONLINE_PROVIDER_IDS)
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = re.split(r"[,，\s]+", value)
    else:
        raw_items = defaults
    providers = []
    for item in raw_items:
        provider_id = normalize_text(item).lower()
        if provider_id in allowed and provider_id not in providers:
            providers.append(provider_id)
    return providers or (list(defaults) if fallback else [])


def normalize_online_site_urls(config: Dict[str, Any]) -> Dict[str, str]:
    raw = config.get("online_site_urls") if isinstance(config.get("online_site_urls"), dict) else {}
    roots = {
        "subhd": raw.get("subhd") or config.get("subhd_url"),
        "zimuku": raw.get("zimuku") or config.get("zimuku_url"),
        "assrt": raw.get("assrt") or config.get("assrt_url"),
        "opensubtitles": raw.get("opensubtitles") or config.get("opensubtitles_url"),
    }
    return normalize_provider_roots(roots)


def build_default_config(
    *,
    default_auto_language_priority: Optional[Iterable[str]] = None,
    default_auto_format_priority: Optional[Iterable[str]] = None,
    default_online_provider_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    config["auto_subtitle_language_priority"] = list(
        default_auto_language_priority or DEFAULT_AUTO_LANGUAGE_PRIORITY
    )
    config["auto_subtitle_format_priority"] = list(default_auto_format_priority or DEFAULT_AUTO_FORMAT_PRIORITY)
    config["online_providers"] = list(default_online_provider_ids or DEFAULT_ONLINE_PROVIDER_IDS)
    return config


def normalize_plugin_config(
    config: Optional[Dict[str, Any]],
    *,
    subtitle_exts: Optional[Iterable[str]] = None,
    default_auto_language_priority: Optional[Iterable[str]] = None,
    default_auto_format_priority: Optional[Iterable[str]] = None,
    available_provider_ids: Optional[Iterable[str]] = None,
    default_provider_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    raw_config = config or {}
    assrt_api_key = normalize_text(raw_config.get("assrt_api_key"))
    opensubtitles_api_key = normalize_text(raw_config.get("opensubtitles_api_key"))
    opensubtitles_username = normalize_text(raw_config.get("opensubtitles_username"))
    if "@" in opensubtitles_username:
        opensubtitles_username = ""

    available_provider_list = list(available_provider_ids or AVAILABLE_ONLINE_PROVIDER_IDS)
    default_provider_list = list(default_provider_ids or DEFAULT_ONLINE_PROVIDER_IDS)
    online_provider_ids = normalize_provider_ids(
        raw_config.get("online_providers"),
        available_provider_ids=available_provider_list,
        default_provider_ids=default_provider_list,
    )
    if not raw_config.get("assrt_provider_migrated") and not assrt_api_key:
        online_provider_ids = [item for item in online_provider_ids if item != "assrt"]
    if assrt_api_key and "assrt" not in online_provider_ids:
        online_provider_ids.append("assrt")
    if opensubtitles_api_key and "opensubtitles" not in online_provider_ids:
        online_provider_ids.append("opensubtitles")
    online_provider_ids = [
        item
        for item in online_provider_ids
        if item in available_provider_list
        and (item != "assrt" or assrt_api_key)
        and (item != "opensubtitles" or opensubtitles_api_key)
    ]

    legacy_proxy_default = "online_proxy_migrated" not in raw_config and raw_config.get("online_use_proxy") is True
    return {
        "enabled": bool(raw_config.get("enabled")),
        "show_sidebar_nav": bool(raw_config.get("show_sidebar_nav", True)),
        "rar_dependency_mode": normalize_rar_dependency_mode(raw_config.get("rar_dependency_mode")),
        "rar_tool_path": normalize_text(raw_config.get("rar_tool_path")) or DEFAULT_RAR_TOOL_PATH,
        "online_providers": online_provider_ids,
        "online_engine": normalize_online_engine(raw_config.get("online_engine")),
        "online_use_proxy": False if legacy_proxy_default else bool(raw_config.get("online_use_proxy", False)),
        "online_site_urls": normalize_online_site_urls(raw_config),
        "assrt_api_key": assrt_api_key,
        "assrt_api_url": normalize_root_url(raw_config.get("assrt_api_url"), DEFAULT_ASSRT_API_URL),
        "opensubtitles_api_key": opensubtitles_api_key,
        "opensubtitles_api_url": normalize_root_url(
            raw_config.get("opensubtitles_api_url"),
            DEFAULT_OPENSUBTITLES_API_URL,
        ),
        "opensubtitles_username": opensubtitles_username,
        "opensubtitles_password": normalize_text(raw_config.get("opensubtitles_password")),
        "ai_link_enabled": bool(raw_config.get("ai_link_enabled", True)),
        "traditional_to_simplified": bool(raw_config.get("traditional_to_simplified", False)),
        "auto_search_on_transfer": bool(raw_config.get("auto_search_on_transfer", False)),
        "auto_skip_chinese_media_on_transfer": bool(raw_config.get("auto_skip_chinese_media_on_transfer", True)),
        "auto_transfer_subtitle_strategy": normalize_auto_transfer_subtitle_strategy(
            raw_config.get("auto_transfer_subtitle_strategy")
        ),
        "trust_transfer_history_paths": bool(raw_config.get("trust_transfer_history_paths", False)),
        "auto_multi_subtitle_mode": normalize_auto_multi_subtitle_mode(raw_config.get("auto_multi_subtitle_mode")),
        "auto_subtitle_language_priority": normalize_auto_language_priority(
            raw_config.get("auto_subtitle_language_priority"),
            list(default_auto_language_priority or DEFAULT_AUTO_LANGUAGE_PRIORITY),
        ),
        "auto_subtitle_format_priority": normalize_auto_format_priority(
            raw_config.get("auto_subtitle_format_priority"),
            subtitle_exts or DEFAULT_AUTO_FORMAT_PRIORITY,
            list(default_auto_format_priority or DEFAULT_AUTO_FORMAT_PRIORITY),
        ),
        "auto_ass_to_srt_for_ai": bool(raw_config.get("auto_ass_to_srt_for_ai", True)),
        "timeline_max_offset_seconds": normalize_timeline_max_offset(raw_config.get("timeline_max_offset_seconds")),
        "timeline_min_offset_seconds": normalize_timeline_min_offset(raw_config.get("timeline_min_offset_seconds")),
        "timeline_vad_mode": normalize_timeline_vad_mode(raw_config.get("timeline_vad_mode")),
        "timeline_allow_risky_offset": bool(raw_config.get("timeline_allow_risky_offset", False)),
    }


def _field(component: str, props: Dict[str, Any]) -> Dict[str, Any]:
    return {"component": component, "props": props}


def _col(component: str, props: Dict[str, Any], *, md: Optional[int] = None) -> Dict[str, Any]:
    col_props = {"cols": 12}
    if md is not None:
        col_props["md"] = md
    return {"component": "VCol", "props": col_props, "content": [_field(component, props)]}


def _row(*columns: Dict[str, Any]) -> Dict[str, Any]:
    return {"component": "VRow", "content": list(columns)}


def _alert(text: str) -> Dict[str, Any]:
    return _row(
        {
            "component": "VCol",
            "props": {"cols": 12},
            "content": [
                _field(
                    "VAlert",
                    {
                        "type": "info",
                        "variant": "tonal",
                        "text": text,
                    },
                )
            ],
        }
    )


def build_config_form(
    *,
    default_auto_language_priority: Optional[Iterable[str]] = None,
    default_auto_format_priority: Optional[Iterable[str]] = None,
    default_online_provider_ids: Optional[Iterable[str]] = None,
) -> Tuple[List[dict], Dict[str, Any]]:
    form = [
        {
            "component": "VForm",
            "content": [
                _row(
                    _col("VSwitch", {"model": "enabled", "label": "启用插件"}, md=3),
                    _col("VSwitch", {"model": "show_sidebar_nav", "label": "显示侧边栏入口"}, md=3),
                    _col("VSwitch", {"model": "traditional_to_simplified", "label": "写入前繁体转简体"}, md=3),
                    _col("VSwitch", {"model": "auto_search_on_transfer", "label": "入库后自动搜索匹配字幕"}, md=3),
                ),
                _row(
                    _col(
                        "VTextField",
                        {
                            "model": "timeline_max_offset_seconds",
                            "label": "智能调轴最大偏移秒数",
                            "type": "number",
                            "placeholder": "120",
                            "min": 1,
                            "max": 300,
                            "suffix": "秒",
                            "hint": "默认 120；不建议超过 120 秒，过大偏移通常意味着字幕错集或错版本。",
                            "persistentHint": True,
                        },
                        md=4,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "timeline_min_offset_seconds",
                            "label": "智能调轴最小应用阈值",
                            "placeholder": "0.2",
                        },
                        md=4,
                    ),
                    _col(
                        "VSelect",
                        {
                            "model": "timeline_vad_mode",
                            "label": "音频 VAD 模式",
                            "items": [
                                {"title": "WebRTC VAD（推荐）", "value": "webrtc"},
                                {"title": "RMS 能量阈值（降级）", "value": "rms"},
                            ],
                        },
                        md=4,
                    ),
                ),
                _row(
                    _col(
                        "VSwitch",
                        {"model": "auto_skip_chinese_media_on_transfer", "label": "入库自动处理跳过中文资源"},
                        md=6,
                    ),
                    _col(
                        "VSelect",
                        {
                            "model": "auto_transfer_subtitle_strategy",
                            "label": "入库后字幕处理策略",
                            "items": [
                                {"title": "在线匹配优先，AI 来源兜底", "value": "online_then_ai_source"},
                                {"title": "只用在线匹配来源", "value": "online_source_only"},
                                {"title": "只用 AI 来源生成", "value": "ai_source_only"},
                            ],
                        },
                        md=6,
                    ),
                    _col(
                        "VSwitch",
                        {
                            "model": "trust_transfer_history_paths",
                            "label": "信任整理历史路径",
                            "hint": "CD2、网盘挂载、SMB 等慢路径可开启，刷新资源清单时不逐条访问文件。",
                            "persistentHint": True,
                        },
                        md=6,
                    ),
                    _col(
                        "VSelect",
                        {
                            "model": "auto_multi_subtitle_mode",
                            "label": "自动多字幕处理",
                            "items": [
                                {"title": "按偏好选择最佳", "value": "best"},
                                {"title": "中文/双语全部入库", "value": "chinese_all"},
                                {"title": "全部入库", "value": "all"},
                            ],
                        },
                        md=4,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "auto_subtitle_language_priority",
                            "label": "语言优先级",
                            "placeholder": "bilingual,chi,cht,eng",
                            "hint": "默认：双语, 简中, 繁中, 英文",
                            "persistentHint": True,
                        },
                        md=4,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "auto_subtitle_format_priority",
                            "label": "格式优先级",
                            "placeholder": "ass,srt,ssa,vtt",
                            "hint": "默认：ASS, SRT, SSA, VTT",
                            "persistentHint": True,
                        },
                        md=4,
                    ),
                    _col(
                        "VSwitch",
                        {"model": "auto_ass_to_srt_for_ai", "label": "英文 ASS 转临时 SRT 后提交 AI"},
                        md=4,
                    ),
                ),
                _row(
                    _col(
                        "VSelect",
                        {
                            "model": "online_providers",
                            "label": "自动字幕源（API）",
                            "multiple": True,
                            "chips": True,
                            "items": [
                                {"title": "SubHD 中文字幕", "value": "subhd"},
                                {"title": "Zimuku 中文字幕", "value": "zimuku"},
                                {"title": "射手网(伪，需 API Key)", "value": "assrt"},
                                {"title": "OpenSubtitles 多语言字幕", "value": "opensubtitles"},
                            ],
                        },
                        md=6,
                    ),
                    _col(
                        "VSwitch",
                        {"model": "online_use_proxy", "label": "API 搜索和下载使用 MoviePilot 系统代理（默认关闭）"},
                        md=6,
                    ),
                ),
                _row(
                    _col(
                        "VTextField",
                        {
                            "model": "subhd_url",
                            "label": "SubHD 站点地址",
                            "placeholder": DEFAULT_PROVIDER_ROOTS["subhd"],
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "zimuku_url",
                            "label": "Zimuku 站点地址",
                            "placeholder": DEFAULT_PROVIDER_ROOTS["zimuku"],
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "assrt_url",
                            "label": "射手网(伪) 站点地址",
                            "placeholder": DEFAULT_PROVIDER_ROOTS["assrt"],
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "opensubtitles_url",
                            "label": "OpenSubtitles 站点地址",
                            "placeholder": DEFAULT_PROVIDER_ROOTS["opensubtitles"],
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "assrt_api_url",
                            "label": "射手网(伪) API 地址",
                            "placeholder": DEFAULT_ASSRT_API_URL,
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "assrt_api_key",
                            "label": "射手网(伪) API Key",
                            "type": "password",
                            "placeholder": "未填写时不参与自动搜索",
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "opensubtitles_api_url",
                            "label": "OpenSubtitles API 地址",
                            "placeholder": DEFAULT_OPENSUBTITLES_API_URL,
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "opensubtitles_api_key",
                            "label": "OpenSubtitles API Key",
                            "type": "password",
                            "placeholder": "未填写时不参与自动搜索",
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "opensubtitles_username",
                            "label": "OpenSubtitles 用户名（可选）",
                            "placeholder": "下载时用于后台登录换取 token",
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "opensubtitles_password",
                            "label": "OpenSubtitles 密码（可选）",
                            "type": "password",
                            "placeholder": "下载时用于后台登录换取 token",
                        },
                        md=6,
                    ),
                ),
                _alert("从 MoviePilot 本地整理记录中搜索已有视频资源；在线字幕搜索支持 SubHD、Zimuku、射手网(伪) 和 OpenSubtitles。"),
                _row(
                    _col(
                        "VSelect",
                        {
                            "model": "rar_dependency_mode",
                            "label": "压缩包解压器处理方式",
                            "items": [
                                {"title": "不处理，仅检测", "value": "none"},
                                {"title": "加载插件时尝试容器内安装 unar", "value": "container_install"},
                                {"title": "使用宿主机映射文件", "value": "mapped_binary"},
                            ],
                        },
                        md=6,
                    ),
                    _col(
                        "VTextField",
                        {
                            "model": "rar_tool_path",
                            "label": "容器内映射路径",
                            "placeholder": DEFAULT_RAR_TOOL_PATH,
                        },
                        md=6,
                    ),
                ),
            ],
        }
    ]
    return form, build_default_config(
        default_auto_language_priority=default_auto_language_priority,
        default_auto_format_priority=default_auto_format_priority,
        default_online_provider_ids=default_online_provider_ids,
    )
