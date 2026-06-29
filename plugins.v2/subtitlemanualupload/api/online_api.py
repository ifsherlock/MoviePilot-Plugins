from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.log import logger

from ..config_schema import host_from_url, normalize_provider_ids
from ..online_subtitle import CaptchaRequiredError, build_search_keywords
from .request_helpers import (
    filter_unlocked_target_ids,
    locked_target_ids_from_body,
    online_keywords,
    results_from_body,
    target_ids_from_body,
)
from .upload_api import UploadApi


def download_online_results_to_uploads(
    owner: Any,
    selected_results: List[Dict[str, Any]],
    session_dir: Path,
    upload_session: Optional[Any] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, str]]]:
    upload_session = upload_session or owner._upload_session_service()
    prepared_uploads: List[Dict[str, Any]] = []
    unsupported_files: List[str] = []
    invalid_files: List[Dict[str, str]] = []
    downloads = owner._online_service().download(selected_results)
    for downloaded in downloads:
        result = downloaded.get("result") or {}
        source_name = upload_session.normalize_online_download_name(
            downloaded.get("source_name", ""),
            downloaded.get("content") or b"",
            result,
        )
        try:
            extracted = upload_session.extract_subtitle_files(
                source_name,
                downloaded.get("content") or b"",
                session_dir,
            )
        except ValueError as exc:
            invalid_files.append({"name": source_name, "reason": str(exc)})
            continue
        if not extracted:
            unsupported_files.append(source_name)
            continue
        for item in extracted:
            item["online_source"] = downloaded.get("provider")
            item["online_title"] = result.get("title", "")
            if not item.get("archive_name") and source_name != item.get("source_name"):
                item["archive_name"] = source_name
        prepared_uploads.extend(extracted)
    return prepared_uploads, unsupported_files, invalid_files


