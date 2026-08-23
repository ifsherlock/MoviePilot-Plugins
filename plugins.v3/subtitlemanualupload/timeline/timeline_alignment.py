from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class TimelineAlignmentConfig:
    sample_rate: int
    frame_duration_ms: int
    framerate_ratios: Sequence[float]
    min_confident_score: float
    min_score_margin: float
    risky_offset_seconds: int
    local_alignment_min_events: int
    local_alignment_segments: int
    local_alignment_max_spread_seconds: int
    local_alignment_search_radius_seconds: int
    local_alignment_min_segment_score: float
    local_alignment_min_segment_advantage: float


SubtitleEventsToVadCached = Callable[..., Any]


def calculate_best_alignment(
    np: Any,
    base_vad: Any,
    source_events: Sequence[Tuple[int, int, str]],
    subtitle_path: Path,
    max_offset_seconds: int,
    cache_dir: Optional[Path],
    *,
    config: TimelineAlignmentConfig,
    subtitle_events_to_vad_cached: SubtitleEventsToVadCached,
) -> Dict[str, float]:
    max_offset_samples = int(abs(max_offset_seconds) * config.sample_rate)
    candidates = []
    for ratio in unique_float_values(config.framerate_ratios):
        source_vad = subtitle_events_to_vad_cached(
            np=np,
            events=source_events,
            scale_factor=ratio,
            subtitle_path=subtitle_path,
            cache_dir=cache_dir,
        )
        if source_vad.size < config.sample_rate:
            continue
        offset_samples, raw_score, raw_peak_margin = fft_fit(
            np=np,
            ref_floats=base_vad,
            sub_floats=source_vad,
            max_offset_samples=max_offset_samples,
            config=config,
        )
        if abs(offset_samples) > max_offset_samples:
            continue
        normalized_score = raw_score / max(1.0, float(source_vad.size))
        normalized_peak_margin = raw_peak_margin / max(1.0, float(source_vad.size))
        active_ratio = float(np.mean(source_vad > 0))
        candidates.append(
            {
                "offset_samples": float(offset_samples),
                "score": float(normalized_score),
                "peak_score_margin": float(normalized_peak_margin),
                "raw_score": float(raw_score),
                "scale_factor": float(ratio),
                "active_ratio": active_ratio,
            }
        )
    if not candidates:
        raise RuntimeError("no valid timeline alignment candidate")
    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = dict(candidates[0])
    second_score = float(candidates[1]["score"]) if len(candidates) > 1 else 0.0
    best["score_margin"] = float(best["score"]) - second_score
    best["risk_flags"] = local_alignment_risk_flags(
        np=np,
        base_vad=base_vad,
        source_events=source_events,
        scale_factor=float(best["scale_factor"]),
        offset_samples=int(best["offset_samples"]),
        max_offset_samples=max_offset_samples,
        config=config,
    )
    return best


def local_alignment_risk_flags(
    *,
    np: Any,
    base_vad: Any,
    source_events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    offset_samples: int,
    max_offset_samples: int,
    config: TimelineAlignmentConfig,
    local_activity_match_near_global_offset_func: Optional[Callable[..., Optional[Dict[str, float]]]] = None,
) -> List[str]:
    if len(source_events) < config.local_alignment_min_events:
        return []
    segment_size = max(1, math.ceil(len(source_events) / config.local_alignment_segments))
    local_offsets: List[int] = []
    strong_conflicts = 0
    for index in range(0, len(source_events), segment_size):
        segment = source_events[index : index + segment_size]
        if len(segment) < 3:
            continue
        search_radius_samples = min(
            max_offset_samples,
            int(round(config.local_alignment_search_radius_seconds * config.sample_rate)),
        )
        if local_activity_match_near_global_offset_func:
            local = local_activity_match_near_global_offset_func(
                np=np,
                base_vad=base_vad,
                segment_events=segment,
                scale_factor=scale_factor,
                offset_samples=offset_samples,
                search_radius_samples=search_radius_samples,
            )
        else:
            local = local_activity_match_near_global_offset(
                np=np,
                base_vad=base_vad,
                segment_events=segment,
                scale_factor=scale_factor,
                offset_samples=offset_samples,
                search_radius_samples=search_radius_samples,
                config=config,
            )
        if not local:
            continue
        expected_score = float(local["expected_score"])
        best_score = float(local["best_score"])
        if best_score < config.local_alignment_min_segment_score:
            continue
        local_offset = int(offset_samples) + int(local["best_delta"])
        local_offsets.append(local_offset)
        if (
            abs(int(local["best_delta"])) / float(config.sample_rate) > config.local_alignment_max_spread_seconds
            and best_score - expected_score >= config.local_alignment_min_segment_advantage
        ):
            strong_conflicts += 1
    if len(local_offsets) < 2:
        return []
    spread_seconds = (max(local_offsets) - min(local_offsets)) / float(config.sample_rate)
    max_delta_seconds = max(abs(int(local_offset) - int(offset_samples)) for local_offset in local_offsets) / float(config.sample_rate)
    if strong_conflicts >= 2 and (
        spread_seconds > config.local_alignment_max_spread_seconds
        or max_delta_seconds > config.local_alignment_max_spread_seconds
    ):
        return ["local_alignment_unstable"]
    return []


