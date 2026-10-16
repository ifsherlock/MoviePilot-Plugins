from __future__ import annotations

import codecs
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple

from .subtitle_formats import is_text_subtitle


def decode_subtitle_bytes(raw: bytes) -> Tuple[str, str]:
    for bom, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"),
        (codecs.BOM_UTF8, "utf-8-sig"),
    ):
        if raw.startswith(bom):
            return raw.decode(encoding), encoding
    if b"\x00" in raw:
        if len(raw) % 2 == 0:
            for offset, encoding in ((1, "utf-16-le"), (0, "utf-16-be")):
                lane = raw[offset::2]
                if lane and lane.count(0) / len(lane) > 0.3:
                    return raw.decode(encoding), encoding
        raise ValueError("文字字幕包含无法识别的二进制内容")
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    from bs4.dammit import EncodingDetector
    from charset_normalizer import from_bytes

    declared = EncodingDetector.find_declared_encoding(raw, is_html=True)
    if declared:
        try:
            return raw.decode(declared), declared
        except (LookupError, UnicodeDecodeError) as exc:
            raise ValueError(f"字幕编码声明无效或与内容不符: {declared}") from exc
    match = from_bytes(raw, cp_isolation=["gb18030", "big5", "cp1252", "cp1251", "shift_jis", "euc_kr"]).best()
    if match is None or match.percent_chaos > 20:
        raise ValueError("无法可靠识别字幕编码，请将文字字幕转换为 UTF-8 后重试")
    text = raw.decode(match.encoding)
    if text.encode(match.encoding) != raw:
        raise ValueError("字幕编码转换无法保持全部原始字符")
    return text, match.encoding


def normalize_subtitle_encoding(source: Path, output: Path) -> bool:
    raw = source.read_bytes()
    if not is_text_subtitle(source, raw):
        raise ValueError("只有文字字幕可以转换编码")
    text, _ = decode_subtitle_bytes(raw)
    if source.suffix.lower() in {".smi", ".sami"}:
        from bs4 import BeautifulSoup

        encoded = BeautifulSoup(text, "html.parser").encode("utf-8")
    elif source.suffix.lower() in {".ttml", ".dfxp"}:
        encoded = ET.tostring(ET.fromstring(text), encoding="utf-8", xml_declaration=True)
    else:
        encoded = text.encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return encoded != raw
