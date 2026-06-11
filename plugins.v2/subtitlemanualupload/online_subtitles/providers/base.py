from __future__ import annotations

from ..common import *  # noqa: F401,F403

class BaseSubtitleProvider:
    provider_id = ""
    display_name = ""
    default_root_url = ""

    def __init__(self, fetcher: OnlinePageClient, root_url: str = ""):
        self.fetcher = fetcher
        self.root_url = normalize_root_url(root_url, self.default_root_url)

    def status(self) -> Dict[str, Any]:
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "available": True,
            "message": "使用 API 自动搜索",
            "manual_only": False,
            "root_url": self.root_url,
            "host": _host(self.root_url),
        }

    def manual_url(self, keyword: str) -> str:
        raise NotImplementedError

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        raise NotImplementedError

    def search_all(self, keywords: List[str], targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        for keyword in keywords:
            found = self.search(keyword, targets, scope)
            if found:
                return found
        return []

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        download_url = result.get("download_url") or result.get("page_url")
        if not download_url:
            raise ValueError("没有可下载链接")
        filename, content, final_url = self.fetcher.get_bytes(download_url, referer=result.get("page_url") or "")
        if self._looks_like_html(content, filename):
            raise ValueError(f"{self.display_name} 返回了网页而不是字幕文件，请尝试手动搜索")
        logger.info(
            "[SubtitleManualUpload] 在线字幕下载完成 provider=%s final_host=%s size=%s",
            self.provider_id,
            _host(final_url),
            len(content),
        )
        return filename or self._safe_download_name(result), content

    @staticmethod
    def _looks_like_html(content: bytes, filename: str = "") -> bool:
        return _looks_like_html_bytes(content, filename)

    def _safe_download_name(self, result: Dict[str, Any]) -> str:
        title = re.sub(r"[\\/:*?\"<>|]+", " ", result.get("title") or "subtitle").strip()
        return f"{title or self.provider_id}.zip"


class ManualSubtitleProvider(BaseSubtitleProvider):
    def __init__(self, fetcher: OnlinePageClient, provider_id: str, display_name: str, root_url: str, url_builder):
        self.provider_id = provider_id
        self.display_name = display_name
        self.default_root_url = root_url
        self._url_builder = url_builder
        super().__init__(fetcher, root_url=root_url)

    def status(self) -> Dict[str, Any]:
        status = super().status()
        status["message"] = "仅保留手动跳转"
        status["manual_only"] = True
        return status

    def manual_url(self, keyword: str) -> str:
        return self._url_builder(self.root_url, keyword)

    def search(self, keyword: str, targets: List[Dict[str, Any]], scope: str) -> List[OnlineSubtitleResult]:
        raise ValueError(f"{self.display_name} 是手动跳转源，请使用右侧手动链接")

    def download(self, result: Dict[str, Any], captcha_code: str = "") -> Tuple[str, bytes]:
        raise ValueError(f"{self.display_name} 是手动跳转源，请手动下载字幕包后上传")


def _subhd_manual_url(root_url: str, keyword: str) -> str:
    return f"{root_url}/search/{quote(keyword)}"


def _zimuku_manual_url(root_url: str, keyword: str) -> str:
    chost = _host(root_url) or "zmk.pw"
    return f"{root_url}/search?q={quote(keyword)}&chost={quote(chost)}"
