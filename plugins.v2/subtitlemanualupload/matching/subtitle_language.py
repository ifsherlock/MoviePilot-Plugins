from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .subtitle_formats import is_bitmap_subtitle


DEFAULT_AUTO_LANGUAGE_PRIORITY = ["chi&eng", "chi&jp", "chi&kr", "other_bilingual", "chi", "cht", "eng"]
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

LANGUAGE_PAIR_LABELS = {
    "chi&eng": "中英双语",
    "chi&jp": "中日双语",
    "chi&kr": "中韩双语",
    "cht&eng": "中英双语",
}

LEGACY_BILINGUAL_BUCKETS = ["chi&eng", "chi&jp", "chi&kr", "other_bilingual"]
LANGUAGE_PAIR_ALIASES = {
    "eng": "eng",
    "en": "eng",
    "english": "eng",
    "jpn": "jp",
    "jap": "jp",
    "japanese": "jp",
    "ja": "jp",
    "jp": "jp",
    "kor": "kr",
    "korean": "kr",
    "ko": "kr",
    "kr": "kr",
    "fre": "fre",
    "fra": "fre",
    "french": "fre",
    "fr": "fre",
    "spa": "spa",
    "spanish": "spa",
    "es": "spa",
    "ger": "ger",
    "deu": "ger",
    "german": "ger",
    "de": "ger",
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
    label = LANGUAGE_PAIR_LABELS.get(suffix) or LANGUAGE_LABELS.get(suffix, "未知")
    return {"suffix": suffix, "label": label}


def detect_language_profile(file_name: str, raw_bytes: bytes, subtitle_exts: Iterable[str]) -> Dict[str, str]:
    lowered = file_name.lower()
    filename_suffix = language_suffix_from_filename(file_name, subtitle_exts)
    if filename_suffix["suffix"] != "und":
        return filename_suffix

    preview = "" if is_bitmap_subtitle(file_name, raw_bytes) else decode_preview_bytes(raw_bytes[:16000])
    preview = _subtitle_dialogue_text(file_name, preview)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", preview))
    kana_count = len(re.findall(r"[\u3040-\u30ff]", preview))
    hangul_count = len(re.findall(r"[\uac00-\ud7af]", preview))
    has_cjk = cjk_count >= 20
    has_kana = kana_count >= 20
    has_hangul = hangul_count >= 20
    # Kanji density cannot distinguish Chinese from Japanese. Look for separate
    # Chinese dialogue or particles that are not part of normal Japanese text.
    chinese_lines = "\n".join(
        line for line in preview.splitlines()
        if not re.search(r"[\u3040-\u30ff\uac00-\ud7af]", line)
    )
    has_chinese_content = has_cjk and (
        not has_kana
        or len(re.findall(r"[\u4e00-\u9fff]", chinese_lines)) >= 20
        or len(re.findall(r"[这這们們吗嗎呢]", preview)) >= 3
    )
    has_ascii = len(re.findall(r"\b[A-Za-z]{3,}\b", preview)) >= 20
    has_chinese_name = bool(
        re.search(r"(^|[\s._\-\[\]()])(?:zh|chi|chs|cht|zho|cmn)(?=$|[\s._\-\[\]()])", lowered)
        or any(token in lowered for token in ("中英", "中日", "中韩", "中文", "中字"))
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

    if (has_chinese_name or has_chinese_content) and (has_japanese_name or has_kana):
        suffix = "chi&jp"
        label = "中日双语"
    elif (has_chinese_name or has_chinese_content) and (has_korean_name or has_hangul):
        suffix = "chi&kr"
        label = "中韩双语"
    elif (has_chinese_name or (has_cjk and not has_kana and not has_hangul)) and (has_english_name or has_ascii):
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
    elif any(token in lowered for token in ("zh", "chi", "zho", "cmn", "中文", "中字")) or (has_cjk and not has_kana and not has_hangul):
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


def _subtitle_dialogue_text(file_name: str, text: str) -> str:
    """Remove common subtitle metadata so format headers cannot imply languages."""
    if Path(file_name).suffix.lower() in {".ass", ".ssa"}:
        in_events = False
        dialogue = []
        field_count = 10
        text_index = 9
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower() == "[events]":
                in_events = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_events = False
                continue
            if in_events and stripped.lower().startswith("format:"):
                fields = [field.strip().lower() for field in stripped.split(":", 1)[1].split(",")]
                if "text" in fields:
                    field_count = len(fields)
                    text_index = fields.index("text")
            elif in_events and stripped.lower().startswith("dialogue:"):
                payload = stripped.split(":", 1)[1]
                fields = payload.split(",", field_count - 1)
                if len(fields) == field_count:
                    dialogue.append(fields[text_index])
        text = "\n".join(dialogue)
        text = re.sub(r"\\[Nn]", "\n", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", " ", text)
    text = re.sub(r"(?m)^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{2,3}\s*-->.*$", " ", text)
    text = re.sub(r"\{[^}]*\}|<[^>]*>", " ", text)
    return text


def is_chinese_language_suffix(suffix: Any) -> bool:
    return any(part in {"chi", "cht"} for part in normalize_language_suffix(suffix).split("&"))


def target_has_chinese_subtitle(
    target: Dict[str, Any],
    *,
    is_chinese_language_suffix_func: Callable[[Any], bool] = is_chinese_language_suffix,
) -> bool:
    subtitles = target.get("subtitles") or []
    if any(
        is_chinese_language_suffix_func((item or {}).get("language_suffix") or (item or {}).get("language"))
        for item in subtitles
        if isinstance(item, dict)
    ):
        return True
    embedded_subtitles = target.get("embedded_subtitles") or []
    return any(
        bool((item or {}).get("is_chinese"))
        or is_chinese_language_suffix_func((item or {}).get("language_suffix") or (item or {}).get("language"))
        for item in embedded_subtitles
        if isinstance(item, dict)
    )


def auto_target_has_chinese_subtitle(
    entry: Dict[str, Any],
    target: Dict[str, Any],
    *,
    subtitle_inventory: Any,
    is_chinese_language_suffix_func: Callable[[Any], bool] = is_chinese_language_suffix,
    language_priority: Optional[List[str]] = None,
    strict: bool = False,
) -> bool:
    if strict:
        if target_has_preferred_subtitle(target, language_priority or []):
            return True
        embedded_subtitles = subtitle_inventory.embedded_subtitle_tracks_for_target(entry)
        if embedded_subtitles:
            target["has_embedded_subtitle"] = True
            target["embedded_subtitle_count"] = len(embedded_subtitles)
            target["embedded_subtitles"] = embedded_subtitles
        return target_has_preferred_subtitle(target, language_priority or [])
    if target_has_chinese_subtitle(target, is_chinese_language_suffix_func=is_chinese_language_suffix_func):
        return True
    embedded_subtitles = subtitle_inventory.embedded_subtitle_tracks_for_target(entry)
    if embedded_subtitles:
        target["has_embedded_subtitle"] = True
        target["embedded_subtitle_count"] = len(embedded_subtitles)
        target["embedded_subtitles"] = embedded_subtitles
    return target_has_chinese_subtitle(target, is_chinese_language_suffix_func=is_chinese_language_suffix_func)


def auto_language_bucket(suffix: Any) -> str:
    parts = [item for item in normalize_language_suffix(suffix).split("&") if item]
    if len(parts) == 2 and sum(item in {"chi", "cht"} for item in parts) == 1:
        other = next(item for item in parts if item not in {"chi", "cht"})
        if other in {"eng", "en"}:
            return "chi&eng"
        if other in {"jp", "jpn"}:
            return "chi&jp"
        if other in {"kr", "kor"}:
            return "chi&kr"
        return "other_bilingual"
    if len(parts) > 1:
        return "und"
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
    language_order = normalize_auto_language_priority(language_priority)
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
    bilingual_bonus = 0 if "&" in language_bucket else 1
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
        "中英双语": "chi&eng",
        "简英双语": "chi&eng",
        "繁英双语": "cht&eng",
        "中日双语": "chi&jp",
        "中韩双语": "chi&kr",
        "其他中外双语": "other_bilingual",
    }
    normalized = aliases.get(text, text if text == "other_bilingual" else normalize_language_suffix(text))
    if "&" in normalized:
        return auto_language_bucket(normalized)
    return normalized


def normalize_auto_language_priority(
    value: Any,
    default_priority: Optional[List[str]] = None,
) -> List[str]:
    defaults = list(DEFAULT_AUTO_LANGUAGE_PRIORITY if default_priority is None else default_priority)
    if value is None:
        return defaults
    raw_items = value
    if isinstance(raw_items, str):
        raw_items = re.split(r"[\s,，/|]+", raw_items)
    if not isinstance(raw_items, list):
        return []
    result: List[str] = []
    for item in raw_items:
        key = normalize_auto_language_key(item)
        keys = LEGACY_BILINGUAL_BUCKETS if key == "bilingual" else [key]
        for normalized in keys:
            if normalized and normalized != "und" and normalized not in result:
                result.append(normalized)
    return result


def language_matches_preferences(suffix: Any, priority: Optional[List[str]]) -> bool:
    bucket = auto_language_bucket(suffix)
    return bucket != "und" and bucket in normalize_auto_language_priority(priority)


def auto_candidate_language_bucket(item: Dict[str, Any]) -> str:
    title = normalize_text(item.get("title"))
    title_bucket = auto_language_bucket(language_profile_from_text(title)["suffix"])
    if "&" in title_bucket or title_bucket == "other_bilingual":
        return title_bucket
    language_bucket = auto_language_bucket(language_profile_from_text(item.get("language"))["suffix"])
    if "&" in language_bucket or language_bucket == "other_bilingual":
        return language_bucket
    # Provider language fields are coarse: a Chinese result can contain Chinese-English subtitles.
    return "und"


def auto_candidate_language_rank(item: Dict[str, Any], priority: Optional[List[str]]) -> Tuple[int, int]:
    bucket = auto_candidate_language_bucket(item)
    language_order = normalize_auto_language_priority(priority)
    if bucket in language_order:
        return 0, language_order.index(bucket)
    return (1, len(language_order)) if bucket == "und" else (2, len(language_order))


def auto_rank_candidates(
    candidates: List[Dict[str, Any]], priority: Optional[List[str]], *, strict: bool
) -> List[Dict[str, Any]]:
    selected = normalize_auto_language_priority(priority)
    if not selected:
        return [] if strict else candidates
    allowed = []
    for item in candidates:
        bucket = auto_candidate_language_bucket(item)
        if not strict or bucket in selected or bucket == "und":
            allowed.append(item)
    return sorted(allowed, key=lambda item: auto_candidate_language_rank(item, selected))


def target_has_preferred_subtitle(target: Dict[str, Any], language_priority: Optional[List[str]]) -> bool:
    subtitles = [*(target.get("subtitles") or []), *(target.get("embedded_subtitles") or [])]
    return any(
        isinstance(item, dict)
        and language_matches_preferences(item.get("language_suffix") or item.get("language"), language_priority)
        for item in subtitles
    )


def language_profile_from_text(value: Any) -> Dict[str, str]:
    text = normalize_text(value).lower()
    languages = set()
    explicit_chinese = False
    explicit_traditional = False
    for marker in ("中英", "简英", "繁英", "中日", "中韩", "中法"):
        if marker in text:
            languages.add("eng" if marker in {"中英", "简英", "繁英"} else {"中日": "jp", "中韩": "kr", "中法": "fre"}[marker])
            explicit_chinese = True
            explicit_traditional = marker == "繁英"
    if any(marker in text for marker in ("中文", "简体", "简中", "chinese", "chs", "cht", "zh-cn", "zh-hans", "zh-hant")):
        explicit_chinese = True
        explicit_traditional = explicit_traditional or any(marker in text for marker in ("繁体", "繁中", "cht", "zh-hant"))
    if explicit_chinese:
        languages.add("cht" if explicit_traditional else "chi")

    token_text = re.sub(r"(?<=[a-z])[_+/,]+(?=[a-z])", "&", text)
    token_text = re.sub(r"(?<=chinese)-(?=english)|(?<=english)-(?=chinese)", "&", token_text)
    for token in re.findall(r"(?<![a-z0-9-])(?:zh-hans|zh-hant|zh-cn|zh-tw|chs|cht|zho|cmn|chi|zh|english|eng|en|jpn|jap|japanese|ja|jp|kor|korean|ko|kr|fre|fra|french|fr|spa|spanish|es|ger|deu|german|de)(?![a-z0-9-])", token_text):
        if token in {"zh-hans", "zh-cn", "chs", "zho", "cmn", "chi", "zh"}:
            languages.add("chi")
        elif token in {"zh-hant", "zh-tw", "cht"}:
            languages.add("cht")
        else:
            languages.add(LANGUAGE_PAIR_ALIASES.get(token, ""))
    languages.discard("")

    for marker, code in (("英文", "eng"), ("英语", "eng"), ("日文", "jp"), ("日语", "jp"), ("韩文", "kr"), ("韩语", "kr"), ("法文", "fre"), ("法语", "fre")):
        if marker in text:
            languages.add(code)
    if len(languages) == 1:
        suffix = next(iter(languages))
    elif len(languages) == 2 and any(item in {"chi", "cht"} for item in languages):
        suffix = "&".join(sorted(languages))
    else:
        suffix = "und"
    suffix = normalize_language_suffix(suffix)
    label = LANGUAGE_PAIR_LABELS.get(suffix) or LANGUAGE_LABELS.get(suffix, "未知")
    return {"suffix": suffix, "label": label}


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
