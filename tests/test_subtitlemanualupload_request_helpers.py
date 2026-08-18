import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPERS_PATH = ROOT / "plugins.v2" / "subtitlemanualupload" / "api" / "request_helpers.py"


def load_helpers_module():
    if "fastapi" not in sys.modules:
        fastapi_stub = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code=None, detail=None):
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        fastapi_stub.HTTPException = HTTPException
        sys.modules["fastapi"] = fastapi_stub
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_request_helpers", HELPERS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalize_text(value):
    return str(value or "").strip()


def test_results_from_body_accepts_selected_results_alias():
    helpers = load_helpers_module()

    assert helpers.results_from_body({"selected_results": {"id": "one"}}) == [{"id": "one"}]
    assert helpers.results_from_body({"results": [{"id": "one"}, "bad", {"id": "two"}]}) == [
        {"id": "one"},
        {"id": "two"},
    ]
    assert helpers.results_from_body({"results": "bad"}) == []


def test_online_keywords_keeps_manual_keyword_first_and_deduplicated():
    helpers = load_helpers_module()

    def build_search_keywords(_media, _targets, scope):
        assert scope == "auto"
        return ["The Million Pound Note", "百万英镑", "Manual"]

    keywords = helpers.online_keywords(
        {"keyword": "Manual"},
        [{"title": "百万英镑"}],
        normalize_text,
        build_search_keywords,
    )

    assert keywords == ["Manual", "The Million Pound Note", "百万英镑"]


def test_enrich_targets_with_media_restores_canonical_title_aliases():
    helpers = load_helpers_module()
    targets = [{"title": "我与超人的冒险", "en_title": "MAWS", "season": 3, "episode": 9}]
    media = {
        "original_title": "My Adventures with Superman",
        "en_title": "My Adventures with Superman",
        "tmdb_aliases": ["My Adventures with Superman", "MAWS"],
    }

    enriched = helpers.enrich_targets_with_media(targets, media)

    assert enriched[0]["original_title"] == "My Adventures with Superman"
    assert "My Adventures with Superman" in enriched[0]["tmdb_aliases"]
    assert enriched[0]["season"] == 3
    assert targets[0].get("original_title") is None
