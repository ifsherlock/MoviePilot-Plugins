from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class TimelineVadConfig:
    sample_rate: int
    audio_sample_rate: int
    frame_samples: int
    frame_bytes: int
    min_subtitle_events: int
    text_subtitle_codecs: Sequence[str]
    audio_extraction_min_timeout_seconds: int
    audio_extraction_max_timeout_seconds: int


def build_base_vad(
    np: Any,
    pysubs2: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    vad_mode: str,
    config: TimelineVadConfig,
    cached_vad_path: Callable[[Optional[Path], Path, str], Optional[Path]],
    cached_embedded_subtitle_path: Callable[[Optional[Path], Path, int, int], Optional[Path]],
    cached_audio_pcm_path: Callable[[Optional[Path], Path], Optional[Path]],
    record_cache_entry: Callable[..., None],
    subtitle_events_to_vad: Callable[[Any, Sequence[Tuple[int, int, str]], float], Any],
    subprocess_module: Any,
    importlib_util_module: Any,
) -> Tuple[Any, str]:
    subtitle_base = build_embedded_subtitle_vad(
        np,
        pysubs2,
        video_path,
        cache_dir=cache_dir,
        config=config,
        cached_embedded_subtitle_path=cached_embedded_subtitle_path,
        record_cache_entry=record_cache_entry,
        subtitle_events_to_vad=subtitle_events_to_vad,
        subprocess_module=subprocess_module,
    )
    if subtitle_base:
        return subtitle_base
    return build_audio_vad(
        np,
        video_path,
        cache_dir=cache_dir,
        vad_mode=vad_mode,
        config=config,
        cached_vad_path=cached_vad_path,
        cached_audio_pcm_path=cached_audio_pcm_path,
        record_cache_entry=record_cache_entry,
        subprocess_module=subprocess_module,
        importlib_util_module=importlib_util_module,
    )


def build_embedded_subtitle_vad(
    np: Any,
    pysubs2: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    config: TimelineVadConfig,
    cached_embedded_subtitle_path: Callable[[Optional[Path], Path, int, int], Optional[Path]],
    record_cache_entry: Callable[..., None],
    subtitle_events_to_vad: Callable[[Any, Sequence[Tuple[int, int, str]], float], Any],
    subprocess_module: Any,
) -> Optional[Tuple[Any, str]]:
    streams = probe_text_subtitle_streams(video_path, config=config, subprocess_module=subprocess_module)
    if not streams:
        return None

    best: Optional[Tuple[int, Any, str]] = None
    with tempfile.TemporaryDirectory(prefix="mp-subtitle-fix-") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        for order, stream in enumerate(streams[:8]):
            stream_index = stream.get("index")
            if stream_index is None:
                continue
            out_path = cached_embedded_subtitle_path(
                cache_dir,
                video_path,
                int(stream_index),
                order,
            ) or tmp_dir / f"embedded-{order}.srt"
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
                result = subprocess_module.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 128:
                    continue
                record_cache_entry(
                    out_path,
                    kind="embedded_subtitle",
                    source=str(video_path),
                    metadata={"stream_index": int(stream_index), "order": int(order)},
                )
            try:
                events = load_subtitle_events(pysubs2, out_path)
            except Exception:
                continue
            if len(events) < config.min_subtitle_events:
                continue
            vad = subtitle_events_to_vad(np, events, 1.0)
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


def probe_text_subtitle_streams(
    video_path: Path,
    *,
    config: TimelineVadConfig,
    subprocess_module: Any,
) -> List[Dict[str, Any]]:
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
    result = subprocess_module.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return []
    streams = payload.get("streams") or []
    text_codecs = {str(item).lower() for item in config.text_subtitle_codecs}
    return [
        stream
        for stream in streams
        if str(stream.get("codec_name") or "").lower() in text_codecs
    ]


def build_audio_vad(
    np: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    vad_mode: str,
    config: TimelineVadConfig,
    cached_vad_path: Callable[[Optional[Path], Path, str], Optional[Path]],
    cached_audio_pcm_path: Callable[[Optional[Path], Path], Optional[Path]],
    record_cache_entry: Callable[..., None],
    subprocess_module: Any,
    importlib_util_module: Any,
) -> Tuple[Any, str]:
    cache_path = cached_vad_path(cache_dir, video_path, vad_mode)
    if cache_path and cache_path.exists():
        values = np.load(str(cache_path))
        return values.astype(np.float32), f"audio:{vad_mode}:cache"

    if vad_mode == "webrtc" and importlib_util_module.find_spec("webrtcvad") is not None:
        vad = build_webrtc_audio_vad(
            np,
            video_path,
            cache_dir=cache_dir,
            config=config,
            cached_audio_pcm_path=cached_audio_pcm_path,
            record_cache_entry=record_cache_entry,
            subprocess_module=subprocess_module,
        )
        base_name = "audio:webrtc"
    else:
        vad = build_rms_audio_vad(
            np,
            video_path,
            cache_dir=cache_dir,
            config=config,
            cached_audio_pcm_path=cached_audio_pcm_path,
            record_cache_entry=record_cache_entry,
            subprocess_module=subprocess_module,
        )
        base_name = "audio:rms"

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), vad)
        record_cache_entry(cache_path, kind="vad", source=str(video_path), metadata={"mode": vad_mode})
    return vad, base_name


