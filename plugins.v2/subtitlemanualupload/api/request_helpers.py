from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

from fastapi import HTTPException


NormalizeText = Callable[[Any], str]
BuildSearchKeywords = Callable[[Dict[str, Any], List[Dict[str, Any]], str], List[str]]


def target_ids_from_body(body: Dict[str, Any], normalize_text: NormalizeText) -> List[str]:
    target_ids = body.get("target_ids") or []
    if isinstance(target_ids, str):
        try:
            target_ids = json.loads(target_ids)
        except Exception:
            target_ids = [target_ids]
    if not isinstance(target_ids, list):
        return []
    return [normalize_text(item) for item in target_ids if normalize_text(item)]


def locked_target_ids_from_body(body: Dict[str, Any], normalize_text: NormalizeText) -> Set[str]:
    locked_ids = body.get("locked_target_ids") or []
    if isinstance(locked_ids, str):
        try:
            locked_ids = json.loads(locked_ids)
        except Exception:
            locked_ids = [locked_ids]
    if not isinstance(locked_ids, list):
        return set()
    return {normalize_text(item) for item in locked_ids if normalize_text(item)}


def filter_unlocked_target_ids(
    target_ids: Iterable[str],
    locked_ids: Set[str],
    normalize_text: NormalizeText,
) -> Tuple[List[str], List[Dict[str, str]]]:
    unlocked: List[str] = []
    skipped: List[Dict[str, str]] = []
    for target_id in target_ids:
        clean_id = normalize_text(target_id)
        if not clean_id:
            continue
        if clean_id in locked_ids:
            skipped.append({"target_id": clean_id, "reason": "目标已锁定"})
            continue
        unlocked.append(clean_id)
    return unlocked, skipped


def ensure_target_not_locked(target_id: str, locked_ids: Set[str], normalize_text: NormalizeText) -> None:
    if normalize_text(target_id) in locked_ids:
        raise HTTPException(status_code=423, detail="目标已锁定，不能执行该操作")


def results_from_body(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = body.get("results") or body.get("selected_results") or []
    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def online_keywords(
    body: Dict[str, Any],
    targets: List[Dict[str, Any]],
    normalize_text: NormalizeText,
    build_search_keywords: BuildSearchKeywords,
) -> List[str]:
    manual_keyword = normalize_text(body.get("keyword"))
    media = body.get("media") if isinstance(body.get("media"), dict) else {}
    scope = normalize_text(body.get("scope")) or "auto"
    keywords = build_search_keywords(media, targets, scope)
    if manual_keyword:
        keywords = [manual_keyword, *[item for item in keywords if item != manual_keyword]]
    return keywords[:8]


def enrich_targets_with_media(targets: List[Dict[str, Any]], media: Any) -> List[Dict[str, Any]]:
    """Carry canonical title metadata into ID-resolved targets used by online search."""
    if not isinstance(media, dict):
        return targets
    title_fields = (
        "original_title",
        "original_name",
        "en_title",
        "title_en",
        "name_en",
        "english_title",
    )
    metadata_fields = (
        "original_language",
        "origin_country",
        "production_countries",
    )
    enriched: List[Dict[str, Any]] = []
    for target in targets or []:
        if not isinstance(target, dict):
            continue
        item = dict(target)
        for field in (*title_fields, *metadata_fields):
            if not item.get(field) and media.get(field):
                item[field] = media[field]

        aliases: List[Any] = []
        existing_aliases = item.get("tmdb_aliases")
        if isinstance(existing_aliases, list):
            aliases.extend(existing_aliases)
        elif existing_aliases:
            aliases.append(existing_aliases)
        for field in title_fields + ("tmdb_aliases", "aliases", "alternative_titles", "translations"):
            value = media.get(field)
            if isinstance(value, list):
                aliases.extend(value)
            elif value:
                aliases.append(value)
        if aliases:
            item["tmdb_aliases"] = aliases
        enriched.append(item)
    return enriched
