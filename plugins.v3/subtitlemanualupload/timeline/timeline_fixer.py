from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import timeline_alignment as _timeline_alignment
from . import timeline_cache as _timeline_cache
from . import timeline_dependencies as _timeline_dependencies
from . import timeline_io as _timeline_io
from . import timeline_vad as _timeline_vad

SAMPLE_RATE = 100
AUDIO_SAMPLE_RATE = 16000
FRAME_DURATION_MS = 10
FRAME_SAMPLES = int(AUDIO_SAMPLE_RATE * FRAME_DURATION_MS / 1000)
FRAME_BYTES = FRAME_SAMPLES * 2
DEFAULT_MAX_OFFSET_SECONDS = 120
DEFAULT_MIN_OFFSET_SECONDS = 0.2
RISKY_OFFSET_SECONDS = 120
HARD_MAX_OFFSET_SECONDS = 300
MIN_SUBTITLE_EVENTS = 4
MIN_CONFIDENT_SCORE = 0.02
MIN_SCORE_MARGIN = 0.002
LOCAL_ALIGNMENT_MIN_EVENTS = 9
LOCAL_ALIGNMENT_SEGMENTS = 3
LOCAL_ALIGNMENT_MAX_SPREAD_SECONDS = 4.0
LOCAL_ALIGNMENT_SEARCH_RADIUS_SECONDS = 12.0
LOCAL_ALIGNMENT_MIN_SEGMENT_SCORE = 0.12
LOCAL_ALIGNMENT_MIN_SEGMENT_ADVANTAGE = 0.05
TIMELINE_CACHE_VERSION = "v4-local-consistency-202606"
DEFAULT_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
DEFAULT_CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024
AUDIO_EXTRACTION_MIN_TIMEOUT_SECONDS = 180
AUDIO_EXTRACTION_MAX_TIMEOUT_SECONDS = 3600
TEXT_SUBTITLE_CODECS = {
    "ass",
    "mov_text",
    "ssa",
    "subrip",
    "text",
    "webvtt",
}
FRAMERATE_RATIOS = (
    1.0,
    24.0 / 23.976,
    25.0 / 23.976,
    25.0 / 24.0,
    23.976 / 24.0,
    23.976 / 25.0,
    24.0 / 25.0,
)


def _timeline_vad_config() -> _timeline_vad.TimelineVadConfig:
    return _timeline_vad.TimelineVadConfig(
        sample_rate=SAMPLE_RATE,
        audio_sample_rate=AUDIO_SAMPLE_RATE,
        frame_samples=FRAME_SAMPLES,
        frame_bytes=FRAME_BYTES,
        min_subtitle_events=MIN_SUBTITLE_EVENTS,
        text_subtitle_codecs=tuple(TEXT_SUBTITLE_CODECS),
        audio_extraction_min_timeout_seconds=AUDIO_EXTRACTION_MIN_TIMEOUT_SECONDS,
        audio_extraction_max_timeout_seconds=AUDIO_EXTRACTION_MAX_TIMEOUT_SECONDS,
    )


def _timeline_alignment_config() -> _timeline_alignment.TimelineAlignmentConfig:
    return _timeline_alignment.TimelineAlignmentConfig(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
        framerate_ratios=tuple(FRAMERATE_RATIOS),
        min_confident_score=MIN_CONFIDENT_SCORE,
        min_score_margin=MIN_SCORE_MARGIN,
        risky_offset_seconds=RISKY_OFFSET_SECONDS,
        local_alignment_min_events=LOCAL_ALIGNMENT_MIN_EVENTS,
        local_alignment_segments=LOCAL_ALIGNMENT_SEGMENTS,
        local_alignment_max_spread_seconds=LOCAL_ALIGNMENT_MAX_SPREAD_SECONDS,
        local_alignment_search_radius_seconds=LOCAL_ALIGNMENT_SEARCH_RADIUS_SECONDS,
        local_alignment_min_segment_score=LOCAL_ALIGNMENT_MIN_SEGMENT_SCORE,
        local_alignment_min_segment_advantage=LOCAL_ALIGNMENT_MIN_SEGMENT_ADVANTAGE,
    )


