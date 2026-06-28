from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_AUTO_LANGUAGE_PRIORITY = ["bilingual", "chi", "cht", "eng"]
DEFAULT_AUTO_FORMAT_PRIORITY = [".ass", ".srt", ".ssa", ".vtt"]

LANGUAGE_SUFFIX_ALIASES = {
    "zh": "chi",
    "zh-hans": "chi",
    "zh_hans": "chi",
    "zh-cn": "chi",
    "zh_cn": "chi",
    "zh-hant": "cht",
    "zh_hant": "cht",
    "zh-tw": "cht",
    "zh_tw": "cht",
    "chs": "chi",
    "cht": "cht",
    "tw": "cht",
    "hk": "cht",
    "zho": "chi",
    "cmn": "chi",
    "cn": "chi",
    "en": "eng",
    "ja": "jpn",
    "jp": "jpn",
    "ko": "kor",
    "kr": "kor",
    "fr": "fre",
    "fra": "fre",
    "de": "ger",
    "deu": "ger",
    "es": "spa",
    "pt": "por",
    "it": "ita",
    "ru": "rus",
}

LANGUAGE_LABELS = {
    "chi": "中文",
    "cht": "繁中",
    "eng": "英文",
    "jpn": "日文",
    "kor": "韩文",
    "fre": "法文",
    "spa": "西文",
    "ger": "德文",
    "por": "葡文",
    "ita": "意文",
    "rus": "俄文",
}


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def decode_preview_bytes(raw_bytes: bytes) -> str:
    if not raw_bytes:
        return ""
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def normalize_language_suffix(value: Any) -> str:
    suffix = normalize_text(value).strip().lower()
    if not suffix:
        return "und"
    if any(separator in suffix for separator in ("&", "+", "/", ",")):
        parts = []
        for part in re.split(r"[&+/,]+", suffix):
            normalized = LANGUAGE_SUFFIX_ALIASES.get(part.strip(), part.strip())
            normalized = {"jpn": "jp", "kor": "kr"}.get(normalized, normalized)
            normalized = re.sub(r"[^a-z0-9-]", "", normalized)
            if normalized and normalized not in parts:
                parts.append(normalized)
        return "&".join(parts) or "und"
    suffix = LANGUAGE_SUFFIX_ALIASES.get(suffix, suffix)
    return re.sub(r"[^a-z0-9-]", "", suffix) or "und"


def language_suffix_from_filename(file_name: str, subtitle_exts: Iterable[str]) -> Dict[str, str]:
    name = Path(normalize_text(file_name)).name
    ext = Path(name).suffix.lower()
    if ext not in set(subtitle_exts):
        return {"suffix": "und", "label": "未知"}

    stem = name[: -len(ext)]
    tokens = [
        re.sub(r"[^a-z0-9&+/,_-]", "", token.lower()).strip("_-")
        for token in re.split(r"[\s.\[\](){}]+", stem)
    ]
    aliases = {
        **LANGUAGE_SUFFIX_ALIASES,
        "chi": "chi",
        "eng": "eng",
        "jpn": "jpn",
        "kor": "kor",
        "english": "eng",
        "chinese": "chi",
        "japanese": "jpn",
        "korean": "kor",
    }
    ignored_tail_tokens = {"forced", "sdh", "hi", "cc", "default", "full", "signs", "songs", "commentary"}
    found: List[str] = []
    for token in reversed([item for item in tokens if item]):
        normalized = normalize_language_suffix(token) if any(sep in token for sep in ("&", "+", "/", ",")) else aliases.get(token, "")
        if normalized and normalized != "und":
            found.append(normalized)
            continue
        if token in ignored_tail_tokens and not found:
            continue
        if found:
            break
        return {"suffix": "und", "label": "未知"}

    if not found:
        return {"suffix": "und", "label": "未知"}

    suffix = normalize_language_suffix("&".join(reversed(found)))
    if suffix == "chi&eng":
        label = "中英双语"
    elif suffix == "chi&jp":
        label = "中日双语"
    elif suffix == "chi&kr":
        label = "中韩双语"
    else:
        label = LANGUAGE_LABELS.get(suffix, "未知")
    return {"suffix": suffix, "label": label}


