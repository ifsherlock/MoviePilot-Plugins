from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_INIT = REPO_ROOT / "plugins.v2" / "subtitlemanualupload" / "__init__.py"
SEARCH_ROOTS = (
    REPO_ROOT / "plugins.v2" / "subtitlemanualupload",
    REPO_ROOT / "tests",
)

MOVIEPILOT_HOOKS = {
    "init_plugin",
    "get_state",
    "get_command",
    "get_render_mode",
    "get_api",
    "get_form",
    "get_page",
    "get_sidebar_nav",
    "stop_service",
    "listen_transfer_complete",
}
ARCHIVE_PREFIXES = (
    "_rar",
    "_sevenzip",
    "_run_archive",
    "_list_rar",
    "_read_rar",
    "_extract_rar",
    "_extract_7z",
    "_extract_command_archive",
    "_extract_subtitle_files",
)
SERVICE_FACTORY_NAMES = {
    "_archive_dependency_service",
    "_upload_session_service_for_path",
    "_upload_session_service",
    "_subtitle_inventory",
    "_subtitle_writer",
    "_subtitle_history",
    "_autosub_bridge",
    "_online_ai_service",
    "_auto_transfer_service",
    "_target_resolver",
    "_local_media_catalog",
    "_media_metadata_service",
    "_timeline_task_store",
    "_online_service",
}
SERVICE_DELEGATE_PREFIXES = (
    "_filter_existing_local_entries",
    "_merge_local_entries_cache",
    "_restore_persisted_local_cache",
    "_start_background_cache_refresh",
    "_load_local_entries",
    "_group_entries_as_media",
    "_resolve_targets",
    "_build_entry_from_history",
    "_entries_from_transfer_event",
    "_merge_seasons",
    "_target_from_entry",
    "_tmdb_detail_for_media",
    "_restore_persisted_match_history_cache",
    "_invalidate_match_history_cache",
    "_match_history_items",
    "_timeline_task_for_target_id",
    "_set_timeline_task",
    "_timeline_tasks_for_entries",
    "_autosub_plugin",
    "_autosub_status",
    "_autosub_tasks_for_entries",
    "_get_session_root",
    "_cleanup_old_sessions",
    "_write_session",
    "_remove_ext_marks",
    "_write_operations_to_disk",
    "_run_timeline_fix",
    "_transfer_auto_key",
    "_claim_transfer_auto_entries",
    "_auto_transfer_entry_key",
    "_auto_transfer_group_key",
    "_trim_auto_transfer_tasks_locked",
    "_ensure_transfer_auto_worker",
    "_update_auto_transfer_task",
    "_claim_next_auto_transfer_batch",
    "_auto_wait_online_rate_limit",
    "_auto_transfer_rate_status",
    "_auto_transfer_queue_summary",
    "_auto_transfer_queue_loop",
    "_auto_search_keywords_for_entry",
    "_auto_search_providers",
    "_auto_search_write_subtitle",
    "_auto_submit_ai_for_entry",
    "_auto_process_transfer_entry",
    "_auto_prepared_items_for_targets",
    "_select_auto_subtitle_items",
    "_auto_write_prepared_uploads_for_entries",
    "_store_auto_season_package_cache",
    "_load_auto_season_package_cache",
    "_auto_write_from_season_cache",
    "_auto_search_write_season_package",
    "_auto_process_transfer_group",
    "_process_transfer_auto_task_batch",
)
AI_AUTOSUB_PREFIXES = (
    "_online_ai",
    "_load_pysubs2",
    "_convert_ass",
    "_ai_ready",
    "_prepare_online_ai",
    "_submit_online_ai",
    "_submit_autosub",
    "_cancel_autosub",
    "_restart_autosub",
    "_filter_restart",
    "_selected_external_subtitle",
    "_autosub_lang",
)
PURE_HELPER_NAMES = {
    "_host_module_value",
    "_ok",
    "_safe_int",
    "_normalize_text",
    "_hash_text",
    "_brief_ids",
    "_decode_preview_bytes",
    "_normalize_auto_transfer_subtitle_strategy",
    "_check_online_rate_limit",
    "_entry_path_is_valid",
    "_entry_filesystem_signature",
    "_timestamp_iso",
    "_normalize_language_suffix",
    "_detect_language_profile",
    "_extract_episode_hint",
    "_media_type_text",
    "_poster_url",
    "_cache_loaded_at",
    "_json_clone",
    "_timeline_task_summary",
    "_autosub_task_summary",
    "_entry_matches_keyword",
    "_tmdb_detail_payload",
    "_tmdb_aliases",
    "_apply_tmdb_detail",
    "_is_stream_path",
    "_is_upload_file",
    "_timeline_result_blocks_auto_write",
    "_timeline_rejection_message",
    "_subtitle_backup_path",
}
REPORT_GROUPS = (
    "ai_autosub_facade",
    "archive_methods",
    "auto_transfer_facade",
    "config_runtime",
    "moviepilot_hooks",
    "other",
    "runtime_helpers",
    "service_delegates",
    "service_factories",
)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _method_group(name: str) -> str:
    if name in MOVIEPILOT_HOOKS:
        return "moviepilot_hooks"
    if name in SERVICE_FACTORY_NAMES:
        return "service_factories"
    if name.startswith(ARCHIVE_PREFIXES):
        return "archive_methods"
    if name in SERVICE_DELEGATE_PREFIXES:
        return "service_delegates"
    if name.startswith(AI_AUTOSUB_PREFIXES):
        return "ai_autosub_facade"
    if name in PURE_HELPER_NAMES:
        return "runtime_helpers"
    if name == "_save_config":
        return "config_runtime"
    if name.startswith("_auto_") or name.startswith("_transfer_auto"):
        return "auto_transfer_facade"
    return "other"


