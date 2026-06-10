#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = SCRIPT_DIR.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
for candidate in (Path("/app"), Path("/moviepilot"), Path("/MoviePilot")):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

try:
    from app.chain.tmdb import TmdbChain  # type: ignore
except Exception:
    TmdbChain = None

try:
    from app.db.models.transferhistory import TransferHistory  # type: ignore
except Exception:
    TransferHistory = None

try:
    from app.schemas.types import MediaType  # type: ignore
except Exception:
    class _NoopMediaType:
        MOVIE = "movie"
        TV = "tv"

    MediaType = _NoopMediaType

try:
    import app.core.config  # type: ignore  # noqa: F401
except Exception:
    sys.modules.setdefault("app", types.ModuleType("app"))
    sys.modules.setdefault("app.core", types.ModuleType("app.core"))
    sys.modules["app.core.config"] = types.SimpleNamespace(settings=types.SimpleNamespace(PROXY=None, PROXY_SERVER=None))
try:
    import app.log  # type: ignore  # noqa: F401
except Exception:
    sys.modules["app.log"] = types.SimpleNamespace(
        logger=types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        )
    )

from online_subtitle import (  # noqa: E402
    OPENSUBTITLES_SEARCH_LANGUAGES,
    OnlinePageClient,
    OpenSubtitlesProvider,
    _assess_result_match,
    _alias_values,
    _extract_years,
    _language_category_from_text,
    _query_plan_for_keyword,
    _region_bucket,
    _target_year_from_targets,
    _year_from_upload_date,
    _years_from_file_info,
    _years_from_opensubtitles_attrs,
    build_search_keywords,
)


