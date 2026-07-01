from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple


RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources" / "tongwen"
PHRASE_DICT = RESOURCE_DIR / "t2s-phrase.min.json"
CHAR_DICT = RESOURCE_DIR / "t2s-char.min.json"


def _load_json(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return {str(key): str(value) for key, value in data.items()}


@lru_cache(maxsize=1)
def _load_t2s_dicts() -> Tuple[Tuple[Tuple[str, str], ...], Dict[int, str]]:
    phrases = _load_json(PHRASE_DICT)
    chars = _load_json(CHAR_DICT)
    ordered_phrases = tuple(sorted(phrases.items(), key=lambda item: len(item[0]), reverse=True))
    char_table = {ord(source): target for source, target in chars.items()}
    return ordered_phrases, char_table


def traditional_to_simplified(text: str) -> str:
    if not text:
        return text
    phrases, char_table = _load_t2s_dicts()
    converted = text
    for source, target in phrases:
        if source in converted:
            converted = converted.replace(source, target)
    return converted.translate(char_table)


def decode_subtitle_bytes(raw_bytes: bytes) -> Tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace"), "utf-8"


def convert_subtitle_file_to_simplified(source_path: Path, output_path: Path) -> bool:
    raw = source_path.read_bytes()
    text, _ = decode_subtitle_bytes(raw)
    converted = traditional_to_simplified(text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(converted, encoding="utf-8")
    return converted != text