def detect_language_profile(file_name: str, raw_bytes: bytes, subtitle_exts: Iterable[str]) -> Dict[str, str]:
    lowered = file_name.lower()
    filename_suffix = language_suffix_from_filename(file_name, subtitle_exts)
    if filename_suffix["suffix"] != "und":
        return filename_suffix

    preview = decode_preview_bytes(raw_bytes[:16000])
    has_cjk = len(re.findall(r"[\u4e00-\u9fff]", preview)) >= 20
    has_kana = len(re.findall(r"[\u3040-\u30ff]", preview)) >= 20
    has_hangul = len(re.findall(r"[\uac00-\ud7af]", preview)) >= 20
    has_ascii = len(re.findall(r"[A-Za-z]{3,}", preview)) >= 20
    has_chinese_name = bool(
        re.search(r"(^|[\s._\-\[\]()])(?:zh|chi|chs|cht|zho|cmn)(?=$|[\s._\-\[\]()])", lowered)
        or any(token in lowered for token in ("中英", "中日", "中韩", "中文", "中字", "双语", "bilingual"))
    )
    has_english_name = bool(
        re.search(r"(^|[\s._\-\[\]()])(?:en|eng)(?=$|[\s._\-\[\]()])", lowered)
        or any(token in lowered for token in ("english", "英文", "英语", "中英"))
    )
    has_japanese_name = bool(
        re.search(r"(^|[\s._\-\[\]()])(?:ja|jp|jpn)(?=$|[\s._\-\[\]()])", lowered)
        or any(token in lowered for token in ("japanese", "日文", "日语", "中日"))
    )
    has_korean_name = bool(
        re.search(r"(^|[\s._\-\[\]()])(?:ko|kr|kor)(?=$|[\s._\-\[\]()])", lowered)
        or any(token in lowered for token in ("korean", "韩文", "韩语", "中韩"))
    )

    suffix = "und"
    label = "未知"

    if (has_chinese_name or has_cjk) and (has_japanese_name or has_kana):
        suffix = "chi&jp"
        label = "中日双语"
    elif (has_chinese_name or has_cjk) and (has_korean_name or has_hangul):
        suffix = "chi&kr"
        label = "中韩双语"
    elif has_chinese_name and (has_english_name or has_ascii):
        suffix = "chi&eng"
        label = "中英双语"
    elif any(token in lowered for token in ("zh-hant", "zh_tw", "zh-tw", "cht", "繁体", "繁中", "big5")) or re.search(
        r"(^|[\s._\-\[\]()])(?:tw|hk)(?=$|[\s._\-\[\]()])",
        lowered,
    ):
        suffix = "cht"
        label = "繁中"
    elif any(token in lowered for token in ("zh-hans", "zh_cn", "zh-cn", "chs", "简体", "简中", "gb")):
        suffix = "chi"
        label = "简中"
    elif any(token in lowered for token in ("zh", "chi", "zho", "cmn", "中文", "中字")) or (has_cjk and not has_kana):
        suffix = "chi"
        label = "中文"
    elif any(token in lowered for token in ("jpn", "japanese", "日文", "日语", ".ja.")) or has_kana:
        suffix = "jpn"
        label = "日文"
    elif any(token in lowered for token in ("kor", "korean", "韩文", "韩语", ".ko.")) or has_hangul:
        suffix = "kor"
        label = "韩文"
    elif any(token in lowered for token in ("eng", "english", "英文", "英语", ".en.")) or has_ascii:
        suffix = "eng"
        label = "英文"
    elif any(token in lowered for token in ("fre", "fra", "french", "français", ".fr.")):
        suffix = "fre"
        label = "法文"
    elif any(token in lowered for token in ("spa", "spanish", "español", ".es.")):
        suffix = "spa"
        label = "西文"
    elif any(token in lowered for token in ("ger", "deu", "german", "deutsch", ".de.")):
        suffix = "ger"
        label = "德文"
    elif any(token in lowered for token in ("por", "portuguese", "português", ".pt.")):
        suffix = "por"
        label = "葡文"
    elif any(token in lowered for token in ("ita", "italian", "italiano", ".it.")):
        suffix = "ita"
        label = "意文"
    elif any(token in lowered for token in ("rus", "russian", ".ru.")):
        suffix = "rus"
        label = "俄文"

    if suffix == "chi" and has_ascii:
        suffix = "chi&eng"
        label = f"{label}/双语"

    return {
        "suffix": normalize_language_suffix(suffix),
        "label": label,
    }


