from __future__ import annotations

import re
from typing import Any


def _guess_language_label(value: str) -> str:
    text = (value or "").lower()
    if any(key in text for key in ["简英", "中英", "双语", "chs&eng", "chi_eng", "zh&en"]):
        return "简英双语"
    if any(key in text for key in ["繁", "cht", "zh-hant", "zh-tw"]) or re.search(
        r"(^|[\s._\-\[\]()])(?:tw|hk)(?=$|[\s._\-\[\]()])",
        text,
    ):
        return "繁体中文"
    if any(key in text for key in ["简", "chs", "zh-hans", "中文", "chinese"]):
        return "简体中文"
    if any(key in text for key in ["eng", "english"]):
        return "英文"
    if any(key in text for key in ["日文", "日语", "jpn", "japanese"]) or re.search(
        r"(^|[\s._\-\[\]()])ja(?=$|[\s._\-\[\]()])",
        text,
    ):
        return "日文"
    return ""


def _language_category_from_text(value: str) -> str:
    text = (value or "").lower()
    if any(
        key in text
        for key in [
            "中文",
            "简体",
            "繁体",
            "简英",
            "中英",
            "双语",
            "chinese",
            "chs",
            "cht",
            "chi",
            "zho",
            "cmn",
            "zh-cn",
            "zh-tw",
            "zh-ca",
            "zh-hans",
            "zh-hant",
        ]
    ) or re.search(r"(^|[\s._\-\[\]()])(?:zh|ze)(?=$|[\s._\-\[\]()])", text):
        return "chinese"
    if any(key in text for key in ["英文", "english", "eng"]):
        return "english"
    if any(key in text for key in ["日文", "日语", "japanese", "jpn"]):
        return "japanese"
    if any(key in text for key in ["韩文", "韩语", "korean", "kor"]):
        return "other"
    if re.search(r"(^|[\s._\-\[\]()])en(?=$|[\s._\-\[\]()])", text):
        return "english"
    if re.search(r"(^|[\s._\-\[\]()])ja(?=$|[\s._\-\[\]()])", text):
        return "japanese"
    return "other"


def _language_label_from_category(category: str, raw_language: str = "") -> str:
    raw = (raw_language or "").lower()
    if category == "chinese":
        if any(key in raw for key in ["zh-tw", "zh-hant", "cht"]):
            return "繁体中文"
        if raw == "ze":
            return "中英双语"
        return "简体中文"
    if category == "english":
        return "英文"
    if category == "japanese":
        return "日文"
    return raw_language or "其他"


def _language_priority(item: Any) -> int:
    category = item.language_category or _language_category_from_text(f"{item.language} {item.title} {item.note}")
    return {
        "chinese": 40,
        "english": 30,
        "japanese": 20,
        "korean": 20,
        "other": 10,
    }.get(category, 0)


def _guess_subtitle_format(value: str) -> str:
    formats = []
    for ext in [".ass", ".srt", ".ssa", ".vtt", ".sub", ".zip", ".rar"]:
        if ext in (value or "").lower():
            formats.append(ext.removeprefix(".").upper())
    return " / ".join(formats)


__all__ = [name for name in globals() if not name.startswith("__")]
