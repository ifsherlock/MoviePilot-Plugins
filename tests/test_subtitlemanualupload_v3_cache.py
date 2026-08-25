from __future__ import annotations

import importlib.util
import sys
import types
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V3_CATALOG = ROOT / "plugins.v3/subtitlemanualupload/catalog"


def load_subtitle_inventory():
    package_name = "subtitlemanualupload_v3_inventory_testpkg"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(V3_CATALOG)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.subtitle_inventory",
        V3_CATALOG / "subtitle_inventory.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SubtitleInventory


def load_local_media_catalog():
    package_name = "subtitlemanualupload_v3_catalog_testpkg"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(V3_CATALOG)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.local_media_catalog",
        V3_CATALOG / "local_media_catalog.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.LocalMediaCatalog


def make_inventory(*, trust=False):
    cls = load_subtitle_inventory()
    return cls(
        subtitle_exts={".ass", ".srt"},
        stream_exts={".strm"},
        embedded_text_codecs=set(),
        embedded_image_codecs=set(),
        embedded_probe_cache=OrderedDict(),
        embedded_probe_cache_max_size=10,
        trust_transfer_history_paths=trust,
        subtitle_directory_cache=OrderedDict(),
        subtitle_directory_cache_max_size=10,
        subtitle_directory_cache_ttl_seconds=900,
        normalize_text=lambda value: str(value or "").strip(),
        normalize_language_suffix=lambda value: str(value or "").strip(),
        detect_language_profile=lambda name, raw: {
            "suffix": "chi" if ".chi." in name else "eng",
            "category": "chinese" if ".chi." in name else "english",
        },
        is_chinese_language_suffix=lambda value: value == "chi",
        safe_int=lambda value, default=0: int(value) if str(value or "").isdigit() else default,
        subtitle_backup_path=lambda path: path.with_suffix(path.suffix + ".bak"),
        subprocess_module=types.SimpleNamespace(),
        logger_warning=lambda *args, **kwargs: None,
    )


def test_v3_trust_history_paths_keeps_external_subtitles(tmp_path):
    media_dir = tmp_path / "Season 1"
    media_dir.mkdir()
    video_path = media_dir / "S01E01.mkv"
    subtitle_path = media_dir / "S01E01.chi.ass"
    subtitle_path.write_text("subtitle", encoding="utf-8")

    inventory = make_inventory(trust=True)
    result = inventory.subtitle_files_for_targets(
        [{"id": "entry-1", "path": str(video_path), "storage": "local"}]
    )

    assert [item["name"] for item in result["entry-1"]] == ["S01E01.chi.ass"]


def test_v3_subtitle_directory_listing_is_shared_by_targets(tmp_path, monkeypatch):
    media_dir = tmp_path / "Season 1"
    media_dir.mkdir()
    first_video = media_dir / "S01E01.mkv"
    second_video = media_dir / "S01E02.mkv"
    first_video.touch()
    second_video.touch()
    (media_dir / "S01E01.chi.ass").write_text("one", encoding="utf-8")
    (media_dir / "S01E02.eng.srt").write_text("two", encoding="utf-8")

    inventory = make_inventory()
    original_iterdir = Path.iterdir
    original_read_bytes = Path.read_bytes
    calls = {"count": 0}
    reads = {"count": 0}

    def counting_iterdir(path):
        calls["count"] += 1
        return original_iterdir(path)

    def counting_read_bytes(path):
        reads["count"] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "iterdir", counting_iterdir)
    monkeypatch.setattr(Path, "read_bytes", counting_read_bytes)
    entries = [
        {"id": "entry-1", "path": str(first_video), "storage": "local"},
        {"id": "entry-2", "path": str(second_video), "storage": "local"},
    ]

    result = inventory.subtitle_files_for_targets(entries)
    first_call_count = calls["count"]
    cached_result = inventory.subtitle_files_for_targets(entries)

    assert first_call_count == 1
    assert calls["count"] == first_call_count
    assert reads["count"] == 2
    assert len(result["entry-1"]) == 1
    assert len(cached_result["entry-2"]) == 1


def test_v3_directory_signature_refreshes_when_subtitle_is_added(tmp_path, monkeypatch):
    media_dir = tmp_path / "Season 1"
    media_dir.mkdir()
    video = media_dir / "S01E01.mkv"
    video.touch()
    inventory = make_inventory()
    entries = [{"id": "entry-1", "path": str(video), "storage": "local"}]
    inventory.subtitle_files_for_targets(entries)
    (media_dir / "S01E01.chi.ass").write_text("new", encoding="utf-8")

    result = inventory.subtitle_files_for_targets(entries)

    assert [item["name"] for item in result["entry-1"]] == ["S01E01.chi.ass"]


