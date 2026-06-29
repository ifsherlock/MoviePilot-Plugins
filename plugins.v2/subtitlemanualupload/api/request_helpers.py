from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

from fastapi import HTTPException


NormalizeText = Callable[[Any], str]


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
