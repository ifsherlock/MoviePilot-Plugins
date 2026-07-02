from typing import Any, Dict, Mapping, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "replace_agent_entry": True,
    "show_sidebar_nav": True,
    "scale": 1.0,
    "speed": 1.0,
    "follow_mouse": True,
    "auto_roam": True,
    "shadow": True,
}

CONFIG_ATTRIBUTES = {
    "enabled": "_enabled",
    "replace_agent_entry": "_replace_agent_entry",
    "show_sidebar_nav": "_show_sidebar_nav",
    "scale": "_scale",
    "speed": "_speed",
    "follow_mouse": "_follow_mouse",
    "auto_roam": "_auto_roam",
    "shadow": "_shadow",
}

NUMERIC_BOUNDS = {
    "scale": (0.6, 2.0, 1.0),
    "speed": (0.4, 2.0, 1.0),
}


def clamp_number(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def normalize_config(config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    raw_config = config or {}
    normalized = {
        "enabled": bool(raw_config.get("enabled", DEFAULT_CONFIG["enabled"])),
        "replace_agent_entry": bool(raw_config.get("replace_agent_entry", DEFAULT_CONFIG["replace_agent_entry"])),
        "show_sidebar_nav": bool(raw_config.get("show_sidebar_nav", DEFAULT_CONFIG["show_sidebar_nav"])),
        "follow_mouse": bool(raw_config.get("follow_mouse", DEFAULT_CONFIG["follow_mouse"])),
        "auto_roam": bool(raw_config.get("auto_roam", DEFAULT_CONFIG["auto_roam"])),
        "shadow": bool(raw_config.get("shadow", DEFAULT_CONFIG["shadow"])),
    }
    for key, (minimum, maximum, default) in NUMERIC_BOUNDS.items():
        normalized[key] = clamp_number(raw_config.get(key), minimum, maximum, default)
    return normalized


def apply_config_state(target: Any, config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    normalized = normalize_config(config)
    for key, attribute in CONFIG_ATTRIBUTES.items():
        setattr(target, attribute, normalized[key])
    return normalized


def current_config_state(source: Any) -> Dict[str, Any]:
    return {
        key: getattr(source, attribute, DEFAULT_CONFIG[key])
        for key, attribute in CONFIG_ATTRIBUTES.items()
    }
