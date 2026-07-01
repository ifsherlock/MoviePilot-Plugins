from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List


OPENSUBTITLES_SEARCH_LANGUAGES = "zh-cn,zh-tw,ze,en,ja,ko"
GENERIC_TITLE_ALIAS_WORDS = {
    "arabic",
    "chinese",
    "danish",
    "dutch",
    "english",
    "french",
    "german",
    "italian",
    "italiano",
    "japanese",
    "korean",
    "mandarin",
    "portuguese",
    "russian",
    "spanish",
    "thai",
    "turkish",
    "vietnamese",
    "cantonese",
    "deutsch",
    "espanol",
    "español",
    "francais",
    "français",
    "nederlands",
    "portugues",
    "português",
    "finnish",
    "suomi",
    "turkce",
    "türkçe",
    "中文",
    "国语",
    "國語",
    "普通话",
    "普通話",
    "粤语",
    "粵語",
    "英文",
    "英语",
    "英語",
    "日文",
    "日语",
    "日語",
    "日本語",
    "韩文",
    "韓文",
    "韩语",
    "韓語",
}
GENERIC_TITLE_ALIAS_CODES = {
    "ar",
    "cn",
    "cmn",
    "da",
    "de",
    "en",
    "eng",
    "es",
    "fr",
    "it",
    "ita",
    "ja",
    "jpn",
    "ko",
    "kor",
    "pt",
    "ru",
    "th",
    "vi",
    "yue",
    "zh",
    "zh-cn",
    "zh-hans",
    "zh-hant",
    "zh-tw",
}
AMBIGUOUS_SINGLE_TITLE_TOKENS = {
    "zero",
    "life",
    "world",
    "another",
    "starting",
}


def build_search_keywords(media: Dict[str, Any], targets: List[Dict[str, Any]], scope: str) -> List[str]:
    title = _clean_keyword(media.get("title") or (targets[0].get("title") if targets else ""))
    year = _clean_keyword(media.get("year") or (targets[0].get("year") if targets else ""))
    media_type = media.get("media_type") or (targets[0].get("media_type") if targets else "")
    search_titles = _search_titles_by_region(media, targets)
    if title and title not in search_titles:
        search_titles.append(title)
    search_titles = _unique_keywords(search_titles)
    keywords: List[str] = []
    if media_type == "tv":
        seasons = sorted({int(target.get("season") or 0) for target in targets if int(target.get("season") or 0)})
        episodes = sorted({int(target.get("episode") or 0) for target in targets if int(target.get("episode") or 0)})
        if search_titles and seasons:
            season = seasons[0]
            if scope in {"season", "batch"} or len(episodes) > 1:
                for item in search_titles[:4]:
                    keywords.append(f"{item} S{season:02d}")
            elif episodes:
                episode = episodes[0]
                for item in search_titles[:4]:
                    keywords.append(f"{item} S{season:02d}E{episode:02d}")
        if not keywords:
            for target in targets[:3]:
                basename = _clean_tv_basename_keyword(target.get("basename") or target.get("filename"))
                if basename:
                    keywords.append(basename)
    elif search_titles:
        if year:
            keywords.extend([f"{item} {year}" for item in search_titles[:5]])
        keywords.extend(search_titles[:5])
    return _unique_keywords([item for item in keywords if item])


def _clean_tv_basename_keyword(value: Any) -> str:
    basename = _clean_keyword(value)
    if not basename:
        return ""
    basename = re.sub(r"\.(mkv|mp4|avi|ts|m2ts|mov|wmv|flv|webm)$", "", basename, flags=re.I)
    episode_match = re.search(r"(?i)(.*?)(S\d{1,2}E\d{1,3})\b", basename)
    if episode_match:
        prefix = re.sub(r"[\s._-]+$", "", episode_match.group(1)).strip()
        code = episode_match.group(2).upper()
        return f"{prefix} {code}".strip() if prefix else code
    season_match = re.search(r"(?i)(.*?)(S\d{1,2})\b", basename)
    if season_match:
        prefix = re.sub(r"[\s._-]+$", "", season_match.group(1)).strip()
        code = season_match.group(2).upper()
        return f"{prefix} {code}".strip() if prefix else code
    return basename


