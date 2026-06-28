from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


NormalizeText = Callable[[Any], str]
NormalizeLanguageSuffix = Callable[[Any], str]
BuildDestinationName = Callable[[Dict[str, Any], Dict[str, Any]], str]


def build_destination_name(
    target_entry: Dict[str, Any],
    subtitle_info: Dict[str, Any],
    *,
    normalize_text: NormalizeText,
    normalize_language_suffix: NormalizeLanguageSuffix,
) -> str:
    basename = normalize_text(target_entry.get("basename")) or "subtitle"
    language_suffix = normalize_language_suffix(subtitle_info.get("language_suffix"))
    ext = normalize_text(subtitle_info.get("ext")) or ".srt"
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"{basename}.{language_suffix}{ext.lower()}"


def build_write_operations(
    items: List[Dict[str, Any]],
    upload_map: Dict[str, Dict[str, Any]],
    target_entries: Dict[str, Dict[str, Any]],
    *,
    normalize_text: NormalizeText,
    normalize_language_suffix: NormalizeLanguageSuffix,
    build_destination_name_func: BuildDestinationName,
    http_exception: Any,
) -> List[Dict[str, Any]]:
    destination_keys = set()
    operations: List[Dict[str, Any]] = []

    for item in items:
        upload_id = normalize_text(item.get("upload_id"))
        target_id = normalize_text(item.get("target_id"))
        if not upload_id or not target_id:
            raise http_exception(status_code=400, detail="存在未完成目标选择的字幕项")

        upload_info = upload_map.get(upload_id)
        target_entry = target_entries.get(target_id)
        if not upload_info or not target_entry:
            raise http_exception(status_code=400, detail="上传项或目标视频不存在，请重新上传")

        storage = normalize_text(target_entry.get("storage")) or "local"
        if storage != "local":
            raise http_exception(status_code=400, detail=f"当前仅支持写入本地媒体文件，目标存储为: {storage}")

        video_path = Path(target_entry["path"])
        if not video_path.exists():
            raise http_exception(status_code=400, detail=f"目标视频不存在: {video_path}")

        source_path = Path(upload_info["stored_path"])
        if not source_path.exists():
            raise http_exception(status_code=400, detail=f"上传缓存文件不存在: {upload_info.get('source_name')}")

        item_ext = normalize_text(item.get("ext")) or upload_info.get("ext") or ".srt"
        item_suffix = normalize_language_suffix(item.get("language_suffix"))
        destination_name = build_destination_name_func(
            target_entry,
            {
                "ext": item_ext,
                "language_suffix": item_suffix,
            },
        )
        unique_key = f"{target_id}|{destination_name}"
        if unique_key in destination_keys:
            raise http_exception(status_code=400, detail=f"重复映射到同一个目标字幕名: {destination_name}")
        destination_keys.add(unique_key)

        operations.append(
            {
                "upload_info": upload_info,
                "target_entry": target_entry,
                "video_path": video_path,
                "source_path": source_path,
                "language_suffix": item_suffix,
                "destination_name": destination_name,
                "destination_path": video_path.parent / destination_name,
            }
        )
    return operations


def timeline_result_blocks_auto_write(timeline_result: Any) -> bool:
    if not timeline_result or not timeline_result.enabled:
        return False
    if timeline_result.base == "strm":
        return False
    confidence = (timeline_result.confidence or "").lower()
    risks = set(timeline_result.risk_flags or [])
    if confidence in {"low", "rejected"} and not (timeline_result.applied and risks <= {"offset_over_120s"}):
        return True
    blocking = {
        "low_score",
        "weak_score_margin",
        "ambiguous_peak",
        "boundary_offset",
        "unstable_subtitle_activity",
        "audio_subtitle_activity_unstable",
        "audio_base_activity_unstable",
        "audio_scale_factor",
        "unusual_scale_factor",
        "rms_low_precision",
        "offset_over_configured_max",
        "local_alignment_unstable",
    }
    if risks & blocking:
        return True
    if timeline_result.reason == "offset below threshold":
        return False
    return False


