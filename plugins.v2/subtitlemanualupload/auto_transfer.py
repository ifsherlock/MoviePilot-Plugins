from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .auto_transfer_processor import AutoTransferProcessor, AutoTransferProcessorCollaborators
from .auto_transfer_queue import AutoTransferQueue
from .auto_transfer_rate_limit import AutoTransferRateLimiter
from .auto_transfer_season import AutoTransferSeasonCache, AutoTransferSeasonCollaborators
from .auto_transfer_write import AutoTransferWriteCollaborators, AutoTransferWriteStrategy
from .matching.subtitle_language import (
    auto_subtitle_sort_key,
    auto_target_has_chinese_subtitle as language_auto_target_has_chinese_subtitle,
    is_chinese_language_suffix,
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
        self._write_strategy = AutoTransferWriteStrategy(
            owner,
            collaborators=AutoTransferWriteCollaborators(
                target_from_entry=lambda entry: self._target_from_entry(entry),
                detect_language_profile=lambda file_name, raw_bytes: self._detect_language_profile(file_name, raw_bytes),
                subtitle_preference_sort_key=self._collaborators.auto_subtitle_sort_key,
                write_operations_to_disk=lambda **kwargs: self._write_operations_to_disk(**kwargs),
                prepare_online_ai_subtitle_overrides=lambda **kwargs: self._prepare_online_ai_subtitle_overrides(**kwargs),
                submit_autosub_for_entries=lambda *args, **kwargs: self._submit_autosub_for_entries(*args, **kwargs),
                select_subtitle_items=lambda prepared_uploads, targets: self.select_auto_subtitle_items(
                    prepared_uploads,
                    targets,
                ),
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
        return self._write_strategy.subtitle_preference_sort_key(item)

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
        return self._write_strategy.prepared_items_for_targets(prepared_uploads, targets)


    def select_auto_subtitle_items(
        self,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._write_strategy.select_subtitle_items(prepared_uploads, targets)


    def auto_write_prepared_uploads_for_entries(
        self,
        *,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        session_dir: Any,
        selected_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._write_strategy.write_prepared_uploads_for_entries(
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            session_dir=session_dir,
            selected_result=selected_result,
        )


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
