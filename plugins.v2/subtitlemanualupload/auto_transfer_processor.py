from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .online_subtitle import build_search_keywords


@dataclass(frozen=True)
class AutoTransferProcessorCollaborators:
    target_from_entry: Callable[[Dict[str, Any]], Dict[str, Any]]
    auto_target_has_chinese_subtitle: Callable[[Dict[str, Any], Dict[str, Any]], bool]
    chinese_transfer_media_evidence: Callable[[Dict[str, Any]], Tuple[bool, str]]
    media_for_transfer_entry: Callable[[Dict[str, Any]], Dict[str, Any]]
    search_providers: Callable[[], List[str]]
    search_keywords_for_entry: Callable[[Dict[str, Any], Dict[str, Any]], List[str]]
    check_online_rate_limit: Callable[[Iterable[str]], None]
    wait_online_rate_limit: Callable[..., None]
    online_service: Callable[[], Any]
    online_download_name: Callable[[str, bytes, Dict[str, Any]], str]
    extract_subtitle_files: Callable[[str, bytes, Path], List[Dict[str, Any]]]
    write_prepared_uploads_for_entries: Callable[..., Dict[str, Any]]
    submit_autosub_for_entries: Callable[..., Dict[str, Any]]
    call_search_write_subtitle: Callable[..., Dict[str, Any]]
    submit_ai_for_entry: Callable[[Dict[str, Any], Dict[str, Any], str], Dict[str, Any]]


