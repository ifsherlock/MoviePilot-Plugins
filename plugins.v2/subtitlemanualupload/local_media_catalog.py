from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class LocalMediaCatalog:
    def __init__(
        self,
        owner: Any,
        *,
        transfer_history: Any,
        http_exception: Any,
        logger: Any,
        target_entry_cache: TargetEntryCache,
        threading_module: Any = None,
    ) -> None:
        self._owner = owner
        self._transfer_history = transfer_history
        self._http_exception = http_exception
        self._logger = logger
        self._target_entry_cache = target_entry_cache
        self._threading = threading_module

    def filter_existing_local_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        owner = self._owner
        filtered = [entry for entry in entries if isinstance(entry, dict) and owner._entry_path_is_valid(entry)]
        dropped = len(entries or []) - len(filtered)
        if dropped:
            self._logger.info("[SubtitleManualUpload] 已剔除失效本地视频目标 count=%s", dropped)
        return filtered

    def prune_local_entries_cache(self) -> None:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        entries = [entry for entry in cache.get("entries") or [] if isinstance(entry, dict)]
        if not entries:
            return
        filtered = self.filter_existing_local_entries(entries)
        if len(filtered) == len(entries):
            return
        media_count = len({entry.get("media_key") for entry in filtered if entry.get("media_key")})
        owner._local_entries_cache = {
            **cache,
            "entries": filtered,
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.prune(owner._entry_path_is_valid)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()

    def merge_local_entries_cache(self, entries: List[Dict[str, Any]]) -> None:
        owner = self._owner
        if not entries:
            return
        entries = self.filter_existing_local_entries(entries)
        if not entries:
            return
        cache = owner._local_entries_cache or {}
        existing = self.filter_existing_local_entries(
            [item for item in cache.get("entries") or [] if isinstance(item, dict)]
        )
        by_path = {entry.get("path"): entry for entry in entries if entry.get("path")}
        merged = list(entries)
        for entry in existing:
            if entry.get("path") not in by_path:
                merged.append(entry)
            if len(merged) >= owner._cache_max_entries:
                break
        media_count = len({entry.get("media_key") for entry in merged if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": datetime.now(),
            "entries": merged[: owner._cache_max_entries],
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.remember(entries)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()

    def local_cache_file(self) -> Path:
        return self._owner.get_data_path() / "local_entries_cache.json"

    def persist_local_cache(self) -> None:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        payload = {
            "loaded_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entries": cache.get("entries") or [],
            "media_count": int(cache.get("media_count") or 0),
        }
        try:
            cache_file = self.local_cache_file()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 写入本地资源持久化缓存失败: %s", exc)

    def restore_persisted_local_cache(self) -> bool:
        owner = self._owner
        try:
            cache_file = self.local_cache_file()
            if not cache_file.exists():
                return False
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 读取本地资源持久化缓存失败: %s", exc)
            return False
        entries = payload.get("entries") if isinstance(payload, dict) else []
        loaded_at = owner._cache_loaded_at(payload.get("loaded_at")) if isinstance(payload, dict) else None
        if not loaded_at or not isinstance(entries, list):
            return False
        valid_entries = self.filter_existing_local_entries([entry for entry in entries if isinstance(entry, dict)])
        media_count = len({entry.get("media_key") for entry in valid_entries if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": loaded_at,
            "entries": valid_entries,
            "media_count": media_count,
            "persisted": True,
        }
        self._target_entry_cache.remember(owner._local_entries_cache["entries"])
        self.reset_media_index_cache()
        self._logger.info(
            "[SubtitleManualUpload] 已恢复本地资源持久化缓存 entries=%s medias=%s",
            len(owner._local_entries_cache["entries"]),
            media_count,
        )
        return True

    def load_local_entries(self, *, force: bool = False, allow_stale: bool = False) -> List[Dict[str, Any]]:
        owner = self._owner
        self.prune_local_entries_cache()
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        now = datetime.now()
        if not force and loaded_at and (now - loaded_at).total_seconds() < owner._cache_ttl_seconds:
            return list(cache.get("entries") or [])
        if not force and not loaded_at and self.restore_persisted_local_cache():
            cache = owner._local_entries_cache or {}
            loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
            if loaded_at and (now - loaded_at).total_seconds() < owner._cache_ttl_seconds:
                return list(cache.get("entries") or [])
        if not force and allow_stale and cache.get("entries"):
            self.start_background_cache_refresh()
            return list(cache.get("entries") or [])

        try:
            histories = self._transfer_history.list_by_page(
                db=None,
                page=1,
                count=owner._cache_max_entries,
                status=True,
            ) or []
        except Exception as exc:
            raise self._http_exception(status_code=500, detail=f"读取 MoviePilot 本地整理记录失败: {exc}") from exc

        entries: List[Dict[str, Any]] = []
        seen_paths = set()
        for history in histories:
            entry = owner._build_entry_from_history(history)
            if not entry:
                continue
            if not owner._entry_path_is_valid(entry):
                continue
            path = entry.get("path")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            entries.append(entry)
            if len(entries) >= owner._cache_max_entries:
                break

        media_count = len({entry.get("media_key") for entry in entries if entry.get("media_key")})
        owner._local_entries_cache = {
            "loaded_at": now,
            "entries": entries,
            "media_count": media_count,
            "persisted": False,
        }
        self._target_entry_cache.remember(entries)
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        self.persist_local_cache()
        self._logger.info(
            "[SubtitleManualUpload] 本地资源缓存已刷新 entries=%s medias=%s",
            len(entries),
            media_count,
        )
        return list(entries)

    def start_background_cache_refresh(self) -> None:
        owner = self._owner
        if owner._cache_refreshing:
            return
        owner._cache_refreshing = True
        owner._cache_refresh_started_at = datetime.now().isoformat(timespec="seconds")
        owner._cache_refresh_completed_at = ""
        owner._cache_refresh_error = ""

        def worker():
            try:
                self.load_local_entries(force=True)
                owner._cache_refresh_completed_at = datetime.now().isoformat(timespec="seconds")
                owner._cache_refresh_error = ""
            except Exception as exc:
                owner._cache_refresh_error = str(exc)
                self._logger.warning("[SubtitleManualUpload] 后台刷新本地资源缓存失败: %s", exc)
            finally:
                owner._cache_refreshing = False

        self._threading.Thread(
            target=worker,
            name="SubtitleManualUploadCacheRefresh",
            daemon=True,
        ).start()

    def refresh_local_cache(self) -> List[Dict[str, Any]]:
        owner = self._owner
        self._target_entry_cache.clear()
        self.reset_media_index_cache()
        owner._invalidate_match_history_cache()
        owner._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
        return self.load_local_entries(force=True)

    def cache_status(self) -> Dict[str, Any]:
        owner = self._owner
        cache = owner._local_entries_cache or {}
        loaded_at = owner._cache_loaded_at(cache.get("loaded_at"))
        expires_in = 0
        stale = False
        if loaded_at:
            age = (datetime.now() - loaded_at).total_seconds()
            expires_in = max(0, int(owner._cache_ttl_seconds - age))
            stale = age >= owner._cache_ttl_seconds
        return {
            "ready": bool(loaded_at),
            "persisted": bool(cache.get("persisted")),
            "stale": stale,
            "refreshing": bool(owner._cache_refreshing),
            "refresh_started_at": owner._cache_refresh_started_at,
            "refresh_completed_at": owner._cache_refresh_completed_at,
            "refresh_error": owner._cache_refresh_error,
            "trust_transfer_history_paths": bool(owner._trust_transfer_history_paths),
            "ttl_seconds": owner._cache_ttl_seconds,
            "expires_in": expires_in,
            "updated_at": loaded_at.isoformat(timespec="seconds") if loaded_at else "",
            "entry_count": len(cache.get("entries") or []),
            "media_count": int(cache.get("media_count") or 0),
            "media_index_count": len(owner._media_index_cache or {}),
            "target_cache_count": self._target_entry_cache.count(),
            "max_entries": owner._cache_max_entries,
        }

    def reset_media_index_cache(self) -> None:
        self._owner._media_index_cache = OrderedDict()

    def media_index_cache_key(self, keyword: str, media_type: str) -> str:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword).lower()
        expected_type = owner._media_type_text(media_type) or "all"
        return f"{expected_type}\0{clean_keyword}"

    def media_index_cache_get(self, key: str, entries: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        owner = self._owner
        cache = owner._media_index_cache or OrderedDict()
        item = cache.get(key)
        if not item:
            return None
        loaded_at = owner._cache_loaded_at((owner._local_entries_cache or {}).get("loaded_at"))
        cached_loaded_at = owner._cache_loaded_at(item.get("loaded_at"))
        if cached_loaded_at != loaded_at or int(item.get("entry_count") or 0) != len(entries):
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return [dict(media) for media in item.get("medias") or [] if isinstance(media, dict)]

    def media_index_cache_set(self, key: str, entries: List[Dict[str, Any]], medias: List[Dict[str, Any]]) -> None:
        owner = self._owner
        cache = owner._media_index_cache or OrderedDict()
        cache[key] = {
            "loaded_at": (owner._local_entries_cache or {}).get("loaded_at"),
            "entry_count": len(entries),
            "medias": [dict(media) for media in medias],
        }
        cache.move_to_end(key)
        while len(cache) > owner._media_index_cache_max_keys:
            cache.popitem(last=False)
        owner._media_index_cache = cache

    async def search_media_candidates(
        self,
        keyword: str,
        media_type: str,
        limit: int,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        owner = self._owner
        clean_keyword = owner._normalize_text(keyword)
        expected_type = owner._media_type_text(media_type)
        all_entries = self.load_local_entries(allow_stale=True)
        cache_key = self.media_index_cache_key(clean_keyword, media_type)
        all_candidates = self.media_index_cache_get(cache_key, all_entries)
        if all_candidates is None:
            entries: List[Dict[str, Any]] = []
            for entry in all_entries:
                if expected_type and entry.get("media_type") != expected_type:
                    continue
                if not owner._entry_matches_keyword(entry, clean_keyword):
                    continue
                entries.append(entry)
            all_candidates = self.group_entries_as_media(entries, 0)
            self.media_index_cache_set(cache_key, all_entries, all_candidates)
        total = len(all_candidates)
        candidates = all_candidates[offset: offset + limit]
        return candidates, total

    def group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        owner = self._owner
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
                    "poster_thumb_url": entry.get("poster_thumb_url") or owner._poster_url(entry.get("poster_url"), "w185"),
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
            if entry.get("poster_thumb_url") and not group.get("poster_thumb_url"):
                group["poster_thumb_url"] = entry["poster_thumb_url"]
            if entry.get("date") and entry["date"] > group.get("latest_at", ""):
                group["latest_at"] = entry["date"]

        result = []
        for group in groups.values():
            seasons = owner._merge_seasons(group.pop("_entries"))
            group["seasons"] = seasons
            group["season_count"] = len(seasons)
            result.append(group)
        result.sort(key=lambda item: (item.get("latest_at", ""), item.get("title", "")), reverse=True)
        return result[:limit] if limit else result

    def resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        target_id_list = [owner._normalize_text(item) for item in target_ids if owner._normalize_text(item)]
        target_id_set = set(target_id_list)
        result: Dict[str, Dict[str, Any]] = {}
        for target_id in target_id_list:
            entry = self._target_entry_cache.get(target_id)
            if entry and owner._entry_path_is_valid(entry):
                result[target_id] = entry
            elif entry:
                self._target_entry_cache.discard(target_id)
        missing_ids = target_id_set - set(result.keys())
        if not missing_ids:
            return result

        self._logger.info(
            "[SubtitleManualUpload] 目标缓存未命中，回查本地整理记录 target_ids=%s missing=%s",
            owner._brief_ids(target_id_list),
            len(missing_ids),
        )

        def take_matches(source_entries: List[Dict[str, Any]]) -> None:
            for entry in source_entries:
                target_id = owner._normalize_text(entry.get("id"))
                if target_id not in missing_ids:
                    continue
                self._target_entry_cache.remember([entry])
                result[target_id] = entry
                missing_ids.remove(target_id)
                if not missing_ids:
                    break

        try:
            take_matches(self.load_local_entries(allow_stale=True))
            if missing_ids:
                take_matches(self.load_local_entries(force=True))
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] 回查本地整理记录失败: %s", exc)
            return result

        if missing_ids:
            self._logger.warning(
                "[SubtitleManualUpload] 仍有目标无法解析 target_ids=%s missing=%s",
                owner._brief_ids(target_id_list),
                len(missing_ids),
            )
        return result

    def cached_unlocked_targets(self, locked_ids: set) -> List[Dict[str, Any]]:
        owner = self._owner
        entries: List[Dict[str, Any]] = []
        for target_id, entry in self._target_entry_cache.items():
            if owner._normalize_text(target_id) in locked_ids:
                continue
            if owner._entry_path_is_valid(entry):
                entries.append(entry)
        return entries



__all__ = [name for name in globals() if not name.startswith("__")]
