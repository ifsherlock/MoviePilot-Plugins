from __future__ import annotations

from ..clients import *  # noqa: F401,F403
from ..keyword_builder import *  # noqa: F401,F403
from ..language import *  # noqa: F401,F403
from ..matcher import *  # noqa: F401,F403
from ..models import *  # noqa: F401,F403
from ..shared import *  # noqa: F401,F403
from .base import BaseSubtitleProvider

class AssrtProvider(BaseSubtitleProvider):
    provider_id = "assrt"
    display_name = "射手网(伪)"
    default_root_url = DEFAULT_PROVIDER_ROOTS["assrt"]

    def __init__(
        self,
        fetcher: OnlinePageClient,
        root_url: str = "",
        *,
        api_key: str = "",
        api_url: str = DEFAULT_ASSRT_API_URL,
    ):
        super().__init__(fetcher, root_url=root_url)
        self.api_key = str(api_key or "").strip()
        self.api_url = normalize_root_url(api_url, DEFAULT_ASSRT_API_URL)

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["api_configured"] = bool(self.api_key)
        status["api_host"] = _host(self.api_url)
        status["message"] = "已配置 API Key，使用官方 API 搜索" if self.api_key else "未配置 API Key；不参与自动搜索"
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/sub/?{urlencode({'searchword': keyword})}"

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if self.api_key:
            return self._search_api(keyword, targets)
        raise ValueError("射手网(伪) 未配置 API Key，已跳过自动搜索")

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        result_id = str(result.get("result_id") or "").strip()
        download_url = str(result.get("download_url") or "").strip()
        if self.api_key and (result_id.isdigit() or download_url.startswith("assrt-api:")):
            return self._download_api(result_id or download_url.replace("assrt-api:", "", 1))
        page_url = result.get("page_url") or ""
        download_url = download_url or self._extract_download_url(page_url)
        if not download_url:
            raise ValueError("射手网(伪) 未找到可下载链接，请使用手动搜索")
        return super().download({**result, "download_url": download_url, "page_url": page_url}, captcha_code=captcha_code)

    def _search_api(self, keyword: str, targets: List[Dict[str, Any]]) -> List[OnlineSubtitleResult]:
        query = str(keyword or "").strip()
        payload = self._api_json(
            "/v1/sub/search",
            {
                "q": query,
                "cnt": "15",
                "pos": "0",
                "is_file": "1",
                "no_muxer": "1",
                "filelist": "1",
            },
        )
        subs = self._extract_subs(payload)
        results: List[OnlineSubtitleResult] = []
        for item in subs:
            sid = str(item.get("id") or "").strip()
            if not sid:
                continue
            title = self._api_subtitle_title(item)
            if _looks_like_mojibake(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("native_name", "title", "videoname", "filename", "desc")
                )
                or title
            ):
                logger.info("[SubtitleManualUpload] 丢弃 ASSRT 乱码字幕结果 id=%s", sid)
                continue
            language_text = " ".join([title, str(item.get("lang") or ""), str(item.get("desc") or "")])
            language_label = _guess_language_label(language_text)
            season, episode = _episode_from_text(title) or (0, 0)
            assessment = _assess_result_match(title=title, keyword=keyword, targets=targets)
            target_media_type = next((str(target.get("media_type") or "") for target in targets or [] if target.get("media_type")), "")
            if assessment["identity_status"] == "failed" and target_media_type == "tv":
                logger.info(
                    "[SubtitleManualUpload] 丢弃 ASSRT 不匹配字幕结果 id=%s reason=%s",
                    sid,
                    assessment["reject_reason"],
                )
                continue
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=sid,
                    title=title,
                    page_url=self._detail_url(sid),
                    download_url=f"assrt-api:{sid}",
                    language=language_label,
                    language_category=_language_category_from_text(language_text or language_label),
                    format=_guess_subtitle_format(" ".join([title, str(item.get("subtype") or ""), str(item.get("filename") or "")])),
                    season=season,
                    episode=episode,
                    score=assessment["score"] + 8,
                    source=self.display_name,
                    note="通过 ASSRT 官方 API 搜索",
                    downloadable=True,
                    relevance_status=assessment["relevance_status"],
                    region_bucket=_region_bucket({}, targets),
                    query_plan=_query_plan_for_keyword(keyword, targets)["label"],
                    identity_status=assessment["identity_status"],
                    reject_reason=assessment["reject_reason"],
                    match_detail=assessment["match_detail"],
                )
        )
        results = _dedupe_results(results)[:30]
        logger.info(
            "[SubtitleManualUpload] ASSRT API 搜索完成 query=%s results=%s",
            query,
            len(results),
        )
        return results

    def _detail_url(self, subtitle_id: str) -> str:
        sid = str(subtitle_id or "").strip()
        if sid.isdigit():
            return f"{self.root_url}/xml/sub/{int(sid) // 1000}/{sid}.xml"
        return f"{self.root_url}/sub/{quote(sid)}"

    def _download_api(self, subtitle_id: str) -> Tuple[str, bytes]:
        if not subtitle_id:
            raise ValueError("射手网(伪) API 缺少字幕 ID")
        payload = self._api_json("/v1/sub/detail", {"id": subtitle_id})
        subs = self._extract_subs(payload)
        detail = subs[0] if subs else {}
        download_url = str(detail.get("url") or "").strip()
        filename = str(detail.get("filename") or "").strip()
        filelist = detail.get("filelist") or []
        if isinstance(filelist, dict):
            filelist = [filelist]
        if not download_url and isinstance(filelist, list):
            for item in filelist:
                if not isinstance(item, dict):
                    continue
                download_url = str(item.get("url") or "").strip()
                filename = filename or str(item.get("f") or "").strip()
                if download_url:
                    break
        if not download_url:
            raise ValueError("射手网(伪) API 未返回可下载链接")
        name, content, final_url = OnlineDirectDownloader(use_proxy=self.fetcher.use_proxy).get_bytes(download_url)
        logger.info(
            "[SubtitleManualUpload] 射手网(伪) API 字幕下载完成 host=%s size=%s",
            _host(final_url),
            len(content),
        )
        return filename or name or f"assrt-{subtitle_id}.zip", content

    def _api_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
        url = f"{self.api_url}{path}?{query}"
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        handlers = []
        proxies = getattr(settings, "PROXY", None) if self.fetcher.use_proxy else None
        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))
        opener = urllib.request.build_opener(*handlers)
        try:
            request = urllib.request.Request(url, headers=headers)
            with opener.open(request, timeout=40) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = _decode_bytes(exc.read()[:500], exc.headers.get_content_charset())
            raise ValueError(f"射手网(伪) API 请求失败 HTTP {exc.code}: {_compact_error_message(detail)}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(_format_network_error(self.api_url, exc)) from exc
        except OSError as exc:
            raise ValueError(_format_network_error(self.api_url, exc)) from exc
        try:
            payload = json.loads(_decode_bytes(raw, None) or "{}")
        except Exception as exc:
            raise ValueError("射手网(伪) API 返回内容不是 JSON") from exc
        error = self._api_error_message(payload)
        if error:
            raise ValueError(error)
        return payload

    @staticmethod
    def _api_error_message(payload: Dict[str, Any]) -> str:
        status = payload.get("status")
        if status in {0, "0", None}:
            return ""
        message = (
            payload.get("message")
            or payload.get("msg")
            or payload.get("error")
            or payload.get("err")
            or payload.get("result")
            or "API 返回错误"
        )
        text = str(message)
        lowered = text.lower()
        if "invalid token" in lowered:
            return "射手网(伪) API Key 无效，请在插件设置中检查。"
        if "quota" in lowered or "limit" in lowered:
            return "射手网(伪) API 配额不足或请求过于频繁，请稍后再试。"
        return f"射手网(伪) API 返回错误: {text}"

    @staticmethod
    def _extract_subs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        containers = [
            payload.get("sub") if isinstance(payload, dict) else None,
            payload,
        ]
        for container in containers:
            if not isinstance(container, dict):
                continue
            subs = container.get("subs") or container.get("sub")
            if isinstance(subs, list):
                return [item for item in subs if isinstance(item, dict)]
            if isinstance(subs, dict):
                return [subs]
        return []

    @staticmethod
    def _api_subtitle_title(item: Dict[str, Any]) -> str:
        for key in ("native_name", "title", "videoname", "filename"):
            value = re.sub(r"\s+", " ", html.unescape(str(item.get(key) or ""))).strip()
            if value:
                return value
        return f"射手网(伪) 字幕 {item.get('id') or ''}".strip()

    def _extract_download_url(self, page_url: str) -> str:
        if not page_url:
            return ""
        if self._looks_like_download_href(page_url):
            return page_url
        status, text, _ = self.fetcher.get_text(page_url, referer=self.root_url)
        if status >= 400 or not text:
            return ""
        candidates = []
        for link in _extract_links(text):
            href = (link.href or "").strip()
            if self._looks_like_download_href(href) or re.search(r"下载|download", link.text or "", re.I):
                candidates.append(urljoin(self.root_url, href))
        return candidates[0] if candidates else ""

    @staticmethod
    def _is_result_link(href: str, title: str) -> bool:
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            return False
        if not title or len(title) < 3:
            return False
        lowered = href.lower()
        if "searchword=" in lowered:
            return False
        return "/sub/" in lowered or "/download" in lowered or "/down" in lowered

    @staticmethod
    def _looks_like_download_href(href: str) -> bool:
        lowered = (href or "").lower()
        return bool(
            re.search(r"\.(zip|rar|srt|ass|ssa|sub|vtt|webvtt)(?:$|[?#])", lowered)
            or "/download" in lowered
            or "/down" in lowered
        )