PROBLEM_SAMPLES = [
    {
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
    {"title": "指环王3：王者无敌", "media_type": "movie", "year": "2003", "en_title": "The Lord of the Rings: The Return of the King"},
    {"title": "蜘蛛侠：平行宇宙", "media_type": "movie", "year": "2018", "en_title": "Spider-Man: Into the Spider-Verse"},
    {
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
        "negative_titles": ["Youth.Sherlock.S01E07.zh", "青年夏洛克 S01E07"],
    },
]


def load_cache(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else []
    return [item for item in entries if isinstance(item, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number_from_tag(value: Any) -> int:
    text = _text(value)
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else 0


def entry_from_transfer_history(history: Any) -> Optional[Dict[str, Any]]:
    if not getattr(history, "status", False):
        return None
    raw_fileitem = getattr(history, "dest_fileitem", None)
    fileitem = raw_fileitem if isinstance(raw_fileitem, dict) else {}
    path = _text(fileitem.get("path") or getattr(history, "dest", ""))
    if not path:
        return None
    file_path = Path(path)
    media_type = _text(getattr(history, "type", "")).lower()
    if media_type not in {"movie", "tv", "电影", "电视剧"}:
        return None
    media_type = "tv" if media_type in {"tv", "电视剧"} else "movie"
    filename = _text(fileitem.get("name")) or file_path.name
    basename = _text(fileitem.get("basename")) or file_path.stem
    title = _text(getattr(history, "title", ""))
    year = _text(getattr(history, "year", ""))
    tmdb_id = int(getattr(history, "tmdbid", 0) or 0)
    douban_id = _text(getattr(history, "doubanid", ""))
    season = _number_from_tag(getattr(history, "seasons", ""))
    episode = _number_from_tag(getattr(history, "episodes", ""))
    return {
        "id": f"{media_type}:{tmdb_id or douban_id or title}:{path}",
        "media_key": f"{media_type}:{tmdb_id or douban_id or title}:{year}",
        "media_type": media_type,
        "title": title,
        "year": year,
        "tmdb_id": tmdb_id,
        "douban_id": douban_id,
        "season": season,
        "episode": episode,
        "path": path,
        "basename": basename,
        "filename": filename,
        "target_label": filename,
    }


def load_transfer_history(limit: int) -> List[Dict[str, Any]]:
    if TransferHistory is None:
        return []
    histories = TransferHistory.list_by_page(db=None, page=1, count=max(limit, 100), status=True) or []
    entries: List[Dict[str, Any]] = []
    seen = set()
    for history in histories:
        entry = entry_from_transfer_history(history)
        if not entry:
            continue
        path = entry.get("path")
        if path in seen:
            continue
        seen.add(path)
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries


def sample_entries(entries: List[Dict[str, Any]], movie_count: int, tv_count: int) -> List[Dict[str, Any]]:
    by_media: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("media_key") or entry.get("id") or "")
        if key and key not in by_media:
            by_media[key] = entry
    movies = [item for item in by_media.values() if item.get("media_type") == "movie"]
    tvs = [item for item in by_media.values() if item.get("media_type") == "tv"]
    random.seed(20260610)
    random.shuffle(movies)
    random.shuffle(tvs)
    return movies[:movie_count] + tvs[:tv_count]


def target_from_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": entry.get("id"),
        "media_type": entry.get("media_type"),
        "title": entry.get("title"),
        "year": entry.get("year"),
        "tmdb_id": entry.get("tmdb_id"),
        "douban_id": entry.get("douban_id"),
        "season": entry.get("season", 0),
        "episode": entry.get("episode", 0),
        "basename": entry.get("basename"),
        "filename": entry.get("filename"),
        "path": entry.get("path"),
        "original_language": entry.get("original_language"),
        "origin_country": entry.get("origin_country"),
        "production_countries": entry.get("production_countries"),
        "original_title": entry.get("original_title"),
        "original_name": entry.get("original_name"),
        "en_title": entry.get("en_title"),
        "tmdb_aliases": entry.get("tmdb_aliases"),
    }


def target_from_problem(sample: Dict[str, Any]) -> Dict[str, Any]:
    basename = sample.get("basename") or f"{sample.get('title')} {sample.get('year', '')}".strip()
    return {
        "media_type": sample.get("media_type"),
        "title": sample.get("title"),
        "year": sample.get("year"),
        "season": sample.get("season", 0),
        "episode": sample.get("episode", 0),
        "basename": basename,
        "filename": f"{basename}.mkv",
        "original_language": sample.get("original_language"),
        "origin_country": sample.get("origin_country"),
        "original_title": sample.get("original_title"),
        "en_title": sample.get("en_title"),
        "negative_titles": sample.get("negative_titles") or [],
    }


def _value(detail: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(detail, dict) and key in detail:
            return detail.get(key)
        if hasattr(detail, key):
            return getattr(detail, key)
    return None


def _english_alias(aliases: List[str]) -> str:
    for item in aliases:
        if any("a" <= ch.lower() <= "z" for ch in item) and not any("\u3400" <= ch <= "\u9fff" for ch in item):
            return item
    return ""


def tmdb_detail_for_target(target: Dict[str, Any]) -> Dict[str, Any]:
    tmdb_id = int(target.get("tmdb_id") or 0)
    if not tmdb_id or TmdbChain is None:
        return {}
    media_type = str(target.get("media_type") or "").lower()
    mp_type = MediaType.TV if media_type == "tv" else MediaType.MOVIE
    try:
        detail = TmdbChain().tmdb_info(tmdbid=tmdb_id, mtype=mp_type)
    except TypeError:
        detail = TmdbChain().tmdb_info(tmdb_id=tmdb_id, mtype=mp_type)
    aliases = _alias_values(_value(detail, "translations")) + _alias_values(_value(detail, "alternative_titles"))
    return {
        "original_language": _value(detail, "original_language") or "",
        "origin_country": _value(detail, "origin_country") or [],
        "production_countries": _value(detail, "production_countries") or [],
        "original_title": _value(detail, "original_title", "original_name") or "",
        "en_title": _english_alias(aliases),
        "tmdb_aliases": aliases[:80],
    }


def enrich_with_tmdb(target: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(target)
    try:
        detail = tmdb_detail_for_target(target)
    except Exception as exc:
        enriched["tmdb_detail_error"] = str(exc)
        return enriched
    for key, value in detail.items():
        if value and not enriched.get(key):
            enriched[key] = value
    return enriched


def iter_samples(entries: List[Dict[str, Any]], movie_count: int, tv_count: int) -> Iterable[Dict[str, Any]]:
    for entry in sample_entries(entries, movie_count, tv_count):
        target = enrich_with_tmdb(target_from_entry(entry))
        yield {"source": "library", "media": target, "targets": [target]}
    for item in PROBLEM_SAMPLES:
        target = enrich_with_tmdb(target_from_problem(item))
        yield {"source": "problem", "media": target, "targets": [target]}


def provider_from_env(api_url: str) -> OpenSubtitlesProvider | None:
    api_key = os.getenv("OPENSUBTITLES_API_KEY", "").strip()
    if not api_key:
        return None
    fetcher = OnlinePageClient(engine="cloakbrowser", use_proxy=False)
    return OpenSubtitlesProvider(
        fetcher,
        api_key=api_key,
        api_url=api_url,
        username=os.getenv("OPENSUBTITLES_USERNAME", "").strip(),
        password=os.getenv("OPENSUBTITLES_PASSWORD", "").strip(),
    )


def _mp_plugin_config() -> Dict[str, Any]:
    try:
        from app.plugins import _PluginBase  # type: ignore
    except Exception:
        return {}
    noop_plugin = type(
        "NoopPlugin",
        (_PluginBase,),
        {
            "init_plugin": lambda self, config=None: None,
            "get_state": lambda self: False,
            "get_form": lambda self: None,
            "get_page": lambda self: None,
            "get_api": lambda self: [],
            "stop_service": lambda self: None,
        },
    )
    try:
        config = noop_plugin().get_config("SubtitleManualUpload") or {}
    except Exception:
        return {}
    return config if isinstance(config, dict) else {}


def provider_from_mp_config(api_url: str) -> OpenSubtitlesProvider | None:
    config = _mp_plugin_config()
    api_key = str(config.get("opensubtitles_api_key") or "").strip()
    if not api_key:
        return None
    fetcher = OnlinePageClient(engine="cloakbrowser", use_proxy=False)
    return OpenSubtitlesProvider(
        fetcher,
        api_key=api_key,
        api_url=str(config.get("opensubtitles_api_url") or api_url).strip() or api_url,
        username=str(config.get("opensubtitles_username") or "").strip(),
        password=str(config.get("opensubtitles_password") or "").strip(),
    )


def raw_opensubtitles_assessments(
    provider: OpenSubtitlesProvider,
    keyword: str,
    targets: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    payload = provider._api_json(
        "/subtitles",
        {
            "query": keyword,
            "languages": OPENSUBTITLES_SEARCH_LANGUAGES,
            "order_by": "download_count",
            "order_direction": "desc",
        },
    )
    rows = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    target_year = _target_year_from_targets(targets)
    assessments: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        files = attrs.get("files") if isinstance(attrs.get("files"), list) else []
        file_info = next((item for item in files if isinstance(item, dict)), {})
        title = provider._subtitle_title(attrs, file_info)
        result_years = _years_from_opensubtitles_attrs(attrs, file_info, title)
        file_years = _years_from_file_info(file_info)
        upload_year = _year_from_upload_date(attrs.get("upload_date") or attrs.get("uploaded_at"))
        assessment = _assess_result_match(
            title=title,
            keyword=keyword,
            targets=targets,
            result_years=result_years,
            attrs=attrs,
            file_info=file_info,
        )
        hard_reject = ""
        if target_year and result_years and target_year not in result_years:
            hard_reject = "年份冲突"
        elif target_year and file_years and target_year not in file_years:
            hard_reject = "文件名年份冲突"
        elif target_year and upload_year and upload_year < target_year:
            hard_reject = "字幕上传时间早于资源年份"
        accepted = not hard_reject and assessment.get("identity_status") != "failed"
        assessments.append(
            {
                "title": title,
                "language_category": _language_category_from_text(
                    " ".join([str(attrs.get("language") or ""), title, str(file_info.get("file_name") or "")])
                ),
                "score": assessment.get("score", 0),
                "identity_status": assessment.get("identity_status"),
                "reject_reason": hard_reject or assessment.get("reject_reason", ""),
                "match_detail": assessment.get("match_detail", ""),
                "result_years": result_years,
                "file_years": file_years,
                "upload_year": upload_year,
                "accepted": accepted,
            }
        )
    return assessments


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only OpenSubtitles sampling for SubtitleManualUpload.")
    parser.add_argument("--cache", default="/config/plugins/SubtitleManualUpload/local_entries_cache.json")
    parser.add_argument("--movies", type=int, default=20)
    parser.add_argument("--tvs", type=int, default=20)
    parser.add_argument("--api-url", default="https://api.opensubtitles.com/api/v1")
    parser.add_argument("--max-keywords", type=int, default=3)
    parser.add_argument("--raw-limit", type=int, default=20)
    parser.add_argument("--output", default="", help="Optional JSONL output path for local debugging.")
    parser.add_argument("--use-mp-config", action="store_true", help="Read OpenSubtitles API settings from MoviePilot plugin config.")
    args = parser.parse_args()

    entries = load_cache(Path(args.cache))
    if not entries:
        entries = load_transfer_history((args.movies + args.tvs) * 5)
    provider = provider_from_mp_config(args.api_url) if args.use_mp_config else provider_from_env(args.api_url)
    output_file: Optional[Path] = Path(args.output) if args.output else None
    output_handle = output_file.open("w", encoding="utf-8") if output_file else None
    for sample in iter_samples(entries, args.movies, args.tvs):
        media = sample["media"]
        targets = sample["targets"]
        keywords = build_search_keywords(media, targets, "episode" if media.get("media_type") == "tv" else "movie")
        row = {
            "source": sample["source"],
            "title": media.get("title"),
            "media_type": media.get("media_type"),
            "year": media.get("year"),
            "tmdb_id": media.get("tmdb_id"),
            "original_language": media.get("original_language"),
            "origin_country": media.get("origin_country"),
            "production_countries": media.get("production_countries"),
            "original_title": media.get("original_title") or media.get("original_name"),
            "en_title": media.get("en_title"),
            "region_bucket": _region_bucket(media, targets),
            "keywords": keywords[: args.max_keywords],
            "languages": OPENSUBTITLES_SEARCH_LANGUAGES,
            "query_plan": _query_plan_for_keyword(keywords[0] if keywords else "", targets),
            "results": [],
            "raw_assessments": [],
            "negative_assessments": [],
        }
        if provider and keywords:
            try:
                collected_results = []
                collected_raw = []
                for query in keywords[: args.max_keywords]:
                    raw_items = raw_opensubtitles_assessments(
                        provider,
                        query,
                        targets,
                        limit=max(args.raw_limit, 1),
                    )
                    collected_raw.extend([{**item, "query": query} for item in raw_items])
                    collected_results.extend(
                        [
                            {
                                "query": query,
                                "provider": "opensubtitles",
                                "title": item.get("title"),
                                "language_category": item.get("language_category"),
                                "score": item.get("score", 0),
                                "identity_status": item.get("identity_status"),
                                "reject_reason": item.get("reject_reason", ""),
                                "match_detail": item.get("match_detail", ""),
                                "result_years": item.get("result_years") or [],
                                "filename_years": item.get("file_years") or _extract_years(item.get("title")),
                            }
                            for item in raw_items
                            if item.get("accepted")
                        ]
                    )
                row["raw_assessments"] = collected_raw
                row["results"] = collected_results
            except Exception as exc:
                row["error"] = str(exc)
        elif keywords:
            row["local_assessment_example"] = _assess_result_match(title=keywords[0], keyword=keywords[0], targets=targets)
        if keywords and media.get("negative_titles"):
            row["negative_assessments"] = [
                {
                    "title": title,
                    **_assess_result_match(title=title, keyword=keywords[0], targets=targets),
                }
                for title in media.get("negative_titles") or []
            ]
        line = json.dumps(row, ensure_ascii=False)
        if output_handle:
            output_handle.write(line + "\n")
        print(line)
    if output_handle:
        output_handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