def timeline_rejection_message(timeline_result: Any) -> str:
    flags = ",".join(timeline_result.risk_flags or []) or "-"
    return (
        f"confidence={timeline_result.confidence or '-'} "
        f"offset={timeline_result.offset_seconds:.3f}s "
        f"score={timeline_result.score:.3f} "
        f"margin={timeline_result.score_margin:.3f} "
        f"risks={flags}"
    )


def subtitle_backup_path(subtitle_path: Path) -> Path:
    return subtitle_path.with_name(f"{subtitle_path.name}.mp-timeline-bk")


def backup_subtitle_if_needed(subtitle_path: Path) -> Optional[Path]:
    if not subtitle_path.exists():
        return None
    backup_path = subtitle_backup_path(subtitle_path)
    if not backup_path.exists():
        shutil.copyfile(subtitle_path, backup_path)
    return backup_path


class SubtitleWriter:
    def __init__(
        self,
        owner: Any,
        *,
        http_exception: Any,
        logger: Any,
        timeline_result_type: Any,
        timeline_fix_func: Callable[..., Any],
        convert_subtitle_file_to_simplified: Callable[[Path, Path], bool],
    ) -> None:
        self._owner = owner
        self._http_exception = http_exception
        self._logger = logger
        self._timeline_result_type = timeline_result_type
        self._timeline_fix_func = timeline_fix_func
        self._convert_subtitle_file_to_simplified = convert_subtitle_file_to_simplified

    def maybe_convert_operation_to_simplified(self, operation: Dict[str, Any], output_dir: Path) -> None:
        owner = self._owner
        operation["simplified_result"] = {"enabled": False, "converted": False}
        if not owner._traditional_to_simplified:
            return
        if not owner._is_chinese_language_suffix(operation.get("language_suffix")):
            return
        source_path = Path(operation["write_source_path"])
        if source_path.suffix.lower() not in owner._subtitle_exts:
            return
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{operation['upload_info'].get('upload_id')}{source_path.suffix.lower()}"
        try:
            converted = self._convert_subtitle_file_to_simplified(source_path, output_path)
        except Exception as exc:
            self._logger.error(
                "[SubtitleManualUpload] 繁转简失败 %s -> %s: %s",
                operation["upload_info"].get("source_name"),
                operation["destination_name"],
                exc,
            )
            raise self._http_exception(
                status_code=500,
                detail=f"繁转简失败: {operation['upload_info'].get('source_name')} - {exc}",
            ) from exc
        operation["write_source_path"] = output_path
        operation["simplified_result"] = {"enabled": True, "converted": converted}

    def write_operations_to_disk(
        self,
        *,
        session_dir: Path,
        operations: List[Dict[str, Any]],
        fix_timeline: bool = False,
        allow_risky_offset: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        owner = self._owner
        fixed_dir = session_dir / "timeline_fixed"
        simplified_dir = session_dir / "simplified"
        for operation in operations:
            operation["write_source_path"] = operation["source_path"]
            operation["timeline_result"] = None
            operation["simplified_result"] = {"enabled": False, "converted": False}
            if fix_timeline:
                owner._set_timeline_task(operation, status="pending", message="等待智能调轴")
                fixed_dir.mkdir(parents=True, exist_ok=True)
                fixed_source_path = fixed_dir / f"{operation['upload_info'].get('upload_id')}{operation['source_path'].suffix}"
                if operation["video_path"].suffix.lower() in owner._stream_exts:
                    shutil.copyfile(operation["source_path"], fixed_source_path)
                    operation["write_source_path"] = fixed_source_path
                    operation["timeline_result"] = self._timeline_result_type(
                        enabled=True,
                        applied=False,
                        reason="stream target skipped",
                        base="strm",
                        offset_seconds=0.0,
                        scale_factor=1.0,
                        score=0.0,
                    )
                    owner._set_timeline_task(
                        operation,
                        status="skipped",
                        message="STRM 资源跳过智能调轴",
                        timeline_result=operation["timeline_result"],
                    )
                    self._logger.info(
                        "[SubtitleManualUpload] STRM 目标跳过智能调轴 %s -> %s",
                        operation["upload_info"].get("source_name"),
                        operation["destination_name"],
                    )
                    self.maybe_convert_operation_to_simplified(operation, simplified_dir)
                    continue
                try:
                    owner._set_timeline_task(operation, status="in_progress", message="智能调轴处理中")
                    timeline_result = owner._run_timeline_fix(
                        video_path=operation["video_path"],
                        subtitle_path=operation["source_path"],
                        output_path=fixed_source_path,
                        allow_risky_offset=allow_risky_offset,
                    )
                except Exception as exc:
                    owner._set_timeline_task(operation, status="failed", message=f"智能调轴失败: {exc}")
                    self._logger.error(
                        "[SubtitleManualUpload] 智能调轴失败 %s -> %s: %s",
                        operation["upload_info"].get("source_name"),
                        operation["destination_name"],
                        exc,
                    )
                    raise self._http_exception(
                        status_code=500,
                        detail=f"智能调轴失败: {operation['upload_info'].get('source_name')} - {exc}",
                    ) from exc
                if owner._timeline_result_blocks_auto_write(timeline_result):
                    owner._set_timeline_task(
                        operation,
                        status="failed",
                        message=f"智能调轴低可信，已拒绝写入: {owner._timeline_rejection_message(timeline_result)}",
                        timeline_result=timeline_result,
                    )
                    raise self._http_exception(
                        status_code=409,
                        detail=(
                            f"智能调轴低可信，已拒绝写入: {operation['upload_info'].get('source_name')} - "
                            f"{owner._timeline_rejection_message(timeline_result)}"
                        ),
                    )
                operation["write_source_path"] = fixed_source_path
                operation["timeline_result"] = timeline_result
                owner._set_timeline_task(
                    operation,
                    status="completed",
                    message="智能调轴完成" if timeline_result.applied else "智能调轴未调整",
                    timeline_result=timeline_result,
                )
            self.maybe_convert_operation_to_simplified(operation, simplified_dir)

        written_results = []
        for operation in operations:
            destination_path = operation["destination_path"]
            temp_path = destination_path.with_name(f"{destination_path.name}.mp-uploading")
            if temp_path.exists():
                temp_path.unlink()

            backup_path = backup_subtitle_if_needed(destination_path)
            shutil.copyfile(operation["write_source_path"], temp_path)
            temp_path.replace(destination_path)
            timeline_result = operation.get("timeline_result")
            written_results.append(
                {
                    "source_name": operation["upload_info"].get("source_name"),
                    "archive_name": operation["upload_info"].get("archive_name"),
                    "target_label": owner._target_from_entry(operation["target_entry"]).get("label"),
                    "output_name": operation["destination_name"],
                    "output_path": str(destination_path),
                    "backup_path": str(backup_path) if backup_path else "",
                    "backup_available": bool(backup_path and backup_path.exists()),
                    "timeline": timeline_result.to_dict() if timeline_result else {"enabled": False},
                    "simplified": operation.get("simplified_result") or {"enabled": False, "converted": False},
                }
            )

        touched_videos: Dict[str, Path] = {
            str(operation["video_path"]): operation["video_path"]
            for operation in operations
        }
        for video_path in touched_videos.values():
            owner._remove_ext_marks(video_path)

        fixed_count = len(
            [
                item
                for item in written_results
                if item.get("timeline", {}).get("enabled") and item.get("timeline", {}).get("applied")
            ]
        )
        simplified_count = len(
            [
                item
                for item in written_results
                if item.get("simplified", {}).get("enabled") and item.get("simplified", {}).get("converted")
            ]
        )
        owner._invalidate_match_history_cache()
        return written_results, fixed_count, simplified_count

    def run_timeline_fix(
        self,
        *,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        allow_risky_offset: Optional[bool] = None,
    ) -> Any:
        owner = self._owner
        effective_allow_risky_offset = (
            owner._timeline_allow_risky_offset if allow_risky_offset is None else bool(allow_risky_offset)
        )
        try:
            return self._timeline_fix_func(
                video_path=video_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                max_offset_seconds=owner._timeline_max_offset_seconds,
                min_offset_seconds=owner._timeline_min_offset_seconds,
                cache_dir=owner._timeline_cache_dir(),
                allow_risky_offset=effective_allow_risky_offset,
                vad_mode=owner._timeline_vad_mode,
            )
        except TypeError as exc:
            if "unexpected keyword" not in str(exc):
                raise
            return self._timeline_fix_func(video_path, subtitle_path, output_path)

    def existing_timeline_operations(
        self,
        requested_items: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        owner = self._owner
        target_ids = [owner._normalize_text(item.get("target_id")) for item in requested_items if isinstance(item, dict)]
        target_entries = owner._resolve_targets(target_ids)
        operations: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        seen = set()
        for request_item in requested_items:
            if not isinstance(request_item, dict):
                continue
            target_id = owner._normalize_text(request_item.get("target_id"))
            if not target_id:
                skipped.append({"reason": "缺少 target_id"})
                continue
            entry = target_entries.get(target_id)
            if not entry:
                skipped.append({"target_id": target_id, "reason": "目标视频已失效"})
                continue
            target = owner._target_from_entry(entry)
            if target.get("is_stream"):
                skipped.append({"target_id": target_id, "reason": "STRM 资源不启用智能调轴"})
                continue
            subtitles = target.get("subtitles") or []
            expected_path = owner._normalize_text(request_item.get("subtitle_path"))
            if expected_path:
                subtitles = [
                    item for item in subtitles
                    if owner._normalize_text(item.get("path")) == expected_path
                ]
            if not subtitles:
                skipped.append({"target_id": target_id, "reason": "没有可调轴的外挂字幕"})
                continue
            for subtitle in subtitles:
                subtitle_path = Path(owner._normalize_text(subtitle.get("path")))
                key = f"{target_id}|{subtitle_path}"
                if key in seen:
                    continue
                seen.add(key)
                if not subtitle_path.is_file():
                    skipped.append({"target_id": target_id, "subtitle_path": str(subtitle_path), "reason": "外挂字幕不存在"})
                    continue
                try:
                    raw_bytes = subtitle_path.read_bytes()
                except Exception:
                    raw_bytes = b""
                language_profile = owner._detect_language_profile(subtitle_path.name, raw_bytes)
                upload_id = owner._hash_text(f"existing-timeline|{target_id}|{subtitle_path}|{subtitle_path.stat().st_mtime_ns}")[:16]
                upload_info = {
                    "upload_id": upload_id,
                    "source_name": subtitle_path.name,
                    "archive_name": "",
                    "stored_path": str(subtitle_path),
                    "ext": subtitle_path.suffix.lower(),
                }
                item = {
                    "upload_id": upload_id,
                    "target_id": target_id,
                    "ext": subtitle_path.suffix.lower(),
                    "language_suffix": language_profile["suffix"],
                }
                try:
                    operation = owner._build_write_operations(
                        [item],
                        {upload_id: upload_info},
                        {target_id: entry},
                    )[0]
                except self._http_exception as exc:
                    failed.append(
                        {
                            "target_id": target_id,
                            "subtitle_path": str(subtitle_path),
                            "reason": owner._normalize_text(getattr(exc, "detail", "")) or str(exc),
                        }
                    )
                    continue
                operations.append(operation)
        return operations, skipped, failed

    def run_existing_timeline_fix(
        self,
        session_dir: Path,
        operations: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> None:
        owner = self._owner
        try:
            owner._write_operations_to_disk(
                session_dir=session_dir,
                operations=operations,
                fix_timeline=True,
                allow_risky_offset=allow_risky_offset,
            )
            self._logger.info("[SubtitleManualUpload] 匹配历史智能调轴完成 count=%s", len(operations))
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] 匹配历史智能调轴失败: %s", exc)
            for operation in operations:
                target_id = owner._normalize_text((operation.get("target_entry") or {}).get("id"))
                task = owner._timeline_task_for_target_id(target_id)
                if task and task.get("status") in {"completed", "skipped", "failed"}:
                    continue
                owner._set_timeline_task(operation, status="failed", message=f"历史字幕智能调轴失败: {exc}")
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)
            owner._invalidate_match_history_cache()
