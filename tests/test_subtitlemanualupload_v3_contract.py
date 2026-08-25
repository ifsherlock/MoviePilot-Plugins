from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v3_manual_strm_config_and_manifest_are_consistent():
    schema = (ROOT / "plugins.v3/subtitlemanualupload/config/config_schema.py").read_text(encoding="utf-8-sig")
    runtime = (ROOT / "plugins.v3/subtitlemanualupload/config/config_runtime.py").read_text(encoding="utf-8-sig")
    factory = (ROOT / "plugins.v3/subtitlemanualupload/runtime/service_factories.py").read_text(encoding="utf-8-sig")
    owner = (ROOT / "plugins.v3/subtitlemanualupload/__init__.py").read_text(encoding="utf-8-sig")
    package = json.loads((ROOT / "plugins.v3/subtitlemanualupload/package.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))

    assert "manual_strm_enabled" in schema
    assert "manual_strm_paths" in schema
    assert '"_manual_strm_enabled"' in runtime
    assert '"_manual_strm_paths"' in runtime
    assert "ManualStrmCatalog" in factory
    assert "MetaInfoPath(path, force_video=True)" in factory
    assert "build_media_key=build_media_key" in factory
    assert '"origin": "manual_strm"' in (ROOT / "plugins.v3/subtitlemanualupload/catalog/manual_strm.py").read_text(encoding="utf-8-sig")
    assert package["version"] == "1.2.6"
    assert index["SubtitleManualUpload"]["version"] == package["version"]
    assert "manual_strm_enabled" in owner


def test_v2_v3_use_batch_subtitle_resolution_and_precise_invalidation():
    for version in ("plugins.v2", "plugins.v3"):
        root = ROOT / version / "subtitlemanualupload"
        factory = (root / "runtime/service_factories.py").read_text(encoding="utf-8-sig")
        resolver = (root / "catalog/media_target_resolver.py").read_text(encoding="utf-8-sig")
        writer = (root / "matching/subtitle_writer.py").read_text(encoding="utf-8-sig")
        inventory = (root / "catalog/subtitle_inventory.py").read_text(encoding="utf-8-sig")

        assert "subtitle_files_batch_provider" in resolver
        assert "subtitle_files_batch_provider=getattr(subtitle_inventory_service, \"subtitle_files_for_targets\", None)" in factory
        assert "invalidate_directory" in writer
        assert "def invalidate_directory" in inventory


def test_v2_v3_match_history_cache_version_is_three():
    for version in ("plugins.v2", "plugins.v3"):
        source = (ROOT / version / "subtitlemanualupload/matching/subtitle_history.py").read_text(encoding="utf-8-sig")
        assert "MATCH_HISTORY_CACHE_VERSION = 3" in source
        assert '"version": MATCH_HISTORY_CACHE_VERSION' in source


def test_v2_v3_strm_placeholder_uses_real_newline_binding():
    for version in ("plugins.v2", "plugins.v3"):
        source = (ROOT / version / "subtitlemanualupload/src/components/Config.vue").read_text(encoding="utf-8-sig")
        assert "const manualStrmPathPlaceholder = `/vol2/1000/raid/2/links2\n/vol1/1000/media-strm`" in source
        assert ':placeholder="manualStrmPathPlaceholder"' in source
        assert 'placeholder="/vol2/1000/raid/2/links2\\n/vol1/1000/media-strm"' not in source


def test_v2_v3_targets_initialize_tmdb_detail_before_optional_lookup():
    for version in ("plugins.v2", "plugins.v3"):
        source = (ROOT / version / "subtitlemanualupload/catalog/media_target_resolver.py").read_text(encoding="utf-8-sig")
        function = source.split("def targets_for_media", 1)[1].split("def is_stream_path", 1)[0]
        initialization = function.index("tmdb_detail: Dict[str, Any] = {}")
        final_use = function.rindex("if tmdb_detail:")
        assert initialization < final_use
