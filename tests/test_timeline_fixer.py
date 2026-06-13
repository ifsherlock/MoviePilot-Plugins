from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def load_timeline_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "plugins.v2" / "subtitlemanualupload" / "timeline_fixer.py"
    module_name = "subtitlemanualupload_timeline_fixer_testpkg"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_max_offset_defaults_and_caps():
    module = load_timeline_module()

    assert module._normalize_max_offset(None) == 120
    assert module._normalize_max_offset(-1) == 120
    assert module._normalize_max_offset("45") == 45
    assert module._normalize_max_offset(700) == 300


def test_dependency_status_treats_webrtcvad_as_optional(monkeypatch):
    module = load_timeline_module()

    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}" if name in {"ffmpeg", "ffprobe"} else None)
    monkeypatch.setattr(
        module.importlib_util,
        "find_spec",
        lambda name: None if name == "webrtcvad" else object(),
    )
    monkeypatch.setattr(module, "_binary_version", lambda path: "version")

    status = module.check_timeline_fixer_dependencies()

    assert status["available"] is True
    assert status["modules"]["webrtcvad"] is False
    assert "webrtcvad" not in module._missing_dependency_names(status)


def test_audio_extraction_timeout_scales_with_video_duration(monkeypatch, tmp_path):
    module = load_timeline_module()
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    monkeypatch.setattr(module, "_probe_video_duration_seconds", lambda path: 10571.0)

    assert module._audio_extraction_timeout_seconds(video) > module.AUDIO_EXTRACTION_MIN_TIMEOUT_SECONDS
    assert module._audio_extraction_timeout_seconds(video) <= module.AUDIO_EXTRACTION_MAX_TIMEOUT_SECONDS

    monkeypatch.setattr(module, "_probe_video_duration_seconds", lambda path: 0.0)

    assert module._audio_extraction_timeout_seconds(video) == module.AUDIO_EXTRACTION_MIN_TIMEOUT_SECONDS


def test_alignment_confidence_rejects_over_configured_max_and_flags_over_120():
    module = load_timeline_module()

    confidence, risks = module._alignment_confidence(
        base_name="embedded:ass",
        offset_seconds=121.0,
        scale_factor=1.0,
        score=0.5,
        score_margin=0.1,
        active_ratio=0.2,
        max_offset_seconds=120,
    )
    assert confidence == "rejected"
    assert "offset_over_configured_max" in risks
    assert "offset_over_120s" in risks

    confidence, risks = module._alignment_confidence(
        base_name="embedded:ass",
        offset_seconds=121.0,
        scale_factor=1.0,
        score=0.5,
        score_margin=0.1,
        active_ratio=0.2,
        max_offset_seconds=300,
    )
    assert confidence == "low"
    assert "offset_over_120s" in risks


def test_alignment_confidence_rejects_boundary_and_weak_audio_results():
    module = load_timeline_module()

    confidence, risks = module._alignment_confidence(
        base_name="embedded:ass",
        offset_seconds=-119.99,
        scale_factor=1.0,
        score=0.5,
        score_margin=0.1,
        peak_score_margin=0.1,
        active_ratio=0.2,
        max_offset_seconds=120,
    )
    assert confidence == "rejected"
    assert "boundary_offset" in risks

    confidence, risks = module._alignment_confidence(
        base_name="audio:rms",
        offset_seconds=-30.0,
        scale_factor=1.0,
        score=0.5,
        score_margin=0.0,
        peak_score_margin=0.1,
        active_ratio=0.899,
        base_active_ratio=0.4,
        max_offset_seconds=120,
    )
    assert confidence == "rejected"
    assert "weak_score_margin" in risks
    assert "audio_subtitle_activity_unstable" in risks
    assert module._timeline_alignment_auto_approved(
        confidence=confidence,
        risk_flags=risks,
        offset_seconds=-30.0,
        allow_risky_offset=True,
    ) is False


def test_allow_risky_offset_only_bypasses_large_offset_risk():
    module = load_timeline_module()

    assert module._timeline_alignment_auto_approved(
        confidence="low",
        risk_flags=["offset_over_120s"],
        offset_seconds=121.0,
        allow_risky_offset=True,
    ) is True
    assert module._timeline_alignment_auto_approved(
        confidence="low",
        risk_flags=["offset_over_120s", "weak_score_margin"],
        offset_seconds=121.0,
        allow_risky_offset=True,
    ) is False


