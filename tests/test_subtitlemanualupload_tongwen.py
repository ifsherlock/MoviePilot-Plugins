from __future__ import annotations

import importlib.util
from pathlib import Path


def load_tongwen_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "plugins.v2" / "subtitlemanualupload" / "matching" / "tongwen.py"
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_tongwen", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_traditional_to_simplified_uses_phrase_and_char_dicts():
    module = load_tongwen_module()

    assert module.traditional_to_simplified("繁體中文與極速快感") == "繁体中文与极品飞车"


def test_convert_subtitle_file_to_simplified(tmp_path):
    module = load_tongwen_module()
    source = tmp_path / "sample.cht.srt"
    output = tmp_path / "sample.chi.srt"
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\n這是一個繁體字幕\n", encoding="utf-8")

    converted = module.convert_subtitle_file_to_simplified(source, output)

    assert converted is True
    assert "这是一个繁体字幕" in output.read_text(encoding="utf-8")
