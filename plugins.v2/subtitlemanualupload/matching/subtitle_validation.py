"""Validation at the extracted online-file boundary, before preview/cache/write."""
import re
from pathlib import Path

from .subtitle_encoding import decode_subtitle_bytes
from .subtitle_formats import is_text_subtitle, pysubs2_format
from .tongwen import load_sami_subtitles, load_ttml_subtitles


def validate_online_subtitle_files(files):
    import pysubs2

    for item in files:
        path = Path(item["stored_path"])
        raw = path.read_bytes()
        if not is_text_subtitle(path, raw):
            continue
        name = item.get("source_name") or path.name
        text, _ = decode_subtitle_bytes(raw)
        if _is_html_document(text):
            raise ValueError(f"在线字幕实际为错误网页: {name}")
        if path.suffix.lower() in {".smi", ".sami"}:
            subtitles = load_sami_subtitles(pysubs2, raw)
        elif path.suffix.lower() in {".ttml", ".dfxp"}:
            subtitles = load_ttml_subtitles(pysubs2, raw)
        else:
            subtitles = pysubs2.SSAFile.from_string(text, format_=pysubs2_format(path))
        if not any(event.end > event.start >= 0 and event.plaintext.strip() for event in subtitles):
            raise ValueError(f"在线字幕没有有效时间轴和正文: {name}")


def _is_html_document(text):
    return re.match(r"(?is)^\s*(?:<!doctype\s+html\b|<html\b)", text.lstrip("\ufeff")) is not None