def test_local_alignment_unstable_blocks_auto_approval(monkeypatch):
    np = pytest.importorskip("numpy")
    module = load_timeline_module()
    events = []
    for index in range(9):
        start = 1000 + index * 4000
        events.append((start, start + 1000, f"line {index}"))
    matches = iter(
        [
            {"best_delta": 0, "best_score": 0.8, "expected_score": 0.8},
            {"best_delta": module.SAMPLE_RATE * 10, "best_score": 0.8, "expected_score": 0.2},
            {"best_delta": module.SAMPLE_RATE * 10, "best_score": 0.8, "expected_score": 0.2},
        ]
    )

    def fake_local_match(**kwargs):
        return next(matches)

    monkeypatch.setattr(module, "_local_activity_match_near_global_offset", fake_local_match)

    risks = module._local_alignment_risk_flags(
        np=np,
        base_vad=np.ones(module.SAMPLE_RATE * 60, dtype=np.float32),
        source_events=events,
        scale_factor=1.0,
        offset_samples=0,
        max_offset_samples=module.SAMPLE_RATE * 120,
    )

    assert risks == ["local_alignment_unstable"]
    assert module._timeline_alignment_auto_approved(
        confidence="high",
        risk_flags=risks,
        offset_seconds=0.0,
        allow_risky_offset=False,
    ) is False


def test_audio_pcm_cache_writes_manifest_and_reuses_cached_bytes(tmp_path, monkeypatch):
    module = load_timeline_module()
    cache_dir = tmp_path / "timeline_cache"
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")
    calls = {"count": 0}

    class Result:
        returncode = 0
        stdout = b"\x01\x00" * module.FRAME_SAMPLES * module.SAMPLE_RATE
        stderr = b""

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_probe_video_duration_seconds", lambda path: 0.0)

    first, _ = module._read_pcm_frames(video, cache_dir=cache_dir)
    second, _ = module._read_pcm_frames(video, cache_dir=cache_dir)
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))

    assert first == second
    assert calls["count"] == 1
    assert list((cache_dir / "audio").glob("*.s16le"))
    assert any(item["kind"] == "audio" for item in manifest["items"].values())


def test_timeline_result_cache_roundtrips_with_manifest(tmp_path):
    module = load_timeline_module()
    cache_dir = tmp_path / "timeline_cache"
    module._prepare_timeline_cache(cache_dir, ttl_seconds=3600, max_bytes=1024 * 1024)
    result = module.TimelineFixResult(
        enabled=True,
        applied=True,
        reason="timeline adjusted",
        base="audio:webrtc",
        offset_seconds=5.0,
        scale_factor=1.0,
        score=0.9,
        confidence="high",
        score_margin=0.5,
        active_ratio=0.2,
        risk_flags=[],
    )

    module._store_timeline_result_cache(cache_dir, "abc", result)
    cached = module._load_timeline_result_cache(cache_dir, "abc")
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))

    assert cached["result"]["offset_seconds"] == 5.0
    assert cached["result"]["confidence"] == "high"
    assert any(item["kind"] == "result" for item in manifest["items"].values())


def test_timeline_result_cache_ignores_old_payload_version(tmp_path):
    module = load_timeline_module()
    cache_dir = tmp_path / "timeline_cache"
    result_dir = cache_dir / "results"
    result_dir.mkdir(parents=True)
    (result_dir / "abc.json").write_text(
        json.dumps(
            {
                "version": "v2-webrtc-202606",
                "result": {
                    "enabled": True,
                    "applied": True,
                    "reason": "timeline adjusted",
                    "base": "audio:rms",
                    "offset_seconds": -119.99,
                    "scale_factor": 1.0,
                    "score": 0.1,
                    "confidence": "low",
                    "score_margin": 0.0,
                    "active_ratio": 0.9,
                    "risk_flags": ["rms_low_precision"],
                },
            }
        ),
        encoding="utf-8",
    )

    assert module._load_timeline_result_cache(cache_dir, "abc") is None


def test_cache_version_is_part_of_file_signature(tmp_path):
    module = load_timeline_module()
    video = tmp_path / "Movie.mkv"
    video.write_bytes(b"video")

    original = module._file_signature(video)
    module.TIMELINE_CACHE_VERSION = "changed-version"

    assert module._file_signature(video) != original


def test_cache_cleanup_removes_expired_manifest_entries(tmp_path, monkeypatch):
    module = load_timeline_module()
    cache_dir = tmp_path / "timeline_cache"
    old_file = cache_dir / "audio" / "old.s16le"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    monkeypatch.setattr(module, "_now_ts", lambda: 1000.0)
    module._record_cache_entry(old_file, kind="audio", source="video")

    monkeypatch.setattr(module, "_now_ts", lambda: 2000.0)
    module._prepare_timeline_cache(cache_dir, ttl_seconds=1, max_bytes=1024 * 1024)
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))

    assert not old_file.exists()
    assert manifest["items"] == {}


