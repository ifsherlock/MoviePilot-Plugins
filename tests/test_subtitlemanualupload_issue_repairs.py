from __future__ import annotations

import json
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_subtitlemanualupload_sup import make_bitmap_writer, make_target, sup_modules


class CatalogHttpError(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code


@pytest.mark.parametrize("token", ["E06", "EP06", "Episode 6", "episode.006"])
def test_episode_only_names_resolve_exact_episode(sup_modules, token):
    resolver = sup_modules.load("catalog.target_resolver")
    hint = resolver.extract_episode_hint
    targets = [{"id": str(index), "season": 1, "episode": index} for index in range(1, 21)]
    assert hint(f"Alchemy of Souls 2022 {token} 2160p.ass") == {"season": 0, "episode": 6}
    assert resolver.suggest_target({"source_name": f"Show.{token}.ass"}, targets, extract_episode_hint=hint) == "6"


def test_unknown_names_and_ambiguous_seasons_are_never_matched_by_position(sup_modules):
    resolver = sup_modules.load("catalog.target_resolver")
    targets = [{"id": "s1", "season": 1, "episode": 6}, {"id": "s2", "season": 2, "episode": 6}]
    items = [{"source_name": "Show.E06.ass", "target_id": None}, {"source_name": "unknown.ass", "target_id": None}]
    resolver.auto_fill_missing_targets(items, targets, extract_episode_hint=resolver.extract_episode_hint)
    assert all(item["target_id"] is None for item in items)
    duplicates = [{"id": "one", "season": 1, "episode": 6}, {"id": "two", "season": 1, "episode": 6}]
    assert resolver.suggest_target({"source_name": "Show.S01E06.ass"}, duplicates, extract_episode_hint=resolver.extract_episode_hint) is None


@pytest.mark.parametrize("name", ["Movie.2022.2160p.DDP2.0.EAC3.ass", "Show.HEVC.ass", "Show.E2022.ass"])
def test_non_episode_tokens_are_not_interpreted_as_episode(sup_modules, name):
    assert sup_modules.load("catalog.target_normalizers").extract_episode_hint(name) is None


def make_catalog(modules, tmp_path, records):
    module = modules.load("catalog.local_media_catalog")
    owner = types.SimpleNamespace(
        _local_entries_cache={"loaded_at": None, "entries": [], "media_count": 0},
        _cache_ttl_seconds=1800, _manual_strm_enabled=False, _manual_strm_paths=[],
        _normalize_text=lambda value: str(value or "").strip(),
        _cache_loaded_at=lambda value: datetime.fromisoformat(value) if isinstance(value, str) else value,
        _entry_path_is_valid=lambda entry: True,
        _build_entry_from_history=lambda history: dict(history),
        _invalidate_match_history_cache=Mock(),
        get_data_path=lambda: tmp_path,
    )
    calls = []

    def list_by_page(**kwargs):
        calls.append(kwargs)
        start = (kwargs["page"] - 1) * kwargs["count"]
        return records[start:start + kwargs["count"]]

    histories = types.SimpleNamespace(list_by_page=list_by_page)
    catalog = module.LocalMediaCatalog(owner, transfer_history=histories, http_exception=CatalogHttpError, logger=Mock(), target_entry_cache=Mock())
    return module, owner, catalog, histories, calls


def history_records(count):
    return [{"id": str(index), "path": f"/media/episode-{index}.mkv", "media_key": f"show-{index // 20}"} for index in range(count)]


@pytest.mark.parametrize("count", [5001, 18691, 30000])
def test_all_history_pages_are_indexed_and_survive_restart(sup_modules, tmp_path, count):
    records = history_records(count)
    module, owner, catalog, _, calls = make_catalog(sup_modules, tmp_path, records)
    entries = catalog.load_local_entries(force=True)
    assert len(entries) == count
    assert entries[-1]["id"] == str(count - 1)
    assert all(call["count"] == module.HISTORY_PAGE_SIZE for call in calls)
    assert len(calls) >= (count + module.HISTORY_PAGE_SIZE - 1) // module.HISTORY_PAGE_SIZE
    _, restored_owner, restored, _, restore_calls = make_catalog(sup_modules, tmp_path, [])
    assert len(restored.load_local_entries()) == count
    assert restored_owner._local_entries_cache["complete"] is True
    assert restore_calls == []


def test_old_cache_is_rebuilt_and_incremental_merge_does_not_evict_old_entries(sup_modules, tmp_path):
    records = history_records(5001)
    _, owner, catalog, _, calls = make_catalog(sup_modules, tmp_path, records)
    catalog.local_cache_file().write_text(json.dumps({"loaded_at": datetime.now().isoformat(), "entries": records[:100], "media_count": 5}), encoding="utf-8")
    assert len(catalog.load_local_entries()) == 5001
    assert len(calls) > 1
    catalog.merge_local_entries_cache([{"id": "added", "path": "/media/new.mkv", "media_key": "new"}])
    assert len(owner._local_entries_cache["entries"]) == 5002
    assert any(entry["id"] == "5000" for entry in owner._local_entries_cache["entries"])


def test_background_refresh_preserves_concurrent_addition_and_removal(sup_modules, tmp_path):
    records = history_records(1200)
    _, owner, catalog, histories, _ = make_catalog(sup_modules, tmp_path, records)
    owner._local_entries_cache = {"loaded_at": datetime.now(), "entries": [dict(entry) for entry in records], "complete": True}
    original = histories.list_by_page
    deleted = set()
    owner._entry_path_is_valid = lambda entry: entry["path"] not in deleted

    def during_scan(**kwargs):
        if kwargs["page"] == 2:
            catalog.merge_local_entries_cache([{"id": "new", "path": "/media/new.mkv", "media_key": "new"}])
            deleted.add(records[3]["path"])
            catalog.prune_local_entries_cache()
        return original(**kwargs)

    histories.list_by_page = during_scan
    entries = catalog.load_local_entries(force=True)
    ids = {entry["id"] for entry in entries}
    assert "new" in ids and "3" not in ids
    assert len(ids) == len(records)


def test_refresh_failure_keeps_last_complete_snapshot(sup_modules, tmp_path):
    records = history_records(1200)
    _, owner, catalog, histories, _ = make_catalog(sup_modules, tmp_path, records)
    catalog.load_local_entries(force=True)
    saved = owner._local_entries_cache
    original = histories.list_by_page

    def broken(**kwargs):
        if kwargs["page"] == 2:
            raise RuntimeError("database failed")
        return original(**kwargs)

    histories.list_by_page = broken
    owner.services = types.SimpleNamespace(subtitle_inventory=lambda: types.SimpleNamespace(clear_subtitle_directory_cache=Mock()))
    with pytest.raises(Exception, match="database failed"):
        catalog.refresh_local_cache()
    assert owner._local_entries_cache is saved


def test_large_fresh_snapshot_does_not_stat_every_media_on_each_query(sup_modules, tmp_path):
    records = history_records(30000)
    _, owner, catalog, _, calls = make_catalog(sup_modules, tmp_path, records)
    catalog.load_local_entries(force=True)
    owner._entry_path_is_valid = Mock(side_effect=AssertionError("fresh index must not stat every file"))
    assert len(catalog.load_local_entries(allow_stale=True)) == 30000
    owner._entry_path_is_valid.assert_not_called()


def test_incremental_event_checks_new_paths_without_rescanning_old_library(sup_modules, tmp_path):
    records = history_records(5001)
    _, owner, catalog, _, _ = make_catalog(sup_modules, tmp_path, records)
    catalog.load_local_entries(force=True)
    owner._entry_path_is_valid = Mock(return_value=True)
    catalog.merge_local_entries_cache([{"id": "new", "path": "/media/new.mkv", "media_key": "new"}])
    assert owner._entry_path_is_valid.call_count == 1
    assert len(owner._local_entries_cache["entries"]) == 5002


def test_resolved_target_from_snapshot_is_validated_before_use(sup_modules, tmp_path):
    records = history_records(1)
    _, owner, catalog, _, _ = make_catalog(sup_modules, tmp_path, records)
    catalog.load_local_entries(force=True)
    owner._brief_ids = lambda values: ",".join(values)
    owner._entry_path_is_valid = lambda entry: False
    catalog._target_entry_cache.get.return_value = None
    assert catalog.resolve_targets(["0"]) == {}


def test_repeating_history_page_fails_instead_of_hanging_or_publishing_partial_index(sup_modules, tmp_path):
    records = history_records(1200)
    module, owner, catalog, histories, _ = make_catalog(sup_modules, tmp_path, records)
    original = owner._local_entries_cache
    histories.list_by_page = lambda **kwargs: records[:module.HISTORY_PAGE_SIZE]
    with pytest.raises(CatalogHttpError, match="分页未前进"):
        catalog.load_local_entries(force=True)
    assert owner._local_entries_cache is original


def test_manual_strm_incremental_change_keeps_complete_history_and_reads_exact_path(sup_modules, tmp_path):
    records = history_records(5001)
    _, owner, catalog, _, _ = make_catalog(sup_modules, tmp_path / "cache", records)
    catalog.load_local_entries(force=True)
    owner._manual_strm_enabled = True
    owner._manual_strm_paths = [str(tmp_path)]
    owner._subtitle_exts = sup_modules.formats.SUBTITLE_EXTS
    owner.services = types.SimpleNamespace(subtitle_inventory=lambda: types.SimpleNamespace(invalidate_directory=Mock()))
    source = tmp_path / "Show.S01E99.strm"
    source.write_text("https://example.invalid/video", encoding="utf-8")
    manual = sup_modules.load("catalog.manual_strm").ManualStrmCatalog(
        normalize_text=owner._normalize_text, safe_int=lambda value, default=0: int(value or default),
        hash_text=lambda value: value, extract_episode_hint=sup_modules.load("catalog.target_normalizers").extract_episode_hint,
        meta_info_path=None, logger_warning=Mock(),
    )
    catalog._manual_strm_catalog = manual
    result = catalog.apply_manual_strm_changes([str(source)])
    assert len(result["changed_entries"]) == 1
    assert len(owner._local_entries_cache["entries"]) == 5002
    assert owner._local_entries_cache["complete"] is True
    source.unlink()
    catalog.apply_manual_strm_changes([str(source)])
    assert len(owner._local_entries_cache["entries"]) == 5001


def test_manual_strm_scan_is_not_limited_to_5000_candidates(sup_modules, tmp_path):
    module = sup_modules.load("catalog.manual_strm")
    catalog = module.ManualStrmCatalog(
        normalize_text=str, safe_int=lambda value, default=0: int(value or default),
        hash_text=str, extract_episode_hint=lambda name: None, meta_info_path=None, logger_warning=Mock(),
    )
    catalog._iter_strm_files = lambda root: (root / f"Episode-{index}.strm" for index in range(5001))
    catalog._entry_from_path = lambda root, path: {"id": path.name, "path": str(path)}
    assert len(catalog.scan([str(tmp_path)])) == 5001


def test_empty_legacy_upload_session_cannot_write_empty_subtitle(sup_modules, tmp_path):
    source = tmp_path / "empty.srt"
    source.touch()
    writer, _, _ = make_bitmap_writer(sup_modules, tmp_path)
    target = make_target(tmp_path)
    with pytest.raises(Exception, match="内容为空"):
        writer.build_write_operations(
            [{"upload_id": "empty", "target_id": target["id"], "ext": ".srt"}],
            {"empty": {"source_name": source.name, "stored_path": str(source)}}, {target["id"]: target},
        )


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "big5"])
def test_text_write_is_utf8_even_when_simplification_and_timeline_are_disabled(sup_modules, tmp_path, encoding):
    text = "[Script Info]\nTitle: 中文字幕\n這是一段繁體字幕，測試影片中的對話內容。\n"
    source = tmp_path / "uploaded.ass"
    original = text.encode(encoding)
    source.write_bytes(original)
    writer, owner, simplify = make_bitmap_writer(sup_modules, tmp_path)
    owner._traditional_to_simplified = False
    target = make_target(tmp_path)
    operations = writer.build_write_operations(
        [{"upload_id": "source", "target_id": target["id"], "language_suffix": "cht", "ext": ".ass"}],
        {"source": {"upload_id": "source", "source_name": source.name, "stored_path": str(source), "ext": ".ass"}},
        {target["id"]: target},
    )
    written, _, _ = writer.write_operations_to_disk(session_dir=tmp_path / "session", operations=operations)
    assert Path(written[0]["output_path"]).read_text(encoding="utf-8") == text
    assert source.read_bytes() == original
    simplify.assert_not_called()


