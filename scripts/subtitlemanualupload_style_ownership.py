from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import subtitlemanualupload_frontend_inventory as frontend_inventory  # noqa: E402


APP_PAGE = frontend_inventory.APP_PAGE
STYLE_CLASS_RE = frontend_inventory.CSS_CLASS_RE


@dataclass(frozen=True)
class FragmentRange:
    name: str
    owner: str
    migration: str
    start: int
    end: int


FRAGMENT_RANGES = [
    FragmentRange("app-page-shell", "AppPage", "stay-in-app-page", 721, 760),
    FragmentRange("media-search-panel", "MediaSearchPanel", "move-in-3.2", 761, 857),
    FragmentRange("match-history-entry", "MatchHistoryPanel", "move-in-3.4", 858, 1077),
    FragmentRange("target-detail-panel", "TargetDetailPanel", "move-in-3.2", 1078, 1394),
    FragmentRange("auto-transfer-queue-dialog", "AutoTransferQueuePanel", "move-in-3.4", 1395, 1445),
    FragmentRange("ai-task-dialog", "AiTaskDialog", "move-in-3.3", 1446, 1564),
    FragmentRange("online-subtitle-dialog", "OnlineSubtitleDialog", "move-in-3.3", 1565, 1821),
    FragmentRange("upload-preview-dialog", "UploadPreviewDialog", "move-in-3.3", 1822, 2010),
    FragmentRange("rar-help-dialog", "UploadPreviewDialog", "move-in-3.3", 2011, 2084),
]

SHARED_SELECTORS = {
    "glass-card": "SharedCardSurface",
    "section-kicker": "SharedTypography",
    "media-type": "SharedTypography",
    "poster-frame": "SharedPosterFrame",
    "media-copy": "SharedMediaCopy",
    "pager-row": "SharedPagination",
    "empty-state": "SharedEmptyState",
    "compact-empty": "SharedEmptyState",
    "compact-status": "SharedStatus",
    "compact-subtitles": "SharedSubtitleHistory",
    "timeline-meta": "SharedTimelineMeta",
    "timeline-meta-list": "SharedTimelineMeta",
    "subtitle-history-list": "SharedSubtitleHistory",
    "subtitle-history-item": "SharedSubtitleHistory",
    "subtitle-history-copy": "SharedSubtitleHistory",
    "subtitle-history-actions": "SharedSubtitleHistory",
    "dialog-title": "SharedDialogChrome",
    "dialog-actions": "SharedDialogChrome",
    "dialog-actions-top": "SharedDialogChrome",
    "online-title-actions": "SharedDialogChrome",
    "command-block": "SharedCommandBlock",
}

APP_PAGE_SELECTORS = {
    "subtitle-upload-page",
    "hero-card",
    "root-tabs",
    "media-stage",
    "episode-stage",
}

LEGACY_ORPHAN_SELECTORS = {
    "auto-queue-head",
    "detail-tabs",
    "history-actions",
    "history-list",
    "history-main",
    "history-panel",
    "history-row",
    "toolbar-hint",
}

FRAMEWORK_DESCENDANT_SELECTORS = {
    "v-btn",
}


def _section_body_start(source: str, tag: str) -> int:
    for match in frontend_inventory.SECTION_RE.finditer(source):
        if match.group("tag").lower() != tag:
            continue
        attrs = match.group("attrs")
        if tag == "style" and not re.search(r"\bscoped\b", attrs):
            continue
        return source[: match.start("body")].count("\n") + 1
    raise ValueError(f"missing {tag} section")


def _fragment_for_line(line_number: int) -> FragmentRange:
    for fragment in FRAGMENT_RANGES:
        if fragment.start <= line_number <= fragment.end:
            return fragment
    return FragmentRange("unclassified-template-fragment", "Unknown", "review-before-extract", line_number, line_number)


def _style_selector_lines(style: str, style_start_line: int) -> dict[str, list[int]]:
    selector_lines: dict[str, list[int]] = {}
    for offset, line in enumerate(style.splitlines(), start=0):
        line_number = style_start_line + offset
        for match in STYLE_CLASS_RE.finditer(line):
            selector_lines.setdefault(match.group(1), []).append(line_number)
    return {selector: sorted(set(lines)) for selector, lines in selector_lines.items()}


