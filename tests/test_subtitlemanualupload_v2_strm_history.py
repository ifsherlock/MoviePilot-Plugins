from __future__ import annotations

from pathlib import Path

from test_subtitlemanualupload_cache import load_plugin_module, make_plugin


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