def is_chinese_language_suffix(suffix: Any) -> bool:
    return any(part in {"chi", "cht"} for part in normalize_language_suffix(suffix).split("&"))


def auto_language_bucket(suffix: Any) -> str:
    parts = [item for item in normalize_language_suffix(suffix).split("&") if item]
    if any(item in {"chi", "cht"} for item in parts) and any(item not in {"chi", "cht"} for item in parts):
        return "bilingual"
    if "chi" in parts:
        return "chi"
    if "cht" in parts:
        return "cht"
    if any(item in {"eng", "en"} for item in parts):
        return "eng"
    return parts[0] if parts else "und"


def auto_subtitle_sort_key(
    item: Dict[str, Any],
    *,
    language_priority: Optional[List[str]] = None,
    format_priority: Optional[List[str]] = None,
) -> Tuple[int, int, int, str]:
    language_bucket = auto_language_bucket(item.get("language_suffix"))
    language_order = list(language_priority or DEFAULT_AUTO_LANGUAGE_PRIORITY)
    format_order = list(format_priority or DEFAULT_AUTO_FORMAT_PRIORITY)
    try:
        language_rank = language_order.index(language_bucket)
    except ValueError:
        language_rank = len(language_order)
    ext = normalize_text(item.get("ext")).lower()
    try:
        format_rank = format_order.index(ext)
    except ValueError:
        format_rank = len(format_order)
    bilingual_bonus = 0 if language_bucket == "bilingual" else 1
    return (language_rank, format_rank, bilingual_bonus, normalize_text(item.get("source_name")).lower())


def autosub_lang_from_suffix(suffix: Any) -> str:
    normalized = normalize_language_suffix(suffix)
    first = next((part for part in normalized.split("&") if part and part not in {"chi", "cht"}), "")
    return {
        "eng": "en",
        "en": "en",
        "jpn": "ja",
        "jp": "ja",
        "kor": "ko",
        "kr": "ko",
        "fre": "fr",
        "fra": "fr",
        "spa": "es",
        "ger": "de",
        "deu": "de",
        "por": "pt",
        "ita": "it",
        "rus": "ru",
    }.get(first, first or "en")


def normalize_auto_language_key(value: Any) -> str:
    text = normalize_text(value).lower()
    aliases = {
        "双语": "bilingual",
        "bilingual": "bilingual",
        "chi&eng": "bilingual",
        "chi&jp": "bilingual",
        "chi&kr": "bilingual",
        "简中": "chi",
        "简体": "chi",
        "中文": "chi",
        "zh": "chi",
        "chs": "chi",
        "chi": "chi",
        "繁中": "cht",
        "繁体": "cht",
        "zh-tw": "cht",
        "cht": "cht",
        "英文": "eng",
        "英语": "eng",
        "en": "eng",
        "eng": "eng",
    }
    return aliases.get(text, normalize_language_suffix(text))


def normalize_auto_language_priority(
    value: Any,
    default_priority: Optional[List[str]] = None,
) -> List[str]:
    raw_items = value
    if isinstance(raw_items, str):
        raw_items = re.split(r"[\s,，/|]+", raw_items)
    if not isinstance(raw_items, list):
        raw_items = []
    result: List[str] = []
    for item in raw_items:
        key = normalize_auto_language_key(item)
        if key and key != "und" and key not in result:
            result.append(key)
    for item in list(default_priority or DEFAULT_AUTO_LANGUAGE_PRIORITY):
        if item not in result:
            result.append(item)
    return result


def normalize_auto_format_priority(
    value: Any,
    subtitle_exts: Iterable[str],
    default_priority: Optional[List[str]] = None,
) -> List[str]:
    raw_items = value
    if isinstance(raw_items, str):
        raw_items = re.split(r"[\s,，/|]+", raw_items)
    if not isinstance(raw_items, list):
        raw_items = []
    result: List[str] = []
    subtitle_ext_set = set(subtitle_exts)
    for item in raw_items:
        ext = normalize_text(item).lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext in subtitle_ext_set and ext not in result:
            result.append(ext)
    for item in list(default_priority or DEFAULT_AUTO_FORMAT_PRIORITY):
        if item not in result:
            result.append(item)
    for item in sorted(subtitle_ext_set):
        if item not in result:
            result.append(item)
    return result
