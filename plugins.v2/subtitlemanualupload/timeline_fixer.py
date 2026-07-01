from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from hashlib import sha1
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import timeline_dependencies as _timeline_dependencies

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
    subtitle_base = _build_embedded_subtitle_vad(np, pysubs2, video_path, cache_dir=cache_dir)
    if subtitle_base:
        return subtitle_base
    return _build_audio_vad(np, video_path, cache_dir=cache_dir, vad_mode=vad_mode)


def _build_embedded_subtitle_vad(
    np: Any,
    pysubs2: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
) -> Optional[Tuple[Any, str]]:
    streams = _probe_text_subtitle_streams(video_path)
    if not streams:
        return None

    best: Optional[Tuple[int, Any, str]] = None
    with tempfile.TemporaryDirectory(prefix="mp-subtitle-fix-") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        for order, stream in enumerate(streams[:8]):
            stream_index = stream.get("index")
            if stream_index is None:
                continue
            out_path = _cached_embedded_subtitle_path(cache_dir, video_path, int(stream_index), order) or tmp_dir / f"embedded-{order}.srt"
            if not out_path.exists():
                out_path.parent.mkdir(parents=True, exist_ok=True)
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(video_path),
                    "-map",
                    f"0:{stream_index}",
                    "-c:s",
                    "srt",
                    str(out_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 128:
                    continue
                _record_cache_entry(
                    out_path,
                    kind="embedded_subtitle",
                    source=str(video_path),
                    metadata={"stream_index": int(stream_index), "order": int(order)},
                )
            try:
                events = _load_subtitle_events(pysubs2, out_path)
            except Exception:
                continue
            if len(events) < MIN_SUBTITLE_EVENTS:
                continue
            vad = _subtitle_events_to_vad(np, events, 1.0)
            active_count = int(np.count_nonzero(vad > 0))
            if active_count <= 0:
                continue
            codec = str(stream.get("codec_name") or "subtitle")
            base_name = f"embedded:{codec}"
            score = len(events)
            if not best or score > best[0]:
                best = (score, vad, base_name)

    if not best:
        return None
    return best[1], best[2]


def _probe_text_subtitle_streams(video_path: Path) -> List[Dict[str, Any]]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index,codec_name",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return []
    streams = payload.get("streams") or []
    return [
        stream
        for stream in streams
        if str(stream.get("codec_name") or "").lower() in TEXT_SUBTITLE_CODECS
    ]


def _build_audio_vad(np: Any, video_path: Path, *, cache_dir: Optional[Path], vad_mode: str) -> Tuple[Any, str]:
    cache_path = _cached_vad_path(cache_dir, video_path, vad_mode)
    if cache_path and cache_path.exists():
        values = np.load(str(cache_path))
        return values.astype(np.float32), f"audio:{vad_mode}:cache"

    if vad_mode == "webrtc" and importlib_util.find_spec("webrtcvad") is not None:
        vad = _build_webrtc_audio_vad(np, video_path, cache_dir=cache_dir)
        base_name = "audio:webrtc"
    else:
        vad = _build_rms_audio_vad(np, video_path, cache_dir=cache_dir)
        base_name = "audio:rms"

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), vad)
        _record_cache_entry(cache_path, kind="vad", source=str(video_path), metadata={"mode": vad_mode})
    return vad, base_name


def _read_pcm_frames(video_path: Path, cache_dir: Optional[Path] = None) -> Tuple[bytes, str]:
    cache_path = _cached_audio_pcm_path(cache_dir, video_path)
    if cache_path and cache_path.exists():
        return cache_path.read_bytes(), ""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(AUDIO_SAMPLE_RATE),
        "-f",
        "s16le",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=_audio_extraction_timeout_seconds(video_path))
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg audio extraction failed: {stderr or result.returncode}")
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(result.stdout)
        _record_cache_entry(cache_path, kind="audio", source=str(video_path), metadata={"sample_rate": AUDIO_SAMPLE_RATE})
    return result.stdout, result.stderr.decode("utf-8", errors="ignore").strip()


