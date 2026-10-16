from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..matching.subtitle_formats import pysubs2_format
from ..matching.tongwen import rewrite_sami_subtitle


def save_adjusted_subtitle(
    pysubs2: Any,
    source_path: Path,
    output_path: Path,
    scale_factor: float,
    offset_seconds: float,
    *,
    load_subtitle_file: Callable[[Any, Path], Any],
) -> None:
    if source_path.suffix.lower() in {".smi", ".sami"}:
        offset_ms = int(round(offset_seconds * 1000))
        rewrite_sami_subtitle(
            source_path,
            output_path,
            time_transform=lambda value: max(0, int(round(value * scale_factor + offset_ms))),
        )
        return
    subtitles = load_subtitle_file(pysubs2, source_path)
    offset_ms = int(round(offset_seconds * 1000))
    for event in subtitles.events:
        original_duration = max(1, int(getattr(event, "end", 0)) - int(getattr(event, "start", 0)))
        scaled_duration = max(1, int(round(original_duration * scale_factor)))
        new_start = int(round(int(getattr(event, "start", 0)) * scale_factor + offset_ms))
        new_end = int(round(int(getattr(event, "end", 0)) * scale_factor + offset_ms))
        if new_start < 0:
            new_start = 0
        if new_end <= new_start:
            new_end = new_start + scaled_duration
        event.start = new_start
        event.end = new_end
    if output_path.suffix.lower() in {".dfxp", ".webvtt"}:
        subtitles.save(str(output_path), format_=pysubs2_format(output_path))
    else:
        subtitles.save(str(output_path))
