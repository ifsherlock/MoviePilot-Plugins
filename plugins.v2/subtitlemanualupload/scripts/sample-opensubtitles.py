#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = SCRIPT_DIR.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

if "app.core.config" not in sys.modules:
    sys.modules.setdefault("app", types.ModuleType("app"))
    sys.modules.setdefault("app.core", types.ModuleType("app.core"))
    sys.modules["app.core.config"] = types.SimpleNamespace(settings=types.SimpleNamespace(PROXY=None, PROXY_SERVER=None))
if "app.log" not in sys.modules:
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
    _language_category_from_text,
    _query_plan_for_keyword,
    build_search_keywords,
)


PROBLEM_SAMPLES = [
    {"title": "九龙大众浪漫", "media_type": "tv", "year": "2025", "season": 1, "episode": 4},
    {"title": "指环王3：王者无敌", "media_type": "movie", "year": "2003"},
    {"title": "蜘蛛侠：平行宇宙", "media_type": "movie", "year": "2018"},
    {
        "title": "灰原同学的第二轮青春游戏",
        "media_type": "tv",
        "year": "2025",
        "season": 1,
        "episode": 7,
        "basename": "灰原同学的第二轮青春游戏 S01E07 奔向最棒的夏天",
    },
]


def load_cache(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else []
    return [item for item in entries if isinstance(item, dict)]


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
    }


def iter_samples(entries: List[Dict[str, Any]], movie_count: int, tv_count: int) -> Iterable[Dict[str, Any]]:
    for entry in sample_entries(entries, movie_count, tv_count):
        target = target_from_entry(entry)
        yield {"source": "library", "media": target, "targets": [target]}
    for item in PROBLEM_SAMPLES:
        target = target_from_problem(item)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only OpenSubtitles sampling for SubtitleManualUpload.")
    parser.add_argument("--cache", default="/config/plugins/SubtitleManualUpload/local_entries_cache.json")
    parser.add_argument("--movies", type=int, default=20)
    parser.add_argument("--tvs", type=int, default=20)
    parser.add_argument("--api-url", default="https://api.opensubtitles.com/api/v1")
    parser.add_argument("--max-keywords", type=int, default=3)
    args = parser.parse_args()

    entries = load_cache(Path(args.cache))
    provider = provider_from_env(args.api_url)
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
            "keywords": keywords[: args.max_keywords],
            "languages": OPENSUBTITLES_SEARCH_LANGUAGES,
            "query_plan": _query_plan_for_keyword(keywords[0] if keywords else "", targets),
            "results": [],
        }
        if provider and keywords:
            try:
                results = provider.search(keywords[0], targets, "episode" if media.get("media_type") == "tv" else "movie")
                row["results"] = [
                    {
                        "provider": item.provider,
                        "title": item.title,
                        "language_category": item.language_category or _language_category_from_text(item.language),
                        "score": item.score,
                        "identity_status": item.identity_status,
                        "match_detail": item.match_detail,
                        "result_years": item.result_years or [],
                    }
                    for item in results[:10]
                ]
            except Exception as exc:
                row["error"] = str(exc)
        elif keywords:
            row["local_assessment_example"] = _assess_result_match(title=keywords[0], keyword=keywords[0], targets=targets)
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
