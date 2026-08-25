from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Set


class ManualStrmMonitor:
    """监控用户配置的 STRM 根目录，并把变化交给本地目录缓存。"""

    def __init__(self, owner: Any, *, logger: Any) -> None:
        self._owner = owner
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_error = ""
        self._last_event_at = ""
        self._last_change_count = 0

    def start(self) -> None:
        self.stop()
        owner = self._owner
        if not getattr(owner, "_manual_strm_enabled", False):
            return
        roots = self._roots()
        if not roots:
            return
        self._stop_event.clear()
        self._last_error = ""
        self._thread = threading.Thread(
            target=self._run,
            args=(roots,),
            name="SubtitleManualUploadStrmMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3)
        self._thread = None
        self._running = False

    def status(self) -> dict[str, Any]:
        return {
            "enabled": bool(getattr(self._owner, "_manual_strm_enabled", False)),
            "running": bool(self._running and self._thread and self._thread.is_alive()),
            "roots": self._roots(),
            "last_error": self._last_error,
            "last_event_at": self._last_event_at,
            "last_change_count": self._last_change_count,
        }

    def _roots(self) -> list[str]:
        roots: list[str] = []
        for raw in getattr(self._owner, "_manual_strm_paths", []) or []:
            try:
                root = Path(str(raw)).expanduser().resolve()
                if root.is_dir() and str(root) not in roots:
                    roots.append(str(root))
            except OSError:
                continue
        return roots

    def _run(self, roots: list[str]) -> None:
        self._running = True
        try:
            self._bootstrap(roots)
            from watchfiles import watch

            self._run_watch(watch, roots)
        except ImportError:
            self._logger.warning("[SubtitleManualUpload] watchfiles 不可用，额外 STRM 改用轮询监控")
            self._run_polling(roots)
        except Exception as exc:
            if not self._stop_event.is_set():
                self._last_error = str(exc)
                self._logger.warning("[SubtitleManualUpload] 额外 STRM 实时监控异常，改用轮询: %s", exc)
                self._run_polling(roots)
        finally:
            self._running = False

    def _bootstrap(self, roots: list[str]) -> None:
        """启动时做一次基线刷新，覆盖监控停止期间发生的新增/修改。"""
        try:
            entries = self._owner.services.local_media_catalog().refresh_local_cache()
            manual_entries = [item for item in entries if item.get("origin") == "manual_strm"]
            self._queue_changed_entries(manual_entries)
        except Exception as exc:
            self._last_error = str(exc)
            self._logger.warning("[SubtitleManualUpload] 额外 STRM 启动基线刷新失败: %s", exc)

    def _run_watch(self, watch: Any, roots: list[str]) -> None:
        for changes in watch(
            *roots,
            stop_event=self._stop_event,
            recursive=True,
            yield_on_timeout=True,
            rust_timeout=1000,
            poll_delay_ms=1000,
            ignore_permission_denied=True,
        ):
            if self._stop_event.is_set():
                return
            paths = self._interesting_paths(changes)
            if paths:
                self._dispatch(paths)

    def _run_polling(self, roots: list[str]) -> None:
        previous = self._snapshot(roots)
        while not self._stop_event.wait(3):
            current = self._snapshot(roots)
            changed = {path for path in set(previous) | set(current) if previous.get(path) != current.get(path)}
            previous = current
            if changed:
                self._dispatch(changed)

    def _snapshot(self, roots: Iterable[str]) -> dict[str, tuple[int, int]]:
        snapshot: dict[str, tuple[int, int]] = {}
        for root_text in roots:
            root = Path(root_text)
            try:
                for path in root.rglob("*"):
                    if not path.is_file() or not self._is_interesting(path):
                        continue
                    try:
                        stat = path.stat()
                        snapshot[str(path)] = (int(stat.st_size), int(stat.st_mtime_ns))
                    except OSError:
                        continue
            except OSError:
                continue
        return snapshot

    def _interesting_paths(self, changes: Any) -> Set[str]:
        paths: Set[str] = set()
        for _, raw_path in changes or []:
            path = Path(str(raw_path))
            if path.is_dir() or self._is_interesting(path) or (not path.exists() and not path.suffix):
                paths.add(str(path))
        return paths

    def _is_interesting(self, path: Path) -> bool:
        return path.suffix.casefold() in {
            ".strm",
            ".nfo",
            *set(getattr(self._owner, "_subtitle_exts", set()) or set()),
        }

    def _dispatch(self, paths: Set[str]) -> None:
        debounce = max(float(getattr(self._owner, "_manual_strm_watch_debounce_seconds", 2)), 0.2)
        if self._stop_event.wait(debounce):
            return
        try:
            result = self._owner.services.local_media_catalog().apply_manual_strm_changes(paths)
            changed_entries = result.get("changed_entries") or []
            self._queue_changed_entries(changed_entries)
            self._last_change_count = len(paths)
            self._last_event_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception as exc:
            self._last_error = str(exc)
            self._logger.warning("[SubtitleManualUpload] 处理额外 STRM 变化失败: %s", exc)

    def _entry_signature(self, entry: dict[str, Any]) -> str:
        path = Path(str(entry.get("path") or ""))
        identity = "|".join(
            str(entry.get(key) or "")
            for key in ("media_source", "media_id", "title", "year", "season", "episode")
        )
        try:
            stat = path.stat()
            return f"{path}|{stat.st_size}|{stat.st_mtime_ns}|{identity}"
        except OSError:
            return f"{path}|missing|{identity}"

    def _signature_file(self) -> Path:
        return self._owner.get_data_path() / "manual_strm_auto_signatures.json"

    def _load_signatures(self) -> dict[str, str]:
        try:
            payload = json.loads(self._signature_file().read_text(encoding="utf-8"))
            return {str(key): str(value) for key, value in payload.items()} if isinstance(payload, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_signatures(self, signatures: dict[str, str]) -> None:
        try:
            path = self._signature_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(signatures, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            self._logger.warning("[SubtitleManualUpload] 保存额外 STRM 自动处理指纹失败: %s", exc)

    def _queue_changed_entries(self, entries: list[dict[str, Any]]) -> None:
        if not getattr(self._owner, "_auto_search_on_manual_strm", False) or not entries:
            return
        signatures = self._load_signatures()
        enriched_entries = [self._owner.services.media_metadata().enrich_media(entry) for entry in entries]
        for entry in enriched_entries:
            tmdb_id = str(entry.get("tmdb_id") or "").strip()
            if tmdb_id:
                entry["media_source"] = "themoviedb"
                entry["media_id"] = tmdb_id
        candidates = [
            entry for entry in enriched_entries
            if str(entry.get("path") or "") and signatures.get(str(entry.get("path"))) != self._entry_signature(entry)
        ]
        if not candidates:
            return
        auto_transfer = self._owner.services.auto_transfer()
        if not auto_transfer.auto_search_providers():
            self._logger.info(
                "[SubtitleManualUpload] 额外 STRM 自动搜索等待配置 ASSRT/OpenSubtitles API 源 count=%s",
                len(candidates),
            )
            return
        queued, skipped = auto_transfer.enqueue_transfer_auto_entries(candidates)
        if queued or skipped:
            for entry in candidates:
                signatures[str(entry.get("path"))] = self._entry_signature(entry)
            self._save_signatures(signatures)
        self._logger.info(
            "[SubtitleManualUpload] 额外 STRM 自动字幕任务 changed=%s queued=%s skipped=%s",
            len(candidates), queued, skipped,
        )


__all__ = ["ManualStrmMonitor"]
