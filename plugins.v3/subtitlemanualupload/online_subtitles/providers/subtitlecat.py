from __future__ import annotations

import re
import time
from dataclasses import replace
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse

from ..keyword_builder import _title_aliases, _strong_title_matches, _unique_keywords
from ..language import _language_category_from_text
from ..matcher import _assess_result_match, _episode_from_text, _extract_years
from ..models import OnlineSubtitleResult
from ..shared import _stable_result_id
from .base import BaseSubtitleProvider


class _SearchTable(HTMLParser):
    """Read the first cell only: metrics and language counts are not language evidence."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found_table = False
        self.data_rows = 0
        self.rows = []
        self._in_table = False
        self._cell = 0
        self._in_cell = False
        self._href = ""
        self._title = []
        self._text = []
        self._in_anchor = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table" and "sub-table" in (attributes.get("class") or "").split():
            self.found_table = self._in_table = True
        if not self._in_table:
            return
        if tag == "tr":
            self._cell, self._href, self._title, self._text = 0, "", [], []
        elif tag == "td":
            self._cell += 1
            self._in_cell = self._cell == 1
        elif tag == "a" and self._in_cell and not self._href:
            self._href = attributes.get("href") or ""
            self._in_anchor = True

    def handle_data(self, data):
        if self._in_cell:
            self._text.append(data)
        if self._in_anchor:
            self._title.append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self._in_anchor = False
        elif tag == "td":
            self._in_cell = False
        elif tag == "tr" and self._in_table:
            self.data_rows += bool(self._cell)
            if self._href:
                self.rows.append((self._href, "".join(self._title).strip(), " ".join(self._text)))
        elif tag == "table":
            self._in_table = False


class _DownloadLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = {}
        self.originals = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and (attributes.get("id") or "").startswith("download_"):
            self.links[attributes["id"].removeprefix("download_")] = attributes.get("href") or ""
        if tag == "a" and (attributes.get("href") or "").endswith("-orig.srt"):
            self.originals.append(attributes["href"])
        # This is a static filename reference, never an instruction to run page JavaScript.
        call = re.fullmatch(
            r"\s*translate_from_server_folder\('[^']+',\s*'([^']+-orig\.srt)',\s*'(/subs/\d+/)'\);?\s*",
            attributes.get("onclick") or "",
        )
        if call:
            self.originals.append(call.group(2) + call.group(1))


class SubtitleCatProvider(BaseSubtitleProvider):
    provider_id = "subtitlecat"
    display_name = "SubtitleCat"
    default_root_url = "https://www.subtitlecat.com"
    MAX_KEYWORDS = 3
    MAX_RESULTS = 20
    MAX_TRANSLATION_DETAILS = 4
    SEARCH_BUDGET_SECONDS = 20

    def __init__(self, fetcher, root_url: str = "", include_translations: bool = False):
        super().__init__(fetcher, root_url=root_url)
        self.include_translations = bool(include_translations)

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["message"] = "搜索原始上传字幕；原语言未知时保留未知"
        if self.include_translations:
            status["message"] += "，包含已生成的站点中文翻译"
        return status

    def manual_url(self, keyword: str) -> str:
        return f"{self.root_url}/index.php?search={quote(keyword)}"

    def search_all(self, keywords, targets, scope):
        deadline = time.monotonic() + self.SEARCH_BUDGET_SECONDS
        for keyword in _unique_keywords(keywords)[:self.MAX_KEYWORDS]:
            results = self._search(keyword, targets, scope, deadline)
            if results:
                return results
        return []

    def search(self, keyword, targets, scope):
        return self._search(keyword, targets, scope, time.monotonic() + self.SEARCH_BUDGET_SECONDS)

    def _search(self, keyword, targets, scope, deadline):
        if not keyword.strip():
            return []
        search_url = self.manual_url(keyword)
        status, text, final_url = self._get_page(search_url, deadline)
        self._check_page(status, text, final_url, "搜索")
        parser = _SearchTable()
        parser.feed(text)
        if not parser.found_table:
            raise ValueError("SubtitleCat 搜索页面结构变化或被拦截，未找到字幕表格")
        if parser.data_rows and not parser.rows:
            raise ValueError("SubtitleCat 字幕表格结构变化，无法解析候选链接")
        results = []
        seen = set()
        aliases = _title_aliases({}, targets) or [keyword]
        for href, title, description in parser.rows:
            page_url = self._safe_url(href, search_url, ".html")
            if page_url in seen or not title:
                continue
            seen.add(page_url)
            if not any(_strong_title_matches(alias, title) for alias in aliases):
                continue
            assessment = _assess_result_match(title=title, keyword=keyword, targets=targets)
            if assessment["identity_status"] == "failed":
                continue
            season, episode = _episode_from_text(title) or (0, 0)
            # Single SRT files cannot prove season packs or a requested episode from season alone.
            is_tv = scope in {"episode", "season"} or any(target.get("media_type") == "tv" for target in targets)
            if is_tv and not self._matches_episode(season, episode, targets):
                continue
            original_language = re.search(r"\(\s*translated from\s+([^()]+)\)", description, re.I)
            language = original_language.group(1).strip() if original_language else "Unknown"
            result = OnlineSubtitleResult(
                provider=self.provider_id,
                provider_label=self.display_name,
                result_id=_stable_result_id(self.provider_id, page_url + "|original"),
                title=title,
                page_url=page_url,
                download_url="subtitlecat-original:" + page_url,
                language=language,
                language_category=_language_category_from_text(language),
                format="SRT",
                season=season,
                episode=episode,
                score=assessment["score"],
                source=self.display_name,
                note=f"原始上传；页面声明原语言：{language}（不代表人工校对）",
                translation_source="original_upload",
                result_years=_extract_years(title),
                identity_status=assessment["identity_status"],
                relevance_status=assessment["relevance_status"],
                match_detail=assessment["match_detail"],
            )
            results.append(result)
            if len(results) >= self.MAX_RESULTS:
                break
        if self.include_translations:
            results.extend(self._translations(results[:self.MAX_TRANSLATION_DETAILS], deadline))
        return results

    @staticmethod
    def _matches_episode(season, episode, targets):
        if not season or not episode:
            return False
        return any(
            season == int(target.get("season") or 0)
            and (not int(target.get("episode") or 0) or episode == int(target["episode"]))
            for target in targets
        )

    def _translations(self, originals, deadline):
        translated = []
        for original in originals:
            links = self._detail(original.page_url, deadline)
            for code, language in (("zh-CN", "简体中文"), ("zh-TW", "繁体中文")):
                if not links.links.get(code):
                    continue
                self._translation_url(links.links[code], original.page_url, code)
                translated.append(replace(
                    original,
                    result_id=_stable_result_id(self.provider_id, original.page_url + "|" + code),
                    download_url=f"subtitlecat-{code}:" + original.page_url,
                    language=language,
                    language_category="chinese",
                    translation_source="site_translation",
                    note=f"站点翻译（{language}），原始语言：{original.language}；未经人工校对",
                ))
        return translated

    def _safe_url(self, value, base, suffix):
        url = urljoin(base, value)
        parsed, root = urlparse(url), urlparse(self.root_url)
        path = unquote(parsed.path)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc != root.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r"/subs/\d+/[^/]+", path)
            or not path.endswith(suffix)
            or "\\" in path or any(part in {".", ".."} for part in path.split("/"))
        ):
            raise ValueError("SubtitleCat 返回了不受支持的字幕链接")
        return parsed._replace(path=quote(path, safe="/-._~")).geturl()

    def _translation_url(self, value, page_url, code):
        url = self._safe_url(value, page_url, f"-{code}.srt")
        expected_name = unquote(urlparse(page_url).path).rsplit("/", 1)[-1].removesuffix(".html") + f"-{code}.srt"
        if unquote(urlparse(url).path).rsplit("/", 1)[-1] != expected_name:
            raise ValueError("SubtitleCat 翻译字幕文件名与详情页不一致")
        return url

    def _check_page(self, status, text, url, stage):
        if status != 200:
            raise ValueError(f"SubtitleCat {stage}失败 HTTP {status}")
        if not text.strip() or urlparse(url).netloc != urlparse(self.root_url).netloc:
            raise ValueError(f"SubtitleCat {stage}返回空页面或跳转到其他站点")

    def _get_page(self, url, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("SubtitleCat 搜索超出时间预算，请减少搜索范围或关闭站点翻译")
        previous_timeout = getattr(self.fetcher, "timeout", None)
        if previous_timeout is not None:
            self.fetcher.timeout = min(previous_timeout, remaining)
        try:
            return self.fetcher.get_text(url, referer=self.root_url)
        finally:
            if previous_timeout is not None:
                self.fetcher.timeout = previous_timeout

    def _detail(self, page_url, deadline=None):
        deadline = deadline if deadline is not None else time.monotonic() + self.SEARCH_BUDGET_SECONDS
        status, text, final_url = self._get_page(page_url, deadline)
        self._check_page(status, text, final_url, "详情")
        parser = _DownloadLinks()
        parser.feed(text)
        if not parser.links and not parser.originals:
            raise ValueError("SubtitleCat 详情页面结构变化或被拦截，未找到下载信息")
        return parser

    def download(self, result, captcha_code=""):
        page_url = self._safe_url(str(result.get("page_url") or ""), self.root_url, ".html")
        marker = str(result.get("download_url") or "").partition(":")[0]
        if marker not in {"subtitlecat-original", "subtitlecat-zh-CN", "subtitlecat-zh-TW"}:
            raise ValueError("SubtitleCat 下载候选缺少语言来源标记，请重新搜索")
        if marker != "subtitlecat-original" and not self.include_translations:
            raise ValueError("SubtitleCat 站点翻译已停用，请重新搜索原字幕")
        links = self._detail(page_url)
        if marker == "subtitlecat-original":
            expected = page_url.removesuffix(".html") + "-orig.srt"
            urls = [self._safe_url(value, page_url, "-orig.srt") for value in links.originals]
            if unquote(expected) not in {unquote(url) for url in urls}:
                raise ValueError("SubtitleCat 详情页未确认原字幕地址")
            download_url = expected
        else:
            code = marker.removeprefix("subtitlecat-")
            if not links.links.get(code):
                raise ValueError("SubtitleCat 目标语言没有现成字幕，不会自动提交翻译")
            download_url = self._translation_url(links.links[code], page_url, code)
        return super().download({**result, "download_url": download_url}, captcha_code=captcha_code)