@dataclass
class TimelineFixResult:
    enabled: bool
    applied: bool
    reason: str
    base: str
    offset_seconds: float
    scale_factor: float
    score: float
    confidence: str = "medium"
    score_margin: float = 0.0
    active_ratio: float = 0.0
    risk_flags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["offset_seconds"] = round(float(self.offset_seconds), 3)
        data["scale_factor"] = round(float(self.scale_factor), 6)
        data["score"] = round(float(self.score), 3)
        data["score_margin"] = round(float(self.score_margin), 3)
        data["active_ratio"] = round(float(self.active_ratio), 4)
        data["risk_flags"] = list(self.risk_flags or [])
        return data


def check_timeline_fixer_dependencies() -> Dict[str, Any]:
    return _timeline_dependencies.check_timeline_fixer_dependencies(
        sample_rate=SAMPLE_RATE,
        max_offset_seconds=DEFAULT_MAX_OFFSET_SECONDS,
        min_offset_seconds=DEFAULT_MIN_OFFSET_SECONDS,
        shutil_module=shutil,
        importlib_util_module=importlib_util,
        binary_version_func=_binary_version,
    )


def _binary_version(path: Optional[str]) -> str:
    return _timeline_dependencies._binary_version(path, subprocess_module=subprocess)


def fix_subtitle_timeline(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    max_offset_seconds: int = DEFAULT_MAX_OFFSET_SECONDS,
    min_offset_seconds: float = DEFAULT_MIN_OFFSET_SECONDS,
    *,
    cache_dir: Optional[Path] = None,
    allow_risky_offset: bool = False,
    vad_mode: str = "webrtc",
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    cache_max_bytes: int = DEFAULT_CACHE_MAX_BYTES,
) -> TimelineFixResult:
    status = check_timeline_fixer_dependencies()
    if not status["available"]:
        missing = _missing_dependency_names(status)
        raise RuntimeError(f"timeline fixer dependency missing: {', '.join(missing)}")

    import numpy as np
    import pysubs2

    video_path = Path(video_path)
    subtitle_path = Path(subtitle_path)
    output_path = Path(output_path)
    cache_dir = Path(cache_dir) if cache_dir else None
    if cache_dir:
        _prepare_timeline_cache(cache_dir, ttl_seconds=cache_ttl_seconds, max_bytes=cache_max_bytes)
    if not video_path.exists():
        raise RuntimeError(f"video does not exist: {video_path}")
    if not subtitle_path.exists():
        raise RuntimeError(f"subtitle does not exist: {subtitle_path}")

    source_events = _load_subtitle_events(pysubs2, subtitle_path)
    if len(source_events) < MIN_SUBTITLE_EVENTS:
        raise RuntimeError("not enough dialogue lines in uploaded subtitle")

    max_offset_seconds = _normalize_max_offset(max_offset_seconds)
    result_cache_key = _timeline_result_cache_key(
        video_path=video_path,
        subtitle_path=subtitle_path,
        max_offset_seconds=max_offset_seconds,
        min_offset_seconds=min_offset_seconds,
        vad_mode=vad_mode,
        allow_risky_offset=allow_risky_offset,
    )
    cached_result = _load_timeline_result_cache(cache_dir, result_cache_key) if cache_dir else None
    if cached_result:
        result = TimelineFixResult(**cached_result["result"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if result.applied:
            _save_adjusted_subtitle(
                pysubs2=pysubs2,
                source_path=subtitle_path,
                output_path=output_path,
                scale_factor=result.scale_factor,
                offset_seconds=result.offset_seconds,
            )
        else:
            shutil.copyfile(subtitle_path, output_path)
        return result

    base_vad, base_name = _build_base_vad(np, pysubs2, video_path, cache_dir=cache_dir, vad_mode=vad_mode)
    if base_vad.size < SAMPLE_RATE:
        raise RuntimeError("not enough reference speech features")
    base_active_ratio = float(np.mean(base_vad > 0))

    best = _calculate_best_alignment(
        np=np,
        base_vad=base_vad,
        source_events=source_events,
        subtitle_path=subtitle_path,
        max_offset_seconds=max_offset_seconds,
        cache_dir=cache_dir,
    )
    offset_seconds = best["offset_samples"] / float(SAMPLE_RATE)
    scale_factor = best["scale_factor"]
    confidence, risk_flags = _alignment_confidence(
        base_name=base_name,
        offset_seconds=offset_seconds,
        scale_factor=scale_factor,
        score=float(best.get("score", 0.0)),
        score_margin=float(best.get("score_margin", 0.0)),
        peak_score_margin=float(best.get("peak_score_margin", 0.0)),
        active_ratio=float(best.get("active_ratio", 0.0)),
        base_active_ratio=base_active_ratio,
        max_offset_seconds=max_offset_seconds,
    )
    risk_flags.extend(str(flag) for flag in best.get("risk_flags", []) if flag not in risk_flags)
    if "local_alignment_unstable" in risk_flags:
        confidence = "rejected"
    if (abs(offset_seconds) > RISKY_OFFSET_SECONDS and not allow_risky_offset) and "offset_over_120s" not in risk_flags:
        risk_flags.append("offset_over_120s")
    auto_approved = _timeline_alignment_auto_approved(
        confidence=confidence,
        risk_flags=risk_flags,
        offset_seconds=offset_seconds,
        allow_risky_offset=allow_risky_offset,
    )
    if not auto_approved:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(subtitle_path, output_path)
        reason = "offset exceeds safe range" if "offset_over_120s" in risk_flags and not allow_risky_offset else "timeline alignment rejected"
        result = TimelineFixResult(
            enabled=True,
            applied=False,
            reason=reason,
            base=base_name,
            offset_seconds=offset_seconds,
            scale_factor=scale_factor,
            score=best["score"],
            confidence="rejected" if confidence == "rejected" else confidence,
            score_margin=best.get("score_margin", 0.0),
            active_ratio=best.get("active_ratio", 0.0),
            risk_flags=risk_flags,
        )
        _store_timeline_result_cache(cache_dir, result_cache_key, result) if cache_dir else None
        return result
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if abs(offset_seconds) < min_offset_seconds and abs(scale_factor - 1.0) < 0.0001:
        shutil.copyfile(subtitle_path, output_path)
        result = TimelineFixResult(
            enabled=True,
            applied=False,
            reason="offset below threshold",
            base=base_name,
            offset_seconds=offset_seconds,
            scale_factor=scale_factor,
            score=best["score"],
            confidence=confidence,
            score_margin=best.get("score_margin", 0.0),
            active_ratio=best.get("active_ratio", 0.0),
            risk_flags=risk_flags,
        )
        _store_timeline_result_cache(cache_dir, result_cache_key, result) if cache_dir else None
        return result

    _save_adjusted_subtitle(
        pysubs2=pysubs2,
        source_path=subtitle_path,
        output_path=output_path,
        scale_factor=scale_factor,
        offset_seconds=offset_seconds,
    )
    result = TimelineFixResult(
        enabled=True,
        applied=True,
        reason="timeline adjusted",
        base=base_name,
        offset_seconds=offset_seconds,
        scale_factor=scale_factor,
        score=best["score"],
        confidence=confidence,
        score_margin=best.get("score_margin", 0.0),
        active_ratio=best.get("active_ratio", 0.0),
        risk_flags=risk_flags,
    )
    _store_timeline_result_cache(cache_dir, result_cache_key, result) if cache_dir else None
    return result


def _normalize_max_offset(value: Any) -> int:
    try:
        seconds = int(value)
    except Exception:
        seconds = DEFAULT_MAX_OFFSET_SECONDS
    if seconds <= 0:
        return DEFAULT_MAX_OFFSET_SECONDS
    return min(seconds, HARD_MAX_OFFSET_SECONDS)


def _missing_dependency_names(status: Dict[str, Any]) -> List[str]:
    return _timeline_dependencies.missing_dependency_names(status)


def _build_base_vad(
    np: Any,
    pysubs2: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    vad_mode: str,
) -> Tuple[Any, str]:
    return _timeline_vad.build_base_vad(
        np,
        pysubs2,
        video_path,
        cache_dir=cache_dir,
        vad_mode=vad_mode,
        config=_timeline_vad_config(),
        cached_vad_path=_cached_vad_path,
        cached_embedded_subtitle_path=_cached_embedded_subtitle_path,
        cached_audio_pcm_path=_cached_audio_pcm_path,
        record_cache_entry=_record_cache_entry,
        subtitle_events_to_vad=_subtitle_events_to_vad,
        subprocess_module=subprocess,
        importlib_util_module=importlib_util,
    )


def _build_embedded_subtitle_vad(
    np: Any,
    pysubs2: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
) -> Optional[Tuple[Any, str]]:
    return _timeline_vad.build_embedded_subtitle_vad(
        np,
        pysubs2,
        video_path,
        cache_dir=cache_dir,
        config=_timeline_vad_config(),
        cached_embedded_subtitle_path=_cached_embedded_subtitle_path,
        record_cache_entry=_record_cache_entry,
        subtitle_events_to_vad=_subtitle_events_to_vad,
        subprocess_module=subprocess,
    )


def _probe_text_subtitle_streams(video_path: Path) -> List[Dict[str, Any]]:
    return _timeline_vad.probe_text_subtitle_streams(
        video_path,
        config=_timeline_vad_config(),
        subprocess_module=subprocess,
    )


def _build_audio_vad(np: Any, video_path: Path, *, cache_dir: Optional[Path], vad_mode: str) -> Tuple[Any, str]:
    return _timeline_vad.build_audio_vad(
        np,
        video_path,
        cache_dir=cache_dir,
        vad_mode=vad_mode,
        config=_timeline_vad_config(),
        cached_vad_path=_cached_vad_path,
        cached_audio_pcm_path=_cached_audio_pcm_path,
        record_cache_entry=_record_cache_entry,
        subprocess_module=subprocess,
        importlib_util_module=importlib_util,
    )


def _read_pcm_frames(video_path: Path, cache_dir: Optional[Path] = None) -> Tuple[bytes, str]:
    return _timeline_vad.read_pcm_frames(
        video_path,
        cache_dir=cache_dir,
        config=_timeline_vad_config(),
        cached_audio_pcm_path=_cached_audio_pcm_path,
        record_cache_entry=_record_cache_entry,
        audio_extraction_timeout_seconds=_audio_extraction_timeout_seconds,
        subprocess_module=subprocess,
    )


def _audio_extraction_timeout_seconds(video_path: Path) -> int:
    return _timeline_vad.audio_extraction_timeout_seconds(
        video_path,
        config=_timeline_vad_config(),
        probe_video_duration_seconds=_probe_video_duration_seconds,
    )


def _probe_video_duration_seconds(video_path: Path) -> float:
    return _timeline_vad.probe_video_duration_seconds(video_path, subprocess_module=subprocess)


def _build_webrtc_audio_vad(np: Any, video_path: Path, *, cache_dir: Optional[Path]) -> Any:
    return _timeline_vad.build_webrtc_audio_vad(
        np,
        video_path,
        cache_dir=cache_dir,
        config=_timeline_vad_config(),
        cached_audio_pcm_path=_cached_audio_pcm_path,
        record_cache_entry=_record_cache_entry,
        subprocess_module=subprocess,
    )


def _build_rms_audio_vad(np: Any, video_path: Path, *, cache_dir: Optional[Path]) -> Any:
    return _timeline_vad.build_rms_audio_vad(
        np,
        video_path,
        cache_dir=cache_dir,
        config=_timeline_vad_config(),
        cached_audio_pcm_path=_cached_audio_pcm_path,
        record_cache_entry=_record_cache_entry,
        subprocess_module=subprocess,
    )


def _active_flags_to_vad(np: Any, active_flags: Sequence[bool]) -> Any:
    return _timeline_vad.active_flags_to_vad(np, active_flags, config=_timeline_vad_config())


def _load_subtitle_events(pysubs2: Any, subtitle_path: Path) -> List[Tuple[int, int, str]]:
    return _timeline_vad.load_subtitle_events(pysubs2, subtitle_path)


def _load_subtitle_file(pysubs2: Any, subtitle_path: Path) -> Any:
    return _timeline_vad.load_subtitle_file(pysubs2, subtitle_path)


def _clean_subtitle_text(text: Any) -> str:
    return _timeline_vad.clean_subtitle_text(text)


def _calculate_best_alignment(
    np: Any,
    base_vad: Any,
    source_events: Sequence[Tuple[int, int, str]],
    subtitle_path: Path,
    max_offset_seconds: int,
    cache_dir: Optional[Path],
) -> Dict[str, float]:
    return _timeline_alignment.calculate_best_alignment(
        np,
        base_vad,
        source_events,
        subtitle_path,
        max_offset_seconds,
        cache_dir,
        config=_timeline_alignment_config(),
        subtitle_events_to_vad_cached=_subtitle_events_to_vad_cached,
    )


def _local_alignment_risk_flags(
    *,
    np: Any,
    base_vad: Any,
    source_events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    offset_samples: int,
    max_offset_samples: int,
) -> List[str]:
    return _timeline_alignment.local_alignment_risk_flags(
        np=np,
        base_vad=base_vad,
        source_events=source_events,
        scale_factor=scale_factor,
        offset_samples=offset_samples,
        max_offset_samples=max_offset_samples,
        config=_timeline_alignment_config(),
        local_activity_match_near_global_offset_func=_local_activity_match_near_global_offset,
    )


def _local_activity_match_near_global_offset(
    *,
    np: Any,
    base_vad: Any,
    segment_events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    offset_samples: int,
    search_radius_samples: int,
) -> Optional[Dict[str, float]]:
    return _timeline_alignment.local_activity_match_near_global_offset(
        np=np,
        base_vad=base_vad,
        segment_events=segment_events,
        scale_factor=scale_factor,
        offset_samples=offset_samples,
        search_radius_samples=search_radius_samples,
        config=_timeline_alignment_config(),
    )


def _alignment_confidence(
    *,
    base_name: str = "",
    offset_seconds: float,
    scale_factor: float,
    score: float,
    score_margin: float,
    peak_score_margin: float = 1.0,
    active_ratio: float,
    base_active_ratio: float = 0.0,
    max_offset_seconds: int,
) -> Tuple[str, List[str]]:
    return _timeline_alignment.alignment_confidence(
        base_name=base_name,
        offset_seconds=offset_seconds,
        scale_factor=scale_factor,
        score=score,
        score_margin=score_margin,
        peak_score_margin=peak_score_margin,
        active_ratio=active_ratio,
        base_active_ratio=base_active_ratio,
        max_offset_seconds=max_offset_seconds,
        config=_timeline_alignment_config(),
    )


def _timeline_alignment_auto_approved(
    *,
    confidence: str,
    risk_flags: Sequence[str],
    offset_seconds: float,
    allow_risky_offset: bool,
) -> bool:
    return _timeline_alignment.timeline_alignment_auto_approved(
        confidence=confidence,
        risk_flags=risk_flags,
        offset_seconds=offset_seconds,
        allow_risky_offset=allow_risky_offset,
        config=_timeline_alignment_config(),
    )


def _unique_float_values(values: Iterable[float]) -> List[float]:
    return _timeline_alignment.unique_float_values(values)


def _subtitle_events_to_vad(
    np: Any,
    events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
) -> Any:
    if not events:
        return np.asarray([], dtype=np.float32)
    scaled_end_ms = max(int(round(end * scale_factor)) for _, end, _ in events)
    length = int(math.floor(scaled_end_ms / FRAME_DURATION_MS)) + 2
    vad = np.full(max(length, 1), -1.0, dtype=np.float32)
    for start, end, _ in events:
        scaled_start = max(0, int(round(start * scale_factor)))
        scaled_end = max(scaled_start + 1, int(round(end * scale_factor)))
        start_index = max(0, int(math.ceil(scaled_start / FRAME_DURATION_MS)))
        end_index = min(vad.size - 1, int(math.floor(scaled_end / FRAME_DURATION_MS)))
        if end_index >= start_index:
            vad[start_index : end_index + 1] = 1.0
    return vad


def _fft_fit(np: Any, ref_floats: Any, sub_floats: Any, max_offset_samples: int) -> Tuple[int, float, float]:
    return _timeline_alignment.fft_fit(
        np,
        ref_floats,
        sub_floats,
        max_offset_samples,
        config=_timeline_alignment_config(),
    )


def _second_peak_score(np: Any, values: Any, best_index: int, suppress_radius: int) -> float:
    return _timeline_alignment.second_peak_score(np, values, best_index, suppress_radius)


def _offset_to_convolve_index(convolve_len: int, sub_len: int, offset: int) -> int:
    return _timeline_alignment.offset_to_convolve_index(convolve_len, sub_len, offset)


def _next_power_of_two(value: int) -> int:
    return _timeline_alignment.next_power_of_two(value)


def _file_signature(path: Path) -> str:
    return _timeline_cache.file_signature(path, cache_version=TIMELINE_CACHE_VERSION)


def _subtitle_content_signature(path: Path) -> str:
    return _timeline_cache.subtitle_content_signature(path, cache_version=TIMELINE_CACHE_VERSION)


def _cache_manifest_path(cache_dir: Optional[Path]) -> Optional[Path]:
    return _timeline_cache.cache_manifest_path(cache_dir)


def _prepare_timeline_cache(cache_dir: Path, *, ttl_seconds: int, max_bytes: int) -> None:
    _timeline_cache.prepare_timeline_cache(
        cache_dir,
        cache_version=TIMELINE_CACHE_VERSION,
        ttl_seconds=ttl_seconds,
        max_bytes=max_bytes,
        now_ts_func=_now_ts,
    )


def _read_cache_manifest(cache_dir: Optional[Path]) -> Dict[str, Any]:
    return _timeline_cache.read_cache_manifest(cache_dir, cache_version=TIMELINE_CACHE_VERSION)


def _write_cache_manifest(cache_dir: Optional[Path], payload: Dict[str, Any]) -> None:
    _timeline_cache.write_cache_manifest(cache_dir, payload)


def _record_cache_entry(path: Path, *, kind: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    _timeline_cache.record_cache_entry(
        path,
        cache_version=TIMELINE_CACHE_VERSION,
        kind=kind,
        source=source,
        metadata=metadata,
        now_ts_func=_now_ts,
    )


def _timeline_cache_root_for(path: Path) -> Optional[Path]:
    return _timeline_cache.timeline_cache_root_for(path)


def _cleanup_timeline_cache(cache_dir: Path, *, ttl_seconds: int, max_bytes: int) -> None:
    _timeline_cache.cleanup_timeline_cache(
        cache_dir,
        cache_version=TIMELINE_CACHE_VERSION,
        ttl_seconds=ttl_seconds,
        max_bytes=max_bytes,
        now_ts_func=_now_ts,
    )


def _now_ts() -> float:
    return _timeline_cache.now_ts()


def _cached_vad_path(cache_dir: Optional[Path], video_path: Path, vad_mode: str) -> Optional[Path]:
    return _timeline_cache.cached_vad_path(
        cache_dir,
        video_path,
        vad_mode,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _cached_audio_pcm_path(cache_dir: Optional[Path], video_path: Path) -> Optional[Path]:
    return _timeline_cache.cached_audio_pcm_path(
        cache_dir,
        video_path,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _cached_embedded_subtitle_path(cache_dir: Optional[Path], video_path: Path, stream_index: int, order: int) -> Optional[Path]:
    return _timeline_cache.cached_embedded_subtitle_path(
        cache_dir,
        video_path,
        stream_index,
        order,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _cached_subtitle_vad_path(cache_dir: Optional[Path], subtitle_path: Path, scale_factor: float) -> Optional[Path]:
    return _timeline_cache.cached_subtitle_vad_path(
        cache_dir,
        subtitle_path,
        scale_factor,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _subtitle_events_to_vad_cached(
    *,
    np: Any,
    events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    subtitle_path: Path,
    cache_dir: Optional[Path],
) -> Any:
    return _timeline_cache.subtitle_events_to_vad_cached(
        np=np,
        events=events,
        scale_factor=scale_factor,
        subtitle_path=subtitle_path,
        cache_dir=cache_dir,
        cache_version=TIMELINE_CACHE_VERSION,
        subtitle_events_to_vad=_subtitle_events_to_vad,
    )


def _timeline_result_cache_key(
    *,
    video_path: Path,
    subtitle_path: Path,
    max_offset_seconds: int,
    min_offset_seconds: float,
    vad_mode: str,
    allow_risky_offset: bool,
) -> str:
    return _timeline_cache.timeline_result_cache_key(
        video_path=video_path,
        subtitle_path=subtitle_path,
        max_offset_seconds=max_offset_seconds,
        min_offset_seconds=min_offset_seconds,
        vad_mode=vad_mode,
        allow_risky_offset=allow_risky_offset,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _cached_result_path(cache_dir: Optional[Path], key: str) -> Optional[Path]:
    return _timeline_cache.cached_result_path(cache_dir, key)


def _load_timeline_result_cache(cache_dir: Optional[Path], key: str) -> Optional[Dict[str, Any]]:
    return _timeline_cache.load_timeline_result_cache(
        cache_dir,
        key,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _store_timeline_result_cache(cache_dir: Optional[Path], key: str, result: TimelineFixResult) -> None:
    _timeline_cache.store_timeline_result_cache(
        cache_dir,
        key,
        result,
        cache_version=TIMELINE_CACHE_VERSION,
    )


def _save_adjusted_subtitle(
    pysubs2: Any,
    source_path: Path,
    output_path: Path,
    scale_factor: float,
    offset_seconds: float,
) -> None:
    _timeline_io.save_adjusted_subtitle(
        pysubs2,
        source_path,
        output_path,
        scale_factor,
        offset_seconds,
        load_subtitle_file=_load_subtitle_file,
    )