@pytest.mark.parametrize("extension", [".smi", ".sami", ".ttml", ".dfxp"])
def test_encoding_declarations_match_utf8_output(sup_modules, tmp_path, extension):
    module = sup_modules.load("matching.subtitle_encoding")
    if extension in {".smi", ".sami"}:
        text = '<SAMI><HEAD><META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=big5"></HEAD><BODY><SYNC Start=0><P>這是繁體字幕</BODY></SAMI>'
        raw = text.encode("big5")
    else:
        raw = '<?xml version="1.0" encoding="utf-16"?><tt><body><p>這是繁體字幕</p></body></tt>'.encode("utf-16")
    source = tmp_path / f"source{extension}"
    output = tmp_path / f"output{extension}"
    source.write_bytes(raw)
    module.normalize_subtitle_encoding(source, output)
    result = output.read_text(encoding="utf-8")
    assert "這是繁體字幕" in result
    assert "charset=big5" not in result and 'encoding="utf-16"' not in result


@pytest.mark.parametrize("stream", [False, True])
def test_text_is_normalized_before_timeline_or_stream_skip(sup_modules, tmp_path, stream):
    text = "[Script Info]\nTitle: 中文字幕\n這是一段繁體字幕，測試影片中的對話內容。\n"
    source = tmp_path / "source.ass"
    source.write_bytes(text.encode("gb18030"))
    writer, owner, _ = make_bitmap_writer(sup_modules, tmp_path)
    owner._traditional_to_simplified = False
    owner._timeline_result_blocks_auto_write = lambda result: False
    target = make_target(tmp_path)
    if stream:
        path = Path(target["path"]).with_suffix(".strm")
        path.touch()
        target["path"] = str(path)

    def fix(**kwargs):
        assert kwargs["subtitle_path"].read_text(encoding="utf-8") == text
        kwargs["output_path"].write_bytes(kwargs["subtitle_path"].read_bytes())
        return sup_modules.timeline.TimelineFixResult(enabled=True, applied=False, reason="offset below threshold", base="audio", offset_seconds=0, scale_factor=1, score=1)

    owner._run_timeline_fix = Mock(side_effect=fix)
    operations = writer.build_write_operations(
        [{"upload_id": "text", "target_id": target["id"], "language_suffix": "chi", "ext": ".ass"}],
        {"text": {"upload_id": "text", "source_name": source.name, "stored_path": str(source)}}, {target["id"]: target},
    )
    written, _, _ = writer.write_operations_to_disk(session_dir=tmp_path / "session", operations=operations, fix_timeline=True)
    assert Path(written[0]["output_path"]).read_text(encoding="utf-8") == text
    assert owner._run_timeline_fix.call_count == (0 if stream else 1)


def test_binary_text_and_invalid_declared_encoding_fail_without_output(sup_modules, tmp_path):
    module = sup_modules.load("matching.subtitle_encoding")
    for raw in [b"\x00\x80\x00\x81\x12", b'<SAMI><META charset="made-up">\xff</SAMI>']:
        source = tmp_path / "broken.smi"
        output = tmp_path / "output.smi"
        source.write_bytes(raw)
        with pytest.raises(ValueError):
            module.normalize_subtitle_encoding(source, output)
        assert not output.exists()
