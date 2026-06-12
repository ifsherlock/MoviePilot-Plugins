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
TIMELINE_CACHE_VERSION = "v2-webrtc-202606"
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
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    modules = {
        "numpy": importlib_util.find_spec("numpy") is not None,
        "pysubs2": importlib_util.find_spec("pysubs2") is not None,
        "webrtcvad": importlib_util.find_spec("webrtcvad") is not None,
    }
    required_modules = {key: modules[key] for key in ("numpy", "pysubs2")}
    return {
        "available": bool(ffmpeg and ffprobe and all(required_modules.values())),
        "ffmpeg": bool(ffmpeg),
        "ffprobe": bool(ffprobe),
        "ffmpeg_path": ffmpeg or "",
        "ffprobe_path": ffprobe or "",
        "ffmpeg_version": _binary_version(ffmpeg),
        "ffprobe_version": _binary_version(ffprobe),
        "modules": modules,
        "sample_rate": SAMPLE_RATE,
        "max_offset_seconds": DEFAULT_MAX_OFFSET_SECONDS,
        "min_offset_seconds": DEFAULT_MIN_OFFSET_SECONDS,
    }


def _binary_version(path: Optional[str]) -> str:
    if not path:
        return ""
    try:
        result = subprocess.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    first_line = (result.stdout or result.stderr or "").splitlines()
    return first_line[0][:160] if first_line else ""


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
    if not video_path.exists():
        raise RuntimeError(f"video does not exist: {video_path}")
    if not subtitle_path.exists():
        raise RuntimeError(f"subtitle does not exist: {subtitle_path}")

    source_events = _load_subtitle_events(pysubs2, subtitle_path)
    if len(source_events) < MIN_SUBTITLE_EVENTS:
        raise RuntimeError("not enough dialogue lines in uploaded subtitle")

    max_offset_seconds = _normalize_max_offset(max_offset_seconds)
    base_vad, base_name = _build_base_vad(np, pysubs2, video_path, cache_dir=cache_dir, vad_mode=vad_mode)
    if base_vad.size < SAMPLE_RATE:
        raise RuntimeError("not enough reference speech features")

    best = _calculate_best_alignment(
        np=np,
        base_vad=base_vad,
        source_events=source_events,
        max_offset_seconds=max_offset_seconds,
    )
    offset_seconds = best["offset_samples"] / float(SAMPLE_RATE)
    scale_factor = best["scale_factor"]
    confidence, risk_flags = _alignment_confidence(
        offset_seconds=offset_seconds,
        scale_factor=scale_factor,
        score=float(best.get("score", 0.0)),
        score_margin=float(best.get("score_margin", 0.0)),
        active_ratio=float(best.get("active_ratio", 0.0)),
        max_offset_seconds=max_offset_seconds,
    )
    if confidence == "rejected" or (abs(offset_seconds) > RISKY_OFFSET_SECONDS and not allow_risky_offset):
        reason = "timeline alignment rejected"
        if abs(offset_seconds) > RISKY_OFFSET_SECONDS and not allow_risky_offset:
            reason = "offset exceeds safe range"
        raise RuntimeError(
            f"{reason}: offset={offset_seconds:.3f}s score={float(best.get('score', 0.0)):.3f} "
            f"margin={float(best.get('score_margin', 0.0)):.3f} risks={','.join(risk_flags) or '-'}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if abs(offset_seconds) < min_offset_seconds and abs(scale_factor - 1.0) < 0.0001:
        shutil.copyfile(subtitle_path, output_path)
        return TimelineFixResult(
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

    _save_adjusted_subtitle(
        pysubs2=pysubs2,
        source_path=subtitle_path,
        output_path=output_path,
        scale_factor=scale_factor,
        offset_seconds=offset_seconds,
    )
    return TimelineFixResult(
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


def _normalize_max_offset(value: Any) -> int:
    try:
        seconds = int(value)
    except Exception:
        seconds = DEFAULT_MAX_OFFSET_SECONDS
    if seconds <= 0:
        return DEFAULT_MAX_OFFSET_SECONDS
    return min(seconds, HARD_MAX_OFFSET_SECONDS)


def _missing_dependency_names(status: Dict[str, Any]) -> List[str]:
    missing = []
    if not status.get("ffmpeg"):
        missing.append("ffmpeg")
    if not status.get("ffprobe"):
        missing.append("ffprobe")
    for name, ok in (status.get("modules") or {}).items():
        if name == "webrtcvad":
            continue
        if not ok:
            missing.append(name)
    return missing


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
        vad = _build_webrtc_audio_vad(np, video_path)
        base_name = "audio:webrtc"
    else:
        vad = _build_rms_audio_vad(np, video_path)
        base_name = "audio:rms"

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), vad)
    return vad, base_name


def _read_pcm_frames(video_path: Path) -> Tuple[bytes, str]:
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
    result = subprocess.run(cmd, capture_output=True, timeout=180)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg audio extraction failed: {stderr or result.returncode}")
    return result.stdout, result.stderr.decode("utf-8", errors="ignore").strip()


def _build_webrtc_audio_vad(np: Any, video_path: Path) -> Any:
    import webrtcvad

    pcm, _ = _read_pcm_frames(video_path)
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


def _build_rms_audio_vad(np: Any, video_path: Path) -> Any:
    pcm, stderr = _read_pcm_frames(video_path)
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
    max_offset_seconds: int,
) -> Dict[str, float]:
    max_offset_samples = int(abs(max_offset_seconds) * SAMPLE_RATE)
    candidates = []
    for ratio in _unique_float_values(FRAMERATE_RATIOS):
        source_vad = _subtitle_events_to_vad(np, source_events, ratio)
        if source_vad.size < SAMPLE_RATE:
            continue
        offset_samples, raw_score = _fft_fit(
            np=np,
            ref_floats=base_vad,
            sub_floats=source_vad,
            max_offset_samples=max_offset_samples,
        )
        if abs(offset_samples) > max_offset_samples:
            continue
        normalized_score = raw_score / max(1.0, float(source_vad.size))
        active_ratio = float(np.mean(source_vad > 0))
        candidates.append(
            {
                "offset_samples": float(offset_samples),
                "score": float(normalized_score),
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
    return best


def _alignment_confidence(
    *,
    offset_seconds: float,
    scale_factor: float,
    score: float,
    score_margin: float,
    active_ratio: float,
    max_offset_seconds: int,
) -> Tuple[str, List[str]]:
    risks: List[str] = []
    abs_offset = abs(float(offset_seconds))
    if abs_offset > RISKY_OFFSET_SECONDS:
        risks.append("offset_over_120s")
    if abs_offset > max_offset_seconds:
        risks.append("offset_over_configured_max")
    if score < MIN_CONFIDENT_SCORE:
        risks.append("low_score")
    if score_margin < MIN_SCORE_MARGIN:
        risks.append("weak_score_margin")
    if active_ratio <= 0.01 or active_ratio >= 0.95:
        risks.append("unstable_subtitle_activity")
    if abs(float(scale_factor) - 1.0) > 0.08:
        risks.append("unusual_scale_factor")
    if "offset_over_configured_max" in risks or "low_score" in risks:
        return "rejected", risks
    if "offset_over_120s" in risks or "weak_score_margin" in risks or "unstable_subtitle_activity" in risks:
        return "low", risks
    if abs(float(scale_factor) - 1.0) > 0.0001:
        return "medium", risks
    return "high", risks


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


def _fft_fit(np: Any, ref_floats: Any, sub_floats: Any, max_offset_samples: int) -> Tuple[int, float]:
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
    return best_offset, best_score


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


def _cached_vad_path(cache_dir: Optional[Path], video_path: Path, vad_mode: str) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "vad" / f"{_file_signature(video_path)}.{vad_mode}.npy"


def _cached_embedded_subtitle_path(cache_dir: Optional[Path], video_path: Path, stream_index: int, order: int) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "embedded_subtitles" / f"{_file_signature(video_path)}.{order}.{stream_index}.srt"


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
