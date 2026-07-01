from __future__ import annotations

import json
import time
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple


TIMELINE_CACHE_SUBDIRS = (
    "audio",
    "embedded_subtitles",
    "vad",
    "subtitle_activity",
    "results",
)


def file_signature(path: Path, *, cache_version: str) -> str:
    try:
        stat = path.stat()
        raw = f"{cache_version}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except Exception:
        raw = f"{cache_version}|{path}"
    return sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def subtitle_content_signature(path: Path, *, cache_version: str) -> str:
    try:
        stat = path.stat()
        digest = sha1()
        digest.update(
            f"{cache_version}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|".encode(
                "utf-8",
                errors="ignore",
            )
        )
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return file_signature(path, cache_version=cache_version)


def cache_manifest_path(cache_dir: Optional[Path]) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "manifest.json"


def prepare_timeline_cache(
    cache_dir: Path,
    *,
    cache_version: str,
    ttl_seconds: int,
    max_bytes: int,
    now_ts_func: Optional[Callable[[], float]] = None,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in TIMELINE_CACHE_SUBDIRS:
        (cache_dir / name).mkdir(parents=True, exist_ok=True)
    manifest = cache_manifest_path(cache_dir)
    if manifest and not manifest.exists():
        manifest.write_text(
            json.dumps({"version": cache_version, "items": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
    cleanup_timeline_cache(
        cache_dir,
        cache_version=cache_version,
        ttl_seconds=ttl_seconds,
        max_bytes=max_bytes,
        now_ts_func=now_ts_func or now_ts,
    )


def read_cache_manifest(cache_dir: Optional[Path], *, cache_version: str) -> Dict[str, Any]:
    manifest = cache_manifest_path(cache_dir)
    if not manifest or not manifest.exists():
        return {"version": cache_version, "items": {}}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return {"version": cache_version, "items": {}}
    if payload.get("version") != cache_version:
        return {"version": cache_version, "items": {}}
    if not isinstance(payload.get("items"), dict):
        payload["items"] = {}
    return payload


def write_cache_manifest(cache_dir: Optional[Path], payload: Dict[str, Any]) -> None:
    manifest = cache_manifest_path(cache_dir)
    if not manifest:
        return
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_cache_entry(
    path: Path,
    *,
    cache_version: str,
    kind: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
    now_ts_func: Optional[Callable[[], float]] = None,
) -> None:
    cache_dir = timeline_cache_root_for(path)
    if not cache_dir:
        return
    payload = read_cache_manifest(cache_dir, cache_version=cache_version)
    rel_path = str(path.relative_to(cache_dir)).replace("\\", "/")
    try:
        size = path.stat().st_size
    except Exception:
        size = 0
    payload["items"][rel_path] = {
        "kind": kind,
        "source": source,
        "size": int(size),
        "updated_at": int((now_ts_func or now_ts)()),
        "metadata": metadata or {},
    }
    write_cache_manifest(cache_dir, payload)


def timeline_cache_root_for(path: Path) -> Optional[Path]:
    known_subdirs = set(TIMELINE_CACHE_SUBDIRS)
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


def cleanup_timeline_cache(
    cache_dir: Path,
    *,
    cache_version: str,
    ttl_seconds: int,
    max_bytes: int,
    now_ts_func: Optional[Callable[[], float]] = None,
) -> None:
    payload = read_cache_manifest(cache_dir, cache_version=cache_version)
    now = (now_ts_func or now_ts)()
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
        write_cache_manifest(cache_dir, payload)


def now_ts() -> float:
    return time.time()


def cached_vad_path(
    cache_dir: Optional[Path],
    video_path: Path,
    vad_mode: str,
    *,
    cache_version: str,
) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "vad" / f"{file_signature(video_path, cache_version=cache_version)}.{vad_mode}.npy"


def cached_audio_pcm_path(
    cache_dir: Optional[Path],
    video_path: Path,
    *,
    cache_version: str,
) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "audio" / f"{file_signature(video_path, cache_version=cache_version)}.s16le"


def cached_embedded_subtitle_path(
    cache_dir: Optional[Path],
    video_path: Path,
    stream_index: int,
    order: int,
    *,
    cache_version: str,
) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "embedded_subtitles" / f"{file_signature(video_path, cache_version=cache_version)}.{order}.{stream_index}.srt"


def cached_subtitle_vad_path(
    cache_dir: Optional[Path],
    subtitle_path: Path,
    scale_factor: float,
    *,
    cache_version: str,
) -> Optional[Path]:
    if not cache_dir:
        return None
    ratio_key = f"{float(scale_factor):.8f}".replace(".", "_")
    return Path(cache_dir) / "subtitle_activity" / f"{subtitle_content_signature(subtitle_path, cache_version=cache_version)}.{ratio_key}.npy"


def subtitle_events_to_vad_cached(
    *,
    np: Any,
    events: Sequence[Tuple[int, int, str]],
    scale_factor: float,
    subtitle_path: Path,
    cache_dir: Optional[Path],
    cache_version: str,
    subtitle_events_to_vad: Callable[..., Any],
) -> Any:
    cache_path = cached_subtitle_vad_path(
        cache_dir,
        subtitle_path,
        scale_factor,
        cache_version=cache_version,
    )
    if cache_path and cache_path.exists():
        return np.load(str(cache_path)).astype(np.float32)
    vad = subtitle_events_to_vad(np, events, scale_factor)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), vad)
        record_cache_entry(
            cache_path,
            cache_version=cache_version,
            kind="subtitle_activity",
            source=str(subtitle_path),
            metadata={"scale_factor": float(scale_factor)},
        )
    return vad


def timeline_result_cache_key(
    *,
    video_path: Path,
    subtitle_path: Path,
    max_offset_seconds: int,
    min_offset_seconds: float,
    vad_mode: str,
    allow_risky_offset: bool,
    cache_version: str,
) -> str:
    raw = "|".join(
        [
            cache_version,
            "result",
            file_signature(video_path, cache_version=cache_version),
            subtitle_content_signature(subtitle_path, cache_version=cache_version),
            str(int(max_offset_seconds)),
            f"{float(min_offset_seconds):.3f}",
            str(vad_mode or "webrtc"),
            "risky" if allow_risky_offset else "safe",
        ]
    )
    return sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def cached_result_path(cache_dir: Optional[Path], key: str) -> Optional[Path]:
    if not cache_dir:
        return None
    return Path(cache_dir) / "results" / f"{key}.json"


def load_timeline_result_cache(
    cache_dir: Optional[Path],
    key: str,
    *,
    cache_version: str,
) -> Optional[Dict[str, Any]]:
    path = cached_result_path(cache_dir, key)
    if not path or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("version") != cache_version:
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    return payload


def store_timeline_result_cache(
    cache_dir: Optional[Path],
    key: str,
    result: Any,
    *,
    cache_version: str,
) -> None:
    path = cached_result_path(cache_dir, key)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": cache_version,
        "key": key,
        "result": result.to_dict(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    record_cache_entry(
        path,
        cache_version=cache_version,
        kind="result",
        source=key,
        metadata={"confidence": result.confidence},
    )
