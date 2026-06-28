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

    def clear_subtitles(
        self,
        target_ids: List[str],
        target_entries: Dict[str, Dict[str, Any]],
        locked_skipped: List[Dict[str, str]],
    ) -> Tuple[Dict[str, Any], str]:
        owner = self._owner
        deleted: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = [*locked_skipped]
        visited_paths = set()
        for target_id in target_ids:
            clean_target_id = owner._normalize_text(target_id)
            target_entry = target_entries.get(clean_target_id)
            if not target_entry:
                failed.append({"target_id": clean_target_id, "reason": "目标视频已失效"})
                continue
            if owner._normalize_text(target_entry.get("storage")) not in {"", "local"}:
                failed.append({"target_id": clean_target_id, "reason": "当前仅支持清空本地媒体文件的外挂字幕"})
                continue

            target_label = owner._target_from_entry(target_entry).get("label")
            for subtitle in owner._subtitle_files_for_target(target_entry):
                subtitle_path = Path(subtitle["path"])
                path_key = str(subtitle_path)
                if path_key in visited_paths:
                    continue
                visited_paths.add(path_key)
                try:
                    subtitle_path.unlink()
                    deleted.append(
                        {
                            "target_id": clean_target_id,
                            "target_label": target_label,
                            "name": subtitle_path.name,
                            "path": path_key,
                        }
                    )
                except Exception as exc:
                    self._logger.error(
                        "[SubtitleManualUpload] 删除外挂字幕失败 target=%s subtitle=%s error=%s",
                        clean_target_id[:8],
                        subtitle_path.name,
                        exc,
                    )
                    failed.append({"target_id": clean_target_id, "reason": f"{subtitle_path.name}: {exc}"})

        message = f"已删除 {len(deleted)} 个外挂字幕"
        if failed:
            message += f"，{len(failed)} 个目标处理失败"
        if deleted:
            owner._invalidate_match_history_cache()
        return {"count": len(deleted), "deleted": deleted, "failed": failed}, message

    def delete_subtitle(
        self,
        *,
        target_id: str,
        target_entry: Dict[str, Any],
        subtitle_path_raw: str = "",
        subtitle_name: str = "",
    ) -> Tuple[Dict[str, Any], str]:
        owner = self._owner
        if owner._normalize_text(target_entry.get("storage")) not in {"", "local"}:
            raise self._http_exception(status_code=400, detail="当前仅支持删除本地媒体文件的外挂字幕")

        target_path = self._subtitle_path_from_target(
            target_entry,
            subtitle_path_raw=subtitle_path_raw,
            subtitle_name=subtitle_name,
        )
        try:
            target_path.unlink()
        except FileNotFoundError:
            raise self._http_exception(status_code=404, detail="字幕文件已经不存在") from None
        except Exception as exc:
            self._logger.error(
                "[SubtitleManualUpload] 删除单个外挂字幕失败 target=%s subtitle=%s error=%s",
                target_id[:8],
                target_path.name,
                exc,
            )
            raise self._http_exception(status_code=500, detail=f"删除字幕失败: {exc}") from exc

        owner._invalidate_match_history_cache()
        return (
            {
                "deleted": {
                    "target_id": target_id,
                    "target_label": owner._target_from_entry(target_entry).get("label"),
                    "name": target_path.name,
                    "path": str(target_path),
                },
            },
            f"已删除外挂字幕：{target_path.name}",
        )

    def restore_subtitle_backup(
        self,
        *,
        target_id: str,
        target_entry: Dict[str, Any],
        subtitle_path_raw: str = "",
        subtitle_name: str = "",
    ) -> Tuple[Dict[str, Any], str]:
        owner = self._owner
        if owner._normalize_text(target_entry.get("storage")) not in {"", "local"}:
            raise self._http_exception(status_code=400, detail="当前仅支持恢复本地媒体文件的外挂字幕")

        target_path = self._subtitle_path_from_target(
            target_entry,
            subtitle_path_raw=subtitle_path_raw,
            subtitle_name=subtitle_name,
        )
        backup_path = subtitle_backup_path(target_path)
        if not backup_path.exists():
            raise self._http_exception(status_code=404, detail="没有找到调轴前备份")
        temp_path = target_path.with_name(f"{target_path.name}.mp-restore")
        try:
            shutil.copyfile(backup_path, temp_path)
            temp_path.replace(target_path)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            self._logger.error(
                "[SubtitleManualUpload] 恢复字幕备份失败 target=%s subtitle=%s error=%s",
                target_id[:8],
                target_path.name,
                exc,
            )
            raise self._http_exception(status_code=500, detail=f"恢复字幕备份失败: {exc}") from exc

        owner._invalidate_match_history_cache()
        return (
            {
                "restored": {
                    "target_id": target_id,
                    "target_label": owner._target_from_entry(target_entry).get("label"),
                    "name": target_path.name,
                    "path": str(target_path),
                    "backup_path": str(backup_path),
                },
            },
            f"已恢复调轴前字幕：{target_path.name}",
        )

    def _subtitle_path_from_target(
        self,
        target_entry: Dict[str, Any],
        *,
        subtitle_path_raw: str = "",
        subtitle_name: str = "",
    ) -> Path:
        owner = self._owner
        allowed_subtitles = owner._subtitle_files_for_target(target_entry)
        for subtitle in allowed_subtitles:
            subtitle_path = Path(subtitle["path"])
            if subtitle_path_raw and str(subtitle_path) == subtitle_path_raw:
                return subtitle_path
            if subtitle_name and subtitle_path.name == subtitle_name:
                return subtitle_path
        raise self._http_exception(status_code=400, detail="字幕不属于当前目标或已经被删除")
