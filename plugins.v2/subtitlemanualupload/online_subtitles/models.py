from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class OnlineSubtitleResult:
    provider: str
    result_id: str
    title: str
    page_url: str
    download_url: str = ""
    language: str = ""
    format: str = ""
    season: int = 0
    episode: int = 0
    score: int = 0
    source: str = ""
    note: str = ""
    downloadable: bool = True
    language_category: str = ""
    provider_label: str = ""
    requires_captcha: bool = False
    captcha_hint: str = ""
    download_steps: str = ""
    result_years: Optional[List[int]] = None
    match_year: int = 0
    relevance_status: str = ""
    region_bucket: str = ""
    query_plan: str = ""
    identity_status: str = ""
    reject_reason: str = ""
    match_detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        from .language import _language_category_from_text

        return {
            "provider": self.provider,
            "provider_label": self.provider_label or self.source or self.provider,
            "result_id": self.result_id,
            "title": self.title,
            "page_url": self.page_url,
            "download_url": self.download_url,
            "language": self.language,
            "format": self.format,
            "season": self.season,
            "episode": self.episode,
            "score": self.score,
            "source": self.source,
            "note": self.note,
            "downloadable": self.downloadable,
            "language_category": self.language_category or _language_category_from_text(self.language),
            "requires_captcha": self.requires_captcha,
            "captcha_hint": self.captcha_hint,
            "download_steps": self.download_steps,
            "result_years": self.result_years or [],
            "match_year": self.match_year,
            "relevance_status": self.relevance_status,
            "region_bucket": self.region_bucket,
            "query_plan": self.query_plan,
            "identity_status": self.identity_status,
            "reject_reason": self.reject_reason,
            "match_detail": self.match_detail,
        }


@dataclass
class HtmlLink:
    href: str
    text: str


class CaptchaRequiredError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        verify_url: str = "",
        captcha_image: str = "",
        captcha_hint: str = "",
    ):
        super().__init__(message)
        self.provider = provider
        self.verify_url = verify_url
        self.captcha_image = captcha_image
        self.captcha_hint = captcha_hint or message

    def to_payload(self) -> Dict[str, Any]:
        return {
            "captcha_required": True,
            "provider": self.provider,
            "message": str(self),
            "verify_url": self.verify_url,
            "captcha_image": self.captcha_image,
            "captcha_hint": self.captcha_hint,
        }
