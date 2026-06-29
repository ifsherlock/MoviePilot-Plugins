from __future__ import annotations

from typing import Any, Dict

from fastapi import Request
from app.log import logger


class CatalogApi:
    def __init__(self, owner: Any):
        self.owner = owner

    async def search(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        keyword = owner._normalize_text(request.query_params.get("keyword"))
        media_type = owner._normalize_text(request.query_params.get("media_type")) or "all"
        page = max(owner._safe_int(request.query_params.get("page"), 1), 1)
        page_size = min(
            max(owner._safe_int(request.query_params.get("page_size") or request.query_params.get("limit"), 20), 1),
            80,
        )
        medias, total = await owner._local_media_catalog().search_media_candidates(
            keyword=keyword,
            media_type=media_type,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        logger.info(
            "[SubtitleManualUpload] 本地资源搜索完成 keyword=%s media_type=%s page=%s size=%s result=%s total=%s",
            keyword or "<recent>",
            media_type,
            page,
            page_size,
            len(medias),
            total,
        )
        return owner._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": page * page_size < total,
                "medias": medias,
            }
        )

    def match_history(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        keyword = owner._normalize_text(request.query_params.get("keyword"))
        media_type = owner._normalize_text(request.query_params.get("media_type")) or "all"
        page = max(owner._safe_int(request.query_params.get("page"), 1), 1)
        page_size = min(max(owner._safe_int(request.query_params.get("page_size"), 20), 5), 80)
        items = owner._match_history_items(keyword=keyword, media_type=media_type)
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return owner._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": end < total,
                "items": items[start:end],
            }
        )

    def targets(self, request: Request) -> Dict[str, Any]:
        owner = self.owner
        media_type = owner._normalize_text(request.query_params.get("media_type"))
        tmdb_id = owner._normalize_text(request.query_params.get("tmdb_id"))
        douban_id = owner._normalize_text(request.query_params.get("douban_id"))
        title = owner._normalize_text(request.query_params.get("title"))
        year = owner._normalize_text(request.query_params.get("year"))
        season = owner._normalize_text(request.query_params.get("season"))
        result = owner._target_resolver().targets_for_media(
            media_type=media_type,
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            title=title,
            year=year,
            season=season,
        )
        logger.info(
            "[SubtitleManualUpload] 本地目标读取完成 media=%s year=%s type=%s season=%s targets=%s all_targets=%s",
            title or tmdb_id or douban_id,
            year or "-",
            media_type or "-",
            result.get("selected_season"),
            result.get("target_count"),
            result.get("all_target_count"),
        )
        return owner._ok(result)
