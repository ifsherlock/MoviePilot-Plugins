from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.log import logger


class OnlineApi:
    def __init__(self, owner: Any):
        self.owner = owner

    def online_status(self) -> Dict[str, Any]:
        owner = self.owner
        status = owner._online_service().status()
        status["enabled_providers"] = owner._online_provider_ids
        status["online_engine"] = owner._online_engine
        status["provider_roots"] = owner._online_site_urls
        status["assrt_api_configured"] = bool(owner._assrt_api_key)
        status["assrt_api_host"] = owner._host_from_url(owner._assrt_api_url)
        status["opensubtitles_api_configured"] = bool(owner._opensubtitles_api_key)
        status["opensubtitles_api_host"] = owner._host_from_url(owner._opensubtitles_api_url)
        status["opensubtitles_download_configured"] = bool(
            owner._opensubtitles_username and owner._opensubtitles_password
        )
        status["rate_limit_per_minute"] = owner._online_rate_limit_per_minute
        return owner._ok(status)

    async def online_manual_links(self, request: Any) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = owner._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [owner._target_from_entry(item) for item in target_entries]
        keywords = owner._online_keywords(body, targets)
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

    async def online_search(self, request: Any) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = owner._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [owner._target_from_entry(item) for item in target_entries]
        keywords = owner._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        requested_providers = body.get("providers") if isinstance(body.get("providers"), list) else owner._online_provider_ids
        providers = owner._normalize_provider_ids(requested_providers, fallback=not isinstance(body.get("providers"), list))
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

    async def online_search_provider(self, request: Any) -> Dict[str, Any]:
        owner = self.owner
        body = await request.json()
        target_ids = owner._target_ids_from_body(body)
        if not target_ids:
            raise HTTPException(status_code=400, detail="请先选择要搜索字幕的本地视频")
        target_entries = list(owner._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新选择资源")
        targets = [owner._target_from_entry(item) for item in target_entries]
        keywords = owner._online_keywords(body, targets)
        if not keywords:
            raise HTTPException(status_code=400, detail="没有可用搜索关键词，请手动输入关键词")
        provider_id = owner._normalize_text(body.get("provider"))
        providers = owner._normalize_provider_ids([provider_id], fallback=False)
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
