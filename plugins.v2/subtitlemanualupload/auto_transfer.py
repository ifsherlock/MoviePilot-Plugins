from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .config_schema import normalize_auto_multi_subtitle_mode
from .auto_transfer_processor import AutoTransferProcessor, AutoTransferProcessorCollaborators
from .auto_transfer_queue import AutoTransferQueue
from .auto_transfer_rate_limit import AutoTransferRateLimiter
from .auto_transfer_season import AutoTransferSeasonCache, AutoTransferSeasonCollaborators
from .subtitle_language import (
    auto_subtitle_sort_key,
    auto_target_has_chinese_subtitle as language_auto_target_has_chinese_subtitle,
    is_chinese_language_suffix,
)
from .target_resolver import (
    auto_fill_missing_targets as fill_missing_target_ids,
    suggest_target as suggest_target_id,
)


@dataclass(frozen=True)
class AutoTransferCollaborators:
    online_service_factory: Optional[Callable[[], Any]] = None
    target_from_entry: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    extract_subtitle_files: Optional[Callable[..., List[Dict[str, Any]]]] = None
    write_operations_to_disk: Optional[Callable[..., Tuple[List[Dict[str, Any]], int, int]]] = None
    submit_autosub_for_entries: Optional[Callable[..., Dict[str, Any]]] = None
    prepare_online_ai_subtitle_overrides: Optional[Callable[..., Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]] = None
    auto_media_for_entry: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    is_chinese_transfer_media: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None
    normalize_online_download_name: Optional[Callable[..., str]] = None
    detect_language_profile: Optional[Callable[[str, bytes], Dict[str, Any]]] = None
    auto_subtitle_sort_key: Optional[Callable[[Dict[str, Any]], Tuple[int, int, int, str]]] = None
    auto_target_has_chinese_subtitle: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None
    check_online_rate_limit: Optional[Callable[[Iterable[str]], None]] = None
    wait_online_rate_limit: Optional[Callable[..., None]] = None
    logger: Any = None
    threading_module: Any = None
    time_module: Any = None
    http_exception: Any = None

    @classmethod
    def from_owner(
        cls,
        owner: Any,
        *,
        logger: Any,
        threading_module: Any,
        time_module: Any,
        http_exception: Any,
    ) -> "AutoTransferCollaborators":
        return cls(
            online_service_factory=owner._online_service,
            target_from_entry=owner._target_from_entry,
            extract_subtitle_files=lambda upload_name, raw_bytes, session_dir: owner._upload_session_service_for_path(
                session_dir.parent
            ).extract_subtitle_files(upload_name, raw_bytes, session_dir),
            write_operations_to_disk=lambda **kwargs: owner._subtitle_writer().write_operations_to_disk(**kwargs),
            submit_autosub_for_entries=lambda *args, **kwargs: owner._autosub_bridge().submit_autosub_for_entries(
                *args,
                **kwargs,
            ),
            prepare_online_ai_subtitle_overrides=lambda *args, **kwargs: owner._online_ai_service().prepare_online_ai_subtitle_overrides(
                *args,
                **kwargs,
            ),
            auto_media_for_entry=lambda entry: owner._media_metadata_service().auto_media_for_entry(entry),
            is_chinese_transfer_media=lambda entry: owner._media_metadata_service().is_chinese_transfer_media(entry),
            normalize_online_download_name=lambda name, content, result: owner._upload_session_service().normalize_online_download_name(
                name,
                content,
                result,
            ),
            detect_language_profile=owner._detect_language_profile,
            auto_subtitle_sort_key=lambda item: auto_subtitle_sort_key(
                item,
                language_priority=list(getattr(owner, "_auto_subtitle_language_priority", None) or owner._default_auto_language_priority),
                format_priority=list(getattr(owner, "_auto_subtitle_format_priority", None) or owner._default_auto_format_priority),
            ),
            auto_target_has_chinese_subtitle=lambda entry, target: language_auto_target_has_chinese_subtitle(
                entry,
                target,
                subtitle_inventory=owner._subtitle_inventory(),
                is_chinese_language_suffix_func=is_chinese_language_suffix,
            ),
            check_online_rate_limit=owner._check_online_rate_limit,
            logger=logger,
            threading_module=threading_module,
            time_module=time_module,
            http_exception=http_exception,
        )


