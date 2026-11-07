"""Resolve Whisper models without changing MoviePilot's shared network settings."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional


def _model_files_present(model_path) -> bool:
    if not model_path:
        return False
    directory = Path(model_path)
    # A cached snapshot can be partial; missing tokenizer.json makes Whisper
    # fetch a tokenizer outside the isolated downloader.
    required = ("config.json", "model.bin", "tokenizer.json")
    return all((directory / name).is_file() for name in required) and any(
        path.is_file() for path in directory.glob("vocabulary.*")
    )


def resolve_model_path(
    model_name: str,
    cache_dir: str,
    proxies: Optional[dict],
    raise_if_cancelled: Callable[[], None],
) -> str:
    from faster_whisper import download_model
    from huggingface_hub.utils import LocalEntryNotFoundError

    raise_if_cancelled()
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    try:
        model_path = download_model(model_name, local_files_only=True, cache_dir=cache_dir)
    except LocalEntryNotFoundError:
        model_path = None
    if _model_files_present(model_path):
        return model_path

    # Both supported Hub HTTP backends read environment proxies. Only the child
    # receives these overrides; even a temporary parent override affects peers.
    env = os.environ.copy()
    for scheme, proxy in (proxies or {}).items():
        if scheme in ("http", "https") and proxy:
            env[f"{scheme}_proxy"] = proxy
            env[f"{scheme.upper()}_PROXY"] = proxy

    with tempfile.TemporaryDirectory(prefix="autosub-model-") as temporary:
        result_path = Path(temporary) / "result.json"
        command = [sys.executable, str(Path(__file__).resolve()), model_name, cache_dir, str(result_path)]
        with subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            try:
                while True:
                    raise_if_cancelled()
                    try:
                        output, _ = process.communicate(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

        if process.returncode:
            from ..translate.api_diagnostics import sanitize_api_error

            proxy_values = [value for key, value in env.items() if key.lower() in ("http_proxy", "https_proxy", "all_proxy")]
            # The final traceback line contains the cause; redact before trimming.
            detail = sanitize_api_error(output, *proxy_values, limit=len(output))[-800:]
            raise RuntimeError(f"模型下载进程失败（退出码 {process.returncode}）：{detail}")
        raise_if_cancelled()
        model_path = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(model_path, str) or not _model_files_present(model_path):
            raise RuntimeError("模型下载后缺少必要文件，请检查 Hugging Face 下载结果")
        return model_path


if __name__ == "__main__":
    from faster_whisper import download_model

    model_path = download_model(sys.argv[1], local_files_only=False, cache_dir=sys.argv[2])
    # Use a result file so dependency logs cannot corrupt the returned path.
    Path(sys.argv[3]).write_text(json.dumps(model_path), encoding="utf-8")
