#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SAMPLE_SEED = 20260610
DEFAULT_LANGUAGES = "zh-cn,zh-tw,ze,en,ja,ko"
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
    "vietnamese",
    "cantonese",
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

PROBLEM_SAMPLES = [
    {
        "source": "problem",
        "title": "九龙大众浪漫",
        "media_type": "tv",
        "year": "2025",
        "season": 1,
        "episode": 4,
        "original_language": "ja",
        "origin_country": ["JP"],
        "original_title": "九龍ジェネリックロマンス",
        "en_title": "Kowloon Generic Romance",
    },
    {
        "source": "problem",
        "title": "指环王3：王者无敌",
        "media_type": "movie",
        "year": "2003",
        "original_language": "en",
        "origin_country": ["US", "NZ"],
        "original_title": "The Lord of the Rings: The Return of the King",
        "en_title": "The Lord of the Rings: The Return of the King",
    },
    {
        "source": "problem",
        "title": "蜘蛛侠：平行宇宙",
        "media_type": "movie",
        "year": "2018",
        "original_language": "en",
        "origin_country": ["US"],
        "original_title": "Spider-Man: Into the Spider-Verse",
        "en_title": "Spider-Man: Into the Spider-Verse",
    },
    {
        "source": "problem",
        "title": "灰原同学的第二轮青春游戏",
        "media_type": "tv",
        "year": "2025",
        "season": 1,
        "episode": 7,
        "basename": "灰原同学的第二轮青春游戏 S01E07 奔向最棒的夏天",
        "original_language": "ja",
        "origin_country": ["JP"],
        "original_title": "灰原くんの強くて青春ニューゲーム",
        "en_title": "Haibara-kun's New Game Plus",
    },
]


def text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    value_text = text(value)
    return [value_text] if value_text else []


def clean_query(value: Any) -> str:
    return re.sub(r"\s+", " ", text(value).replace(".", " ")).strip()