def local_activity_match_near_global_offset(
    *,
    np: Any,
    base_vad: Any,
    segment_events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    offset_samples: int,
    search_radius_samples: int,
    config: TimelineAlignmentConfig,
) -> Optional[Dict[str, float]]:
    scaled_events: List[Tuple[int, int]] = []
    for start, end, _ in segment_events:
        scaled_start = max(0, int(round(start * scale_factor / config.frame_duration_ms)))
        scaled_end = max(scaled_start + 1, int(round(end * scale_factor / config.frame_duration_ms)))
        scaled_events.append((scaled_start, scaled_end))
    if not scaled_events:
        return None
    source_start = min(start for start, _ in scaled_events)
    source_end = max(end for _, end in scaled_events)
    source_len = max(1, source_end - source_start + 1)
    source_active = np.zeros(source_len, dtype=np.float32)
    for start, end in scaled_events:
        local_start = max(0, start - source_start)
        local_end = min(source_len, end - source_start + 1)
        if local_end > local_start:
            source_active[local_start:local_end] = 1.0
    source_active_count = float(np.sum(source_active > 0))
    if source_active_count < config.sample_rate * 0.5:
        return None

    base_active = np.asarray(base_vad > 0, dtype=np.float32)
    expected_start = int(source_start) + int(offset_samples)
    window_start = expected_start - int(search_radius_samples)
    window_end = expected_start + source_len + int(search_radius_samples)
    ref_window = np.zeros(max(1, window_end - window_start), dtype=np.float32)
    copy_start = max(0, window_start)
    copy_end = min(base_active.size, window_end)
    if copy_end > copy_start:
        ref_start = copy_start - window_start
        ref_window[ref_start : ref_start + (copy_end - copy_start)] = base_active[copy_start:copy_end]
    if ref_window.size < source_active.size:
        return None

    scores = np.correlate(ref_window, source_active, mode="valid")
    if scores.size == 0:
        return None
    expected_index = min(max(int(search_radius_samples), 0), scores.size - 1)
    best_index = int(np.nanargmax(scores))
    return {
        "best_delta": float(best_index - expected_index),
        "best_score": float(scores[best_index]) / source_active_count,
        "expected_score": float(scores[expected_index]) / source_active_count,
    }


def alignment_confidence(
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
    config: TimelineAlignmentConfig,
) -> Tuple[str, List[str]]:
    risks: List[str] = []
    abs_offset = abs(float(offset_seconds))
    base = str(base_name or "")
    is_audio_base = base.startswith("audio:")
    is_rms_base = base.startswith("audio:rms")
    if abs_offset > config.risky_offset_seconds:
        risks.append("offset_over_120s")
    if abs_offset > max_offset_seconds:
        risks.append("offset_over_configured_max")
    if abs_offset >= max(0.0, float(max_offset_seconds) - 1.0):
        risks.append("boundary_offset")
    if score < config.min_confident_score:
        risks.append("low_score")
    if score_margin < config.min_score_margin:
        risks.append("weak_score_margin")
    if peak_score_margin < config.min_score_margin:
        risks.append("ambiguous_peak")
    if active_ratio <= 0.01 or active_ratio >= 0.95:
        risks.append("unstable_subtitle_activity")
    if is_audio_base and (active_ratio <= 0.02 or active_ratio >= 0.85):
        risks.append("audio_subtitle_activity_unstable")
    if is_audio_base and (base_active_ratio <= 0.02 or base_active_ratio >= 0.85):
        risks.append("audio_base_activity_unstable")
    if abs(float(scale_factor) - 1.0) > 0.08:
        risks.append("unusual_scale_factor")
    if is_audio_base and abs(float(scale_factor) - 1.0) > 0.0001:
        risks.append("audio_scale_factor")
    if is_rms_base:
        risks.append("rms_low_precision")
    if (
        "offset_over_configured_max" in risks
        or "low_score" in risks
        or "boundary_offset" in risks
        or "ambiguous_peak" in risks
        or "audio_base_activity_unstable" in risks
        or "audio_subtitle_activity_unstable" in risks
        or "audio_scale_factor" in risks
    ):
        return "rejected", risks
    if (
        "offset_over_120s" in risks
        or "weak_score_margin" in risks
        or "unstable_subtitle_activity" in risks
        or "rms_low_precision" in risks
    ):
        return "low", risks
    if abs(float(scale_factor) - 1.0) > 0.0001:
        return "medium", risks
    return "high", risks


