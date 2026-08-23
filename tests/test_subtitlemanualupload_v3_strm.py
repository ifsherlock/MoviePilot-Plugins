from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V3_CATALOG = ROOT / "plugins.v3/subtitlemanualupload/catalog"
V2_CATALOG = ROOT / "plugins.v2/subtitlemanualupload/catalog"


def load_manual_strm_catalog(catalog_root=V3_CATALOG, package_name="subtitlemanualupload_v3_strm_testpkg"):
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(catalog_root)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.manual_strm",
        catalog_root / "manual_strm.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ManualStrmCatalog


def make_catalog(
    meta_info_path=None,
    *,
    catalog_root=V3_CATALOG,
    package_name="subtitlemanualupload_v3_strm_testpkg",
    build_media_key=None,
):
    cls = load_manual_strm_catalog(catalog_root, package_name)
    return cls(
        normalize_text=lambda value: str(value or "").strip(),
        safe_int=lambda value, default=0: int(value) if str(value or "").isdigit() else default,
        hash_text=lambda value: f"hash:{value}",
        extract_episode_hint=lambda value: (
            {"season": 1, "episode": 2}
            if "S01E02" in str(value)
            else None
        ),
        meta_info_path=meta_info_path,
        build_media_key=build_media_key,
        logger_warning=lambda *args, **kwargs: None,
    )


def test_v3_manual_strm_movie_uses_nfo_identity(tmp_path):
    movie_dir = tmp_path / "电影"
    movie_dir.mkdir()
    strm = movie_dir / "Example.Movie.2024.strm"
    strm.write_text("https://remote.invalid/movie", encoding="utf-8")
    strm.with_suffix(".nfo").write_text(
        "<movie><title>示例电影</title><year>2024</year>"
        "<uniqueid type=\"tmdb\">12345</uniqueid></movie>",
        encoding="utf-8",
    )

    entries = make_catalog().scan([str(movie_dir)])

    assert len(entries) == 1
    entry = entries[0]
    assert entry["origin"] == "manual_strm"
    assert entry["media_type"] == "movie"
    assert entry["title"] == "示例电影"
    assert entry["year"] == "2024"
    assert entry["media_source"] == "themoviedb"
    assert entry["media_id"] == "12345"
    assert entry["tmdb_id"] == 12345
    assert entry["writable"] is True


def test_v3_manual_strm_uses_injected_media_key_builder(tmp_path):
    strm = tmp_path / "Movie.strm"
    strm.write_text("remote", encoding="utf-8")
    strm.with_suffix(".nfo").write_text(
        "<movie><title>Movie</title><media_source>themoviedb</media_source>"
        "<media_id>2468</media_id></movie>",
        encoding="utf-8",
    )

    entry = make_catalog(
        build_media_key=lambda source, media_id: "tmdb:" + str(media_id)
        if source == "themoviedb"
        else "",
    ).scan([str(tmp_path)])[0]

    assert entry["media_source"] == "themoviedb"
    assert entry["media_id"] == "2468"
    assert entry["media_key"] == "tmdb:2468"


def test_v3_manual_strm_tv_uses_show_and_season_nfo(tmp_path):
    season_dir = tmp_path / "示例剧集 (2023)" / "Season 1"
    season_dir.mkdir(parents=True)
    (season_dir.parent / "tvshow.nfo").write_text(
        "<tvshow><title>示例剧集</title><year>2023</year>"
        "<uniqueid type=\"tmdb\">9876</uniqueid></tvshow>",
        encoding="utf-8",
    )
    (season_dir / "season.nfo").write_text(
        "<season><seasonnumber>1</seasonnumber></season>",
        encoding="utf-8",
    )
    strm = season_dir / "S01E02.strm"
    strm.write_text("https://remote.invalid/episode", encoding="utf-8")

    entries = make_catalog().scan([str(tmp_path)])

    assert len(entries) == 1
    entry = entries[0]
    assert entry["media_type"] == "tv"
    assert entry["title"] == "示例剧集"
    assert entry["year"] == "2023"
    assert entry["season"] == 1
    assert entry["episode"] == 2
    assert entry["media_source"] == "themoviedb"
    assert entry["media_id"] == "9876"


def test_v3_manual_strm_without_nfo_uses_injected_path_parser(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    strm = root / "Parsed.Show.S02E03.strm"
    strm.write_text("remote", encoding="utf-8")

    def fake_meta_info(path):
        return types.SimpleNamespace(
            type=types.SimpleNamespace(value="电视剧"),
            name="路径识别剧集",
            title="路径识别剧集",
            year="2025",
            begin_season=2,
            begin_episode=3,
        )

    entry = make_catalog(fake_meta_info).scan([str(root)])[0]

    assert entry["media_type"] == "tv"
    assert entry["title"] == "路径识别剧集"
    assert entry["year"] == "2025"
    assert entry["season"] == 2
    assert entry["episode"] == 3


def test_v3_manual_strm_scan_deduplicates_overlapping_roots(tmp_path):
    root = tmp_path / "library"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "S01E01.strm").write_text("remote", encoding="utf-8")

    entries = make_catalog().scan([str(root), str(nested)])

    assert len(entries) == 1


def test_v3_manual_strm_date_is_iso_sortable(tmp_path):
    strm = tmp_path / "Movie.strm"
    strm.write_text("remote", encoding="utf-8")

    entry = make_catalog().scan([str(tmp_path)])[0]

    assert entry["date"]
    assert "T" in entry["date"]


def test_v2_manual_strm_scanner_has_no_v3_runtime_dependency(tmp_path):
    strm = tmp_path / "V2.Movie.strm"
    strm.write_text("remote", encoding="utf-8")

    entries = make_catalog(
        catalog_root=V2_CATALOG,
        package_name="subtitlemanualupload_v2_strm_testpkg",
    ).scan([str(tmp_path)])

    assert len(entries) == 1
    assert entries[0]["origin"] == "manual_strm"
    assert entries[0]["date"]
