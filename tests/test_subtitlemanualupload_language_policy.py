from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=("plugins.v2", "plugins.v3"))
def language_modules(request):
    version = request.param
    plugin_path = ROOT / version / "subtitlemanualupload"
    package_name = f"language_policy_{version.replace('.', '_')}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(plugin_path)]
    sys.modules[package_name] = package
    online_package_name = f"{package_name}.online_subtitles"
    online_package = types.ModuleType(online_package_name)
    online_package.__path__ = [str(plugin_path / "online_subtitles")]
    sys.modules[online_package_name] = online_package
    try:
        yield types.SimpleNamespace(
            language=importlib.import_module(f"{package_name}.matching.subtitle_language"),
            online=importlib.import_module(f"{package_name}.online_subtitles.language"),
        )
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)


def test_language_combinations_have_exact_buckets(language_modules):
    language = language_modules.language

    assert language.auto_language_bucket("chi&eng") == "chi&eng"
    assert language.auto_language_bucket("eng&cht") == "chi&eng"
    assert language.auto_language_bucket("eng&zh") == "chi&eng"
    assert language.auto_language_bucket("jpn+chi") == "chi&jp"
    assert language.auto_language_bucket("kor,chs") == "chi&kr"
    assert language.auto_language_bucket("chi&jpn&eng") == "und"


def test_legacy_bilingual_migrates_without_losing_supported_languages(language_modules):
    language = language_modules.language
    legacy = ["bilingual", "chi", "cht", "eng"]

    normalized = language.normalize_auto_language_priority(legacy)

    assert normalized == ["chi&eng", "chi&jp", "chi&kr", "other_bilingual", "chi", "cht", "eng"]
    assert language.normalize_auto_language_priority(normalized) == normalized
    assert language.normalize_auto_language_priority([]) == []
    assert language.normalize_auto_language_priority(None) == language.DEFAULT_AUTO_LANGUAGE_PRIORITY


def test_language_filter_and_sort_distinguish_pairs(language_modules):
    language = language_modules.language
    candidates = [
        {"source_name": "z-ass", "language_suffix": "chi&jp", "ext": ".ass"},
        {"source_name": "a-srt", "language_suffix": "chi&eng", "ext": ".srt"},
        {"source_name": "b-kr", "language_suffix": "chi&kr", "ext": ".srt"},
    ]
    priority = ["chi&eng"]

    assert language.language_matches_preferences("eng&cht", priority)
    assert not language.language_matches_preferences("chi&jp", priority)
    assert [item["language_suffix"] for item in sorted(candidates, key=lambda item: language.auto_subtitle_sort_key(item, language_priority=priority))] == ["chi&eng", "chi&jp", "chi&kr"]


def test_preferred_existing_subtitle_uses_exact_pair(language_modules):
    language = language_modules.language

    assert not language.target_has_preferred_subtitle({"subtitles": [{"language_suffix": "chi&jp"}]}, ["chi&eng"])
    assert language.target_has_preferred_subtitle({"subtitles": [{"language_suffix": "eng&cht"}]}, ["chi&eng"])


def test_strict_existing_subtitle_requires_selected_pair(language_modules):
    language = language_modules.language

    class Inventory:
        def embedded_subtitle_tracks_for_target(self, entry):
            return [{"language_suffix": "chi&jp"}]

    target = {"subtitles": [{"language_suffix": "chi&jp"}]}
    assert not language.auto_target_has_chinese_subtitle(
        {}, target, subtitle_inventory=Inventory(), language_priority=["chi&eng"], strict=True
    )
    target["subtitles"].append({"language_suffix": "chi&eng"})
    assert language.auto_target_has_chinese_subtitle(
        {}, target, subtitle_inventory=Inventory(), language_priority=["chi&eng"], strict=True
    )