def _template_class_usages(template: str, template_start_line: int) -> dict[str, list[dict[str, Any]]]:
    usages: dict[str, list[dict[str, Any]]] = {}

    def add_usage(selector: str, line_number: int, source: str) -> None:
        fragment = _fragment_for_line(line_number)
        item = {
            "line": line_number,
            "fragment": fragment.name,
            "source": source,
        }
        if item not in usages.setdefault(selector, []):
            usages[selector].append(item)

    for offset, line in enumerate(template.splitlines(), start=0):
        line_number = template_start_line + offset
        for attr in re.finditer(r'(?<![:A-Za-z0-9_-])(?:class|selected-class)\s*=\s*"([^"]*)"', line):
            for token in frontend_inventory._compact_text(attr.group(1)).split():
                if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", token):
                    add_usage(token, line_number, "class-attribute")

        dynamic_match = re.search(r'(?<![A-Za-z0-9_-]):class\s*=\s*"([^"]*)"', line)
        if dynamic_match:
            expression = dynamic_match.group(1)
            if "auto-queue-${task.status}" in expression:
                for selector in ("auto-queue-failed", "auto-queue-in_progress", "auto-queue-pending"):
                    add_usage(selector, line_number, "dynamic-auto-queue-status")
            if "aiTaskStatusClass(target)" in expression:
                add_usage("ai-row-btn", line_number, "dynamic-ai-target-status")
            if "ai-${task.status}" in expression:
                add_usage("ai-task-row", line_number, "dynamic-ai-task-status")

        if "<VBtn" in line:
            add_usage("v-btn", line_number, "vuetify-component-descendant")

    return usages


def _owner_from_usages(selector: str, usages: list[dict[str, Any]]) -> tuple[str, str, bool]:
    if selector in LEGACY_ORPHAN_SELECTORS:
        return "LegacyOrphanCleanup", "remove-in-3.5-if-still-unused", False
    if selector in FRAMEWORK_DESCENDANT_SELECTORS:
        return "VuetifyDescendant", "keep-with-consuming-component", False
    if selector in APP_PAGE_SELECTORS:
        return "AppPage", "stay-in-app-page", True
    if selector in SHARED_SELECTORS:
        return SHARED_SELECTORS[selector], "shared-style-extract-or-co-locate-with-first-component", False
    if not usages:
        return "LegacyOrphanCleanup", "remove-in-3.5-if-still-unused", False

    owners = []
    migrations = []
    for usage in usages:
        fragment = _fragment_for_line(int(usage["line"]))
        if fragment.owner not in owners:
            owners.append(fragment.owner)
        if fragment.migration not in migrations:
            migrations.append(fragment.migration)

    if len(owners) == 1:
        return owners[0], migrations[0], migrations[0] == "stay-in-app-page"
    return "SharedAcrossComponents", "shared-style-extract-or-co-locate-with-first-component", False


def build_style_ownership() -> dict[str, Any]:
    source = APP_PAGE.read_text(encoding="utf-8")
    sections = frontend_inventory._parse_sections(source)
    template = sections["template"]["body"]
    style = sections["style_scoped"]["body"]
    template_start_line = _section_body_start(source, "template")
    style_start_line = _section_body_start(source, "style")
    selector_lines = _style_selector_lines(style, style_start_line)
    template_usages = _template_class_usages(template, template_start_line)

    selectors: list[dict[str, Any]] = []
    for selector in sorted(selector_lines):
        usages = sorted(template_usages.get(selector, []), key=lambda item: item["line"])
        owner, migration, retain = _owner_from_usages(selector, usages)
        selectors.append(
            {
                "selector": f".{selector}",
                "style_lines": selector_lines[selector],
                "template_usages": usages,
                "owner": owner,
                "migration": migration,
                "retain_in_app_page": retain,
            }
        )

    unmapped = [item["selector"] for item in selectors if item["owner"] == "Unknown"]
    legacy_orphans = [item["selector"] for item in selectors if item["owner"] == "LegacyOrphanCleanup"]
    moving = [item["selector"] for item in selectors if item["migration"].startswith("move-in-")]
    staying = [item["selector"] for item in selectors if item["retain_in_app_page"]]
    shared = [item["selector"] for item in selectors if item["migration"].startswith("shared-style")]

    return {
        "target": frontend_inventory._relative(APP_PAGE),
        "selector_count": len(selectors),
        "unmapped_selectors": unmapped,
        "legacy_orphan_cleanup_selectors": legacy_orphans,
        "stay_in_app_page_selectors": staying,
        "shared_selectors": shared,
        "move_with_component_selectors": moving,
        "fragment_ranges": [fragment.__dict__ for fragment in FRAGMENT_RANGES],
        "selectors": selectors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Map SubtitleManualUpload AppPage CSS selectors to template owners.")
    parser.add_argument("--summary", action="store_true", help="print counts and selector groups without per-selector usages")
    args = parser.parse_args()
    ownership = build_style_ownership()
    if args.summary:
        summary = {key: value for key, value in ownership.items() if key != "selectors"}
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(json.dumps(ownership, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
