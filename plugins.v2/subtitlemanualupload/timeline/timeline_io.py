from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def save_adjusted_subtitle(
    pysubs2: Any,
    source_path: Path,
    output_path: Path,
    scale_factor: float,
    offset_seconds: float,
    *,
    load_subtitle_file: Callable[[Any, Path], Any],
) -> None:
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
    subtitles.save(str(output_path))
