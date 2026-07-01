from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config.config_schema import normalize_auto_multi_subtitle_mode
from ..matching.subtitle_language import auto_subtitle_sort_key, is_chinese_language_suffix
from ..catalog.target_resolver import (
    auto_fill_missing_targets as fill_missing_target_ids,
    suggest_target as suggest_target_id,
)


@dataclass(frozen=True)
class AutoTransferWriteCollaborators:
    target_from_entry: Callable[[Dict[str, Any]], Dict[str, Any]]
    detect_language_profile: Callable[[str, bytes], Dict[str, Any]]
    write_operations_to_disk: Callable[..., Tuple[List[Dict[str, Any]], int, int]]
    prepare_online_ai_subtitle_overrides: Callable[..., Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]
    submit_autosub_for_entries: Callable[..., Dict[str, Any]]
    select_subtitle_items: Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], List[Dict[str, Any]]]
    subtitle_preference_sort_key: Optional[Callable[[Dict[str, Any]], Tuple[int, int, int, str]]] = None


class AutoTransferWriteStrategy:
    def __init__(self, owner: Any, *, collaborators: AutoTransferWriteCollaborators) -> None:
        self._owner = owner
        self._collaborators = collaborators

    def subtitle_preference_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, int, str]:
        callback = self._collaborators.subtitle_preference_sort_key
        if callback:
            return callback(item)
        owner = self._owner
        return auto_subtitle_sort_key(
            item,
            language_priority=list(getattr(owner, "_auto_subtitle_language_priority", None) or owner._default_auto_language_priority),
            format_priority=list(getattr(owner, "_auto_subtitle_format_priority", None) or owner._default_auto_format_priority),
        )

    def prepared_items_for_targets(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            try:
                raw_bytes = Path(prepared["stored_path"]).read_bytes()
            except Exception:
                raw_bytes = b""
            language_profile = self._collaborators.detect_language_profile(prepared.get("source_name", ""), raw_bytes)
            items.append(
                {
                    "upload_id": prepared["upload_id"],
                    "source_name": prepared.get("source_name", ""),
                    "archive_name": prepared.get("archive_name", ""),
                    "ext": prepared.get("ext") or Path(prepared.get("source_name", "")).suffix.lower() or ".srt",
                    "target_id": suggest_target_id(prepared, targets, extract_episode_hint=owner._extract_episode_hint),
                    "detected_label": language_profile["label"],
                    "language_suffix": language_profile["suffix"],
                    "online_source": prepared.get("online_source", ""),
                }
            )
        fill_missing_target_ids(items, targets, extract_episode_hint=owner._extract_episode_hint)
        return items

    def select_subtitle_items(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        items = self.prepared_items_for_targets(prepared_uploads, targets)
        if not items:
            return []

        mode = normalize_auto_multi_subtitle_mode(getattr(owner, "_auto_multi_subtitle_mode", "best"))
        target_lookup = {item.get("id"): item for item in targets if item.get("id")}
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            target_id = owner._normalize_text(item.get("target_id"))
            if not target_id:
                continue
            grouped.setdefault(target_id, []).append(item)

        selected: List[Dict[str, Any]] = []
        for target_id, group in grouped.items():
            sorted_group = sorted(group, key=self.subtitle_preference_sort_key)
            chinese_group = [item for item in sorted_group if is_chinese_language_suffix(item.get("language_suffix"))]
            foreign_group = [item for item in sorted_group if not is_chinese_language_suffix(item.get("language_suffix"))]
            if mode == "all":
                chosen = [*chinese_group, *foreign_group]
            elif mode == "chinese_all":
                chosen = chinese_group or sorted_group[:1]
            else:
                chosen = sorted_group[:1]

            seen_destinations = set()
            target = target_lookup.get(target_id)
            for item in chosen:
                if target:
                    destination_key = owner._subtitle_writer().build_destination_name(target, item)
                else:
                    destination_key = f"{target_id}|{item.get('source_name')}"
                if destination_key in seen_destinations:
                    continue
                seen_destinations.add(destination_key)
                selected.append(item)
        return selected

    def write_prepared_uploads_for_entries(
        self,
        *,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        session_dir: Path,
        selected_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        targets = [self._collaborators.target_from_entry(entry) for entry in target_entries]
        target_entry_map = {owner._normalize_text(entry.get("id")): entry for entry in target_entries}
        upload_map = {item["upload_id"]: item for item in prepared_uploads if item.get("upload_id")}
        chosen_items = [
            item
            for item in self._collaborators.select_subtitle_items(prepared_uploads, targets)
            if owner._normalize_text(item.get("target_id")) in target_entry_map
        ]
        used_targets = {owner._normalize_text(item.get("target_id")) for item in chosen_items}
        if not chosen_items:
            return {
                "status": "skipped",
                "reason": "整季包未能匹配到当前入库集数",
                "written_by_target": {},
                "prepared_count": len(prepared_uploads),
            }

        missing_target_ids = [
            target_id
            for target_id in target_entry_map
            if target_id not in used_targets
        ]
        chinese_items = [item for item in chosen_items if is_chinese_language_suffix(item.get("language_suffix"))]
        foreign_items = [item for item in chosen_items if not is_chinese_language_suffix(item.get("language_suffix"))]

        written: List[Dict[str, Any]] = []
        simplified_count = 0
        operations: List[Dict[str, Any]] = []
        if chinese_items:
            operations = owner._subtitle_writer().build_write_operations(chinese_items, upload_map, target_entry_map)
            written, _, simplified_count = self._collaborators.write_operations_to_disk(
                session_dir=session_dir,
                operations=operations,
                fix_timeline=True,
            )

        ai_submit_result: Optional[Dict[str, Any]] = None
        fixed_subtitles: List[Dict[str, Any]] = []
        if foreign_items:
            foreign_target_ids = {owner._normalize_text(item.get("target_id")) for item in foreign_items}
            foreign_entries = [entry for target_id, entry in target_entry_map.items() if target_id in foreign_target_ids]
            foreign_upload_ids = {item.get("upload_id") for item in foreign_items}
            foreign_uploads = [item for item in prepared_uploads if item.get("upload_id") in foreign_upload_ids]
            subtitle_overrides, fixed_subtitles = self._collaborators.prepare_online_ai_subtitle_overrides(
                session_dir=session_dir,
                target_entries=foreign_entries,
                prepared_uploads=foreign_uploads,
            )
            ai_submit_result = self._collaborators.submit_autosub_for_entries(
                foreign_entries,
                subtitle_overrides=subtitle_overrides,
                trigger="subtitle_fallback",
                source_policy="matched_external",
                overwrite_policy="new_variant",
            )

        written_by_target: Dict[str, Dict[str, Any]] = {}
        for operation, written_item in zip(operations, written):
            target_id = owner._normalize_text(operation["target_entry"].get("id"))
            written_by_target[target_id] = written_item
        ai_by_target: Dict[str, Dict[str, Any]] = {}
        if ai_submit_result:
            path_to_target_id = {
                owner._normalize_text(entry.get("path")): target_id
                for target_id, entry in target_entry_map.items()
                if owner._normalize_text(entry.get("path"))
            }
            added_target_ids = {
                path_to_target_id.get(owner._normalize_text(item.get("path")))
                for item in ai_submit_result.get("added") or []
                if isinstance(item, dict)
            }
            added_target_ids.discard(None)
            for fixed_item in fixed_subtitles:
                target_id = owner._normalize_text(fixed_item.get("target_id"))
                if target_id and target_id in added_target_ids:
                    ai_by_target[target_id] = fixed_item

        total_completed = len(written_by_target) + len(ai_by_target)
        coverage_complete = not missing_target_ids and total_completed >= len(target_entry_map)
        ai_failed_count = len((ai_submit_result or {}).get("failed") or [])
        ai_skipped_count = len((ai_submit_result or {}).get("skipped") or [])
        reason = "" if coverage_complete else f"整季包覆盖 {total_completed}/{len(target_entry_map)} 集"
        if not ai_by_target and (ai_failed_count or ai_skipped_count):
            reason = f"AI 字幕任务未新增，跳过 {ai_skipped_count} 个，失败 {ai_failed_count} 个"
        return {
            "status": "written" if total_completed else "skipped",
            "reason": reason,
            "result": (selected_result or {}).get("title"),
            "provider": (selected_result or {}).get("provider"),
            "written": written,
            "written_by_target": written_by_target,
            "ai_by_target": ai_by_target,
            "ai_translate": ai_submit_result,
            "fixed_subtitles": fixed_subtitles,
            "written_count": len(written),
            "ai_count": len(ai_by_target),
            "completed_count": total_completed,
            "prepared_count": len(prepared_uploads),
            "simplified_count": simplified_count,
            "missing_target_ids": missing_target_ids,
            "coverage_complete": coverage_complete,
        }