class OnlineApi:
    def __init__(self, owner: Any):
        self.owner = owner

    def download_online_results_to_uploads(
        self,
        selected_results: List[Dict[str, Any]],
        session_dir: Path,
        upload_session: Optional[Any] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, str]]]:
        return download_online_results_to_uploads(
            self.owner,
            selected_results,
            session_dir,
            upload_session,
        )

    def online_status(self) -> Dict[str, Any]:
        owner = self.owner
        status = owner._online_service().status()
        status["enabled_providers"] = owner._online_provider_ids
        status["online_engine"] = owner._online_engine
        status["provider_roots"] = owner._online_site_urls
        status["assrt_api_configured"] = bool(owner._assrt_api_key)
        status["assrt_api_host"] = host_from_url(owner._assrt_api_url)
        status["opensubtitles_api_configured"] = bool(owner._opensubtitles_api_key)
        status["opensubtitles_api_host"] = host_from_url(owner._opensubtitles_api_url)
        status["opensubtitles_download_configured"] = bool(
            owner._opensubtitles_username and owner._opensubtitles_password
        )
        status["rate_limit_per_minute"] = owner._online_rate_limit_per_minute
        return owner._ok(status)

    async def online_manual_links(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [owner._target_from_entry(item) for item in target_entries]
        keywords = online_keywords(body, targets, owner._normalize_text, build_search_keywords)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        providers = list(owner._manual_online_provider_ids)
        links = owner._online_service().manual_links(keywords, providers=providers)
        logger.info(
            "[SubtitleManualUpload] 在线字幕手动链接生成 target_count=%s keywords=%s providers=%s",
            len(targets),
            len(keywords),
            ",".join(providers),
        )
        return owner._ok(
            {
                "keywords": keywords,
                "links": links,
            }
        )

    async def online_search(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [owner._target_from_entry(item) for item in target_entries]
        keywords = online_keywords(body, targets, owner._normalize_text, build_search_keywords)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        requested_providers = body.get("providers") if isinstance(body.get("providers"), list) else owner._online_provider_ids
        providers = normalize_provider_ids(
            requested_providers,
            fallback=not isinstance(body.get("providers"), list),
            available_provider_ids=owner._available_online_provider_ids,
            default_provider_ids=owner._default_online_provider_ids,
        )
        if not providers:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕源")
        owner._check_online_rate_limit(providers)
        scope = owner._normalize_text(body.get("scope")) or "auto"
        service = owner._online_service()
        search_result = await run_in_threadpool(
            service.search,
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope=scope,
        )
        manual_links = service.manual_links(keywords, providers=providers)
        logger.info(
            "[SubtitleManualUpload] 在线字幕搜索完成 scope=%s providers=%s targets=%s results=%s",
            scope,
            ",".join(providers),
            len(targets),
            len(search_result.get("results") or []),
        )
        return owner._ok(
            {
                "keywords": keywords,
                "providers": providers,
                "targets": targets,
                "results": search_result.get("results") or [],
                "messages": search_result.get("messages") or [],
                "manual_links": manual_links,
            }
        )

    async def online_search_provider(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [owner._target_from_entry(item) for item in target_entries]
        keywords = online_keywords(body, targets, owner._normalize_text, build_search_keywords)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        provider_id = owner._normalize_text(body.get("provider"))
        providers = normalize_provider_ids(
            [provider_id],
            fallback=False,
            available_provider_ids=owner._available_online_provider_ids,
            default_provider_ids=owner._default_online_provider_ids,
        )
        if not providers:
            raise HTTPException(status_code=400, detail="未知或未启用的在线字幕源")
        owner._check_online_rate_limit(providers)
        scope = owner._normalize_text(body.get("scope")) or "auto"
        service = owner._online_service()
        search_result = await run_in_threadpool(
            service.search,
            keywords=keywords,
            providers=providers,
            targets=targets,
            scope=scope,
        )
        logger.info(
            "[SubtitleManualUpload] 在线字幕单源搜索完成 scope=%s provider=%s targets=%s results=%s",
            scope,
            providers[0],
            len(targets),
            len(search_result.get("results") or []),
        )
        return owner._ok(
            {
                "keywords": keywords,
                "provider": providers[0],
                "providers": providers,
                "targets": targets,
                "results": search_result.get("results") or [],
                "messages": search_result.get("messages") or [],
            }
        )

    async def online_download_preview(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = target_ids_from_body(body, owner._normalize_text)
        locked_ids = locked_target_ids_from_body(body, owner._normalize_text)
        target_ids, locked_skipped = filter_unlocked_target_ids(target_ids, locked_ids, owner._normalize_text)
        if not target_ids:
            if locked_skipped:
                raise HTTPException(status_code=423, detail="选中的目标均已锁定，不能下载写入在线字幕")
            raise HTTPException(status_code=400, detail="请先选择要写入字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        if len(target_entries) != len(set(target_ids)):
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        selected_results = results_from_body(body)
        if not selected_results:
            raise HTTPException(status_code=400, detail="请至少选择一个在线字幕结果")
        submit_ai_translate = bool(body.get("submit_ai_translate"))
        allow_risky_offset = bool(body.get("allow_risky_offset")) if isinstance(body, dict) else False
        if submit_ai_translate:
            online_ai_service = owner._online_ai_service()
            return await run_in_threadpool(
                online_ai_service.submit_online_ai_translate,
                target_entries,
                selected_results,
                allow_risky_offset,
            )
        owner._check_online_rate_limit([item.get("provider") for item in selected_results if isinstance(item, dict)])

        upload_session = owner._upload_session_service()
        session_id = owner._hash_text(f"online|{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = upload_session.get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        try:
            prepared_uploads, unsupported_files, invalid_files = await run_in_threadpool(
                self.download_online_results_to_uploads,
                selected_results,
                session_dir,
                upload_session,
            )
        except CaptchaRequiredError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.warning("[SubtitleManualUpload] 在线字幕自动仿真下载失败 provider=%s message=%s", exc.provider, exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.warning("[SubtitleManualUpload] 在线字幕下载预览失败：%s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.error("[SubtitleManualUpload] 在线字幕下载预览异常: %s", exc)
            raise HTTPException(status_code=500, detail=f"在线字幕下载失败: {exc}") from exc

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{invalid_files[0]['reason']}")
            raise HTTPException(status_code=400, detail="没有解析到可用的在线字幕文件")

        logger.info(
            "[SubtitleManualUpload] 在线字幕下载完成 selected=%s prepared=%s unsupported=%s invalid=%s",
            len(selected_results),
            len(prepared_uploads),
            len(unsupported_files),
            len(invalid_files),
        )
        return UploadApi(owner).build_preview_response_from_uploads(
            session_id=session_id,
            target_ids=target_ids,
            target_entries=target_entries,
            prepared_uploads=prepared_uploads,
            unsupported_files=unsupported_files,
            invalid_files=invalid_files,
            source="online",
        )
