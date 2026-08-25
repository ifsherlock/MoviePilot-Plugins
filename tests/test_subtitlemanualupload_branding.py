import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins.v2" / "subtitlemanualupload"
BRAND_NAME = "海拉鲁字幕大师"
VERSION = "0.1.91"
ICON_URL = (
    "https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/"
    "main/icons/hyrule-subtitle-master.png"
)


def _plugin_constants() -> dict[str, str]:
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    plugin_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SubtitleManualUpload"
    )
    constants = {}
    for node in plugin_class.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value.value, str):
                constants[target.id] = node.value.value
    return constants


def test_release_branding_stays_in_sync():
    for package_name in ("package.json", "package.v2.json"):
        package = json.loads((ROOT / package_name).read_text(encoding="utf-8"))
        metadata = package["SubtitleManualUpload"]
        assert metadata["name"] == BRAND_NAME
        assert metadata["version"] == VERSION
        assert metadata["icon"] == ICON_URL
        assert "ChineseSubFinder" in metadata["description"]
        assert f"v{VERSION}" in metadata["history"]

    plugin_package = json.loads((PLUGIN_DIR / "package.json").read_text(encoding="utf-8"))
    assert plugin_package["version"] == VERSION

    constants = _plugin_constants()
    assert constants["plugin_name"] == BRAND_NAME
    assert constants["plugin_version"] == VERSION
    assert constants["plugin_icon"] == ICON_URL
    assert "ChineseSubFinder" in constants["plugin_desc"]


def test_branding_reaches_user_visible_surfaces_and_icon():
    visible_surfaces = (
        PLUGIN_DIR / "README.md",
        PLUGIN_DIR / "index.html",
        PLUGIN_DIR / "src" / "components" / "Config.vue",
        PLUGIN_DIR / "src" / "components" / "Page.vue",
        PLUGIN_DIR / "src" / "components" / "UploadDialog.vue",
        PLUGIN_DIR / "src" / "mobile" / "MobileSubtitleHome.vue",
        PLUGIN_DIR / "src" / "mobile" / "MobileSubtitleDetail.vue",
        PLUGIN_DIR / "src" / "mobile" / "MobileSubtitlePage.vue",
    )
    for surface in visible_surfaces:
        assert BRAND_NAME in surface.read_text(encoding="utf-8"), surface

    init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert '"title": "海拉鲁字幕大师"' in init_source

    icon = ROOT / "icons" / "hyrule-subtitle-master.png"
    assert icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
