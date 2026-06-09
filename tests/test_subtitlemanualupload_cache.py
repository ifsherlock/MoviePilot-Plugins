from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def load_plugin_module():
    root = Path(__file__).resolve().parents[1]
    package_dir = root / "plugins.v2" / "subtitlemanualupload"

    class HTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class PluginBase:
        def get_data_path(self):
            return root / ".tmp-test-data"

    class FakeTransferHistory:
        calls = 0
        data = []

        @classmethod
        def list_by_page(cls, **kwargs):
            cls.calls += 1
            return list(cls.data)

    class FakeSiteOper:
        data = []

        def list(self):
            return list(self.data)

    async def run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    modules = {
        "fastapi": types.SimpleNamespace(HTTPException=HTTPException, Request=object),
        "starlette": types.ModuleType("starlette"),
        "starlette.concurrency": types.SimpleNamespace(run_in_threadpool=run_in_threadpool),
        "starlette.datastructures": types.SimpleNamespace(UploadFile=object),
        "app": types.ModuleType("app"),
        "app.core": types.ModuleType("app.core"),
        "app.core.config": types.SimpleNamespace(
            settings=types.SimpleNamespace(TMDB_IMAGE_DOMAIN="image.tmdb.org", RMT_MEDIAEXT={".mkv", ".mp4", ".strm"})
        ),
        "app.core.metainfo": types.SimpleNamespace(MetaInfoPath=lambda path: types.SimpleNamespace()),
        "app.db": types.ModuleType("app.db"),
        "app.db.site_oper": types.SimpleNamespace(SiteOper=FakeSiteOper),
        "app.db.models": types.ModuleType("app.db.models"),
        "app.db.models.transferhistory": types.SimpleNamespace(TransferHistory=FakeTransferHistory),
        "app.log": types.SimpleNamespace(
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None,
                warning=lambda *args, **kwargs: None,
                error=lambda *args, **kwargs: None,
            )
        ),
        "app.plugins": types.SimpleNamespace(_PluginBase=PluginBase),
    }
    for name, module in modules.items():
        sys.modules[name] = module

    package_name = "subtitlemanualupload_cache_testpkg"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module, FakeTransferHistory, FakeSiteOper


def make_plugin(module):
    plugin = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)
    plugin._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
    plugin._entry_map = module.OrderedDict()
    plugin._cache_refreshing = False
    plugin._cache_ttl_seconds = 90
    plugin._cache_max_entries = 10
    plugin._entry_map_max_size = 2
    plugin._build_entry_from_history = lambda history: dict(history)
    cache_file = plugin._local_cache_file()
    if cache_file.exists():
        cache_file.unlink()
    return plugin


def test_local_entries_cache_hits_until_forced_refresh():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [{"id": "a", "path": "/media/a.mkv", "media_key": "movie-a"}]

    first = plugin._load_local_entries()
    second = plugin._load_local_entries()
    forced = plugin._load_local_entries(force=True)

    assert first == second == forced
    assert histories.calls == 2
    assert plugin._cache_status()["entry_count"] == 1
    assert plugin._cache_status()["media_count"] == 1


def test_refresh_local_cache_rebuilds_entries():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [{"id": "a", "path": "/media/a.mkv", "media_key": "movie-a"}]
    plugin._load_local_entries()

    histories.data = [{"id": "b", "path": "/media/b.mkv", "media_key": "movie-b"}]
    refreshed = plugin._refresh_local_cache()

    assert [item["id"] for item in refreshed] == ["b"]
    assert list(plugin._entry_map.keys()) == ["b"]


def test_local_entries_cache_persists_between_plugin_instances():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    histories.data = [{"id": "a", "path": "/media/a.mkv", "media_key": "movie-a"}]

    first = plugin._load_local_entries()
    plugin2 = module.SubtitleManualUpload.__new__(module.SubtitleManualUpload)
    plugin2._local_entries_cache = {"loaded_at": None, "entries": [], "media_count": 0, "persisted": False}
    plugin2._entry_map = module.OrderedDict()
    plugin2._cache_refreshing = False
    plugin2._cache_ttl_seconds = 90
    plugin2._cache_max_entries = 10
    plugin2._entry_map_max_size = 2
    plugin2._build_entry_from_history = lambda history: dict(history)

    restored = plugin2._load_local_entries()

    assert restored == first
    assert histories.calls == 1
    assert plugin2._cache_status()["persisted"] is True


def test_stale_persisted_cache_returns_before_background_refresh():
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    old_time = module.datetime.now() - module.timedelta(seconds=120)
    plugin._local_entries_cache = {
        "loaded_at": old_time,
        "entries": [{"id": "stale", "path": "/media/stale.mkv", "media_key": "movie-stale"}],
        "media_count": 1,
        "persisted": True,
    }
    started = {"value": False}
    plugin._start_background_cache_refresh = lambda: started.update(value=True)

    entries = plugin._load_local_entries(allow_stale=True)

    assert [item["id"] for item in entries] == ["stale"]
    assert started["value"] is True


def test_transfer_event_entries_can_merge_into_local_cache(tmp_path):
    module, histories, _ = load_plugin_module()
    plugin = make_plugin(module)
    histories.calls = 0
    video = tmp_path / "Example.Show.S01E02.mkv"
    video.write_text("video")
    meta = types.SimpleNamespace(begin_season=1, begin_episode=2, episode_list=[2])
    mediainfo = types.SimpleNamespace(type="电视剧", title="Example Show", year="2024", tmdb_id=123)
    transferinfo = types.SimpleNamespace(file_list_new=[str(video)])

    entries = plugin._entries_from_transfer_event(
        {
            "meta": meta,
            "mediainfo": mediainfo,
            "transferinfo": transferinfo,
        }
    )
    plugin._merge_local_entries_cache(entries)

    assert len(entries) == 1
    assert entries[0]["media_type"] == "tv"
    assert entries[0]["season"] == 1
    assert entries[0]["episode"] == 2
    assert plugin._cache_status()["entry_count"] == 1


def test_entry_map_is_bounded_lru():
    module, _, _ = load_plugin_module()
    plugin = make_plugin(module)

    plugin._remember_targets([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    plugin._remember_targets([{"id": "b"}])
    plugin._remember_targets([{"id": "d"}])

    assert list(plugin._entry_map.keys()) == ["b", "d"]
