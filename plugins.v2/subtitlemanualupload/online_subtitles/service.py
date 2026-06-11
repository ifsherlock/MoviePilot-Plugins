from __future__ import annotations

from .common import *  # noqa: F401,F403
from .providers import AssrtProvider, OpenSubtitlesProvider, SubHDProvider, ZimukuProvider
from .providers.base import BaseSubtitleProvider

class OnlineSubtitleSearchService:
    def __init__(
        self,
        *,
        engine: str = DEFAULT_ENGINE,
        use_proxy: bool = False,
        provider_roots: Optional[Dict[str, str]] = None,
        assrt_api_key: str = "",
        assrt_api_url: str = DEFAULT_ASSRT_API_URL,
        opensubtitles_api_key: str = "",
        opensubtitles_api_url: str = DEFAULT_OPENSUBTITLES_API_URL,
        opensubtitles_username: str = "",
        opensubtitles_password: str = "",
    ):
        self.fetcher = OnlinePageClient(engine=engine, use_proxy=use_proxy)
        roots = normalize_provider_roots(provider_roots)
        self.providers: Dict[str, BaseSubtitleProvider] = {
            "subhd": SubHDProvider(self.fetcher, root_url=roots["subhd"]),
            "zimuku": ZimukuProvider(self.fetcher, root_url=roots["zimuku"]),
            "assrt": AssrtProvider(
                self.fetcher,
                root_url=roots["assrt"],
                api_key=assrt_api_key,
                api_url=assrt_api_url,
            ),
            "opensubtitles": OpenSubtitlesProvider(
                self.fetcher,
                root_url=roots["opensubtitles"],
                api_key=opensubtitles_api_key,
                api_url=opensubtitles_api_url,
                username=opensubtitles_username,
                password=opensubtitles_password,
            ),
        }
        self.manual_providers: Dict[str, BaseSubtitleProvider] = {
            "subhd": self.providers["subhd"],
            "zimuku": self.providers["zimuku"],
            "assrt": self.providers["assrt"],
            "opensubtitles": self.providers["opensubtitles"],
        }

    def status(self) -> Dict[str, Any]:
        browser_status = self.fetcher.status()
        return {
            "engine": browser_status["engine"],
            "engine_name": browser_status["engine_name"],
            "providers": [provider.status() for provider in self.providers.values()],
            "manual_providers": [provider.status() for provider in self.manual_providers.values()],
            "capabilities": {
                "ocr": _can_import("app.helper.ocr"),
                "cloakbrowser": browser_status["cloakbrowser"],
                "mp_browser": browser_status["mp_browser"],
                "flaresolverr": _mp_browser_looks_configured(),
                "proxy": browser_status["proxy"],
            },
            "engine_available": browser_status["available"],
        }

    def manual_links(self, keywords: List[str], providers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        provider_ids = list(self.manual_providers.keys()) if providers is None else [item for item in providers if item in self.manual_providers]
        for provider_id in provider_ids:
            provider = self.manual_providers[provider_id]
            links.append(
                {
                    "provider": provider.provider_id,
                    "name": provider.display_name,
                    "root_url": provider.root_url,
                    "host": _host(provider.root_url),
                    "links": [
                        {
                            "keyword": keyword,
                            "url": provider.manual_url(keyword),
                        }
                        for keyword in keywords
                    ],
                }
            )
        return links

    def search(
        self,
        *,
        keywords: List[str],
        providers: List[str],
        targets: List[Dict[str, Any]],
        scope: str,
    ) -> Dict[str, Any]:
        provider_ids = [item for item in providers if item in self.providers]
        if not provider_ids:
            return {
                "results": [],
                "messages": [
                    {
                        "provider": "providers",
                        "level": "info",
                        "message": "未启用在线字幕源，请至少选择一个来源或使用手动上传。",
                    }
                ],
            }
        results: List[OnlineSubtitleResult] = []
        provider_messages: List[Dict[str, str]] = []
        try:
            for provider_id in provider_ids:
                provider = self.providers[provider_id]
                provider_errors: List[str] = []
                found: List[OnlineSubtitleResult] = []
                try:
                    found = provider.search_all(keywords, targets, scope)
                    results.extend(found)
                except Exception as exc:
                    message = _compact_error_message(str(exc))
                    if message not in provider_errors:
                        provider_errors.append(message)
                    logger.warning(
                        "[SubtitleManualUpload] 在线字幕搜索失败 provider=%s keyword_count=%s host=%s error=%s",
                        provider_id,
                        len(keywords),
                        _host(provider.root_url),
                        exc,
                    )
                logger.info(
                    "[SubtitleManualUpload] 在线字幕源搜索完成 provider=%s host=%s keywords=%s results=%s",
                    provider_id,
                    _host(provider.root_url),
                    len(keywords),
                    len(found),
                )
                if not found and provider_errors:
                    provider_messages.append(
                        {
                            "provider": provider_id,
                            "level": "warning",
                            "message": _provider_error_summary(provider_errors, len(keywords)),
                        }
                    )
        finally:
            self.fetcher.close()
        results = _dedupe_results(results)
        results.sort(
            key=lambda item: (
                _provider_priority(item),
                _identity_priority(item),
                _language_priority(item),
                item.score,
                item.title,
            ),
            reverse=True,
        )
        return {
            "results": [item.to_dict() for item in results[:80]],
            "messages": provider_messages,
        }

    def download(self, results: Iterable[Dict[str, Any]], captcha_code: str = "") -> List[Dict[str, Any]]:
        downloaded: List[Dict[str, Any]] = []
        try:
            for result in results:
                provider_id = result.get("provider")
                provider = self.providers.get(provider_id)
                if not provider:
                    raise ValueError(f"未知字幕源 {provider_id}")
                filename, content = provider.download(result, captcha_code=captcha_code)
                downloaded.append(
                    {
                        "provider": provider_id,
                        "source_name": filename,
                        "content": content,
                        "result": result,
                    }
                )
        finally:
            self.fetcher.close()
        return downloaded
