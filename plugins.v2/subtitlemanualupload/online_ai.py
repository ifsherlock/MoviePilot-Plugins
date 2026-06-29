from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .api.online_api import download_online_results_to_uploads
from .online_subtitle import CaptchaRequiredError
from .subtitle_language import auto_subtitle_sort_key, autosub_lang_from_suffix, is_chinese_language_suffix
from .target_resolver import (
    auto_fill_missing_targets as fill_missing_target_ids,
    suggest_target as suggest_target_id,
)


class OnlineAiService:
    def __init__(
        self,
        owner: Any,
        *,
        http_exception: Any,
        logger: Any,
        check_timeline_fixer_dependencies: Any,
    ) -> None:
        self._owner = owner
        self._http_exception = http_exception
        self._logger = logger
        self._check_timeline_fixer_dependencies = check_timeline_fixer_dependencies

    def online_ai_candidate_items(
        self,
        *,
        prepared_uploads: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            if owner._normalize_text(prepared.get("ext")).lower() != ".srt":
                continue
            file_path = Path(prepared["stored_path"])
            raw_bytes = file_path.read_bytes()
            language_profile = owner._detect_language_profile(prepared["source_name"], raw_bytes)
            suffix = language_profile["suffix"]
            if is_chinese_language_suffix(suffix):
                continue
            items.append(
                {
                    "upload_id": prepared["upload_id"],
                    "source_name": prepared["source_name"],
                    "archive_name": prepared.get("archive_name", ""),
                    "ext": prepared["ext"],
                    "target_id": suggest_target_id(prepared, targets, extract_episode_hint=owner._extract_episode_hint),
                    "detected_label": language_profile["label"],
                    "language_suffix": suffix if suffix != "und" else "eng",
                    "online_source": prepared.get("online_source", ""),
                }
            )
        fill_missing_target_ids(items, targets, extract_episode_hint=owner._extract_episode_hint)
        return items

    @staticmethod
    def load_pysubs2_file(path: Path):
        try:
            import pysubs2
        except Exception as exc:
            raise RuntimeError("pysubs2 未安装，无法转换 ASS/SSA 字幕") from exc
        errors: List[str] = []
        for kwargs in (
            {},
            {"encoding": "utf-8-sig"},
            {"encoding": "utf-16"},
            {"encoding": "gb18030"},
            {"encoding": "big5"},
        ):
            try:
                return pysubs2.load(str(path), **kwargs)
            except Exception as exc:
                errors.append(str(exc))
        raise RuntimeError(errors[-1] if errors else f"字幕解析失败: {path.name}")

    def convert_ass_to_ai_srt(
        self,
        *,
        session_dir: Path,
        prepared: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        owner = self._owner
        ext = owner._normalize_text(prepared.get("ext")).lower()
        if ext not in {".ass", ".ssa"} or not getattr(owner, "_auto_ass_to_srt_for_ai", True):
            return None
        source_path = Path(owner._normalize_text(prepared.get("stored_path")))
        if not source_path.is_file():
            return None
        try:
            raw_bytes = source_path.read_bytes()
        except Exception:
            raw_bytes = b""
        profile = owner._detect_language_profile(prepared.get("source_name", ""), raw_bytes)
        if is_chinese_language_suffix(profile.get("suffix")):
            return None
        output_dir = session_dir / "ai_srt_sources"
        output_dir.mkdir(parents=True, exist_ok=True)
        upload_id = f"{prepared.get('upload_id')}-srt"
        output_path = output_dir / f"{upload_id}.srt"
        try:
            subtitles = self.load_pysubs2_file(source_path)
            subtitles.save(str(output_path), format_="srt")
        except Exception as exc:
            self._logger.warning(
                "[SubtitleManualUpload] ASS/SSA 转 AI 临时 SRT 失败 source=%s error=%s",
                prepared.get("source_name"),
                exc,
            )
            return None
        self._logger.info(
            "[SubtitleManualUpload] ASS/SSA 已转为 AI 临时 SRT source=%s output=%s",
            prepared.get("source_name"),
            output_path.name,
        )
        return {
            **prepared,
            "upload_id": upload_id,
            "source_name": f"{Path(prepared.get('source_name') or source_path.name).stem}.srt",
            "stored_path": str(output_path),
            "ext": ".srt",
            "original_source_name": prepared.get("source_name", ""),
            "converted_from_ext": ext,
        }

    def ai_ready_prepared_uploads(
        self,
        *,
        session_dir: Path,
        prepared_uploads: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        owner = self._owner
        ready: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            ext = owner._normalize_text(prepared.get("ext")).lower()
            if ext == ".srt":
                ready.append(prepared)
                continue
            converted = self.convert_ass_to_ai_srt(session_dir=session_dir, prepared=prepared)
            if converted:
                ready.append(converted)
        return ready

    def prepare_online_ai_subtitle_overrides(
        self,
        *,
        session_dir: Path,
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, Any]]]:
        owner = self._owner
        targets = [owner._target_from_entry(item) for item in target_entries]
        ai_ready_uploads = self.ai_ready_prepared_uploads(session_dir=session_dir, prepared_uploads=prepared_uploads)
        candidate_items = self.online_ai_candidate_items(prepared_uploads=ai_ready_uploads, targets=targets)
        if not candidate_items:
            raise self._http_exception(status_code=400, detail="没有解析到可用于 AI 翻译的外语 SRT 字幕")

        target_entry_map = {owner._normalize_text(entry.get("id")): entry for entry in target_entries}
        upload_map = {item["upload_id"]: item for item in ai_ready_uploads}
        converted_source_keys = {
            (
                owner._normalize_text(item.get("target_id")),
                owner._normalize_text(item.get("source_name")),
            )
            for item in candidate_items
            if item.get("converted_from_ext")
        }
        chosen_items: List[Dict[str, Any]] = []
        used_targets = set()
        for item in sorted(
            candidate_items,
            key=lambda candidate: auto_subtitle_sort_key(
                candidate,
                language_priority=list(
                    getattr(owner, "_auto_subtitle_language_priority", None) or owner._default_auto_language_priority
                ),
                format_priority=list(
                    getattr(owner, "_auto_subtitle_format_priority", None) or owner._default_auto_format_priority
                ),
            ),
        ):
            target_id = owner._normalize_text(item.get("target_id"))
            if not target_id or target_id in used_targets or target_id not in target_entry_map:
                continue
            source_name = owner._normalize_text(item.get("source_name"))
            if item.get("ext") == ".srt" and (target_id, source_name) in converted_source_keys:
                continue
            chosen_items.append(item)
            used_targets.add(target_id)

        missing_targets = [
            entry
            for entry in target_entries
            if owner._normalize_text(entry.get("id")) not in used_targets
        ]
        if missing_targets:
            first = missing_targets[0]
            label = first.get("target_label") or first.get("filename") or Path(owner._normalize_text(first.get("path"))).name
            raise self._http_exception(status_code=400, detail=f"没有为 {label} 匹配到可用于 AI 翻译的外语 SRT 字幕")

        operations = owner._subtitle_writer().build_write_operations(chosen_items, upload_map, target_entry_map)
        fixed_dir = session_dir / "ai_timeline_fixed"
        fixed_dir.mkdir(parents=True, exist_ok=True)
        overrides: Dict[str, Dict[str, str]] = {}
        fixed_results: List[Dict[str, Any]] = []
        for operation in operations:
            owner._set_timeline_task(operation, status="pending", message="等待在线字幕智能调轴")
            fixed_path = fixed_dir / f"{operation['upload_info'].get('upload_id')}.srt"
            try:
                owner._set_timeline_task(operation, status="in_progress", message="在线字幕智能调轴处理中")
                timeline_result = owner._run_timeline_fix(
                    video_path=operation["video_path"],
                    subtitle_path=operation["source_path"],
                    output_path=fixed_path,
                    allow_risky_offset=allow_risky_offset,
                )
            except Exception as exc:
                owner._set_timeline_task(operation, status="failed", message=f"在线字幕智能调轴失败: {exc}")
                self._logger.error(
                    "[SubtitleManualUpload] 在线字幕提交 AI 前调轴失败 %s -> %s: %s",
                    operation["upload_info"].get("source_name"),
                    operation["target_entry"].get("target_label"),
                    exc,
                )
                raise self._http_exception(
                    status_code=500,
                    detail=f"在线字幕智能调轴失败: {operation['upload_info'].get('source_name')} - {exc}",
                ) from exc
            if owner._timeline_result_blocks_auto_write(timeline_result):
                owner._set_timeline_task(
                    operation,
                    status="failed",
                    message=f"在线字幕智能调轴低可信，已拒绝提交 AI: {owner._timeline_rejection_message(timeline_result)}",
                    timeline_result=timeline_result,
                )
                raise self._http_exception(
                    status_code=409,
                    detail=(
                        f"在线字幕智能调轴低可信，已拒绝提交 AI: {operation['upload_info'].get('source_name')} - "
                        f"{owner._timeline_rejection_message(timeline_result)}"
                    ),
                )
            owner._set_timeline_task(
                operation,
                status="completed",
                message="在线字幕智能调轴完成" if timeline_result.applied else "在线字幕无需调轴",
                timeline_result=timeline_result,
            )
            video_path = str(operation["video_path"])
            lang = autosub_lang_from_suffix(operation.get("language_suffix"))
            overrides[video_path] = {
                "subtitle_path": str(fixed_path),
                "lang": lang,
                "source_policy": "matched_external",
                "source_name": operation["upload_info"].get("source_name") or fixed_path.name,
                "timeline_fixed": True,
                "overwrite_policy": "new_variant",
            }
            fixed_results.append(
                {
                    "target_id": operation["target_entry"].get("id"),
                    "target_label": owner._target_from_entry(operation["target_entry"]).get("label"),
                    "source_name": operation["upload_info"].get("source_name"),
                    "subtitle_path": str(fixed_path),
                    "language_suffix": operation.get("language_suffix"),
                    "autosub_lang": lang,
                    "timeline": timeline_result.to_dict(),
                }
            )
        return overrides, fixed_results

    def submit_online_ai_translate(
        self,
        target_entries: List[Dict[str, Any]],
        selected_results: List[Dict[str, Any]],
        allow_risky_offset: bool = False,
    ) -> Dict[str, Any]:
        owner = self._owner
        if any((item.get("language_category") or "").lower() == "chinese" for item in selected_results):
            raise self._http_exception(status_code=400, detail="请只选择外语字幕结果后再提交 AI 翻译")
        if any(owner._is_stream_path(entry.get("path")) for entry in target_entries):
            raise self._http_exception(status_code=400, detail="STRM 资源暂不支持在线字幕智能调轴后提交 AI 翻译")
        timeline_status = self._check_timeline_fixer_dependencies()
        if not timeline_status.get("available"):
            missing = [
                key
                for key, value in {
                    "ffmpeg": timeline_status.get("ffmpeg"),
                    "ffprobe": timeline_status.get("ffprobe"),
                    **(timeline_status.get("modules") or {}),
                }.items()
                if not value and key != "webrtcvad"
            ]
            raise self._http_exception(
                status_code=409,
                detail=f"智能调轴不可用，无法提交在线字幕 AI 翻译：缺少 {', '.join(missing) or '依赖'}",
            )
        owner._check_online_rate_limit([item.get("provider") for item in selected_results if isinstance(item, dict)])

        session_id = owner._hash_text(
            f"online-ai|{datetime.now().isoformat()}|{','.join(sorted(owner._normalize_text(item.get('id')) for item in target_entries))}"
        )[:16]
        session_dir = owner.services.upload_session().get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        try:
            prepared_uploads, unsupported_files, invalid_files = download_online_results_to_uploads(
                owner,
                selected_results,
                session_dir,
            )
            if not prepared_uploads:
                if invalid_files:
                    raise self._http_exception(status_code=400, detail=f"没有解析到可用字幕文件，{invalid_files[0]['reason']}")
                raise self._http_exception(status_code=400, detail="没有解析到可用的在线字幕文件")
            subtitle_overrides, fixed_subtitles = self.prepare_online_ai_subtitle_overrides(
                session_dir=session_dir,
                target_entries=target_entries,
                prepared_uploads=prepared_uploads,
                allow_risky_offset=allow_risky_offset,
            )
            ai_result = owner.services.autosub_bridge().submit_autosub_for_entries(
                target_entries,
                subtitle_overrides=subtitle_overrides,
                trigger="manual",
                source_policy="matched_external",
                overwrite_policy="new_variant",
            )
        except self._http_exception:
            raise
        except CaptchaRequiredError as exc:
            self._logger.warning("[SubtitleManualUpload] 在线字幕提交 AI 下载失败 provider=%s message=%s", exc.provider, exc)
            raise self._http_exception(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            self._logger.warning("[SubtitleManualUpload] 在线字幕提交 AI 下载失败：%s", exc)
            raise self._http_exception(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            self._logger.error("[SubtitleManualUpload] 在线字幕提交 AI 异常: %s", exc)
            raise self._http_exception(status_code=500, detail=f"在线字幕提交 AI 失败: {exc}") from exc
        self._logger.info(
            "[SubtitleManualUpload] 在线字幕调轴后提交 AI 翻译 targets=%s selected=%s prepared=%s fixed=%s added=%s skipped=%s failed=%s",
            len(target_entries),
            len(selected_results),
            len(prepared_uploads),
            len(fixed_subtitles),
            len(ai_result.get("added") or []),
            len(ai_result.get("skipped") or []),
            len(ai_result.get("failed") or []),
        )
        return owner._ok(
            {
                "ai_translate": ai_result,
                "targets": ai_result.get("targets") or [owner._target_from_entry(entry) for entry in target_entries],
                "tasks": ai_result.get("tasks"),
                "timeline_tasks": owner.services.timeline_tasks().tasks_for_entries(target_entries),
                "fixed_subtitles": fixed_subtitles,
                "unsupported_files": unsupported_files,
                "invalid_files": invalid_files,
                "timeline_fixer": timeline_status,
            },
            message=(
                f"已提交 {len(ai_result.get('added') or [])} 个 AI 字幕翻译任务，"
                f"在线字幕已先智能调轴 {len(fixed_subtitles)} 个，"
                f"跳过 {len(ai_result.get('skipped') or [])} 个，失败 {len(ai_result.get('failed') or [])} 个。"
            ),
        )