def test_text_profile_recognizes_named_pairs_and_leaves_generic_unknown(language_modules):
    language = language_modules.language

    assert language.language_profile_from_text("Example 中英双语.ass") == {"suffix": "chi&eng", "label": "中英双语"}
    assert language.language_profile_from_text("Example 中日双语.srt") == {"suffix": "chi&jp", "label": "中日双语"}
    assert language.language_profile_from_text("Example 中韩双语.srt") == {"suffix": "chi&kr", "label": "中韩双语"}
    assert language.language_profile_from_text("Movie Chinese-English") == {"suffix": "chi&eng", "label": "中英双语"}
    assert language.language_profile_from_text("Example 双语.srt")["suffix"] == "und"


def test_online_labels_do_not_guess_generic_or_other_pairs_as_english(language_modules):
    online = language_modules.online

    assert online._guess_language_label("chs&eng.ass") == "简英双语"
    assert online._guess_language_label("字幕包 中日双语") == "中日双语"
    assert online._guess_language_label("字幕包 中韩双语") == "中韩双语"
    assert online._guess_language_label("字幕包 双语") == ""


def test_ass_metadata_does_not_override_dialogue_language(language_modules):
    language = language_modules.language
    ass = """[Script Info]
Title: English
Style: English Header
[V4+ Styles]
Format: Name, Fontname
Style: Default,Arial
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,这是中文字幕内容这是中文字幕内容
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,这是中文字幕内容这是中文字幕内容
"""

    profile = language.detect_language_profile("movie.ass", ass.encode("utf-8"), {".ass", ".srt"})

    assert profile["suffix"] == "chi"


def test_filename_labels_cover_known_pair_aliases(language_modules):
    language = language_modules.language

    assert language.language_suffix_from_filename("movie.chs&eng.srt", {".srt"})["label"] == "中英双语"
    assert language.language_suffix_from_filename("movie.chi+jpn.srt", {".srt"})["label"] == "中日双语"
    assert language.language_suffix_from_filename("movie.chs+kor.srt", {".srt"})["label"] == "中韩双语"


def test_dialogue_distinguishes_japanese_from_chinese_japanese(language_modules):
    language = language_modules.language
    japanese = "日本語の字幕を表示します。" * 30
    chinese = "这是中文字幕内容，请确认语言。" * 30

    assert language.detect_language_profile("movie.srt", japanese.encode(), {".srt"})["suffix"] == "jpn"
    assert language.detect_language_profile("movie.srt", (chinese + japanese).encode(), {".srt"})["suffix"] == "chi&jp"


def test_strict_candidate_filter_checks_specific_pairs(language_modules):
    language = language_modules.language
    candidates = [
        {"title": "Movie 中日双语", "language": "Chinese", "score": 99},
        {"title": "Movie 双语", "language": "Chinese", "score": 95},
        {"title": "Movie 中英双语", "language": "Chinese", "score": 90},
    ]

    assert [item["title"] for item in language.auto_rank_candidates(candidates, ["chi&eng"], strict=True)] == [
        "Movie 中英双语", "Movie 双语"
    ]
    assert language.auto_rank_candidates(candidates, [], strict=True) == []
    assert [item["title"] for item in language.auto_rank_candidates(candidates, ["chi&eng"], strict=False)] == [
        "Movie 中英双语", "Movie 双语", "Movie 中日双语"
    ]


def test_kanji_heavy_japanese_is_not_chinese_japanese(language_modules):
    text = "国際連合安全保障理事会の緊急会議開催について報告します。" * 30
    profile = language_modules.language.detect_language_profile("movie.srt", text.encode(), {".srt"})
    assert profile["suffix"] == "jpn"


@pytest.mark.parametrize("ext", [".ass", ".ssa"])
def test_ass_dialogue_keeps_commas_and_line_breaks(language_modules, ext):
    chinese = "这是中文字幕文本内容，请不要丢失前半句话。"
    english = "Hello, this is a complete English subtitle line, with commas."
    lines = [f"Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{chinese}\\N{english}" for _ in range(8)]
    text = "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(lines)
    profile = language_modules.language.detect_language_profile(f"movie{ext}", text.encode(), {ext})
    assert profile["suffix"] == "chi&eng"
