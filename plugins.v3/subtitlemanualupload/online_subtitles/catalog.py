"""Source metadata shared by configuration, scheduling and the Vue UI."""
from __future__ import annotations

import json
from pathlib import Path

PROVIDER_CATALOG = json.loads(Path(__file__).with_name("provider_catalog.json").read_text(encoding="utf-8"))
PROVIDER_SPECS = {item["id"]: item for item in PROVIDER_CATALOG}
AVAILABLE_ONLINE_PROVIDER_IDS = list(PROVIDER_SPECS)
DEFAULT_ONLINE_PROVIDER_IDS = [item["id"] for item in PROVIDER_CATALOG if item["default_enabled"]]
MANUAL_ONLINE_PROVIDER_IDS = list(PROVIDER_SPECS)
DEFAULT_PROVIDER_ROOTS = {item["id"]: item["root_url"] for item in PROVIDER_CATALOG}


def supports_search(provider_id: str, targets: list[dict], scope: str) -> bool:
    spec = PROVIDER_SPECS.get(provider_id)
    if spec is None:
        return False
    media_type = "tv" if scope in {"season", "episode"} or any(
        target.get("media_type") == "tv" or target.get("season") or target.get("episode")
        for target in targets
    ) else "movie"
    return media_type in spec["media_types"]
