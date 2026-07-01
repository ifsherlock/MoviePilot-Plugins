from __future__ import annotations

from ..captcha.subhd import SubHDSvgCaptchaSolver
from ..clients import *  # noqa: F401,F403
from ..language import *  # noqa: F401,F403
from ..matcher import *  # noqa: F401,F403
from ..models import *  # noqa: F401,F403
from ..shared import *  # noqa: F401,F403
from .base import BaseSubtitleProvider, _subhd_manual_url

class SubHDProvider(BaseSubtitleProvider):
    provider_id = "subhd"
    display_name = "SubHD"
    default_root_url = DEFAULT_PROVIDER_ROOTS["subhd"]

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "使用豆瓣 ID 或标题自动搜索，必要时自动处理下载验证码"
        return status

    def manual_url(self, keyword: str) -> str:
        return _subhd_manual_url(self.root_url, keyword)

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        return self._search_keyword(keyword, targets)

    def search_all(self, keywords: List[str], targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        douban_id = _first_target_value(targets, "douban_id")
        if douban_id:
            found = self._search_detail(str(douban_id), targets, "SubHD 豆瓣 ID 查询")
            if found:
                return found
        for keyword in keywords:
            found = self._search_keyword(keyword, targets)
            if found:
                return found
        fallback = self._fallback_ids_from_douban(keywords, targets)
        fallback_douban = fallback.get("douban_id")
        if fallback_douban and fallback_douban != douban_id:
            found = self._search_detail(fallback_douban, targets, "SubHD 豆瓣搜索兜底")
            if found:
                return found
        fallback_imdb = fallback.get("imdb_id") or _first_target_value(targets, "imdb_id")
        if fallback_imdb:
            resolved = self._resolve_imdb(fallback_imdb)
            if resolved:
                return self._search_detail(resolved, targets, "SubHD IMDb 兜底查询")
        return []

    def _search_keyword(self, keyword: str, targets: List[Dict[str, Any]]) -> List[OnlineSubtitleResult]:
        if not keyword:
            return []
        status, text, final_url = self.fetcher.get_text(self.manual_url(keyword), referer=self.root_url)
        if status >= 400 or not text:
            logger.warning(
                "[SubtitleManualUpload] SubHD 标题搜索页面不可用 keyword=%s status=%s",
                keyword,
                status,
            )
            return []
        ids = _extract_unique_matches(r'href=["\']/d/(\d+)["\']', text)
        direct_count = len(re.findall(r'href=["\']/a/[A-Za-z0-9_-]+["\']', text or "", flags=re.I))
        logger.info(
            "[SubtitleManualUpload] SubHD 标题搜索页面解析完成 keyword=%s status=%s detail_candidates=%s direct_candidates=%s final_host=%s",
            keyword,
            status,
            len(ids),
            direct_count,
            _host(final_url),
        )
        results: List[OnlineSubtitleResult] = []
        for sid in ids[:4]:
            results.extend(self._search_detail(sid, targets, f"SubHD 标题查询 · {keyword}"))
            if results:
                break
        if not results and "/a/" in text:
            results.extend(self._parse_subtitles(text, final_url, targets, f"SubHD 标题查询 · {keyword}"))
        return _dedupe_results(results)[:30]

    def _search_detail(self, detail_id: str, targets: List[Dict[str, Any]], query_plan: str) -> List[OnlineSubtitleResult]:
        detail_id = str(detail_id or "").strip()
        if not detail_id:
            return []
        page_url = f"{self.root_url}/d/{quote(detail_id)}"
        status, text, final_url = self.fetcher.get_text(page_url, referer=self.root_url)
        if status >= 400 or not text:
            logger.warning(
                "[SubtitleManualUpload] SubHD 详情页不可用 detail_id=%s status=%s",
                detail_id,
                status,
            )
            return []
        results = self._parse_subtitles(text, final_url or page_url, targets, query_plan)
        logger.info(
            "[SubtitleManualUpload] SubHD 详情页解析完成 detail_id=%s results=%s query_plan=%s",
            detail_id,
            len(results),
            query_plan,
        )
        return results

    def _parse_subtitles(self, text: str, page_url: str, targets: List[Dict[str, Any]], query_plan: str) -> List[OnlineSubtitleResult]:
        results: List[OnlineSubtitleResult] = []
        target_episode = _target_episode_from_targets(targets)
        for match in re.finditer(r'<a[^>]+href=["\'](/a/([A-Za-z0-9_-]+))["\'][^>]*>(.*?)</a>', text or "", flags=re.I | re.S):
            href, sid, raw_title = match.groups()
            title = _strip_tags(raw_title) or f"SubHD 字幕 {sid}"
            if target_episode:
                include, _ = _episode_include_for_title(title, target_episode)
                if not include:
                    continue
            season, episode = _episode_from_text(title) or (0, 0)
            assessment = _assess_result_match(title=title, keyword=title, targets=targets)
            if assessment["identity_status"] == "failed" and targets:
                continue
            window_start = max(0, match.start() - 700)
            window_end = min(len(text or ""), match.end() + 300)
            language_text = f"{title} {_strip_tags((text or '')[window_start:window_end])}"
            page = urljoin(self.root_url, href)
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=sid,
                    title=title,
                    page_url=page,
                    download_url=f"subhd-page:{page}",
                    language=_guess_language_label(language_text),
                    language_category=_language_category_from_text(language_text),
                    format=_guess_subtitle_format(language_text),
                    season=season,
                    episode=episode,
                    score=assessment["score"] + 10,
                    source=self.display_name,
                    note="通过 SubHD 自动搜索",
                    downloadable=True,
                    query_plan=query_plan,
                    identity_status=assessment["identity_status"],
                    match_detail=assessment["match_detail"],
                )
            )
        return _dedupe_results(results)

    def _resolve_imdb(self, imdb_id: str) -> str:
        imdb = _normalize_imdb_tt(imdb_id)
        if not imdb:
            return ""
        status, text, _ = self.fetcher.get_text(f"{self.root_url}/search/{quote(imdb)}", referer=self.root_url)
        if status >= 400 or not text:
            return ""
        ids = _extract_unique_matches(r'href=["\']/d/(\d+)["\']', text)
        return ids[0] if ids else ""

    def _fallback_ids_from_douban(self, keywords: List[str], targets: List[Dict[str, Any]]) -> Dict[str, str]:
        for keyword in keywords[:2]:
            candidate = _search_douban_subject(keyword, _target_year_from_targets(targets), self.fetcher)
            if candidate.get("douban_id"):
                if not candidate.get("imdb_id"):
                    candidate["imdb_id"] = _fetch_douban_imdb_id(candidate["douban_id"], self.fetcher)
                return candidate
        return {}

    @staticmethod
    def _extract_api_download_url(data: Any) -> str:
        if isinstance(data, str):
            text = html.unescape(data.strip())
            if not text:
                return ""
            if text.startswith(("http://", "https://", "/")):
                return text
            if text.startswith("{") or text.startswith("["):
                try:
                    return SubHDProvider._extract_api_download_url(json.loads(text))
                except Exception:
                    pass
            hrefs = _extract_download_hrefs(text)
            if hrefs:
                return hrefs[0]
            if re.search(r"(?i)(download|down|api|file|zip|rar|7z|srt|ass|ssa|sub|vtt)", text) and not re.search(r"\s", text):
                return text
            return ""
        if isinstance(data, list):
            for item in data:
                found = SubHDProvider._extract_api_download_url(item)
                if found:
                    return found
            return ""
        if not isinstance(data, dict):
            return ""
        for key in (
            "url",
            "download_url",
            "downloadUrl",
            "down_url",
            "downUrl",
            "file_url",
            "fileUrl",
            "link",
            "href",
            "path",
            "location",
            "redirect",
        ):
            found = SubHDProvider._extract_api_download_url(data.get(key))
            if found:
                return found
        for key in ("data", "result", "sub", "subtitle", "file", "download", "resource"):
            found = SubHDProvider._extract_api_download_url(data.get(key))
            if found:
                return found
        for value in data.values():
            found = SubHDProvider._extract_api_download_url(value)
            if found:
                return found
        return ""

    def _download_first_valid_link(self, links: List[str], base_url: str, referer: str) -> Optional[Tuple[str, bytes]]:
        for href in links:
            file_url = urljoin(base_url, html.unescape(href))
            try:
                filename, content, final_url = self.fetcher.get_bytes(file_url, referer=referer)
                if content and not _looks_like_html_bytes(content, filename or final_url):
                    return filename, content
            except Exception as exc:
                logger.info("[SubtitleManualUpload] SubHD 下载候选链接失败 host=%s error=%s", _host(file_url), exc)
        return None

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        page_url = str(result.get("page_url") or result.get("download_url") or "").replace("subhd-page:", "", 1)
        if not page_url:
            raise ValueError("SubHD 缺少下载页面")
        status, text, _ = self.fetcher.get_text(page_url, referer=self.root_url)
        if status >= 400 or not text:
            raise ValueError("SubHD 下载页面不可访问")
        down_match = re.search(r'href=["\']([^"\']*/down/[A-Za-z0-9_-]+[^"\']*)["\']', text, re.I)
        if not down_match:
            raise ValueError("SubHD 未找到下载按钮")
        down_url = urljoin(self.root_url, html.unescape(down_match.group(1)))
        sid = Path(urlparse(down_url).path).name
        if not sid:
            raise ValueError("SubHD 下载按钮缺少 sid")
        down_status, down_text, down_final_url = self.fetcher.get_text(down_url, referer=page_url)
        payload = {"sid": sid, "cap": captcha_code or ""}
        api_url = f"{self.root_url}/api/sub/down"
        data = self.fetcher.post_json(api_url, payload, referer=down_url)
        if data.get("pass") is False and not payload["cap"]:
            payload["cap"] = SubHDSvgCaptchaSolver().solve(str(data.get("msg") or ""))
            data = self.fetcher.post_json(api_url, payload, referer=down_url)
        if not data.get("success"):
            raise ValueError("SubHD 下载验证码校验失败或接口未返回下载地址")
        file_url = self._extract_api_download_url(data)
        if not file_url:
            fallback_links = _extract_download_hrefs(down_text or "")
            fallback = self._download_first_valid_link(fallback_links, down_final_url or down_url, down_url)
            if fallback:
                return fallback
            url_value = data.get("url") if isinstance(data, dict) else ""
            logger.warning(
                "[SubtitleManualUpload] SubHD API 未返回下载地址 sid=%s keys=%s success=%s pass=%s url_len=%s url_type=%s msg_hint=%s down_status=%s",
                sid,
                ",".join(sorted(str(key) for key in data.keys())) if isinstance(data, dict) else type(data).__name__,
                data.get("success") if isinstance(data, dict) else "",
                data.get("pass") if isinstance(data, dict) else "",
                len(str(url_value or "")),
                type(url_value).__name__,
                _compact_error_message(str(data.get("msg") or ""))[:80] if isinstance(data, dict) else "",
                down_status,
            )
            raise ValueError("SubHD API 未返回下载地址")
        resolved_url = urljoin(self.root_url, file_url)
        filename, content, final_url = self.fetcher.get_bytes(resolved_url, referer=down_url)
        if _looks_like_html_bytes(content, filename or final_url):
            text = _decode_bytes(content, filename)
            fallback = self._download_first_valid_link(_extract_download_hrefs(text), final_url or resolved_url, resolved_url)
            if fallback:
                return fallback
            raise ValueError("SubHD 下载地址返回了 HTML 页面，未解析到有效字幕文件")
        return filename or f"subhd-{sid}.zip", content
