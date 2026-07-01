from __future__ import annotations

from ..captcha.zimuku import ZimukuBmpCaptchaSolver
from ..clients import *  # noqa: F401,F403
from ..keyword_builder import *  # noqa: F401,F403
from ..language import *  # noqa: F401,F403
from ..matcher import *  # noqa: F401,F403
from ..models import *  # noqa: F401,F403
from ..shared import *  # noqa: F401,F403
from .base import BaseSubtitleProvider, _zimuku_manual_url

class ZimukuProvider(BaseSubtitleProvider):
    provider_id = "zimuku"
    display_name = "Zimuku"
    default_root_url = DEFAULT_PROVIDER_ROOTS["zimuku"]
    _captcha_retries = 3

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "使用标题自动搜索候选页，必要时自动处理站点验证码"
        return status

    def manual_url(self, keyword: str) -> str:
        return _zimuku_manual_url(self.root_url, keyword)

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        return self._search_keyword(keyword, targets)

    def _search_urls(self, keyword: str) -> List[str]:
        quoted = quote(keyword)
        parsed = urlparse(self.root_url)
        scheme = parsed.scheme or "https"
        host = parsed.netloc or parsed.path
        hosts = [host]
        if host.startswith("www."):
            hosts.append(host[4:])
        elif host:
            hosts.append(f"www.{host}")
        urls: List[str] = []
        for candidate_host in _unique_keywords([item for item in hosts if item]):
            root = f"{scheme}://{candidate_host}".rstrip("/")
            chosts = _unique_keywords([candidate_host, candidate_host[4:] if candidate_host.startswith("www.") else f"www.{candidate_host}", "zimuku.org", "www.zimuku.org"])
            for chost in chosts:
                urls.append(f"{root}/search?{urlencode({'q': keyword, 'chost': chost})}")
                urls.append(f"{root}/search?q={quoted}&chost={chost}")
            urls.append(f"{root}/search/{quoted}")
        result: List[str] = []
        seen = set()
        for url in urls:
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(url)
        return result

    def _get_text(self, url: str, *, referer: str = "") -> Tuple[int, str, str]:
        current = url
        for attempt in range(self._captcha_retries + 1):
            status, text, final_url = self.fetcher.get_text(current, referer=referer)
            if 'class="verifyimg"' not in text and "class='verifyimg'" not in text:
                return status, text, final_url
            code = ZimukuBmpCaptchaSolver.from_html(text)
            if not code:
                logger.warning(
                    "[SubtitleManualUpload] Zimuku 验证码页面无法自动识别 url=%s status=%s attempt=%s",
                    _host(current),
                    status,
                    attempt + 1,
                )
                break
            hex_code = "".join(f"{ord(ch):x}" for ch in code)
            sep = "&" if "?" in current else "?"
            self.fetcher.get_text(f"{current}{sep}security_verify_img={hex_code}", referer=referer)
        logger.warning(
            "[SubtitleManualUpload] Zimuku 验证码处理后仍未进入目标页面 url=%s status=%s",
            _host(current),
            status,
        )
        return status, text, final_url

    def _search_keyword(self, keyword: str, targets: List[Dict[str, Any]]) -> List[OnlineSubtitleResult]:
        if not keyword:
            return []
        status = 0
        text = ""
        final_url = ""
        attempted: List[str] = []
        for search_url in self._search_urls(keyword):
            attempted.append(search_url)
            status, text, final_url = self._get_text(search_url, referer=self.root_url)
            if status < 400 and text:
                break
        if status >= 400 or not text:
            logger.warning(
                "[SubtitleManualUpload] Zimuku 标题搜索页面不可用 keyword=%s status=%s captcha=%s attempts=%s",
                keyword,
                status,
                "verifyimg" in (text or ""),
                len(attempted),
            )
            return []
        subs_urls = []
        for match in re.finditer(r'href=["\']([^"\']*/subs/\d+\.html[^"\']*)["\'][^>]*>(.*?)</a>', text, re.I | re.S):
            title = _strip_tags(match.group(2))
            href = urljoin(final_url or self.root_url, html.unescape(match.group(1)))
            if href not in [item[0] for item in subs_urls]:
                subs_urls.append((href, title))
        logger.info(
            "[SubtitleManualUpload] Zimuku 标题搜索页面解析完成 keyword=%s status=%s candidates=%s attempts=%s final_host=%s",
            keyword,
            status,
            len(subs_urls),
            len(attempted),
            _host(final_url or attempted[-1] if attempted else self.root_url),
        )
        results: List[OnlineSubtitleResult] = []
        for subs_url, title in subs_urls[:4]:
            if title and targets and not any(_title_matches(alias, title) for alias in _series_title_aliases(targets)):
                continue
            results.extend(self._search_subs_page(subs_url, targets, f"Zimuku 标题查询 · {keyword}"))
            if results:
                break
        return _dedupe_results(results)[:30]

    def _search_subs_page(self, subs_url: str, targets: List[Dict[str, Any]], query_plan: str) -> List[OnlineSubtitleResult]:
        status, text, final_url = self._get_text(subs_url, referer=self.root_url)
        if status >= 400 or not text:
            logger.warning(
                "[SubtitleManualUpload] Zimuku 字幕候选页不可用 url=%s status=%s",
                _host(subs_url),
                status,
            )
            return []
        results: List[OnlineSubtitleResult] = []
        target_episode = _target_episode_from_targets(targets)
        for match in re.finditer(r'<tr[^>]*>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>.*?</tr>', text, re.I | re.S):
            href, raw_title = match.groups()
            if not href:
                continue
            title = _strip_tags(raw_title)
            include, collection = _episode_include_for_title(title, target_episode)
            if not include:
                continue
            season, episode = _episode_from_text(title) or (0, 0)
            assessment = _assess_result_match(title=title, keyword=title, targets=targets)
            if assessment["identity_status"] == "failed" and targets and not collection:
                continue
            row_html = match.group(0)
            attr_text = " ".join(re.findall(r'\btitle=["\']([^"\']+)["\']', row_html, re.I))
            row_text = f"{_strip_tags(row_html)} {html.unescape(attr_text)}"
            page_url = urljoin(final_url or subs_url, html.unescape(href))
            result_id = re.sub(r"\D+", "", href) or _stable_result_id(self.provider_id, page_url)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=result_id,
                    title=title or f"Zimuku 字幕 {result_id}",
                    page_url=page_url,
                    download_url=f"zimuku-page:{page_url}",
                    language=_guess_language_label(row_text or title),
                    language_category=_language_category_from_text(row_text or title),
                    format=_guess_subtitle_format(row_text or title),
                    season=season,
                    episode=episode,
                    score=assessment["score"] + 8,
                    source=self.display_name,
                    note="通过 Zimuku 自动搜索",
                    downloadable=True,
                    query_plan=query_plan,
                    identity_status=assessment["identity_status"],
                    match_detail=assessment["match_detail"],
                )
            )
        results = _dedupe_results(results)
        logger.info(
            "[SubtitleManualUpload] Zimuku 字幕候选页解析完成 url=%s results=%s query_plan=%s",
            _host(final_url or subs_url),
            len(results),
            query_plan,
        )
        return results

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = str(result.get("page_url") or result.get("download_url") or "").replace("zimuku-page:", "", 1)
        if not page_url:
            raise ValueError("Zimuku 缺少下载页面")
        status, text, _ = self._get_text(page_url, referer=self.root_url)
        if status >= 400 or not text:
            raise ValueError("Zimuku 下载页面不可访问")
        dl_match = re.search(r'<li[^>]+class=["\'][^"\']*dlsub[^"\']*["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\']', text, re.I | re.S)
        if not dl_match:
            raise ValueError("Zimuku 未找到下载入口")
        dl_url = urljoin(page_url, html.unescape(dl_match.group(1)))
        status, text, _ = self._get_text(dl_url, referer=page_url)
        if status >= 400 or not text:
            raise ValueError("Zimuku 下载跳转页不可访问")
        links = _extract_download_hrefs(text)
        last_error = ""
        for href in links:
            file_url = urljoin(dl_url, href)
            try:
                filename, content, _ = self.fetcher.get_bytes(file_url, referer=dl_url)
                if len(content or b"") > 1024 and not _looks_like_html_bytes(content, filename):
                    return filename or f"zimuku-{result.get('result_id') or 'subtitle'}.zip", content
            except Exception as exc:
                last_error = _compact_error_message(str(exc))
        raise ValueError(last_error or "Zimuku 未能下载到有效字幕文件")
