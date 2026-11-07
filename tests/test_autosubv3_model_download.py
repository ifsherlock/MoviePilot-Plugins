from __future__ import annotations

import importlib
import json
import os
import sys
import threading
import time
import types
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_autosubv3_cancel import load_plugin_module


MODEL_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.json")
PROXIES = {"http": "http://user:secret@proxy.invalid:8080", "https": "http://user:secret@proxy.invalid:8080"}


@pytest.fixture(params=["v2", "v3"])
def setup_model(request, monkeypatch, tmp_path):
    plugin_module = load_plugin_module(monkeypatch, request.param)
    module = importlib.import_module(f"{plugin_module.__name__}.pipeline.model_download")
    asr_module = importlib.import_module(f"{plugin_module.__name__}.pipeline.asr_service")
    cache = tmp_path / "model root" / "cache"
    cache.mkdir(parents=True)
    model = cache / "snapshot 模型"

    class LocalEntryNotFoundError(Exception):
        pass

    def cached_model(_name, *, local_files_only, cache_dir):
        assert local_files_only is True
        assert Path(cache_dir) == cache
        if not model.exists():
            raise LocalEntryNotFoundError("not cached")
        return str(model)

    cache_lookup = Mock(side_effect=cached_model)
    fake_whisper = types.SimpleNamespace(download_model=cache_lookup)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper)
    monkeypatch.setitem(sys.modules, "huggingface_hub", types.ModuleType("huggingface_hub"))
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", types.SimpleNamespace(LocalEntryNotFoundError=LocalEntryNotFoundError))

    # This module runs in a real child interpreter, separate from the parent stubs.
    child_modules = tmp_path / "child modules"
    child_modules.mkdir()
    (child_modules / "faster_whisper.py").write_text(
        '''import json, os, time
from pathlib import Path

def download_model(name, *, local_files_only, cache_dir):
    assert local_files_only is False
    cache = Path(cache_dir)
    control = json.loads((cache / "control.json").read_text())
    keys = {"http_proxy", "https_proxy", "all_proxy", "hf_hub_cache"}
    (cache / "child-env.json").write_text(json.dumps({k: v for k, v in os.environ.items() if k.lower() in keys}))
    (cache / "started").touch()
    print("dependency diagnostic on stdout")
    while control.get("wait") and not (cache / "release").exists():
        time.sleep(0.02)
    if control.get("fail"):
        raise RuntimeError("download denied " + os.environ.get("HTTPS_PROXY", ""))
    model = cache / "snapshot 模型"
    model.mkdir(exist_ok=True)
    for name in control.get("files", ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"]):
        (model / name).write_text("test model")
    return str(model)
''',
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(child_modules))
    (cache / "control.json").write_text("{}")
    return types.SimpleNamespace(
        module=module, asr=asr_module, cache=cache, model=model,
        lookup=cache_lookup, whisper=fake_whisper,
        interrupt=plugin_module.UserInterruptException,
    )


def resolve(setup, proxies=PROXIES, cancel=lambda: None):
    return setup.module.resolve_model_path("tiny", str(setup.cache), proxies, cancel)


def create_cached_model(setup, missing=None):
    setup.model.mkdir()
    for name in MODEL_FILES:
        if name != missing:
            (setup.model / name).write_text("test model")


def wait_for_child(setup):
    deadline = time.monotonic() + 10
    while not (setup.cache / "started").exists():
        if time.monotonic() >= deadline:
            pytest.fail("download child did not start")
        time.sleep(0.02)


def test_complete_cache_never_starts_network_download(setup_model, monkeypatch):
    setup = setup_model
    create_cached_model(setup)
    monkeypatch.setattr(setup.module.subprocess, "Popen", Mock(side_effect=AssertionError("unexpected download")))
    before = dict(os.environ)
    assert resolve(setup) == str(setup.model)
    assert dict(os.environ) == before
    setup.lookup.assert_called_once_with("tiny", local_files_only=True, cache_dir=str(setup.cache))


@pytest.mark.parametrize("missing", [None, *MODEL_FILES])
def test_missing_or_partial_cache_downloads_in_child(setup_model, monkeypatch, missing):
    setup = setup_model
    if missing is not None:
        create_cached_model(setup, missing)
    monkeypatch.setenv("http_proxy", "http://existing.invalid:7000")
    monkeypatch.setenv("https_proxy", "http://existing.invalid:7000")
    monkeypatch.setenv("HF_HUB_CACHE", "existing-cache")
    before = dict(os.environ)

    assert resolve(setup) == str(setup.model)

    child_env = json.loads((setup.cache / "child-env.json").read_text())
    assert child_env["HTTP_PROXY"] == PROXIES["http"]
    assert child_env["HTTPS_PROXY"] == PROXIES["https"]
    if os.name != "nt":
        assert child_env["http_proxy"] == PROXIES["http"]
        assert child_env["https_proxy"] == PROXIES["https"]
    assert dict(os.environ) == before


@pytest.mark.parametrize("proxies", [None, {}])
def test_disabled_or_empty_proxy_keeps_inherited_environment(setup_model, monkeypatch, proxies):
    setup = setup_model
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALL_PROXY", "http://inherited.invalid:7000")
    before = dict(os.environ)

    assert resolve(setup, proxies) == str(setup.model)

    child_env = json.loads((setup.cache / "child-env.json").read_text())
    assert child_env.get("HTTP_PROXY") is None
    assert child_env.get("HTTPS_PROXY") is None
    assert child_env["ALL_PROXY"] == before["ALL_PROXY"]
    assert dict(os.environ) == before