def normalize_title_for_match(value: Any) -> str:
    normalized = str(value or "").lower()
    normalized = re.sub(r"[\[\]【】()（）{}<>《》:：,，.!！?？'\"“”‘’._\-]+", " ", normalized)
    normalized = re.sub(r"\b(?:1080p|2160p|720p|bluray|web-dl|webrip|hdr|x264|x265|h264|h265)\b", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def is_generic_language_alias(value: Any) -> bool:
    alias = clean_query(value).lower()
    if not alias:
        return True
    normalized = normalize_title_for_match(alias)
    if not normalized:
        return True
    if alias in GENERIC_TITLE_ALIAS_WORDS or alias in GENERIC_TITLE_ALIAS_CODES:
        return True
    tokens = [item for item in re.split(r"\s+", normalized) if item]
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
    if tokens and all(item in generic_tokens for item in tokens):
        return True
    return len(tokens) == 1 and tokens[0].isalpha() and len(tokens[0]) < 2


def clean_title_alias(value: Any) -> str:
    alias = clean_query(value)
    if not alias or is_generic_language_alias(alias):
        return ""
    if looks_english(alias):
        words = [
            item
            for item in re.split(r"\s+", normalize_title_for_match(alias))
            if item and not re.fullmatch(r"(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2})", item)
        ]
        if len(words) == 1 and len(words[0]) < 2:
            return ""
    return alias


def unique(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        item = clean_query(value)
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def extract_years(value: Any) -> List[int]:
    current_year = time.localtime().tm_year + 1
    years = []
    for match in re.finditer(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text(value)):
        year = int(match.group(1))
        if 1900 <= year <= current_year:
            years.append(year)
    return sorted(set(years))


def episode_suffix(entry: Dict[str, Any]) -> str:
    if text(entry.get("media_type")).lower() != "tv":
        return ""
    season = safe_int(entry.get("season"))
    episode = safe_int(entry.get("episode"))
    if season and episode:
        return f"S{season:02d}E{episode:02d}"
    if season:
        return f"S{season:02d}"
    return ""


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def title_values(entry: Dict[str, Any], *fields: str) -> List[str]:
    values: List[str] = []
    for field in fields:
        values.extend(alias_values(entry.get(field)))
    return unique(values)


def alias_values(value: Any) -> List[str]:
    values: List[str] = []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw[:1] in "[{":
            try:
                return alias_values(json.loads(raw))
            except Exception:
                pass
        alias = clean_title_alias(raw)
        return [alias] if alias else []
    if isinstance(value, dict):
        for key in ["title", "name", "english_name"]:
            values.extend(alias_values(value.get(key)))
        for key in ["data", "titles", "results", "translations", "alternative_titles", "aliases"]:
            values.extend(alias_values(value.get(key)))
    elif isinstance(value, list):
        for item in value:
            values.extend(alias_values(item))
    return unique(values)


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def has_japanese(value: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", value or ""))


def has_korean(value: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7af]", value or ""))


def looks_english(value: str) -> bool:
    value = text(value)
    return bool(re.search(r"[A-Za-z]", value)) and not has_cjk(value) and not has_japanese(value) and not has_korean(value)


def region_bucket(entry: Dict[str, Any]) -> str:
    languages = {text(item).lower().replace("_", "-") for item in as_list(entry.get("original_language"))}
    countries = {
        text(item).lower()
        for field in ["origin_country", "production_countries", "country", "area", "region"]
        for item in as_list(entry.get(field))
    }
    category = " ".join(text(entry.get(field)) for field in ["category", "media_category", "library_name"])
    if languages & {"zh", "cn", "cmn", "yue"} or countries & {"cn", "hk", "tw", "sg"} or re.search(r"华语|国产|港剧|中国|大陆", category):
        return "chinese"
    if languages & {"ja", "jp"} or countries & {"jp"} or re.search(r"日本|日剧|日漫|动画", category):
        return "japanese"
    if languages & {"ko", "kr"} or countries & {"kr", "kp"} or re.search(r"韩国|韩剧", category):
        return "korean"
    if languages & {"en"} or countries & {"us", "gb", "uk", "ca", "au", "nz", "ie"} or re.search(r"欧美|美剧|英剧", category):
        return "western"
    return "other"


def with_episode(entry: Dict[str, Any], query: str) -> str:
    suffix = episode_suffix(entry)
    if suffix and suffix.casefold() not in query.casefold():
        return f"{query} {suffix}"
    return query


def chinese_titles(entry: Dict[str, Any]) -> List[str]:
    values = title_values(entry, "title", "name", "tmdb_aliases", "aliases", "translations", "alternative_titles")
    return [item for item in values if has_cjk(item) and not has_japanese(item) and not has_korean(item)]


def english_titles(entry: Dict[str, Any]) -> List[str]:
    values = title_values(
        entry,
        "en_title",
        "title_en",
        "name_en",
        "english_title",
        "original_title",
        "original_name",
        "tmdb_aliases",
        "aliases",
        "translations",
        "alternative_titles",
    )
    return [item for item in values if looks_english(item)]


def original_titles(entry: Dict[str, Any]) -> List[str]:
    return title_values(entry, "original_title", "original_name")


def japanese_titles(entry: Dict[str, Any]) -> List[str]:
    values = title_values(entry, "original_title", "original_name", "tmdb_aliases", "aliases", "translations", "alternative_titles")
    return [item for item in values if has_japanese(item)]


def korean_titles(entry: Dict[str, Any]) -> List[str]:
    values = title_values(entry, "original_title", "original_name", "tmdb_aliases", "aliases", "translations", "alternative_titles")
    return [item for item in values if has_korean(item)]


def baseline_chinese_queries(entry: Dict[str, Any]) -> List[str]:
    year = text(entry.get("year"))
    queries = chinese_titles(entry) or title_values(entry, "title", "name")
    if year and text(entry.get("media_type")).lower() != "tv":
        queries = [f"{item} {year}" for item in queries] + queries
    return unique(with_episode(entry, item) for item in queries[:4])


def multilingual_queries(entry: Dict[str, Any]) -> List[str]:
    year = text(entry.get("year"))
    queries = unique([*chinese_titles(entry), *english_titles(entry), *japanese_titles(entry), *korean_titles(entry), *original_titles(entry)])
    if year and text(entry.get("media_type")).lower() != "tv":
        queries = unique([f"{item} {year}" for item in queries[:6]] + queries)
    return unique(with_episode(entry, item) for item in queries[:8])


def region_aware_queries(entry: Dict[str, Any]) -> List[str]:
    bucket = region_bucket(entry)
    if bucket == "chinese":
        ordered = [*chinese_titles(entry), *english_titles(entry)]
    elif bucket == "western":
        ordered = [*english_titles(entry), *chinese_titles(entry)]
    elif bucket == "japanese":
        ordered = [*japanese_titles(entry), *original_titles(entry), *english_titles(entry), *chinese_titles(entry)]
    elif bucket == "korean":
        ordered = [*korean_titles(entry), *original_titles(entry), *english_titles(entry), *chinese_titles(entry)]
    else:
        ordered = [*original_titles(entry), *english_titles(entry), *chinese_titles(entry)]
    year = text(entry.get("year"))
    ordered = unique(ordered)
    if year and text(entry.get("media_type")).lower() != "tv":
        ordered = unique([f"{item} {year}" for item in ordered[:5]] + ordered)
    return unique(with_episode(entry, item) for item in ordered[:8])


STRATEGIES = {
    "baseline_chinese": baseline_chinese_queries,
    "multilingual_titles": multilingual_queries,
    "region_aware": region_aware_queries,
}


def normalize_entry(entry: Dict[str, Any], source: str = "library") -> Dict[str, Any]:
    media_type = text(entry.get("media_type") or entry.get("type")).lower()
    if media_type in {"电影", "movie"}:
        media_type = "movie"
    elif media_type in {"电视剧", "tv", "series"}:
        media_type = "tv"
    title = text(entry.get("title") or entry.get("name"))
    path = text(entry.get("path") or entry.get("file") or entry.get("target_path"))
    filename = text(entry.get("filename") or entry.get("basename") or Path(path).name)
    years = extract_years(" ".join([text(entry.get("year")), filename, title]))
    normalized = dict(entry)
    normalized.update(
        {
            "source": entry.get("source") or source,
            "media_type": media_type,
            "title": title,
            "year": text(entry.get("year") or (years[0] if years else "")),
            "season": safe_int(entry.get("season")),
            "episode": safe_int(entry.get("episode")),
            "filename": filename,
            "path": path,
        }
    )
    return normalized


def load_entries(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        entries = payload.get("entries") or payload.get("items") or payload.get("data") or []
    else:
        entries = payload
    return [normalize_entry(item) for item in entries if isinstance(item, dict)]


def sample_entries(entries: List[Dict[str, Any]], movies: int, tvs: int) -> List[Dict[str, Any]]:
    by_media: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        key = text(entry.get("media_key")) or ":".join(
            [
                text(entry.get("media_type")),
                text(entry.get("tmdb_id") or entry.get("douban_id") or entry.get("title")),
                text(entry.get("year")),
                text(entry.get("season")),
            ]
        )
        if key and key not in by_media:
            by_media[key] = entry
    movie_items = [item for item in by_media.values() if item.get("media_type") == "movie"]
    tv_items = [item for item in by_media.values() if item.get("media_type") == "tv"]
    random.seed(SAMPLE_SEED)
    random.shuffle(movie_items)
    random.shuffle(tv_items)
    return movie_items[:movies] + tv_items[:tvs]


def opensubtitles_get(api_url: str, api_key: str, query: str, languages: str, limit: int, user_agent: str) -> Dict[str, Any]:
    params = {
        "query": query,
        "languages": languages,
        "order_by": "download_count",
        "order_direction": "desc",
    }
    url = f"{api_url.rstrip('/')}/subtitles?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Api-Key": api_key,
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=40) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        payload["data"] = payload["data"][:limit]
    return payload if isinstance(payload, dict) else {"data": []}


def subtitle_title(attrs: Dict[str, Any], file_info: Dict[str, Any]) -> str:
    return text(
        file_info.get("file_name")
        or attrs.get("release")
        or attrs.get("movie_name")
        or attrs.get("feature_details")
        or attrs.get("slug")
    )


def result_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    files = attrs.get("files") if isinstance(attrs.get("files"), list) else []
    file_info = next((item for item in files if isinstance(item, dict)), {})
    title = subtitle_title(attrs, file_info)
    return {
        "id": row.get("id"),
        "language": attrs.get("language"),
        "language_category": language_category(" ".join([text(attrs.get("language")), title])),
        "title": title,
        "movie_name": attrs.get("movie_name"),
        "release": attrs.get("release"),
        "feature_details": attrs.get("feature_details"),
        "file_name": file_info.get("file_name"),
        "year": attrs.get("year") or attrs.get("movie_year") or attrs.get("feature_details", {}).get("year") if isinstance(attrs.get("feature_details"), dict) else attrs.get("year") or attrs.get("movie_year"),
        "upload_date": attrs.get("upload_date") or attrs.get("uploaded_at"),
        "download_count": attrs.get("download_count") or attrs.get("downloads"),
        "imdb_id": attrs.get("imdb_id") or attrs.get("imdbid"),
        "tmdb_id": attrs.get("tmdb_id") or attrs.get("tmdbid"),
        "years_in_text": extract_years(" ".join([title, json.dumps(attrs, ensure_ascii=False, default=str)])),
    }


def language_category(value: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in ["zh", "chi", "zho", "cmn", "chinese", "中文", "中字"]):
        return "chinese"
    if any(token in lowered for token in ["ja", "jpn", "japanese", "日文", "日语"]) or has_japanese(value):
        return "japanese"
    if any(token in lowered for token in ["ko", "kor", "korean", "韩文", "韩语"]) or has_korean(value):
        return "korean"
    if any(token in lowered for token in ["en", "eng", "english", "英文", "英语"]):
        return "english"
    return "other"


def compact_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": entry.get("source"),
        "title": entry.get("title"),
        "media_type": entry.get("media_type"),
        "year": entry.get("year"),
        "season": entry.get("season"),
        "episode": entry.get("episode"),
        "tmdb_id": entry.get("tmdb_id"),
        "douban_id": entry.get("douban_id"),
        "original_language": entry.get("original_language"),
        "origin_country": entry.get("origin_country"),
        "original_title": entry.get("original_title") or entry.get("original_name"),
        "en_title": entry.get("en_title") or entry.get("english_title"),
        "region_bucket": region_bucket(entry),
        "filename": entry.get("filename"),
    }


def run_sample(args: argparse.Namespace) -> List[Dict[str, Any]]:
    entries = load_entries(Path(args.input))
    samples = sample_entries(entries, args.movies, args.tvs)
    samples.extend(normalize_entry(item, source="problem") for item in PROBLEM_SAMPLES)
    api_key = args.api_key or os.getenv("OPENSUBTITLES_API_KEY", "")
    if not api_key:
        raise SystemExit("OpenSubtitles API Key is required. Pass --api-key or set OPENSUBTITLES_API_KEY.")
    rows: List[Dict[str, Any]] = []
    for index, entry in enumerate(samples, start=1):
        base = compact_entry(entry)
        for strategy_name, strategy in STRATEGIES.items():
            queries = strategy(entry)[: args.max_queries]
            strategy_row = {**base, "sample_index": index, "strategy": strategy_name, "queries": queries, "responses": []}
            for query in queries:
                response_item = {"query": query, "languages": args.languages, "elapsed_ms": 0, "results": [], "error": ""}
                started_at = time.perf_counter()
                try:
                    payload = opensubtitles_get(args.api_url, api_key, query, args.languages, args.limit, args.user_agent)
                    data = payload.get("data") if isinstance(payload, dict) else []
                    response_item["results"] = [
                        result_summary(item)
                        for item in data
                        if isinstance(item, dict)
                    ]
                except HTTPError as exc:
                    response_item["error"] = f"HTTP {exc.code}: {exc.reason}"
                except URLError as exc:
                    response_item["error"] = f"URL error: {exc.reason}"
                except Exception as exc:
                    response_item["error"] = str(exc)
                finally:
                    response_item["elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
                strategy_row["responses"].append(response_item)
                if args.sleep:
                    time.sleep(args.sleep)
            rows.append(strategy_row)
            print(json.dumps(strategy_row, ensure_ascii=False), flush=True)
    return rows


def write_jsonl(rows: List[Dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fields = [
        "sample_index",
        "source",
        "media_type",
        "title",
        "year",
        "season",
        "episode",
        "region_bucket",
        "strategy",
        "query",
        "languages",
        "elapsed_ms",
        "rank",
        "result_title",
        "result_language",
        "result_language_category",
        "result_years",
        "upload_date",
        "download_count",
        "imdb_id",
        "tmdb_id",
        "error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            for response in row.get("responses") or []:
                results = response.get("results") or []
                if not results:
                    writer.writerow(
                        {
                            "sample_index": row.get("sample_index"),
                            "source": row.get("source"),
                            "media_type": row.get("media_type"),
                            "title": row.get("title"),
                            "year": row.get("year"),
                            "season": row.get("season"),
                            "episode": row.get("episode"),
                            "region_bucket": row.get("region_bucket"),
                            "strategy": row.get("strategy"),
                            "query": response.get("query"),
                            "languages": response.get("languages"),
                            "elapsed_ms": response.get("elapsed_ms"),
                            "error": response.get("error"),
                        }
                    )
                for rank, item in enumerate(results, start=1):
                    writer.writerow(
                        {
                            "sample_index": row.get("sample_index"),
                            "source": row.get("source"),
                            "media_type": row.get("media_type"),
                            "title": row.get("title"),
                            "year": row.get("year"),
                            "season": row.get("season"),
                            "episode": row.get("episode"),
                            "region_bucket": row.get("region_bucket"),
                            "strategy": row.get("strategy"),
                            "query": response.get("query"),
                            "languages": response.get("languages"),
                            "elapsed_ms": response.get("elapsed_ms"),
                            "rank": rank,
                            "result_title": item.get("title"),
                            "result_language": item.get("language"),
                            "result_language_category": item.get("language_category"),
                            "result_years": ",".join(str(year) for year in item.get("years_in_text") or []),
                            "upload_date": item.get("upload_date"),
                            "download_count": item.get("download_count"),
                            "imdb_id": item.get("imdb_id"),
                            "tmdb_id": item.get("tmdb_id"),
                            "error": response.get("error"),
                        }
                    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Standalone OpenSubtitles sampling. Reads local media entries, samples 20 movies + 20 TV shows, "
            "runs baseline Chinese, multilingual, and region-aware query strategies, then writes raw JSONL/CSV."
        )
    )
    parser.add_argument("--input", required=True, help="JSON file exported from local_entries_cache.json or a prepared sample list.")
    parser.add_argument("--movies", type=int, default=20)
    parser.add_argument("--tvs", type=int, default=20)
    parser.add_argument("--api-key", default="", help="OpenSubtitles API key. Defaults to OPENSUBTITLES_API_KEY.")
    parser.add_argument("--api-url", default="https://api.opensubtitles.com/api/v1")
    parser.add_argument("--languages", default=DEFAULT_LANGUAGES)
    parser.add_argument("--limit", type=int, default=10, help="Raw result limit per query.")
    parser.add_argument("--max-queries", type=int, default=3, help="Max queries per strategy/sample.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between API calls.")
    parser.add_argument("--user-agent", default="SubtitleManualUpload OpenSubtitles sampler/0.1")
    parser.add_argument("--jsonl", default="opensubtitles-sample.jsonl")
    parser.add_argument("--csv", default="opensubtitles-sample.csv")
    args = parser.parse_args()

    rows = run_sample(args)
    write_jsonl(rows, Path(args.jsonl))
    write_csv(rows, Path(args.csv))
    print(f"wrote rows={len(rows)} jsonl={args.jsonl} csv={args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