def timeline_alignment_auto_approved(
    *,
    confidence: str,
    risk_flags: Sequence[str],
    offset_seconds: float,
    allow_risky_offset: bool,
    config: TimelineAlignmentConfig,
) -> bool:
    blocking_risks = {
        "offset_over_configured_max",
        "low_score",
        "weak_score_margin",
        "ambiguous_peak",
        "boundary_offset",
        "unstable_subtitle_activity",
        "audio_subtitle_activity_unstable",
        "audio_base_activity_unstable",
        "audio_scale_factor",
        "unusual_scale_factor",
        "rms_low_precision",
        "local_alignment_unstable",
    }
    risks = set(risk_flags or [])
    if confidence == "rejected":
        return False
    if risks & blocking_risks:
        return False
    if confidence == "low" and not (allow_risky_offset and risks <= {"offset_over_120s"}):
        return False
    if abs(float(offset_seconds)) > config.risky_offset_seconds and not allow_risky_offset:
        return False
    return True


def unique_float_values(values: Iterable[float]) -> List[float]:
    result: List[float] = []
    for value in values:
        if not any(abs(value - existing) < 0.000001 for existing in result):
            result.append(value)
    return result


def fft_fit(
    np: Any,
    ref_floats: Any,
    sub_floats: Any,
    max_offset_samples: int,
    *,
    config: TimelineAlignmentConfig,
) -> Tuple[int, float, float]:
    ref = np.asarray(ref_floats, dtype=np.float32)
    sub = np.asarray(sub_floats, dtype=np.float32)
    if ref.size == 0 or sub.size == 0:
        raise RuntimeError("empty VAD features")

    total_len = next_power_of_two(int(ref.size + sub.size))
    power2_sub = np.zeros(total_len, dtype=np.float32)
    power2_sub[total_len - sub.size :] = sub
    power2_ref = np.zeros(total_len, dtype=np.float32)
    power2_ref[: ref.size] = ref
    power2_ref = power2_ref[::-1]

    convolve = np.fft.ifft(np.fft.fft(power2_sub) * np.fft.fft(power2_ref)).real
    if max_offset_samples:
        start = offset_to_convolve_index(convolve.size, sub.size, -max_offset_samples)
        end = offset_to_convolve_index(convolve.size, sub.size, max_offset_samples)
        start = max(0, min(convolve.size, start))
        end = max(0, min(convolve.size, end))
        if start > 0:
            convolve[:start] = -np.inf
        if end < convolve.size:
            convolve[end:] = -np.inf

    best_index = int(np.nanargmax(convolve))
    best_score = float(convolve[best_index])
    best_offset = int(convolve.size - 1 - best_index - sub.size)
    second_score = second_peak_score(np, convolve, best_index, suppress_radius=max(1, config.sample_rate * 5))
    return best_offset, best_score, float(best_score - second_score)


def second_peak_score(np: Any, values: Any, best_index: int, suppress_radius: int) -> float:
    work = np.array(values, copy=True)
    if work.size <= 1:
        return float("-inf")
    start = max(0, int(best_index) - int(suppress_radius))
    end = min(work.size, int(best_index) + int(suppress_radius) + 1)
    work[start:end] = -np.inf
    if not np.isfinite(work).any():
        return float("-inf")
    return float(np.nanmax(work))


def offset_to_convolve_index(convolve_len: int, sub_len: int, offset: int) -> int:
    return convolve_len - 1 + offset - sub_len


def next_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (int(value) - 1).bit_length()
