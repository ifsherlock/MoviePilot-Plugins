from __future__ import annotations

from ..common import *  # noqa: F401,F403
from .base import BaseSubtitleProvider

class OpenSubtitlesProvider(BaseSubtitleProvider):
    provider_id = "opensubtitles"
    display_name = "OpenSubtitles"
    default_root_url = DEFAULT_PROVIDER_ROOTS["opensubtitles"]

    def __init__(
        self,
        fetcher: OnlinePageClient,
        root_url: str = "",
        *,
        api_key: str = "",
        api_url: str = DEFAULT_OPENSUBTITLES_API_URL,
        username: str = "",
        password: str = "",
    ):
        super().__init__(fetcher, root_url=root_url)
        self.api_key = str(api_key or "").strip()
        self.api_url = normalize_root_url(api_url, DEFAULT_OPENSUBTITLES_API_URL)
        self.username = str(username or "").strip()
        self.password = str(password or "").strip()
        self._session_token = ""

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["api_configured"] = bool(self.api_key)
        status["api_host"] = _host(self.api_url)
        status["download_configured"] = bool(self.username and self.password)
        if self.api_key and status["download_configured"]:
            status["message"] = "已配置 API Key 和账号密码，可搜索并下载多语言字幕"
        elif self.api_key:
            status["message"] = "已配置 API Key，可搜索；下载需 OpenSubtitles 账号密码"
        else:
            status["message"] = "未配置 API Key；不参与自动搜索"
        return status

    def manual_url(self, keyword: str) -> str:
        return (
            f"{self.root_url}/en/en,zh-CN/search-all/q-{quote(keyword)}"
            "/hearing_impaired-include/machine_translated-/trusted_sources-"
        )

    def search_all(self, keywords: List[str], targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if not self.api_key:
            raise ValueError("OpenSubtitles 未配置 API Key，已跳过自动搜索")
        for params, label in self._search_param_plan(keywords, targets):
            found = self._search_with_params(params, label, targets)
            if found:
                return found
        return []

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        if not self.api_key:
            raise ValueError("OpenSubtitles 未配置 API Key，已跳过自动搜索")
        return self._search_with_params(
            {
                "query": keyword,
                "languages": OPENSUBTITLES_SEARCH_LANGUAGES,
                "order_by": "download_count",
                "order_direction": "desc",
            },
            _query_plan_for_keyword(keyword, targets)["label"],
            targets,
            keyword=keyword,
        )

    def _search_with_params(
        self,
        params: Dict[str, Any],
        query_plan_label: str,
        targets: List[Dict[str, Any]],
        *,
        keyword: str = "",
    ) -> List[OnlineSubtitleResult]:
        keyword = keyword or str(params.get("query") or params.get("tmdb_id") or params.get("imdb_id") or "")
        target_year = _target_year_from_targets(targets)
        target_media_type = next((str(target.get("media_type") or "") for target in targets or [] if target.get("media_type")), "")
        strict_year_filter = target_media_type != "tv"
        payload = self._api_json("/subtitles", params)
        rows = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []
        results: List[OnlineSubtitleResult] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
            files = attrs.get("files") if isinstance(attrs.get("files"), list) else []
            file_info = next((item for item in files if isinstance(item, dict) and item.get("file_id")), None)
            if not file_info:
                continue
            title = self._subtitle_title(attrs, file_info)
            language_code = str(attrs.get("language") or attrs.get("languages") or "").strip()
            language_text = " ".join(
                [
                    language_code,
                    str(attrs.get("language_name") or ""),
                    title,
                    str(file_info.get("file_name") or ""),
                ]
            )
            language_category = _language_category_from_text(language_text)
            language_label = _language_label_from_category(language_category, language_code)
            season, episode = _episode_from_text(title) or (0, 0)
            file_id = str(file_info.get("file_id") or "").strip()
            result_years = _years_from_opensubtitles_attrs(attrs, file_info, title)
            file_years = _years_from_file_info(file_info)
            if strict_year_filter and target_year and result_years and target_year not in result_years:
                continue
            if strict_year_filter and target_year and file_years and target_year not in file_years:
                continue
            upload_year = _year_from_upload_date(attrs.get("upload_date") or attrs.get("uploaded_at"))
            if strict_year_filter and target_year and upload_year and upload_year < target_year:
                continue
            assessment = _assess_result_match(
                title=title,
                keyword=keyword,
                targets=targets,
                result_years=result_years,
                attrs=attrs,
                file_info=file_info,
            )
            if assessment["identity_status"] == "failed":
                continue
            results.append(
                OnlineSubtitleResult(
                    provider=self.provider_id,
                    provider_label=self.display_name,
                    result_id=file_id,
                    title=title,
                    page_url=str(attrs.get("url") or self.manual_url(keyword)),
                    download_url=f"opensubtitles-api:{file_id}",
                    language=language_label,
                    language_category=language_category,
                    format=_guess_subtitle_format(" ".join([title, str(file_info.get("file_name") or "")])),
                    season=season or _safe_int(attrs.get("season_number"), 0),
                    episode=episode or _safe_int(attrs.get("episode_number"), 0),
                    score=assessment["score"] + 6 + (12 if target_year and target_year in result_years else 0),
                    source=self.display_name,
                    note=f"通过 OpenSubtitles API 搜索{language_label}字幕",
                    downloadable=True,
                    result_years=result_years,
                    match_year=target_year if target_year and target_year in result_years else 0,
                    relevance_status=assessment["relevance_status"],
                    region_bucket=_region_bucket({}, targets),
                    query_plan=query_plan_label,
                    identity_status=assessment["identity_status"],
                    reject_reason=assessment["reject_reason"],
                    match_detail=assessment["match_detail"],
                )
            )
        results = _dedupe_results(results)[:30]
        logger.info(
            "[SubtitleManualUpload] OpenSubtitles API 搜索完成 query=%s tmdb_id=%s imdb_id=%s results=%s raw=%s",
            str(params.get("query") or ""),
            str(params.get("tmdb_id") or ""),
            str(params.get("imdb_id") or ""),
            len(results),
            len(rows),
        )
        return results

    def _search_param_plan(self, keywords: List[str], targets: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], str]]:
        base = {
            "languages": OPENSUBTITLES_SEARCH_LANGUAGES,
            "order_by": "download_count",
            "order_direction": "desc",
        }
        plans: List[Tuple[Dict[str, Any], str]] = []
        tmdb_id = _first_target_value(targets, "tmdb_id")
        imdb_id = _normalize_imdb_for_opensubtitles(_first_target_value(targets, "imdb_id"))
        if tmdb_id:
            plans.append(({**base, "tmdb_id": tmdb_id}, f"TMDB ID 查询 · 字幕语言 {OPENSUBTITLES_SEARCH_LANGUAGES}"))
        for keyword in keywords:
            plan = _query_plan_for_keyword(keyword, targets)
            plans.append(({**base, "query": keyword}, plan["label"]))
        if imdb_id:
            plans.append(({**base, "imdb_id": imdb_id}, f"IMDb ID 兜底查询 · 字幕语言 {OPENSUBTITLES_SEARCH_LANGUAGES}"))
        return plans

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        result_id = str(result.get("result_id") or "").strip()
        download_url = str(result.get("download_url") or "").strip()
        if download_url.startswith("opensubtitles-api:"):
            result_id = download_url.replace("opensubtitles-api:", "", 1)
        if not result_id:
            raise ValueError("OpenSubtitles 缺少 file_id")
        token = self._auth_token()
        payload = self._api_json("/download", {"file_id": result_id}, method="POST", token=token)
        file_url = str(payload.get("link") or "").strip()
        filename = str(payload.get("file_name") or payload.get("filename") or "").strip()
        if not file_url:
            raise ValueError("OpenSubtitles API 未返回下载链接")
        name, content, final_url = OnlineDirectDownloader(use_proxy=self.fetcher.use_proxy).get_bytes(file_url)
        logger.info(
            "[SubtitleManualUpload] OpenSubtitles API 字幕下载完成 host=%s size=%s",
            _host(final_url),
            len(content),
        )
        return filename or name or f"opensubtitles-{result_id}.srt", content

    def _auth_token(self) -> str:
        if self._session_token:
            return self._session_token
        if not self.username or not self.password:
            raise ValueError("OpenSubtitles 下载需要在插件设置中填写 OpenSubtitles 用户名和密码")
        payload = self._api_json(
            "/login",
            {"username": self.username, "password": self.password},
            method="POST",
            allow_without_token=True,
        )
        token = str(payload.get("token") or "").strip()
        if not token:
            raise ValueError("OpenSubtitles 登录未返回 token")
        self._session_token = token
        return token

    def _api_json(
        self,
        path: str,
        params: Dict[str, Any],
        *,
        method: str = "GET",
        token: str = "",
        allow_without_token: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.api_url}{path}"
        data = None
        headers = {
            "Api-Key": self.api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif method.upper() == "POST" and not allow_without_token and path != "/login":
            raise ValueError("OpenSubtitles 下载接口缺少登录认证 token")
        if method.upper() == "GET":
            query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
            if query:
                url = f"{url}?{query}"
        else:
            data = json.dumps({key: value for key, value in params.items() if value not in {None, ""}}).encode("utf-8")
        handlers = []
        proxies = getattr(settings, "PROXY", None) if self.fetcher.use_proxy else None
        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))
        opener = urllib.request.build_opener(*handlers)
        last_error: Optional[Exception] = None
        raw = b""
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
                with opener.open(request, timeout=40) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as exc:
                detail = _decode_bytes(exc.read()[:500], exc.headers.get_content_charset())
                raise ValueError(f"OpenSubtitles API 请求失败 HTTP {exc.code}: {_compact_error_message(detail)}") from exc
            except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
                last_error = exc
                if attempt < 2 and _is_retryable_network_error(exc):
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break
        if not raw and last_error:
            raise ValueError(_format_network_error(self.api_url, last_error)) from last_error
        try:
            payload = json.loads(_decode_bytes(raw, None) or "{}")
        except Exception as exc:
            raise ValueError("OpenSubtitles API 返回内容不是 JSON") from exc
        if isinstance(payload, dict) and payload.get("message") and payload.get("status") not in {200, "200", None}:
            raise ValueError(f"OpenSubtitles API 返回错误: {payload.get('message')}")
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _subtitle_title(attrs: Dict[str, Any], file_info: Dict[str, Any]) -> str:
        for key in ("release", "feature_details", "url"):
            value = attrs.get(key)
            if isinstance(value, dict):
                for subkey in ("title", "movie_name", "name"):
                    text = re.sub(r"\s+", " ", html.unescape(str(value.get(subkey) or ""))).strip()
                    if text:
                        return text
            else:
                text = re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()
                if text and not text.startswith("http"):
                    return text
        for key in ("file_name", "cd_number"):
            text = re.sub(r"\s+", " ", html.unescape(str(file_info.get(key) or ""))).strip()
            if text:
                return text
        return "OpenSubtitles Subtitle"