class AutoTransferService:
    def __init__(
        self,
        owner: Any,
        *,
        logger: Any,
        threading_module: Any,
        time_module: Any,
        http_exception: Any,
        collaborators: Optional[AutoTransferCollaborators] = None,
    ) -> None:
        self._owner = owner
        self._collaborators = collaborators or AutoTransferCollaborators()
        self._logger = self._collaborators.logger or logger
        self._threading = self._collaborators.threading_module or threading_module
        self._time = self._collaborators.time_module or time_module
        self._http_exception = self._collaborators.http_exception or http_exception
        self._queue = AutoTransferQueue(
            owner,
            time_module=self._time,
            ensure_worker=lambda: self.ensure_transfer_auto_worker(),
            rate_status=self.auto_transfer_rate_status,
        )
        self._rate_limiter = AutoTransferRateLimiter(owner, time_module=self._time)
        self._processor = AutoTransferProcessor(
            owner,
            logger=self._logger,
            http_exception=self._http_exception,
            collaborators=AutoTransferProcessorCollaborators(
                target_from_entry=lambda entry: self._target_from_entry(entry),
                auto_target_has_chinese_subtitle=lambda entry, target: self._auto_target_has_chinese_subtitle(entry, target),
                chinese_transfer_media_evidence=lambda entry: self._chinese_transfer_media_evidence(entry),
                media_for_transfer_entry=lambda entry: self._media_for_transfer_entry(entry),
                search_providers=lambda: self.auto_search_providers(),
                search_keywords_for_entry=lambda entry, target: self.auto_search_keywords_for_entry(entry, target),
                check_online_rate_limit=lambda providers: self._check_online_rate_limit(providers),
                wait_online_rate_limit=lambda providers, task_ids=None: self._wait_online_rate_limit(providers, task_ids=task_ids),
                online_service=lambda: self._online_service(),
                online_download_name=lambda name, content, result: self._online_download_name(name, content, result),
                extract_subtitle_files=lambda upload_name, raw_bytes, session_dir: self._extract_subtitle_files(
                    upload_name,
                    raw_bytes,
                    session_dir,
                ),
                write_prepared_uploads_for_entries=lambda **kwargs: self.auto_write_prepared_uploads_for_entries(**kwargs),
                submit_autosub_for_entries=lambda *args, **kwargs: self._submit_autosub_for_entries(*args, **kwargs),
                call_search_write_subtitle=lambda *args, **kwargs: self._call_auto_search_write_subtitle(*args, **kwargs),
                submit_ai_for_entry=lambda entry, target, reason: self.auto_submit_ai_for_entry(entry, target, reason),
            ),
        )
        self._season_cache = AutoTransferSeasonCache(
            owner,
            logger=self._logger,
            collaborators=AutoTransferSeasonCollaborators(
                target_from_entry=lambda entry: self._target_from_entry(entry),
                auto_target_has_chinese_subtitle=lambda entry, target: self._auto_target_has_chinese_subtitle(entry, target),
                chinese_transfer_media_evidence=lambda entry: self._chinese_transfer_media_evidence(entry),
                media_for_transfer_entry=lambda entry: self._media_for_transfer_entry(entry),
                task_result_key=lambda entry: self._auto_task_result_key(entry),
                search_providers=lambda: self.auto_search_providers(),
                wait_online_rate_limit=lambda providers, task_ids=None: self._wait_online_rate_limit(providers, task_ids=task_ids),
                online_service=lambda: self._online_service(),
                online_download_name=lambda name, content, result: self._online_download_name(name, content, result),
                extract_subtitle_files=lambda upload_name, raw_bytes, session_dir: self._extract_subtitle_files(
                    upload_name,
                    raw_bytes,
                    session_dir,
                ),
                write_prepared_uploads_for_entries=lambda **kwargs: self.auto_write_prepared_uploads_for_entries(**kwargs),
                store_cache=lambda entries, prepared_uploads, selected_result: self.store_auto_season_package_cache(
                    entries,
                    prepared_uploads,
                    selected_result,
                ),
                load_cache=lambda entry: self.load_auto_season_package_cache(entry),
                write_from_cache=lambda entries: self.auto_write_from_season_cache(entries),
                search_write_package=lambda entries, task_ids=None: self.auto_search_write_season_package(
                    entries,
                    task_ids=task_ids,
                ),
                process_entry=lambda entry, **kwargs: self.auto_process_transfer_entry(entry, **kwargs),
            ),
        )

    def _callback(self, name: str, fallback_name: str) -> Callable[..., Any]:
        callback = getattr(self._collaborators, name)
        return callback or getattr(self._owner, fallback_name)

    def _online_service(self) -> Any:
        return self._callback("online_service_factory", "_online_service")()

    def _target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return self._callback("target_from_entry", "_target_from_entry")(entry)

    def _check_online_rate_limit(self, providers: Iterable[str]) -> None:
        self._callback("check_online_rate_limit", "_check_online_rate_limit")(providers)

    def _wait_online_rate_limit(self, providers: Iterable[str], task_ids: Optional[List[str]] = None) -> None:
        if self._collaborators.wait_online_rate_limit:
            self._collaborators.wait_online_rate_limit(providers, task_ids=task_ids)
            return
        self.auto_wait_online_rate_limit(providers, task_ids=task_ids)

    def _online_download_name(self, name: str, content: bytes, result: Dict[str, Any]) -> str:
        callback = self._collaborators.normalize_online_download_name
        if callback:
            return callback(name, content, result)
        return self._owner._upload_session_service().normalize_online_download_name(name, content, result)

    def _extract_subtitle_files(self, upload_name: str, raw_bytes: bytes, session_dir: Path) -> List[Dict[str, Any]]:
        return self._callback("extract_subtitle_files", "_extract_subtitle_files")(upload_name, raw_bytes, session_dir)

    def _auto_target_has_chinese_subtitle(self, entry: Dict[str, Any], target: Dict[str, Any]) -> bool:
        return self._callback("auto_target_has_chinese_subtitle", "_auto_target_has_chinese_subtitle")(entry, target)

    def _media_for_transfer_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        callback = self._collaborators.auto_media_for_entry
        if callback:
            return callback(entry)
        return self._owner._media_metadata_service().auto_media_for_entry(entry)

    def _chinese_transfer_media_evidence(self, entry: Dict[str, Any]) -> Tuple[bool, str]:
        callback = self._collaborators.is_chinese_transfer_media
        if callback:
            return callback(entry)
        return self._owner._media_metadata_service().is_chinese_transfer_media(entry)

    def _auto_search_write_subtitle(self, entry: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        return self.auto_search_write_subtitle(entry, target)

    def _call_auto_search_write_subtitle(
        self,
        entry: Dict[str, Any],
        target: Dict[str, Any],
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            return self.auto_search_write_subtitle(
                entry,
                target,
                queue_rate_limited=queue_rate_limited,
                task_ids=task_ids,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return self._auto_search_write_subtitle(entry, target)

    def _submit_autosub_for_entries(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._callback("submit_autosub_for_entries", "_submit_autosub_for_entries")(*args, **kwargs)

    def _detect_language_profile(self, file_name: str, raw_bytes: bytes) -> Dict[str, Any]:
        return self._callback("detect_language_profile", "_detect_language_profile")(file_name, raw_bytes)

    def _subtitle_preference_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, int, str]:
        callback = self._collaborators.auto_subtitle_sort_key
        if callback:
            return callback(item)
        owner = self._owner
        return auto_subtitle_sort_key(
            item,
            language_priority=list(getattr(owner, "_auto_subtitle_language_priority", None) or owner._default_auto_language_priority),
            format_priority=list(getattr(owner, "_auto_subtitle_format_priority", None) or owner._default_auto_format_priority),
        )

    def _write_operations_to_disk(self, **kwargs: Any) -> Tuple[List[Dict[str, Any]], int, int]:
        return self._callback("write_operations_to_disk", "_write_operations_to_disk")(**kwargs)

    def _prepare_online_ai_subtitle_overrides(self, *args: Any, **kwargs: Any):
        return self._callback("prepare_online_ai_subtitle_overrides", "_prepare_online_ai_subtitle_overrides")(*args, **kwargs)

    def _auto_task_result_key(self, entry: Dict[str, Any]) -> str:
        owner = self._owner
        return owner._normalize_text(entry.get("id")) or self.auto_transfer_entry_key(entry)

    def _auto_season_cache_key(self, entry: Dict[str, Any]) -> str:
        return self._season_cache.cache_key(entry)

    def _auto_season_cache_dir(self, cache_key: str) -> Path:
        return self._season_cache.cache_dir(cache_key)

    def stop(self) -> None:
        self._queue.stop()

    def transfer_auto_key(self, entry: Dict[str, Any]) -> str:
        return self._queue.transfer_key(entry)

    def claim_transfer_auto_entries(self, entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        return self._queue.claim_entries(entries)

    def auto_transfer_entry_key(self, entry: Dict[str, Any]) -> str:
        return self._queue.entry_key(entry)

    def auto_transfer_group_key(self, entry: Dict[str, Any]) -> str:
        return self._queue.group_key(entry)

    def trim_auto_transfer_tasks_locked(self) -> None:
        self._queue.trim_locked()

    def enqueue_transfer_auto_entries(self, entries: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self._queue.enqueue_entries(entries)

    def handle_transfer_complete(self, event: Any) -> Dict[str, Any]:
        owner = self._owner
        event_data = getattr(event, "event_data", None) or {}
        if not isinstance(event_data, dict):
            return {"entries": [], "queued": 0, "skipped": 0}
        entries = owner.services.target_resolver().entries_from_transfer_event(event_data)
        if not entries:
            self._logger.info("[SubtitleManualUpload] 入库事件未解析到本地视频目标，跳过自动字幕搜索")
            return {"entries": [], "queued": 0, "skipped": 0}
        owner.services.local_media_catalog().merge_local_entries_cache(entries)
        queued, skipped = self.enqueue_transfer_auto_entries(entries)
        if skipped:
            self._logger.info("[SubtitleManualUpload] 入库自动字幕处理去重跳过重复目标 count=%s", skipped)
        if queued:
            self._logger.info("[SubtitleManualUpload] 入库自动字幕任务已入队 count=%s", queued)
        return {"entries": entries, "queued": queued, "skipped": skipped}

    def ensure_transfer_auto_worker(self) -> None:
        owner = self._owner
        with owner._transfer_auto_lock:
            if getattr(owner, "_auto_transfer_stopping", False):
                return
            worker = owner._auto_transfer_worker
            if worker and worker.is_alive():
                return
            worker = self._threading.Thread(
                target=self.auto_transfer_queue_loop,
                name="SubtitleManualUploadTransferQueue",
                daemon=True,
            )
            owner._auto_transfer_worker = worker
            worker.start()

    def update_auto_transfer_task(self, task_id: str, **updates: Any) -> None:
        self._queue.update_task(task_id, **updates)

    def claim_next_auto_transfer_batch(self) -> Tuple[List[Dict[str, Any]], float]:
        return self._queue.claim_next_batch()

    def auto_wait_online_rate_limit(self, providers: Iterable[str], task_ids: Optional[List[str]] = None) -> None:
        self._rate_limiter.wait(providers, task_ids=task_ids)

    def auto_transfer_rate_status(self) -> Dict[str, Any]:
        return self._rate_limiter.status(self.auto_search_providers())

    def auto_transfer_queue_summary(self) -> Dict[str, Any]:
        return self._queue.summary()

    def auto_transfer_queue_snapshot(self, limit: int = 100) -> Dict[str, Any]:
        return self._queue.snapshot(limit=limit)

    def auto_transfer_queue_loop(self) -> None:
        owner = self._owner
        while True:
            batch, wait_seconds = owner._claim_next_auto_transfer_batch()
            if wait_seconds < 0:
                return
            if not batch:
                self._time.sleep(max(0.2, wait_seconds))
                continue
            try:
                owner._process_transfer_auto_task_batch(batch)
            except Exception as exc:
                self._logger.warning("[SubtitleManualUpload] 入库自动字幕队列批次失败: %s", exc)
                for task in batch:
                    owner._update_auto_transfer_task(
                        task["id"],
                        status="failed",
                        message=f"入库自动字幕处理异常: {exc}",
                    )

    def auto_search_keywords_for_entry(self, entry: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
        return self._processor.search_keywords_for_entry(entry, target)


    def auto_search_providers(self) -> List[str]:
        owner = self._owner
        return [item for item in (owner._online_provider_ids or []) if item in {"assrt", "opensubtitles"}]


    def auto_search_write_subtitle(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._processor.search_write_subtitle(
            entry,
            target,
            queue_rate_limited=queue_rate_limited,
            task_ids=task_ids,
        )


    def auto_search_and_write_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return self._processor.search_and_write_entry(entry)


    def auto_submit_ai_for_entry(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        return self._processor.submit_ai_for_entry(entry, target, reason)


    def auto_process_transfer_entry(
        self,
        entry: Dict[str, Any],
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._processor.process_entry(
            entry,
            queue_rate_limited=queue_rate_limited,
            task_ids=task_ids,
        )


    def auto_prepared_items_for_targets(
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
            language_profile = self._detect_language_profile(prepared.get("source_name", ""), raw_bytes)
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


    def select_auto_subtitle_items(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        items = self.auto_prepared_items_for_targets(prepared_uploads, targets)
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
            sorted_group = sorted(group, key=self._subtitle_preference_sort_key)
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


    def auto_write_prepared_uploads_for_entries(
        self,
        *,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        session_dir: Path,
        selected_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        targets = [self._target_from_entry(entry) for entry in target_entries]
        target_entry_map = {owner._normalize_text(entry.get("id")): entry for entry in target_entries}
        upload_map = {item["upload_id"]: item for item in prepared_uploads if item.get("upload_id")}
        chosen_items = [
            item
            for item in owner._select_auto_subtitle_items(prepared_uploads, targets)
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
            written, _, simplified_count = self._write_operations_to_disk(
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
            subtitle_overrides, fixed_subtitles = self._prepare_online_ai_subtitle_overrides(
                session_dir=session_dir,
                target_entries=foreign_entries,
                prepared_uploads=foreign_uploads,
            )
            ai_submit_result = self._submit_autosub_for_entries(
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


    def store_auto_season_package_cache(
        self,
        entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        selected_result: Dict[str, Any],
    ) -> None:
        self._season_cache.store_cache(entries, prepared_uploads, selected_result)


    def load_auto_season_package_cache(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._season_cache.load_cache(entry)


    def auto_write_from_season_cache(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._season_cache.write_from_cache(entries)


    def auto_search_write_season_package(
        self,
        entries: List[Dict[str, Any]],
        *,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._season_cache.search_write_package(entries, task_ids=task_ids)


    def auto_process_transfer_group(self, entries: List[Dict[str, Any]], task_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        return self._season_cache.process_group(entries, task_ids=task_ids)


    def process_transfer_auto_task_batch(self, tasks: List[Dict[str, Any]]) -> None:
        owner = self._owner
        entries = [task.get("entry") for task in tasks if isinstance(task.get("entry"), dict)]
        task_ids = [task["id"] for task in tasks if task.get("id")]
        is_tv_batch = (
            bool(entries)
            and all(owner._normalize_text(entry.get("media_type")) == "tv" for entry in entries)
            and len({self.auto_transfer_group_key(entry) for entry in entries}) == 1
        )
        if is_tv_batch:
            results = self.auto_process_transfer_group(entries, task_ids=task_ids)
        else:
            results = {
                self._auto_task_result_key(entry): self.auto_process_transfer_entry(
                    entry,
                    queue_rate_limited=True,
                    task_ids=task_ids,
                )
                for entry in entries
            }
        for task in tasks:
            entry = task.get("entry") or {}
            result = results.get(self._auto_task_result_key(entry)) or {
                "status": "failed",
                "reason": "入库自动字幕任务没有返回结果",
            }
            status = result.get("status") if result.get("status") in {"completed", "written", "skipped", "failed", "ai_submitted"} else "completed"
            public_status = "completed" if status in {"written", "ai_submitted"} else status
            owner._update_auto_transfer_task(
                task["id"],
                status=public_status,
                message=result.get("reason") or result.get("status") or public_status,
                result=result,
            )
            self._logger.info(
                "[SubtitleManualUpload] 入库自动字幕处理完成 target=%s strategy=%s status=%s reason=%s",
                result.get("target") or entry.get("target_label") or entry.get("filename"),
                result.get("strategy"),
                result.get("status"),
                result.get("reason", ""),
            )

    def process_transfer_auto_subtitles(self, entries: List[Dict[str, Any]]) -> None:
        owner = self._owner
        for entry in entries:
            try:
                result = self.auto_process_transfer_entry(entry)
                self._logger.info(
                    "[SubtitleManualUpload] 入库自动字幕处理完成 target=%s strategy=%s status=%s reason=%s",
                    result.get("target"),
                    result.get("strategy"),
                    result.get("status"),
                    result.get("reason", ""),
                )
            except Exception as exc:
                self._logger.warning(
                    "[SubtitleManualUpload] 入库自动字幕处理失败 target=%s error=%s",
                    entry.get("target_label") or entry.get("filename"),
                    exc,
                )
