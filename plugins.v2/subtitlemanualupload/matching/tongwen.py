from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .subtitle_formats import is_bitmap_subtitle, pysubs2_format
from .subtitle_encoding import decode_subtitle_bytes


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


def convert_subtitle_file_to_simplified(source_path: Path, output_path: Path) -> bool:
    raw = source_path.read_bytes()
    if is_bitmap_subtitle(source_path, raw):
        raise ValueError("图片字幕不能进行繁简转换")
    text, _ = decode_subtitle_bytes(raw)
    if source_path.suffix.lower() in {".smi", ".sami"}:
        return rewrite_sami_subtitle(source_path, output_path, text_transform=traditional_to_simplified)
    if source_path.suffix.lower() in {".ttml", ".dfxp"}:
        import pysubs2

        subtitles = load_ttml_subtitles(pysubs2, raw)
        changed = False
        for event in subtitles.events:
            converted = traditional_to_simplified(event.text)
            changed = changed or converted != event.text
            event.text = converted
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subtitles.save(str(output_path), encoding="utf-8", format_=pysubs2_format(source_path))
        return changed
    converted = traditional_to_simplified(text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(converted, encoding="utf-8")
    return converted != text


def rewrite_sami_subtitle(
    source_path: Path,
    output_path: Path,
    *,
    text_transform: Optional[Callable[[str], str]] = None,
    time_transform: Optional[Callable[[int], int]] = None,
) -> bool:
    # pysubs2 can read SAMI but has no writer; retain its HTML structure and attributes.
    sami = _parse_sami_subtitle(source_path.read_bytes())
    changed = False
    if time_transform is not None:
        for sync in sami.find_all("sync"):
            sync["start"] = str(time_transform(int(sync.get("start", "0"))))
    if text_transform is not None:
        body = sami.find("body")
        if body is None:
            raise ValueError(f"SAMI 字幕缺少 BODY 节点: {source_path.name}")
        for value in list(body.find_all(string=True)):
            if value.parent.name in {"script", "style"}:
                continue
            converted = text_transform(str(value))
            changed = changed or converted != value
            value.replace_with(converted)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(sami.encode("utf-8"))
    return changed


def _parse_sami_subtitle(raw_bytes: bytes) -> Any:
    from bs4 import BeautifulSoup

    document = BeautifulSoup(raw_bytes, "html.parser")
    sami = document.find("sami")
    if sami is None:
        raise ValueError("SAMI 字幕缺少 SAMI 根节点")
    return sami


def load_sami_subtitles(pysubs2: Any, raw_bytes: bytes) -> Any:
    return pysubs2.SSAFile.from_string(str(_parse_sami_subtitle(raw_bytes)), format_="sami")


def load_ttml_subtitles(pysubs2: Any, raw_bytes: bytes) -> Any:
    # Normalize the XML declaration before pysubs2 parses a Unicode stream.
    root = ET.fromstring(raw_bytes)
    return pysubs2.SSAFile.from_string(ET.tostring(root, encoding="unicode"), format_="ttml")
