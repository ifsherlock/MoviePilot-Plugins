from __future__ import annotations

import importlib.util
import json
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "plugins.v3/subtitlemanualupload/matching/subtitle_history.py"


def load_history_class():
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_v3_history_test", HISTORY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SubtitleHistory, module.MATCH_HISTORY_CACHE_VERSION


class FakeInventory:
    def __init__(self, directories):
        self.directories = directories
        self.scans = []

    def directory_signatures_for_entries(self, entries):
        return {
            str(Path(entry["path"]).parent): str(Path(entry["path"]).parent.stat().st_mtime_ns)
            for entry in entries
        }

    def subtitle_files_for_targets(self, entries):
        directories = sorted({str(Path(entry["path"]).parent) for entry in entries})
        self.scans.append(directories)
        return {
            entry["id"]: [
                {
                    "name": f"{entry['basename']}.chi.srt",
                    "modified_at": "2026-01-01T00:00:00",
                }
            ]
            for entry in entries
        }


class FakeResolver:
    @staticmethod
    def target_from_entry(entry, *, subtitles):
        return {
            "id": entry["id"],
            "basename": entry["basename"],
            "label": entry["target_label"],
            "season": entry.get("season", 0),
            "episode": entry.get("episode", 0),
            "subtitles": subtitles,
        }


def make_owner(tmp_path, entries, inventory):
    cache = tmp_path / "match_history_cache.json"

    def clone(value):
        return json.loads(json.dumps(value, ensure_ascii=False))

    services = SimpleNamespace(
        subtitle_inventory=lambda: inventory,
        local_media_catalog=lambda: SimpleNamespace(load_local_entries=lambda **kwargs: list(entries)),
        target_resolver=lambda: FakeResolver(),
        timeline_tasks=lambda: SimpleNamespace(task_for_target_id=lambda _target_id: None),
    )
    owner = SimpleNamespace(
        _local_entries_cache={"loaded_at": datetime.now(), "entries": entries},
        _match_history_cache={"version": 3, "loaded_at": None, "validated_at": None, "signature": "", "items": [], "entry_count": 0, "persisted": False},
        _match_history_directory_cache={},
        _match_history_generation=0,
        _match_history_refreshing=False,
        _match_history_refresh_lock=threading.Lock(),
        _match_history_build_lock=threading.Lock(),
        _match_history_cache_ttl_seconds=86400,
        _match_history_validation_interval_seconds=300,
        services=services,
        _normalize_text=lambda value: str(value or "").strip(),
        _cache_loaded_at=lambda value: value if isinstance(value, datetime) else (datetime.fromisoformat(value) if value else None),
        _hash_text=lambda value: f"hash:{value}",
        _json_clone=clone,
        _media_type_text=lambda value: value,
        _entry_matches_keyword=lambda entry, keyword: keyword.lower() in str(entry.get("title") or "").lower(),
        _poster_url=lambda value, prefix="w185": value,
        get_data_path=lambda: tmp_path,
        _invalidate_match_history_cache=lambda: None,
    )
    return owner, cache


def test_v3_history_reuses_unchanged_directories_and_groups_media(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "First.strm"
    second = second_dir / "Second.strm"
    first.write_text("remote", encoding="utf-8")
    second.write_text("remote", encoding="utf-8")
    entries = [
        {"id": "first", "origin": "manual_strm", "media_key": "tmdb:1", "media_type": "movie", "title": "First", "path": str(first), "basename": "First", "target_label": "First", "storage": "local"},
        {"id": "second", "origin": "transfer_history", "media_key": "tmdb:2", "media_type": "movie", "title": "Second", "path": str(second), "basename": "Second", "target_label": "Second", "storage": "local"},
    ]
    inventory = FakeInventory([first_dir, second_dir])
    owner, _ = make_owner(tmp_path, entries, inventory)
    history_class, version = load_history_class()
    history = history_class(
        owner,
        http_exception=RuntimeError,
        logger=SimpleNamespace(warning=lambda *args: None, info=lambda *args: None),
        target_entry_cache=SimpleNamespace(remember=lambda _entries: None),
        subtitle_inventory=inventory,
    )

    first_items = history.rebuild_match_history_cache(entries=entries)
    history.rebuild_match_history_cache(entries=entries)
    (second_dir / "new.ass").write_text("new", encoding="utf-8")
    third_items = history.rebuild_match_history_cache(entries=entries)

    assert version == 3
    assert {item["id"] for item in first_items} == {"tmdb:1", "tmdb:2"}
    assert {item["id"] for item in third_items} == {"tmdb:1", "tmdb:2"}
    assert len(inventory.scans) == 3
    assert inventory.scans[0] == [str(first_dir)]
    assert inventory.scans[1] == [str(second_dir)]
    assert inventory.scans[2] == [str(second_dir)]


def test_v3_history_page_filters_and_paginates_snapshot(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    path = media_dir / "Movie.strm"
    path.write_text("remote", encoding="utf-8")
    entry = {"id": "movie", "origin": "manual_strm", "media_key": "tmdb:9", "media_type": "movie", "title": "Movie", "path": str(path), "basename": "Movie", "target_label": "Movie", "storage": "local"}
    inventory = FakeInventory([media_dir])
    owner, _ = make_owner(tmp_path, [entry], inventory)
    history_class, _ = load_history_class()
    history = history_class(owner, http_exception=RuntimeError, logger=SimpleNamespace(warning=lambda *args: None, info=lambda *args: None), target_entry_cache=SimpleNamespace(remember=lambda _entries: None), subtitle_inventory=inventory)
    history.rebuild_match_history_cache(entries=[entry])

    page = history.match_history_page(keyword="Movie", media_type="movie", page=1, page_size=1)

    assert page["total"] == 1
    assert page["has_more"] is False
    assert page["items"][0]["id"] == "tmdb:9"