def read_pcm_frames(
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    config: TimelineVadConfig,
    cached_audio_pcm_path: Callable[[Optional[Path], Path], Optional[Path]],
    record_cache_entry: Callable[..., None],
    audio_extraction_timeout_seconds: Callable[[Path], int],
    subprocess_module: Any,
) -> Tuple[bytes, str]:
    cache_path = cached_audio_pcm_path(cache_dir, video_path)
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
        str(config.audio_sample_rate),
        "-f",
        "s16le",
        "-",
    ]
    result = subprocess_module.run(cmd, capture_output=True, timeout=audio_extraction_timeout_seconds(video_path))
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg audio extraction failed: {stderr or result.returncode}")
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(result.stdout)
        record_cache_entry(
            cache_path,
            kind="audio",
            source=str(video_path),
            metadata={"sample_rate": config.audio_sample_rate},
        )
    return result.stdout, result.stderr.decode("utf-8", errors="ignore").strip()


def audio_extraction_timeout_seconds(
    video_path: Path,
    *,
    config: TimelineVadConfig,
    probe_video_duration_seconds: Callable[[Path], float],
) -> int:
    duration = probe_video_duration_seconds(video_path)
    if duration <= 0:
        return config.audio_extraction_min_timeout_seconds
    return max(
        config.audio_extraction_min_timeout_seconds,
        min(config.audio_extraction_max_timeout_seconds, int(duration * 0.15) + 180),
    )


def probe_video_duration_seconds(video_path: Path, *, subprocess_module: Any) -> float:
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
        result = subprocess_module.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception:
        return 0.0
    if result.returncode != 0:
        return 0.0
    try:
        return max(0.0, float((result.stdout or "").strip()))
    except Exception:
        return 0.0


def build_webrtc_audio_vad(
    np: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    config: TimelineVadConfig,
    cached_audio_pcm_path: Callable[[Optional[Path], Path], Optional[Path]],
    record_cache_entry: Callable[..., None],
    subprocess_module: Any,
) -> Any:
    import webrtcvad

    pcm, _ = read_pcm_frames(
        video_path,
        cache_dir=cache_dir,
        config=config,
        cached_audio_pcm_path=cached_audio_pcm_path,
        record_cache_entry=record_cache_entry,
        audio_extraction_timeout_seconds=lambda path: audio_extraction_timeout_seconds(
            path,
            config=config,
            probe_video_duration_seconds=lambda probe_path: probe_video_duration_seconds(
                probe_path,
                subprocess_module=subprocess_module,
            ),
        ),
        subprocess_module=subprocess_module,
    )
    if len(pcm) < config.frame_bytes * config.sample_rate:
        raise RuntimeError("not enough audio frames for timeline fixing")

    detector = webrtcvad.Vad()
    detector.set_mode(3)
    active: List[bool] = []
    usable_len = (len(pcm) // config.frame_bytes) * config.frame_bytes
    for index in range(0, usable_len, config.frame_bytes):
        frame = pcm[index : index + config.frame_bytes]
        active.append(bool(detector.is_speech(frame, config.audio_sample_rate)))
    return active_flags_to_vad(np, active, config=config)


def build_rms_audio_vad(
    np: Any,
    video_path: Path,
    *,
    cache_dir: Optional[Path],
    config: TimelineVadConfig,
    cached_audio_pcm_path: Callable[[Optional[Path], Path], Optional[Path]],
    record_cache_entry: Callable[..., None],
    subprocess_module: Any,
) -> Any:
    pcm, stderr = read_pcm_frames(
        video_path,
        cache_dir=cache_dir,
        config=config,
        cached_audio_pcm_path=cached_audio_pcm_path,
        record_cache_entry=record_cache_entry,
        audio_extraction_timeout_seconds=lambda path: audio_extraction_timeout_seconds(
            path,
            config=config,
            probe_video_duration_seconds=lambda probe_path: probe_video_duration_seconds(
                probe_path,
                subprocess_module=subprocess_module,
            ),
        ),
        subprocess_module=subprocess_module,
    )
    energies: List[float] = []
    pending = b""
    chunk_size = config.frame_bytes * 500
    for index in range(0, len(pcm), chunk_size):
        chunk = pcm[index : index + chunk_size]
        pending += chunk
        usable_len = (len(pending) // config.frame_bytes) * config.frame_bytes
        if usable_len <= 0:
            continue
        block = pending[:usable_len]
        pending = pending[usable_len:]
        samples = np.frombuffer(block, dtype="<i2").reshape(-1, config.frame_samples)
        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2, axis=1))
        energies.extend(rms.tolist())

    if len(energies) < config.sample_rate:
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


def active_flags_to_vad(np: Any, active_flags: Sequence[bool], *, config: TimelineVadConfig) -> Any:
    active = np.asarray(active_flags, dtype=bool)
    if active.size < config.sample_rate:
        raise RuntimeError("not enough audio frames for timeline fixing")
    active_ratio = float(np.mean(active))
    if active_ratio <= 0.002 or active_ratio >= 0.998:
        raise RuntimeError("audio speech feature is unstable")
    return np.where(active, 1.0, -1.0).astype(np.float32)


def load_subtitle_events(pysubs2: Any, subtitle_path: Path) -> List[Tuple[int, int, str]]:
    subtitles = load_subtitle_file(pysubs2, subtitle_path)
    events: List[Tuple[int, int, str]] = []
    for event in subtitles.events:
        if getattr(event, "is_comment", False):
            continue
        text = clean_subtitle_text(getattr(event, "plaintext", "") or getattr(event, "text", ""))
        if not text:
            continue
        start = max(0, int(getattr(event, "start", 0)))
        end = max(start + 1, int(getattr(event, "end", 0)))
        events.append((start, end, text))
    events.sort(key=lambda item: (item[0], item[1]))
    return events


def load_subtitle_file(pysubs2: Any, subtitle_path: Path) -> Any:
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


def clean_subtitle_text(text: Any) -> str:
    value = str(text or "")
    value = value.replace("\\N", " ").replace("\\n", " ")
    value = re.sub(r"\{[^}]*}", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
    return value
