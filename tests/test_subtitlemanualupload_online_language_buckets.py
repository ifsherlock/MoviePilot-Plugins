import importlib
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture(params=("plugins.v2", "plugins.v3"))
def result_model(request):
    name = f"online_buckets_{request.param.replace('.', '_')}"
    root = Path(__file__).resolve().parents[1] / request.param / "subtitlemanualupload"
    for module_name, path in ((name, root), (name + ".online_subtitles", root / "online_subtitles")):
        package = types.ModuleType(module_name)
        package.__path__ = [str(path)]
        sys.modules[module_name] = package
    try:
        yield importlib.import_module(name + ".online_subtitles.models").OnlineSubtitleResult
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + "."):
                sys.modules.pop(key, None)


@pytest.mark.parametrize("title,language,bucket", [
    ("Show 中英双语", "Chinese", "chi&eng"),
    ("Show 中日双语", "Chinese", "chi&jp"),
    ("Show 中韩双语", "English", "chi&kr"),
    ("Show", "繁英双语", "chi&eng"),
    ("Show 中法双语", "Chinese", "other_bilingual"),
    ("Show 中德双语", "Chinese", "other_bilingual"),
    ("Show 中西双语", "Chinese", "other_bilingual"),
    ("Show", "简体中文", "chi"),
    ("Show", "繁中", "cht"),
    ("Show", "English", "eng"),
    ("Show", "日文", "jpn"),
    ("Show", "韩文", "kor"),
    ("Show", "French", "other"),
    ("Show 双语", "Chinese", "und"),
    ("Show bilingual", "", "und"),
    ("Show", "", "und"),
])
def test_serialized_results_expose_precise_language_bucket(result_model, title, language, bucket):
    result = result_model(provider="subhd", result_id="sample", title=title, page_url="", language=language)
    payload = result.to_dict()
    assert payload["language_bucket"] == bucket
    assert payload["language"] == language


def test_coarse_provider_category_does_not_hide_explicit_bilingual_pair(result_model):
    result = result_model(provider="subhd", result_id="sample", title="Show 中日双语", page_url="",
                          language="Chinese", language_category="chinese")
    assert result.to_dict()["language_bucket"] == "chi&jp"