class AutoTransferProcessor:
    def __init__(
        self,
        owner: Any,
        *,
        logger: Any,
        http_exception: Any,
        collaborators: AutoTransferProcessorCollaborators,
    ) -> None:
        self._owner = owner
        self._logger = logger
        self._http_exception = http_exception
        self._collaborators = collaborators

    def search_keywords_for_entry(self, entry: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
        owner = self._owner
        media = self._collaborators.media_for_transfer_entry(entry)
        owner._apply_tmdb_detail(target, media)
        return build_search_keywords(media, [target], "auto")[:8]

    def search_write_subtitle(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        target = target or self._collaborators.target_from_entry(entry)
        providers = self._collaborators.search_providers()
        if not providers:
            return {"status": "skipped", "reason": "未配置可用 API 字幕源", "target": target.get("label")}
        keywords = self._collaborators.search_keywords_for_entry(entry, target)
        if not keywords:
            return {"status": "skipped", "reason": "没有可用搜索关键词", "target": target.get("label")}

        if queue_rate_limited:
            self._collaborators.wait_online_rate_limit(providers, task_ids=task_ids)
        else:
            self._collaborators.check_online_rate_limit(providers)
        service = self._collaborators.online_service()
        search_result = service.search(
            keywords=keywords,
            providers=providers,
            targets=[target],
            scope="auto",
        )
        candidates = [
            item
            for item in search_result.get("results") or []
            if item.get("downloadable") is not False and owner._safe_int(item.get("score"), 0) >= owner._auto_search_min_score
        ]
        if not candidates:
            return {
                "status": "skipped",
                "reason": "没有高置信可下载结果",
                "target": target.get("label"),
                "results": len(search_result.get("results") or []),
                "search_results": len(search_result.get("results") or []),
            }

        last_reason = ""
        for selected in candidates[:5]:
            session_id = owner._hash_text(f"auto|{datetime.now().isoformat()}|{entry.get('id')}")[:16]
            session_dir = owner.services.upload_session().get_session_root() / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            try:
                downloads = service.download([selected])
                prepared_uploads: List[Dict[str, Any]] = []
                for downloaded in downloads:
                    result = downloaded.get("result") or {}
                    source_name = self._collaborators.online_download_name(
                        downloaded.get("source_name", ""),
                        downloaded.get("content") or b"",
                        result,
                    )
                    try:
                        extracted = self._collaborators.extract_subtitle_files(
                            source_name,
                            downloaded.get("content") or b"",
                            session_dir,
                        )
                    except ValueError as exc:
                        last_reason = f"下载包解析失败: {owner._normalize_text(exc)}"
                        self._logger.warning(
                            "[SubtitleManualUpload] 自动字幕候选解析失败 target=%s provider=%s result=%s error=%s",
                            target.get("label"),
                            selected.get("provider"),
                            selected.get("title"),
                            exc,
                        )
                        continue
                    if not extracted:
                        last_reason = "下载包未解析到字幕文件"
                        self._logger.info(
                            "[SubtitleManualUpload] 自动字幕候选无字幕文件，尝试下一结果 target=%s provider=%s result=%s",
                            target.get("label"),
                            selected.get("provider"),
                            selected.get("title"),
                        )
                        continue
                    for item in extracted:
                        item["online_source"] = downloaded.get("provider")
                        item["online_title"] = result.get("title", "")
                        if not item.get("archive_name") and source_name != item.get("source_name"):
                            item["archive_name"] = source_name
                    prepared_uploads.extend(extracted)
                if not prepared_uploads:
                    continue
                write_result = self._collaborators.write_prepared_uploads_for_entries(
                    target_entries=[entry],
                    prepared_uploads=prepared_uploads,
                    session_dir=session_dir,
                    selected_result=selected,
                )
                if write_result.get("status") == "written":
                    ai_count = owner._safe_int(write_result.get("ai_count"), 0)
                    written_count = owner._safe_int(write_result.get("written_count"), 0)
                    if ai_count and not written_count:
                        ai_submit = write_result.get("ai_translate") or {}
                        ai_result = {
                            "status": "ai_submitted" if ai_submit.get("added") else "skipped",
                            "reason": "自动入库外语字幕已智能调轴后提交 AI 翻译",
                            "target": target.get("label"),
                            "ai": {
                                "added": len(ai_submit.get("added") or []),
                                "skipped": len(ai_submit.get("skipped") or []),
                                "failed": len(ai_submit.get("failed") or []),
                            },
                            "tasks": ai_submit.get("tasks"),
                        }
                        return {
                            "status": ai_result["status"],
                            "target": target.get("label"),
                            "result": selected.get("title"),
                            "fixed_subtitles": write_result.get("fixed_subtitles") or [],
                            "candidate_count": len(candidates),
                            "search_results": len(search_result.get("results") or []),
                            "ai": ai_result,
                        }
                    return {
                        "status": "written",
                        "target": target.get("label"),
                        "result": selected.get("title"),
                        "written": write_result.get("written") or [],
                        "written_by_target": write_result.get("written_by_target") or {},
                        "ai_by_target": write_result.get("ai_by_target") or {},
                        "ai_translate": write_result.get("ai_translate"),
                        "fixed_subtitles": write_result.get("fixed_subtitles") or [],
                        "written_count": written_count,
                        "ai_count": ai_count,
                        "simplified_count": write_result.get("simplified_count", 0),
                        "candidate_count": len(candidates),
                        "search_results": len(search_result.get("results") or []),
                    }
                last_reason = write_result.get("reason") or "下载包字幕未按偏好匹配"
            except Exception as exc:
                last_reason = f"自动下载在线字幕失败: {owner._normalize_text(exc)}"
                self._logger.warning(
                    "[SubtitleManualUpload] %s target=%s provider=%s result=%s",
                    last_reason,
                    target.get("label"),
                    selected.get("provider"),
                    selected.get("title"),
                )
            finally:
                shutil.rmtree(session_dir, ignore_errors=True)

        return {
            "status": "skipped",
            "reason": last_reason or "高置信结果未解析到可用字幕文件",
            "target": target.get("label"),
            "candidate_count": len(candidates),
            "search_results": len(search_result.get("results") or []),
        }

    def search_and_write_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        target = self._collaborators.target_from_entry(entry)
        if self._collaborators.auto_target_has_chinese_subtitle(entry, target):
            return {"status": "skipped", "reason": "目标已有中文字幕", "target": target.get("label")}
        if target.get("has_subtitle"):
            self._logger.info(
                "[SubtitleManualUpload] 目标已有外挂字幕但未确认中文，继续自动匹配/AI target=%s",
                target.get("label"),
            )
        return self.search_write_subtitle(entry, target)

    def submit_ai_for_entry(
        self,
        entry: Dict[str, Any],
        target: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        owner = self._owner
        target = target or self._collaborators.target_from_entry(entry)
        try:
            result = self._collaborators.submit_autosub_for_entries(
                [entry],
                trigger="subtitle_fallback",
                source_policy="auto",
                overwrite_policy="skip",
            )
        except self._http_exception as exc:
            return {
                "status": "failed",
                "reason": owner._normalize_text(getattr(exc, "detail", "")) or str(exc),
                "target": target.get("label"),
                "ai_reason": reason,
            }
        except Exception as exc:
            self._logger.warning("[SubtitleManualUpload] 入库自动字幕提交 AI 失败 target=%s error=%s", target.get("label"), exc)
            return {
                "status": "failed",
                "reason": f"AI 字幕任务提交失败: {exc}",
                "target": target.get("label"),
                "ai_reason": reason,
            }

        added = result.get("added") or []
        skipped = result.get("skipped") or []
        failed = result.get("failed") or []
        if added:
            status = "ai_submitted"
            message = f"已提交 AI 字幕任务 {len(added)} 个"
        elif failed:
            status = "failed"
            message = (
                owner._normalize_text((failed[0] or {}).get("reason"))
                if isinstance(failed[0], dict)
                else "AI 字幕任务提交失败"
            )
        elif skipped:
            status = "skipped"
            first = skipped[0] if isinstance(skipped[0], dict) else {}
            message = owner._normalize_text(first.get("reason")) or "AI 字幕任务已跳过"
        else:
            status = "skipped"
            message = "AI 插件未返回新增任务"
        return {
            "status": status,
            "reason": message,
            "target": target.get("label"),
            "ai_reason": reason,
            "ai": {
                "added": len(added),
                "skipped": len(skipped),
                "failed": len(failed),
            },
        }

    def process_entry(
        self,
        entry: Dict[str, Any],
        *,
        queue_rate_limited: bool = False,
        task_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        owner = self._owner
        target = self._collaborators.target_from_entry(entry)
        strategy = owner._normalize_auto_transfer_subtitle_strategy(owner._auto_transfer_subtitle_strategy)
        base = {"strategy": strategy, "target": target.get("label")}

        if self._collaborators.auto_target_has_chinese_subtitle(entry, target):
            return {**base, "status": "skipped", "reason": "目标已有中文字幕"}
        if target.get("has_subtitle"):
            self._logger.info(
                "[SubtitleManualUpload] 目标已有外挂字幕但未确认中文，继续自动匹配/AI target=%s",
                target.get("label"),
            )

        if owner._auto_skip_chinese_media_on_transfer:
            is_chinese, evidence = self._collaborators.chinese_transfer_media_evidence(entry)
            if is_chinese:
                return {**base, "status": "skipped", "reason": f"中文资源自动跳过：{evidence}"}
            self._logger.info(
                "[SubtitleManualUpload] 入库自动字幕中文识别未跳过 target=%s evidence=%s",
                target.get("label"),
                evidence,
            )

        if strategy == "ai_source_only":
            return {**base, **self._collaborators.submit_ai_for_entry(entry, target, "策略 ai_source_only")}

        search_result = self._collaborators.call_search_write_subtitle(
            entry,
            target,
            queue_rate_limited=queue_rate_limited,
            task_ids=task_ids,
        )
        if strategy == "online_source_only" or search_result.get("status") == "written":
            return {**base, **search_result}

        ai_result = self._collaborators.submit_ai_for_entry(entry, target, "搜索无单一高置信结果后兜底")
        return {**base, **ai_result, "search": search_result}
