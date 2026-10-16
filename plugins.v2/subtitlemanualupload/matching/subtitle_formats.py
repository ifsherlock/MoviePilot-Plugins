from pathlib import Path


BITMAP_SUBTITLE_EXTS = frozenset({".sup", ".idx"})
TEXT_SUBTITLE_EXTS = frozenset({".ass", ".srt", ".ssa", ".sbv", ".sub", ".vtt", ".webvtt", ".smi", ".sami", ".ttml", ".dfxp"})
SUBTITLE_EXTS = TEXT_SUBTITLE_EXTS | BITMAP_SUBTITLE_EXTS
VOBSUB_HEADERS = (b"\x00\x00\x01\xba", b"\x00\x00\x01\xbd")
PYSUBS2_FORMATS = {
    ".ass": "ass",
    ".ssa": "ssa",
    ".srt": "srt",
    ".vtt": "vtt",
    ".webvtt": "vtt",
    ".sub": "microdvd",
    ".smi": "sami",
    ".sami": "sami",
    ".ttml": "ttml",
    ".dfxp": "ttml",
}


def is_bitmap_subtitle(path: str | Path, raw_bytes: bytes | None = None) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix in BITMAP_SUBTITLE_EXTS:
        return True
    if suffix != ".sub":
        return False
    if raw_bytes is None:
        with Path(path).open("rb") as subtitle_file:
            raw_bytes = subtitle_file.read(64)
    return raw_bytes[:64].startswith(VOBSUB_HEADERS)


def is_text_subtitle(path: str | Path, raw_bytes: bytes | None = None) -> bool:
    return Path(path).suffix.lower() in TEXT_SUBTITLE_EXTS and not is_bitmap_subtitle(path, raw_bytes)


def pysubs2_format(path: str | Path) -> str | None:
    return PYSUBS2_FORMATS.get(Path(path).suffix.lower())