def test_v3_invalidate_directory_forces_metadata_reload(tmp_path, monkeypatch):
    media_dir = tmp_path / "Season 1"
    media_dir.mkdir()
    video = media_dir / "S01E01.mkv"
    video.touch()
    (media_dir / "S01E01.chi.ass").write_text("subtitle", encoding="utf-8")
    inventory = make_inventory()
    entries = [{"id": "entry-1", "path": str(video), "storage": "local"}]
    original_read_bytes = Path.read_bytes
    reads = {"count": 0}

    def counting_read_bytes(path):
        reads["count"] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counting_read_bytes)
    inventory.subtitle_files_for_targets(entries)
    inventory.invalidate_directory(media_dir)
    inventory.subtitle_files_for_targets(entries)

    assert reads["count"] == 2


def test_v3_manual_strm_persisted_entry_respects_current_config(tmp_path):
    root = tmp_path / "strm"
    other_root = tmp_path / "other"
    root.mkdir()
    other_root.mkdir()
    strm = root / "Movie.strm"
    strm.write_text("remote", encoding="utf-8")
    owner = types.SimpleNamespace(
        _manual_strm_enabled=False,
        _manual_strm_paths=[str(root)],
        _normalize_text=lambda value: str(value or "").strip(),
    )
    cache = load_local_media_catalog()(
        owner,
        transfer_history=None,
        http_exception=RuntimeError,
        logger=types.SimpleNamespace(info=lambda *args: None, warning=lambda *args: None),
        target_entry_cache=types.SimpleNamespace(),
    )
    entry = {"origin": "manual_strm", "path": str(strm)}

    assert cache._entry_source_is_enabled(entry) is False
    owner._manual_strm_enabled = True
    assert cache._entry_source_is_enabled(entry) is True
    owner._manual_strm_paths = [str(other_root)]
    assert cache._entry_source_is_enabled(entry) is False


def test_manual_strm_incremental_changes_add_remove_and_invalidate_subtitles(tmp_path):
    for version_root, package_name in (
        (ROOT / "plugins.v2/subtitlemanualupload/catalog", "subtitlemanualupload_v2_incremental_testpkg"),
        (V3_CATALOG, "subtitlemanualupload_v3_incremental_testpkg"),
    ):
        root = tmp_path / package_name
        root.mkdir()
        strm = root / "Movie.strm"
        subtitle = root / "Movie.chi.srt"
        invalidated = []
        target_cache = types.SimpleNamespace(
            clear=lambda: None,
            remember=lambda entries: None,
            prune=lambda predicate: None,
        )

        class FakeManualCatalog:
            def scan(self, roots, max_entries=5000):
                if not strm.exists():
                    return []
                return [{
                    "id": "movie-target",
                    "origin": "manual_strm",
                    "media_key": "movie-key",
                    "media_type": "movie",
                    "title": "Movie",
                    "path": str(strm),
                    "basename": "Movie",
                    "filename": strm.name,
                    "target_label": strm.name,
                    "storage": "local",
                }]

        package = types.ModuleType(package_name)
        package.__path__ = [str(version_root)]
        sys.modules[package_name] = package
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.local_media_catalog",
            version_root / "local_media_catalog.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        owner = types.SimpleNamespace(
            _manual_strm_enabled=True,
            _manual_strm_paths=[str(root)],
            _subtitle_exts={".srt", ".ass"},
            _cache_max_entries=100,
            _local_entries_cache={"loaded_at": None, "entries": [], "media_count": 0, "persisted": False},
            _normalize_text=lambda value: str(value or "").strip(),
            _entry_path_is_valid=lambda entry: Path(entry["path"]).is_file(),
            _cache_loaded_at=lambda value: value,
            _invalidate_match_history_cache=lambda: None,
            get_data_path=lambda: tmp_path / f"data-{package_name}",
        )
        inventory = types.SimpleNamespace(invalidate_directory=lambda path: invalidated.append(path))
        owner.services = types.SimpleNamespace(subtitle_inventory=lambda: inventory)
        catalog = module.LocalMediaCatalog(
            owner,
            transfer_history=None,
            http_exception=RuntimeError,
            logger=types.SimpleNamespace(info=lambda *args: None, warning=lambda *args: None),
            target_entry_cache=target_cache,
            manual_strm_catalog=FakeManualCatalog(),
        )

        strm.write_text("remote", encoding="utf-8")
        added = catalog.apply_manual_strm_changes([str(strm)])
        assert [item["path"] for item in added["changed_entries"]] == [str(strm)]
        assert len(owner._local_entries_cache["entries"]) == 1

        subtitle.write_text("subtitle", encoding="utf-8")
        subtitle_change = catalog.apply_manual_strm_changes([str(subtitle)])
        assert subtitle_change["changed_entries"] == []
        assert root in invalidated

        strm.unlink()
        removed = catalog.apply_manual_strm_changes([str(strm)])
        assert str(strm) in removed["removed"]
        assert owner._local_entries_cache["entries"] == []
