from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.log import logger


class UploadApi:
    def __init__(self, owner: Any):
        self.owner = owner

    def build_preview_response_from_uploads(
        self,
        *,
        session_id: str,
        target_ids: List[str],
        target_entries: List[Dict[str, Any]],
        prepared_uploads: List[Dict[str, Any]],
        unsupported_files: Optional[List[str]] = None,
        invalid_files: Optional[List[Dict[str, str]]] = None,
        source: str = "upload",
    ) -> Dict[str, Any]:
        owner = self.owner
        unsupported_files = unsupported_files or []
        invalid_files = invalid_files or []
        targets = [owner._target_from_entry(item) for item in target_entries]
        preview_items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            file_path = Path(prepared["stored_path"])
            raw_bytes = file_path.read_bytes()
            language_profile = owner._detect_language_profile(prepared["source_name"], raw_bytes)
            preview_item = {
                "upload_id": prepared["upload_id"],
                "source_name": prepared["source_name"],
                "archive_name": prepared.get("archive_name", ""),
                "ext": prepared["ext"],
                "target_id": owner._suggest_target(prepared, targets),
                "detected_label": language_profile["label"],
                "language_suffix": language_profile["suffix"],
                "online_source": prepared.get("online_source", ""),
            }
            preview_items.append(preview_item)

        owner._auto_fill_missing_targets(preview_items, targets)
        target_lookup = {item["id"]: item for item in targets if item.get("id")}
        for item in preview_items:
            target = target_lookup.get(item.get("target_id"))
            item["output_name"] = owner._build_destination_name(target, item) if target else ""

        session_payload = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_ids": list(target_ids),
            "targets": target_entries,
            "uploads": prepared_uploads,
            "source": source,
        }
        owner._write_session(session_id, session_payload)

        resolved_count = len([item for item in preview_items if item.get("target_id")])
        message = f"已解析 {len(preview_items)} 个字幕文件，自动匹配 {resolved_count} 个。"
        if unsupported_files:
            message += f" 已忽略 {len(unsupported_files)} 个不支持的文件。"
        if invalid_files:
            message += f" 有 {len(invalid_files)} 个压缩包解析失败。"

        logger.info(
            "[SubtitleManualUpload] 预览生成完成 source=%s session=%s subtitles=%s resolved=%s unsupported=%s invalid=%s",
            source,
            session_id,
            len(preview_items),
            resolved_count,
            len(unsupported_files),
            len(invalid_files),
        )
        return owner._ok(
            {
                "session_id": session_id,
                "source": source,
                "targets": targets,
                "items": preview_items,
                "unsupported_files": unsupported_files,
                "invalid_files": invalid_files,
            },
            message=message,
        )

    async def prepare_upload(self, request: Any) -> Dict[str, Any]:
        owner = self.owner
        form = await request.form()
        target_ids_raw = owner._normalize_text(form.get("target_ids"))
        if not target_ids_raw:
            logger.warning("[SubtitleManualUpload] 上传预览失败：未提供目标 target_ids")
            raise HTTPException(status_code=400, detail="请先选择目标电影或剧集")

        try:
            target_ids = json.loads(target_ids_raw)
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标参数格式错误 %s", exc)
            raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc
        if not isinstance(target_ids, list) or not target_ids:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：目标视频已失效 target_ids=%s",
                owner._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        upload_files = [item for item in form.getlist("files") if owner._is_upload_file(item)]
        if not upload_files:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：未收到字幕文件 target_count=%s target_ids=%s",
                len(target_entries),
                owner._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="请至少上传一个字幕文件、ZIP 或 RAR")

        logger.info(
            "[SubtitleManualUpload] 开始上传预览 target_count=%s upload_files=%s target_ids=%s",
            len(target_entries),
            len(upload_files),
            owner._brief_ids(target_ids),
        )

        upload_session = owner._upload_session_service()
        session_id = owner._hash_text(f"{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = upload_session.get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        prepared_uploads: List[Dict[str, Any]] = []
        unsupported_files: List[str] = []
        invalid_files: List[Dict[str, str]] = []
        for upload in upload_files:
            file_name = Path(owner._normalize_text(upload.filename)).name
            if not file_name:
                continue
            raw_bytes = await upload.read()
            try:
                extracted = upload_session.extract_subtitle_files(file_name, raw_bytes, session_dir)
            except ValueError as exc:
                invalid_files.append(
                    {
                        "name": file_name,
                        "reason": str(exc),
                    }
                )
                continue
            if not extracted:
                unsupported_files.append(file_name)
                continue
            prepared_uploads.extend(extracted)

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                first_reason = invalid_files[0]["reason"]
                logger.warning(
                    "[SubtitleManualUpload] 上传预览失败：压缩包解析失败 invalid=%s unsupported=%s reason=%s",
                    len(invalid_files),
                    len(unsupported_files),
                    first_reason,
                )
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{first_reason}")
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：没有可用字幕 unsupported=%s",
                len(unsupported_files),
            )
            raise HTTPException(status_code=400, detail="没有解析到可用的字幕文件，请检查文件格式")

        return self.build_preview_response_from_uploads(
            session_id=session_id,
            target_ids=target_ids,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            unsupported_files=unsupported_files,
            invalid_files=invalid_files,
            source="upload",
        )