def _audio_extraction_timeout_seconds(video_path: Path) -> int:
    duration = _probe_video_duration_seconds(video_path)
    if duration <= 0:
        return AUDIO_EXTRACTION_MIN_TIMEOUT_SECONDS
    return max(
        AUDIO_EXTRACTION_MIN_TIMEOUT_SECONDS,
        min(AUDIO_EXTRACTION_MAX_TIMEOUT_SECONDS, int(duration * 0.15) + 180),
    )


def _probe_video_duration_seconds(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception:
        return 0.0
    if result.returncode != 0:
        return 0.0
    try:
        return max(0.0, float((result.stdout or "").strip()))
    except Exception:
        return 0.0


def _build_webrtc_audio_vad(np: Any, video_path: Path, *, cache_dir: Optional[Path]) -> Any:
    import webrtcvad

    pcm, _ = _read_pcm_frames(video_path, cache_dir=cache_dir)
    if len(pcm) < FRAME_BYTES * SAMPLE_RATE:
        raise RuntimeError("not enough audio frames for timeline fixing")

    detector = webrtcvad.Vad()
    detector.set_mode(3)
    active: List[bool] = []
    usable_len = (len(pcm) // FRAME_BYTES) * FRAME_BYTES
    for index in range(0, usable_len, FRAME_BYTES):
        frame = pcm[index : index + FRAME_BYTES]
        active.append(bool(detector.is_speech(frame, AUDIO_SAMPLE_RATE)))
    return _active_flags_to_vad(np, active)


def _build_rms_audio_vad(np: Any, video_path: Path, *, cache_dir: Optional[Path]) -> Any:
    pcm, stderr = _read_pcm_frames(video_path, cache_dir=cache_dir)
    energies: List[float] = []
    pending = b""
    chunk_size = FRAME_BYTES * 500
    for index in range(0, len(pcm), chunk_size):
        chunk = pcm[index : index + chunk_size]
        pending += chunk
        usable_len = (len(pending) // FRAME_BYTES) * FRAME_BYTES
        if usable_len <= 0:
            continue
        block = pending[:usable_len]
        pending = pending[usable_len:]
        samples = np.frombuffer(block, dtype="<i2").reshape(-1, FRAME_SAMPLES)
        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2, axis=1))
        energies.extend(rms.tolist())

    if len(energies) < SAMPLE_RATE:
        raise RuntimeError(f"not enough audio frames for timeline fixing: {stderr}")

    values = np.asarray(energies, dtype=np.float32)
    log_values = np.log1p(values)
    low = float(np.percentile(log_values, 20))
    high = float(np.percentile(log_values, 92))
    threshold = low + max((high - low) * 0.32, 0.12)
    active = log_values >= threshold
    if active.size >= 7:
        kernel = np.ones(7, dtype=np.float32) / 7.0
        active = np.convolve(active.astype(np.float32), kernel, mode="same") >= 0.36
    active_ratio = float(np.mean(active))
    if active_ratio <= 0.002 or active_ratio >= 0.998:
        raise RuntimeError("audio speech feature is unstable")
    return np.where(active, 1.0, -1.0).astype(np.float32)


def _active_flags_to_vad(np: Any, active_flags: Sequence[bool]) -> Any:
    active = np.asarray(active_flags, dtype=bool)
    if active.size < SAMPLE_RATE:
        raise RuntimeError("not enough audio frames for timeline fixing")
    active_ratio = float(np.mean(active))
    if active_ratio <= 0.002 or active_ratio >= 0.998:
        raise RuntimeError("audio speech feature is unstable")
    return np.where(active, 1.0, -1.0).astype(np.float32)


def _load_subtitle_events(pysubs2: Any, subtitle_path: Path) -> List[Tuple[int, int, str]]:
    subtitles = _load_subtitle_file(pysubs2, subtitle_path)
    events: List[Tuple[int, int, str]] = []
    for event in subtitles.events:
        if getattr(event, "is_comment", False):
            continue
        text = _clean_subtitle_text(getattr(event, "plaintext", "") or getattr(event, "text", ""))
        if not text:
            continue
        start = max(0, int(getattr(event, "start", 0)))
        end = max(start + 1, int(getattr(event, "end", 0)))
        events.append((start, end, text))
    events.sort(key=lambda item: (item[0], item[1]))
    return events


def _load_subtitle_file(pysubs2: Any, subtitle_path: Path) -> Any:
    errors: List[str] = []
    for kwargs in (
        {},
        {"encoding": "utf-8-sig"},
        {"encoding": "utf-16"},
        {"encoding": "gb18030"},
        {"encoding": "big5"},
    ):
        try:
            return pysubs2.load(str(subtitle_path), **kwargs)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError(f"subtitle parse failed: {errors[-1] if errors else subtitle_path}")


def _clean_subtitle_text(text: Any) -> str:
    value = str(text or "")
    value = value.replace("\\N", " ").replace("\\n", " ")
    value = re.sub(r"\{[^}]*}", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
    return value


def _calculate_best_alignment(
    np: Any,
    base_vad: Any,
    source_events: Sequence[Tuple[int, int, str]],
    subtitle_path: Path,
    max_offset_seconds: int,
    cache_dir: Optional[Path],
) -> Dict[str, float]:
    max_offset_samples = int(abs(max_offset_seconds) * SAMPLE_RATE)
    candidates = []
    for ratio in _unique_float_values(FRAMERATE_RATIOS):
        source_vad = _subtitle_events_to_vad_cached(
            np=np,
            events=source_events,
            scale_factor=ratio,
            subtitle_path=subtitle_path,
            cache_dir=cache_dir,
        )
        if source_vad.size < SAMPLE_RATE:
            continue
        offset_samples, raw_score, raw_peak_margin = _fft_fit(
            np=np,
            ref_floats=base_vad,
            sub_floats=source_vad,
            max_offset_samples=max_offset_samples,
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
    best["risk_flags"] = _local_alignment_risk_flags(
        np=np,
        base_vad=base_vad,
        source_events=source_events,
        scale_factor=float(best["scale_factor"]),
        offset_samples=int(best["offset_samples"]),
        max_offset_samples=max_offset_samples,
    )
    return best


def _local_alignment_risk_flags(
    *,
    np: Any,
    base_vad: Any,
    source_events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    offset_samples: int,
    max_offset_samples: int,
) -> List[str]:
    if len(source_events) < LOCAL_ALIGNMENT_MIN_EVENTS:
        return []
    segment_size = max(1, math.ceil(len(source_events) / LOCAL_ALIGNMENT_SEGMENTS))
    local_offsets: List[int] = []
    strong_conflicts = 0
    for index in range(0, len(source_events), segment_size):
        segment = source_events[index : index + segment_size]
        if len(segment) < 3:
            continue
        local = _local_activity_match_near_global_offset(
            np=np,
            base_vad=base_vad,
            segment_events=segment,
            scale_factor=scale_factor,
            offset_samples=offset_samples,
            search_radius_samples=min(
                max_offset_samples,
                int(round(LOCAL_ALIGNMENT_SEARCH_RADIUS_SECONDS * SAMPLE_RATE)),
            ),
        )
        if not local:
            continue
        expected_score = float(local["expected_score"])
        best_score = float(local["best_score"])
        if best_score < LOCAL_ALIGNMENT_MIN_SEGMENT_SCORE:
            continue
        local_offset = int(offset_samples) + int(local["best_delta"])
        local_offsets.append(local_offset)
        if (
            abs(int(local["best_delta"])) / float(SAMPLE_RATE) > LOCAL_ALIGNMENT_MAX_SPREAD_SECONDS
            and best_score - expected_score >= LOCAL_ALIGNMENT_MIN_SEGMENT_ADVANTAGE
        ):
            strong_conflicts += 1
    if len(local_offsets) < 2:
        return []
    spread_seconds = (max(local_offsets) - min(local_offsets)) / float(SAMPLE_RATE)
    max_delta_seconds = max(abs(int(local_offset) - int(offset_samples)) for local_offset in local_offsets) / float(SAMPLE_RATE)
    if strong_conflicts >= 2 and (
        spread_seconds > LOCAL_ALIGNMENT_MAX_SPREAD_SECONDS or max_delta_seconds > LOCAL_ALIGNMENT_MAX_SPREAD_SECONDS
    ):
        return ["local_alignment_unstable"]
    return []


def _local_activity_match_near_global_offset(
    *,
    np: Any,
    base_vad: Any,
    segment_events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    offset_samples: int,
    search_radius_samples: int,
) -> Optional[Dict[str, float]]:
    scaled_events: List[Tuple[int, int]] = []
    for start, end, _ in segment_events:
        scaled_start = max(0, int(round(start * scale_factor / FRAME_DURATION_MS)))
        scaled_end = max(scaled_start + 1, int(round(end * scale_factor / FRAME_DURATION_MS)))
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
    if source_active_count < SAMPLE_RATE * 0.5:
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
    risks: List[str] = []
    abs_offset = abs(float(offset_seconds))
    base = str(base_name or "")
    is_audio_base = base.startswith("audio:")
    is_rms_base = base.startswith("audio:rms")
    if abs_offset > RISKY_OFFSET_SECONDS:
        risks.append("offset_over_120s")
    if abs_offset > max_offset_seconds:
        risks.append("offset_over_configured_max")
    if abs_offset >= max(0.0, float(max_offset_seconds) - 1.0):
        risks.append("boundary_offset")
    if score < MIN_CONFIDENT_SCORE:
        risks.append("low_score")
    if score_margin < MIN_SCORE_MARGIN:
        risks.append("weak_score_margin")
    if peak_score_margin < MIN_SCORE_MARGIN:
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


def _timeline_alignment_auto_approved(
    *,
    confidence: str,
    risk_flags: Sequence[str],
    offset_seconds: float,
    allow_risky_offset: bool,
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
    if abs(float(offset_seconds)) > RISKY_OFFSET_SECONDS and not allow_risky_offset:
        return False
    return True


def _unique_float_values(values: Iterable[float]) -> List[float]:
    result: List[float] = []
    for value in values:
        if not any(abs(value - existing) < 0.000001 for existing in result):
            result.append(value)
    return result


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
    ref = np.asarray(ref_floats, dtype=np.float32)
    sub = np.asarray(sub_floats, dtype=np.float32)
    if ref.size == 0 or sub.size == 0:
        raise RuntimeError("empty VAD features")

    total_len = _next_power_of_two(int(ref.size + sub.size))
    power2_sub = np.zeros(total_len, dtype=np.float32)
    power2_sub[total_len - sub.size :] = sub
    power2_ref = np.zeros(total_len, dtype=np.float32)
    power2_ref[: ref.size] = ref
    power2_ref = power2_ref[::-1]

    convolve = np.fft.ifft(np.fft.fft(power2_sub) * np.fft.fft(power2_ref)).real
    if max_offset_samples:
        start = _offset_to_convolve_index(convolve.size, sub.size, -max_offset_samples)
        end = _offset_to_convolve_index(convolve.size, sub.size, max_offset_samples)
        start = max(0, min(convolve.size, start))
        end = max(0, min(convolve.size, end))
        if start > 0:
            convolve[:start] = -np.inf
        if end < convolve.size:
            convolve[end:] = -np.inf

    best_index = int(np.nanargmax(convolve))
    best_score = float(convolve[best_index])
    best_offset = int(convolve.size - 1 - best_index - sub.size)
    second_score = _second_peak_score(np, convolve, best_index, suppress_radius=max(1, SAMPLE_RATE * 5))
    return best_offset, best_score, float(best_score - second_score)


def _second_peak_score(np: Any, values: Any, best_index: int, suppress_radius: int) -> float:
    work = np.array(values, copy=True)
    if work.size <= 1:
        return float("-inf")
    start = max(0, int(best_index) - int(suppress_radius))
    end = min(work.size, int(best_index) + int(suppress_radius) + 1)
    work[start:end] = -np.inf
    if not np.isfinite(work).any():
        return float("-inf")
    return float(np.nanmax(work))


def _offset_to_convolve_index(convolve_len: int, sub_len: int, offset: int) -> int:
    return convolve_len - 1 + offset - sub_len


def _next_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (int(value) - 1).bit_length()


def _file_signature(path: Path) -> str:
    try:
        stat = path.stat()
        raw = f"{TIMELINE_CACHE_VERSION}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except Exception:
        raw = f"{TIMELINE_CACHE_VERSION}|{path}"
    return sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def _subtitle_content_signature(path: Path) -> str:
    try:
        stat = path.stat()
        digest = sha1()
        digest.update(f"{TIMELINE_CACHE_VERSION}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|".encode("utf-8", errors="ignore"))
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return _file_signature(path)


def _cache_manifest_path(cache_dir: Optional[Path]) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "manifest.json"


def _prepare_timeline_cache(cache_dir: Path, *, ttl_seconds: int, max_bytes: int) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in ("audio", "embedded_subtitles", "vad", "subtitle_activity", "results"):
        (cache_dir / name).mkdir(parents=True, exist_ok=True)
    manifest = _cache_manifest_path(cache_dir)
    if manifest and not manifest.exists():
        manifest.write_text(json.dumps({"version": TIMELINE_CACHE_VERSION, "items": {}}, ensure_ascii=False), encoding="utf-8")
    _cleanup_timeline_cache(cache_dir, ttl_seconds=ttl_seconds, max_bytes=max_bytes)


def _read_cache_manifest(cache_dir: Optional[Path]) -> Dict[str, Any]:
    manifest = _cache_manifest_path(cache_dir)
    if not manifest or not manifest.exists():
        return {"version": TIMELINE_CACHE_VERSION, "items": {}}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return {"version": TIMELINE_CACHE_VERSION, "items": {}}
    if payload.get("version") != TIMELINE_CACHE_VERSION:
        return {"version": TIMELINE_CACHE_VERSION, "items": {}}
    if not isinstance(payload.get("items"), dict):
        payload["items"] = {}
    return payload


def _write_cache_manifest(cache_dir: Optional[Path], payload: Dict[str, Any]) -> None:
    manifest = _cache_manifest_path(cache_dir)
    if not manifest:
        return
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_cache_entry(path: Path, *, kind: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    cache_dir = _timeline_cache_root_for(path)
    if not cache_dir:
        return
    payload = _read_cache_manifest(cache_dir)
    rel_path = str(path.relative_to(cache_dir)).replace("\\", "/")
    try:
        size = path.stat().st_size
    except Exception:
        size = 0
    payload["items"][rel_path] = {
        "kind": kind,
        "source": source,
        "size": int(size),
        "updated_at": int(_now_ts()),
        "metadata": metadata or {},
    }
    _write_cache_manifest(cache_dir, payload)


def _timeline_cache_root_for(path: Path) -> Optional[Path]:
    known_subdirs = {"audio", "embedded_subtitles", "vad", "subtitle_activity", "results"}
    if path.parent.name in known_subdirs:
        return path.parent.parent
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "timeline_cache":
            return Path(*parts[: index + 1])
    for parent in path.parents:
        if parent.name == "timeline_cache":
            return parent
    return None


def _cleanup_timeline_cache(cache_dir: Path, *, ttl_seconds: int, max_bytes: int) -> None:
    payload = _read_cache_manifest(cache_dir)
    now = _now_ts()
    items = payload.get("items") or {}
    changed = False
    for rel_path, item in list(items.items()):
        path = cache_dir / rel_path
        updated_at = float((item or {}).get("updated_at") or 0)
        if not path.exists() or (ttl_seconds > 0 and now - updated_at > ttl_seconds):
            path.unlink(missing_ok=True)
            items.pop(rel_path, None)
            changed = True

    file_items = []
    total_size = 0
    for rel_path, item in list(items.items()):
        path = cache_dir / rel_path
        try:
            stat = path.stat()
        except Exception:
            items.pop(rel_path, None)
            changed = True
            continue
        size = int(stat.st_size)
        total_size += size
        file_items.append((float((item or {}).get("updated_at") or stat.st_mtime), size, rel_path, path))

    if max_bytes > 0 and total_size > max_bytes:
        for _, size, rel_path, path in sorted(file_items):
            if total_size <= max_bytes:
                break
            path.unlink(missing_ok=True)
            items.pop(rel_path, None)
            total_size -= size
            changed = True
    if changed:
        payload["items"] = items
        _write_cache_manifest(cache_dir, payload)


def _now_ts() -> float:
    import time

    return time.time()


def _cached_vad_path(cache_dir: Optional[Path], video_path: Path, vad_mode: str) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "vad" / f"{_file_signature(video_path)}.{vad_mode}.npy"


def _cached_audio_pcm_path(cache_dir: Optional[Path], video_path: Path) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "audio" / f"{_file_signature(video_path)}.s16le"


def _cached_embedded_subtitle_path(cache_dir: Optional[Path], video_path: Path, stream_index: int, order: int) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "embedded_subtitles" / f"{_file_signature(video_path)}.{order}.{stream_index}.srt"


def _cached_subtitle_vad_path(cache_dir: Optional[Path], subtitle_path: Path, scale_factor: float) -> Optional[Path]:
    if not cache_dir:
        return None
    ratio_key = f"{float(scale_factor):.8f}".replace(".", "_")
    return Path(cache_dir) / "subtitle_activity" / f"{_subtitle_content_signature(subtitle_path)}.{ratio_key}.npy"


def _subtitle_events_to_vad_cached(
    *,
    np: Any,
    events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    subtitle_path: Path,
    cache_dir: Optional[Path],
) -> Any:
    cache_path = _cached_subtitle_vad_path(cache_dir, subtitle_path, scale_factor)
    if cache_path and cache_path.exists():
        return np.load(str(cache_path)).astype(np.float32)
    vad = _subtitle_events_to_vad(np, events, scale_factor)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), vad)
        _record_cache_entry(
            cache_path,
            kind="subtitle_activity",
            source=str(subtitle_path),
            metadata={"scale_factor": float(scale_factor)},
        )
    return vad


def _timeline_result_cache_key(
    *,
    video_path: Path,
    subtitle_path: Path,
    max_offset_seconds: int,
    min_offset_seconds: float,
    vad_mode: str,
    allow_risky_offset: bool,
) -> str:
    raw = "|".join(
        [
            TIMELINE_CACHE_VERSION,
            "result",
            _file_signature(video_path),
            _subtitle_content_signature(subtitle_path),
            str(int(max_offset_seconds)),
            f"{float(min_offset_seconds):.3f}",
            str(vad_mode or "webrtc"),
            "risky" if allow_risky_offset else "safe",
        ]
    )
    return sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def _cached_result_path(cache_dir: Optional[Path], key: str) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "results" / f"{key}.json"


def _load_timeline_result_cache(cache_dir: Optional[Path], key: str) -> Optional[Dict[str, Any]]:
    path = _cached_result_path(cache_dir, key)
    if not path or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("version") != TIMELINE_CACHE_VERSION:
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    return payload


def _store_timeline_result_cache(cache_dir: Optional[Path], key: str, result: TimelineFixResult) -> None:
    path = _cached_result_path(cache_dir, key)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": TIMELINE_CACHE_VERSION,
        "key": key,
        "result": result.to_dict(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _record_cache_entry(path, kind="result", source=key, metadata={"confidence": result.confidence})


def _save_adjusted_subtitle(
    pysubs2: Any,
    source_path: Path,
    output_path: Path,
    scale_factor: float,
    offset_seconds: float,
) -> None:
    subtitles = _load_subtitle_file(pysubs2, source_path)
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