def _query_plan_for_keyword(keyword: str, targets: List[Dict[str, Any]]) -> Dict[str, str]:
    bucket = _region_bucket({}, targets)
    source = _query_source_for_keyword(keyword, targets)
    return {
        "region_bucket": bucket,
        "query_source": source,
        "subtitle_languages": OPENSUBTITLES_SEARCH_LANGUAGES,
        "label": (
            f"{_region_bucket_label(bucket)}区域 · {source} · "
            f"字幕语言 {OPENSUBTITLES_SEARCH_LANGUAGES}"
        ),
    }


def _search_titles_by_region(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    bucket = _region_bucket(media, targets)
    all_titles = _media_title_aliases(media, targets)
    explicit_english_titles = _explicit_title_values(
        media,
        targets,
        ["en_title", "title_en", "name_en", "english_title"],
    )
    chinese_titles = [item for item in all_titles if _contains_cjk(item)]
    japanese_titles = [item for item in all_titles if _contains_japanese(item)]
    korean_titles = [item for item in all_titles if _contains_korean(item)]
    original_titles = _original_titles(media, targets)

    native_titles = {
        "chinese": chinese_titles,
        "japanese": japanese_titles,
        "korean": korean_titles,
    }.get(bucket, [])
    ordered = [
        *explicit_english_titles,
        *original_titles,
        *native_titles,
        *chinese_titles,
        *japanese_titles,
        *korean_titles,
        *all_titles,
    ]
    return _unique_keywords(ordered)


def _explicit_title_values(media: Dict[str, Any], targets: List[Dict[str, Any]], fields: List[str]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in fields:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
    return _unique_keywords(values)


def _media_title_aliases(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in ["title", "name", "en_title", "original_title", "original_name", "title_en", "name_en", "english_title"]:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
        for field in ["aliases", "alternative_titles", "translations", "tmdb_aliases"]:
            values.extend(_alias_values(source.get(field)))
    return _unique_keywords(values)


def _region_bucket(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> str:
    sources = [media, *(targets or [])]
    languages = {_normalize_code(item) for source in sources for item in _as_list(source.get("original_language") if isinstance(source, dict) else "")}
    countries = {
        _normalize_code(item)
        for source in sources
        if isinstance(source, dict)
        for field in ["origin_country", "production_countries", "country", "area", "region"]
        for item in _as_list(source.get(field))
    }
    category_text = " ".join(
        str(source.get(field) or "")
        for source in sources
        if isinstance(source, dict)
        for field in ["category", "media_category", "library_name"]
    )
    if languages & {"zh", "cn", "cmn", "yue"} or countries & {"cn", "hk", "tw", "sg"} or re.search(r"华语|国产|港|台|中国|大陆", category_text):
        return "chinese"
    if languages & {"ja", "jp"} or countries & {"jp"} or re.search(r"日本|日剧|日漫|动画", category_text):
        return "japanese"
    if languages & {"ko", "kr"} or countries & {"kr", "kp"} or re.search(r"韩国|韩剧", category_text):
        return "korean"
    if languages & {"en"} or countries & {"us", "gb", "uk", "ca", "au", "nz", "ie"} or re.search(r"欧美|美剧|英剧", category_text):
        return "western"
    return "other"


def _region_bucket_label(bucket: str) -> str:
    return {
        "chinese": "华语",
        "western": "欧美",
        "japanese": "日本",
        "korean": "韩国",
        "other": "原始",
    }.get(bucket or "", "原始")


def _query_source_for_keyword(keyword: str, targets: List[Dict[str, Any]]) -> str:
    if not _clean_keyword(keyword):
        return "空查询词"
    aliases = _media_title_aliases({}, targets)
    original_titles = _original_titles({}, targets)
    english_titles = [item for item in aliases if _looks_english_title(item)]
    chinese_titles = [
        item
        for item in aliases
        if _contains_cjk(item) and not _contains_japanese(item) and not _contains_korean(item)
    ]
    for title in original_titles:
        if _strong_title_matches(title, keyword):
            return "原名查询"
    for title in english_titles:
        if _strong_title_matches(title, keyword):
            return "英文标题查询"
    for title in chinese_titles:
        if _strong_title_matches(title, keyword):
            return "中文标题查询"
    if _contains_japanese(keyword):
        return "日文查询"
    if _contains_korean(keyword):
        return "韩文查询"
    if _looks_english_title(keyword):
        return "英文弱兜底"
    if _contains_cjk(keyword):
        return "中文弱兜底"
    return "文件名查询"


def _title_aliases(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in [
            "title",
            "name",
            "en_title",
            "original_title",
            "original_name",
            "title_en",
            "name_en",
            "english_title",
            "filename",
            "basename",
        ]:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
        for field in ["aliases", "alternative_titles", "translations", "tmdb_aliases"]:
            values.extend(_alias_values(source.get(field)))
    return _unique_keywords(values)


def _original_titles(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in ["original_title", "original_name"]:
            value = _clean_title_alias(source.get(field))
            if value:
                values.append(value)
    return _unique_keywords(values)


def _alias_values(value: Any) -> List[str]:
    values: List[str] = []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = None
        if parsed is not None:
            return _alias_values(parsed)
        alias = _clean_title_alias(value)
        return [alias] if alias else []
    if isinstance(value, dict):
        if _looks_translation_metadata(value):
            values.extend(_alias_values(value.get("data")))
            for key in ["titles", "results", "translations", "alternative_titles", "aliases"]:
                values.extend(_alias_values(value.get(key)))
            return _unique_keywords(values)
        for key in ["title", "name", "english_name"]:
            values.extend(_alias_values(value.get(key)))
        for key in ["data", "titles", "results", "translations", "alternative_titles", "aliases"]:
            values.extend(_alias_values(value.get(key)))
        return _unique_keywords(values)
    if isinstance(value, list):
        for item in value:
            values.extend(_alias_values(item))
    return _unique_keywords(values)


def extract_title_aliases(value: Any) -> List[str]:
    return _alias_values(value)


def _looks_translation_metadata(value: Dict[str, Any]) -> bool:
    if "data" not in value:
        return False
    language_keys = {"iso_639_1", "iso_3166_1", "english_name"}
    return bool(language_keys & set(value.keys()))


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    text = str(value or "").strip()
    return [text] if text else []


def _normalize_code(value: Any) -> str:
    return re.sub(r"[^a-z]", "", str(value or "").lower())


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def _contains_japanese(value: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", value or ""))


def _contains_korean(value: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7af]", value or ""))


def _looks_english_title(value: str) -> bool:
    text = value or ""
    return bool(re.search(r"[a-zA-Z]", text)) and not _contains_cjk(text) and not _contains_japanese(text) and not _contains_korean(text)


def _is_cjk_text(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def _series_title_aliases(targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for target in targets or []:
        for field in ["title", "en_title", "original_title", "original_name", "title_en", "name_en", "english_title"]:
            value = _clean_title_alias(target.get(field))
            if value:
                values.append(value)
        for field in ["aliases", "alternative_titles", "translations", "tmdb_aliases"]:
            values.extend(_alias_values(target.get(field)))
    return _unique_keywords(values)


def _title_matches(needle: str, haystack: str) -> bool:
    clean_needle = _normalize_title_for_match(needle)
    clean_haystack = _normalize_title_for_match(haystack)
    if not clean_needle or not clean_haystack:
        return False
    if _is_cjk_text(clean_needle):
        if len(clean_needle) < 3:
            return False
        return clean_needle in clean_haystack or clean_haystack in clean_needle
    parts = [part for part in re.split(r"\s+", clean_needle.lower()) if len(part) >= 2]
    if not parts:
        return False
    haystack_lower = clean_haystack.lower()
    return all(part in haystack_lower for part in parts)


def _strong_title_matches(needle: str, haystack: str) -> bool:
    clean_needle = _normalize_title_for_match(needle)
    clean_haystack = _normalize_title_for_match(haystack)
    if not clean_needle or not clean_haystack:
        return False
    if _is_cjk_text(clean_needle):
        if len(clean_needle) < 3:
            return False
        return clean_needle in clean_haystack
    parts = [
        part
        for part in re.split(r"\s+", clean_needle.lower())
        if len(part) >= 3 and not re.fullmatch(r"(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2})", part)
    ]
    if not parts:
        return False
    matched = sum(1 for part in parts if re.search(rf"(?<![a-z0-9]){re.escape(part)}(?![a-z0-9])", clean_haystack.lower()))
    return matched == len(parts) if len(parts) <= 2 else matched >= max(2, len(parts) - 1)


def _is_ambiguous_single_title_alias(value: Any) -> bool:
    parts = [
        part
        for part in re.split(r"\s+", _normalize_title_for_match(value).lower())
        if len(part) >= 3 and not re.fullmatch(r"(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2})", part)
    ]
    return len(parts) == 1 and parts[0] in AMBIGUOUS_SINGLE_TITLE_TOKENS


def _normalize_title_for_match(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[\[\]【】()（）{}<>《》:：,，.!！?？'\"“”‘’._\-]+", " ", text)
    text = re.sub(r"\b(?:1080p|2160p|720p|bluray|web-dl|webrip|hdr|x264|x265|h264|h265)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_keyword(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace(".", " ")).strip()


def _clean_title_alias(value: Any) -> str:
    alias = _clean_keyword(value)
    if not alias or _is_generic_language_alias(alias):
        return ""
    if len(alias) > 80:
        return ""
    if re.search(r"https?://|www\.|。|！|？|；|……", alias, flags=re.IGNORECASE):
        return ""
    if _looks_english_title(alias):
        words = [
            item
            for item in re.split(r"\s+", _normalize_title_for_match(alias))
            if item and not re.fullmatch(r"(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2})", item)
        ]
        if len(words) == 1 and len(words[0]) < 2:
            return ""
    return alias


def _is_generic_language_alias(value: Any) -> bool:
    alias = _clean_keyword(value).lower()
    if not alias:
        return True
    normalized = _normalize_title_for_match(alias)
    if not normalized:
        return True
    if alias in GENERIC_TITLE_ALIAS_WORDS or alias in GENERIC_TITLE_ALIAS_CODES:
        return True
    tokens = [item for item in re.split(r"\s+", normalized) if item]
    if not tokens:
        return True
    generic_tokens = GENERIC_TITLE_ALIAS_WORDS | GENERIC_TITLE_ALIAS_CODES | {
        "audio",
        "dub",
        "dubbed",
        "forced",
        "hi",
        "sdh",
        "sub",
        "subs",
        "subtitle",
        "subtitles",
    }
    if all(item in generic_tokens for item in tokens):
        return True
    return len(tokens) == 1 and tokens[0].isalpha() and len(tokens[0]) < 2


def _unique_keywords(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result[:8]


def _english_search_titles(media: Dict[str, Any], targets: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for source in [media, *(targets or [])]:
        if not isinstance(source, dict):
            continue
        for field in ["en_title", "original_title", "original_name", "title_en", "name_en"]:
            value = _clean_title_alias(source.get(field))
            if value and not _is_cjk_text(value):
                values.append(value)
    return _unique_keywords(values)


__all__ = [name for name in globals() if not name.startswith("__")]
