from __future__ import annotations

import importlib.util
import sys
import types
from collections import OrderedDict
from pathlib import Path

from test_subtitlemanualupload_cache import load_plugin_module, make_plugin


def load_v2_subtitle_inventory():
    root = Path(__file__).resolve().parents[1] / "plugins.v2/subtitlemanualupload/catalog"
    package_name = "subtitlemanualupload_v2_inventory_testpkg"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.subtitle_inventory",
        root / "subtitle_inventory.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SubtitleInventory


def test_v2_manual_strm_config_normalizes_absolute_paths():
    module, _, _ = load_plugin_module()
    schema = __import__(
        f"{module.__name__}.config.config_schema",
        fromlist=["normalize_plugin_config"],
    )

    normalized = schema.normalize_plugin_config(
        {
            "manual_strm_enabled": True,
            "manual_strm_paths": "/media/library\n/media/library/nested\nrelative\n/media/other",
        }
    )

    assert normalized["manual_strm_enabled"] is True
    assert normalized["manual_strm_paths"] == ["/media/other", "/media/library"]


def test_v2_local_media_catalog_merges_manual_strm_entries(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    root = tmp_path / "strm"
    root.mkdir()
    (root / "Example.Movie.strm").write_text("remote", encoding="utf-8")
    plugin._manual_strm_enabled = True
    plugin._manual_strm_paths = [str(root)]
    histories.data = []

    entries = plugin._local_media_catalog().load_local_entries(force=True)

    assert len(entries) == 1
    assert entries[0]["origin"] == "manual_strm"
    assert entries[0]["path"].endswith("Example.Movie.strm")


def test_v2_manual_strm_reads_generic_media_identity_nfo(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    root = tmp_path / "strm"
    root.mkdir()
    strm = root / "Example.Movie.strm"
    strm.write_text("remote", encoding="utf-8")
    strm.with_suffix(".nfo").write_text(
        "<movie><title>示例电影</title><media_source>themoviedb</media_source>"
        "<media_id>1234</media_id></movie>",
        encoding="utf-8",
    )
    plugin._manual_strm_enabled = True
    plugin._manual_strm_paths = [str(root)]
    histories.data = []

    entry = plugin._local_media_catalog().load_local_entries(force=True)[0]

    assert entry["media_source"] == "themoviedb"
    assert entry["media_id"] == "1234"
    assert entry["tmdb_id"] == 1234


def test_v2_service_factory_uses_core_metainfo_for_manual_strm():
    module, _, _ = load_plugin_module()
    source = Path(module.__file__).parent / "runtime/service_factories.py"
    text = source.read_text(encoding="utf-8-sig")

    assert "from app.core.metainfo import MetaInfoPath" in text
    assert "meta_info_path=MetaInfoPath" in text
    assert "from app.sdk" not in text


def test_v2_trust_history_paths_keeps_external_subtitles(tmp_path):
    media_dir = tmp_path / "Season 1"
    media_dir.mkdir()
    subtitle = media_dir / "S01E01.chi.ass"
    subtitle.write_text("subtitle", encoding="utf-8")
    inventory = load_v2_subtitle_inventory()(
        subtitle_exts={".ass", ".srt"},
        stream_exts={".strm"},
        embedded_text_codecs=set(),
        embedded_image_codecs=set(),
        embedded_probe_cache=OrderedDict(),
        embedded_probe_cache_max_size=10,
        trust_transfer_history_paths=True,
        normalize_text=lambda value: str(value or "").strip(),
        normalize_language_suffix=lambda value: str(value or "").strip(),
        detect_language_profile=lambda name, raw: {"suffix": "chi", "category": "chinese"},
        is_chinese_language_suffix=lambda value: value == "chi",
        safe_int=lambda value, default=0: int(value) if str(value or "").isdigit() else default,
        subtitle_backup_path=lambda path: path.with_suffix(path.suffix + ".bak"),
        subprocess_module=types.SimpleNamespace(),
        logger_warning=lambda *args, **kwargs: None,
    )

    result = inventory.subtitle_files_for_targets(
        [{"id": "entry-1", "path": str(media_dir / "S01E01.mkv"), "storage": "local"}]
    )

    assert [item["name"] for item in result["entry-1"]] == ["S01E01.chi.ass"]
