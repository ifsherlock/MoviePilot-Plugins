from __future__ import annotations

import codecs
from pathlib import Path


def test_autosubv3_requirements_are_utf8_without_bom():
    root = Path(__file__).resolve().parents[1]

    for variant in ("v2", "v3"):
        requirements = root / f"plugins.{variant}" / "autosubv3" / "requirements.txt"
        raw = requirements.read_bytes()
        text = raw.decode("utf-8")
        lines = [line for line in text.splitlines() if line.strip()]

        assert not raw.startswith(codecs.BOM_UTF8), f"{requirements} contains a UTF-8 BOM"
        assert "\ufeff" not in text, f"{requirements} contains an embedded BOM"
        assert lines[0] == "iso639~=0.1.4"