def test_subtitle_activity_cache_reuses_vad_file(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    module = load_timeline_module()
    cache_dir = tmp_path / "timeline_cache"
    subtitle = tmp_path / "Movie.eng.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    events = [(1000, 2000, "Hello"), (3000, 4000, "World"), (5000, 6000, "Again"), (7000, 8000, "End")]

    first = module._subtitle_events_to_vad_cached(
        np=np,
        events=events,
        scale_factor=1.0,
        subtitle_path=subtitle,
        cache_dir=cache_dir,
    )
    monkeypatch.setattr(module, "_subtitle_events_to_vad", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache miss")))
    second = module._subtitle_events_to_vad_cached(
        np=np,
        events=events,
        scale_factor=1.0,
        subtitle_path=subtitle,
        cache_dir=cache_dir,
    )

    assert second.tolist() == first.tolist()
    assert list((cache_dir / "subtitle_activity").glob("*.npy"))


def test_fix_subtitle_timeline_rejected_candidate_copies_original_without_applying(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    pytest.importorskip("pysubs2")
    module = load_timeline_module()
    video = tmp_path / "Movie.mkv"
    subtitle = tmp_path / "Movie.shifted.srt"
    output = tmp_path / "Movie.fixed.srt"
    video.write_bytes(b"video")
    subtitle.write_text(
        "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:02,000",
                "one",
                "",
                "2",
                "00:00:03,000 --> 00:00:04,000",
                "two",
                "",
                "3",
                "00:00:05,000 --> 00:00:06,000",
                "three",
                "",
                "4",
                "00:00:07,000 --> 00:00:08,000",
                "four",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "check_timeline_fixer_dependencies", lambda: {"available": True})
    monkeypatch.setattr(module, "_build_base_vad", lambda *args, **kwargs: (np.ones(module.SAMPLE_RATE * 20), "embedded:ass"))
    monkeypatch.setattr(
        module,
        "_calculate_best_alignment",
        lambda **kwargs: {
            "offset_samples": -11999,
            "scale_factor": 1.0,
            "score": 0.5,
            "score_margin": 0.1,
            "peak_score_margin": 0.1,
            "active_ratio": 0.2,
        },
    )

    result = module.fix_subtitle_timeline(video, subtitle, output, max_offset_seconds=120, cache_dir=tmp_path / "cache")

    assert result.applied is False
    assert result.confidence == "rejected"
    assert "boundary_offset" in result.risk_flags
    assert output.read_text(encoding="utf-8") == subtitle.read_text(encoding="utf-8")


def test_real_media_fixture_fixes_five_second_offset_against_embedded_subtitle(tmp_path):
    pytest.importorskip("numpy")
    pytest.importorskip("pysubs2")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not available")
    module = load_timeline_module()
    base = tmp_path / "base.srt"
    shifted = tmp_path / "shifted.srt"
    fixed = tmp_path / "fixed.srt"
    video = tmp_path / "fixture.mkv"
    base.write_text(
        "\n".join(
            [
                "1",
                "00:00:02,000 --> 00:00:03,000",
                "line one",
                "",
                "2",
                "00:00:05,000 --> 00:00:06,000",
                "line two",
                "",
                "3",
                "00:00:08,000 --> 00:00:09,000",
                "line three",
                "",
                "4",
                "00:00:11,000 --> 00:00:12,000",
                "line four",
                "",
            ]
        ),
        encoding="utf-8",
    )
    shifted.write_text(
        "\n".join(
            [
                "1",
                "00:00:07,000 --> 00:00:08,000",
                "line one",
                "",
                "2",
                "00:00:10,000 --> 00:00:11,000",
                "line two",
                "",
                "3",
                "00:00:13,000 --> 00:00:14,000",
                "line three",
                "",
                "4",
                "00:00:16,000 --> 00:00:17,000",
                "line four",
                "",
            ]
        ),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=160x90:d=20",
        "-i",
        str(base),
        "-c:v",
        "ffv1",
        "-t",
        "20",
        "-c:s",
        "srt",
        str(video),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        pytest.skip(f"ffmpeg fixture generation failed: {result.stderr[:200]}")

    timeline = module.fix_subtitle_timeline(
        video_path=video,
        subtitle_path=shifted,
        output_path=fixed,
        max_offset_seconds=120,
        min_offset_seconds=0.2,
        cache_dir=tmp_path / "timeline_cache",
        vad_mode="rms",
    )

    assert timeline.applied is True
    assert -5.5 < timeline.offset_seconds < -4.5
    assert fixed.exists()