def test_invalid_model_error_does_not_trigger_download(setup_model, monkeypatch):
    setup = setup_model
    setup.lookup.side_effect = ValueError("invalid model")
    monkeypatch.setattr(setup.module.subprocess, "Popen", Mock(side_effect=AssertionError("unexpected download")))
    with pytest.raises(ValueError, match="invalid model"):
        resolve(setup)


def test_child_failure_preserves_environment_and_reports_redacted_error(setup_model):
    setup = setup_model
    (setup.cache / "control.json").write_text('{"fail": true}')
    before = dict(os.environ)

    with pytest.raises(RuntimeError, match="download denied") as error:
        resolve(setup)

    assert "secret" not in str(error.value)
    assert dict(os.environ) == before


def test_inherited_proxy_credentials_are_redacted_when_override_is_disabled(setup_model, monkeypatch):
    setup = setup_model
    (setup.cache / "control.json").write_text('{"fail": true}')
    monkeypatch.setenv("HTTPS_PROXY", PROXIES["https"])
    with pytest.raises(RuntimeError, match="download denied") as error:
        resolve(setup, None)
    assert "secret" not in str(error.value)


def test_incomplete_download_is_rejected(setup_model):
    setup = setup_model
    (setup.cache / "control.json").write_text(json.dumps({"files": ["config.json", "model.bin"]}))
    with pytest.raises(RuntimeError, match="缺少必要文件"):
        resolve(setup)


def test_other_thread_can_request_local_server_during_download(setup_model, monkeypatch):
    setup = setup_model
    for key in list(os.environ):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
            monkeypatch.delenv(key)
    (setup.cache / "control.json").write_text('{"wait": true}')
    before = dict(os.environ)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"local request ok")

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(resolve, setup)
                try:
                    wait_for_child(setup)
                    assert dict(os.environ) == before
                    # Construct the default environment-aware opener while the child is downloading.
                    opener = urllib.request.build_opener()
                    with opener.open(f"http://127.0.0.1:{server.server_port}/", timeout=3) as response:
                        assert response.read() == b"local request ok"
                finally:
                    (setup.cache / "release").touch()
                assert future.result(timeout=10) == str(setup.model)
        finally:
            server.shutdown()
            thread.join(timeout=3)
    assert dict(os.environ) == before


def test_cancellation_stops_download_child_without_environment_changes(setup_model, monkeypatch):
    setup = setup_model
    (setup.cache / "control.json").write_text('{"wait": true}')
    processes = []
    popen = setup.module.subprocess.Popen

    def record_process(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(setup.module.subprocess, "Popen", record_process)

    def cancel_after_start():
        if (setup.cache / "started").exists():
            raise setup.interrupt("cancelled")

    before = dict(os.environ)
    with pytest.raises(setup.interrupt):
        resolve(setup, cancel=cancel_after_start)
    assert len(processes) == 1
    assert processes[0].poll() is not None
    assert dict(os.environ) == before


@pytest.mark.parametrize("proxy_enabled", [True, False])
@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled"])
def test_asr_entry_keeps_environment_on_success_retries_and_cancellation(setup_model, monkeypatch, proxy_enabled, outcome):
    setup = setup_model
    create_cached_model(setup)
    before = dict(os.environ)
    attempted_proxies = []

    def model_path(_name, _cache, proxies, _cancel):
        attempted_proxies.append(proxies)
        assert dict(os.environ) == before
        if outcome == "cancelled":
            raise setup.interrupt("cancelled")
        if outcome == "failure":
            raise RuntimeError("download unavailable")
        return str(setup.model)

    monkeypatch.setattr(setup.asr, "resolve_model_path", model_path)
    monkeypatch.setattr(setup.asr.time, "sleep", Mock())
    monkeypatch.setattr(setup.asr.psutil, "cpu_count", lambda **_kwargs: 2, raising=False)
    monkeypatch.setattr(setup.asr.srt, "Subtitle", lambda **kwargs: types.SimpleNamespace(**kwargs))
    segment = types.SimpleNamespace(start=0, end=1, text="hello", words=[])
    model = Mock()
    model.transcribe.return_value = ([segment], types.SimpleNamespace(language="en", language_probability=1))
    setup.whisper.WhisperModel = Mock(return_value=model)
    proxy_config = Mock(return_value=PROXIES)
    service = setup.asr.AsrService(
        Mock(), threading.Event(), lambda: False, lambda: None, lambda _lang: False,
        lambda: str(setup.cache.parent), lambda: "tiny", lambda: proxy_enabled,
        proxy_config, lambda: 5, lambda: 100, lambda _text: None,
    )
    service.merge_srt = lambda subs: subs
    service.save_srt = Mock()

    if outcome == "cancelled":
        with pytest.raises(setup.interrupt):
            service.do_speech_recognition("en", "audio.wav")
    else:
        assert service.do_speech_recognition("en", "audio.wav") == ((False, None) if outcome == "failure" else (True, "en"))
    assert attempted_proxies == ([PROXIES if proxy_enabled else None] * (3 if outcome == "failure" else 1))
    assert dict(os.environ) == before
    assert setup.asr.time.sleep.call_count == (2 if outcome == "failure" else 0)
    if not proxy_enabled:
        proxy_config.assert_not_called()