def _is_one_line_delegate(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
        return False
    call = node.body[0].value
    if not isinstance(call, ast.Call):
        return False
    text = ast.unparse(call)
    return "self._" in text and ")." in text


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.py") if path.is_file())
    return sorted(files)


def _references_for(names: list[str]) -> dict[str, dict[str, list[str]]]:
    source_references = {name: [] for name in names}
    test_references = {name: [] for name in names}
    patterns = {name: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])") for name in names}
    for path in _iter_python_files():
        rel = _relative(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(errors="ignore").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if path == PLUGIN_INIT and line.lstrip().startswith("def "):
                continue
            for name, pattern in patterns.items():
                if pattern.search(line):
                    target = test_references if rel.startswith("tests/") else source_references
                    target[name].append(f"{rel}:{lineno}")
    return {
        "source_references": {name: refs for name, refs in source_references.items() if refs},
        "test_references": {name: refs for name, refs in test_references.items() if refs},
    }


def build_inventory(*, details: bool = False) -> dict[str, Any]:
    source = PLUGIN_INIT.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    plugin_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SubtitleManualUpload"
    )
    methods = [
        node
        for node in plugin_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    method_items: list[dict[str, Any]] = []
    method_groups: dict[str, list[str]] = {}
    one_line_delegates: list[str] = []
    for node in methods:
        group = _method_group(node.name)
        method_groups.setdefault(group, []).append(node.name)
        if _is_one_line_delegate(node):
            one_line_delegates.append(node.name)
        item = {
            "name": node.name,
            "group": group,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
            "one_line_delegate": node.name in one_line_delegates,
        }
        method_items.append(item)
    for group in REPORT_GROUPS:
        method_groups.setdefault(group, [])

    method_names = [item["name"] for item in method_items]
    references = _references_for(method_names)
    move_groups = {
        "runtime_helpers",
        "archive_methods",
        "service_factories",
        "service_delegates",
        "ai_autosub_facade",
        "auto_transfer_facade",
        "config_runtime",
    }
    candidates = [
        item["name"]
        for item in method_items
        if item["group"] in move_groups or item["one_line_delegate"]
    ]
    inventory: dict[str, Any] = {
        "target": _relative(PLUGIN_INIT),
        "line_count": len(lines),
        "class_name": "SubtitleManualUpload",
        "method_count": len(method_items),
        "method_groups": {
            group: {
                "count": len(names),
                "methods": names if details else [],
            }
            for group, names in sorted(method_groups.items())
        },
        "one_line_delegate_count": len(one_line_delegates),
        "one_line_delegates": one_line_delegates if details else [],
        "delete_or_move_candidates": candidates if details else [],
        "source_references": references["source_references"] if details else {},
        "test_references": references["test_references"] if details else {},
    }
    if details:
        inventory["methods"] = method_items
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory SubtitleManualUpload __init__.py responsibilities.")
    parser.add_argument("--details", action="store_true", help="include methods and source/test reference details")
    args = parser.parse_args()
    print(json.dumps(build_inventory(details=args.details), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
