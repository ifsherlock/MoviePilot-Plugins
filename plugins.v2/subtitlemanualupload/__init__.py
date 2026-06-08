from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.db.models.transferhistory import TransferHistory
from app.log import logger
from app.plugins import _PluginBase

from .timeline_fixer import check_timeline_fixer_dependencies, fix_subtitle_timeline


class SubtitleManualUpload(_PluginBase):
    plugin_name = "字幕手传匹配"
    plugin_desc = "手动上传字幕、ZIP 或 RAR，匹配电影/剧集并按媒体文件名落盘，可选智能调轴。"
    plugin_icon = "upload.png"
    plugin_version = "0.1.11"
    plugin_author = "jaysherlock"
    author_url = "https://github.com/jaysherlock"
    plugin_config_prefix = "subtitlemanualupload_"
    plugin_order = 48
    auth_level = 1

    _enabled = False
    _show_sidebar_nav = True
    _rar_dependency_mode = "none"
    _rar_tool_path = "/usr/local/bin/7z"
    _rar_dependency_status: Dict[str, Any] = {
        "mode": "none",
        "state": "idle",
        "message": "",
        "checked_at": "",
    }
    _entry_map: Dict[str, Dict[str, Any]] = {}

    _subtitle_exts = {".ass", ".srt", ".ssa", ".sbv", ".sub", ".vtt", ".webvtt"}
    _archive_exts = {".zip", ".rar"}
    _rar_exts = {".rar"}
    _rar_tools = ("unrar", "bsdtar", "7z", "7za", "7zz")
    _rar_python_package = "rarfile"
    _rar_dependency_modes = {"none", "container_install", "mapped_binary"}
    _stream_exts = {".strm"}
    _default_session_hours = 24
    _language_suffix_aliases = {
        "zh": "chi",
        "zh-hans": "chi",
        "zh_hans": "chi",
        "zh-cn": "chi",
        "zh_cn": "chi",
        "zh-hant": "chi",
        "zh_hant": "chi",
        "zh-tw": "chi",
        "zh_tw": "chi",
        "chs": "chi",
        "cht": "chi",
        "zho": "chi",
        "cmn": "chi",
        "cn": "chi",
        "en": "eng",
        "ja": "jpn",
        "jp": "jpn",
        "ko": "kor",
        "kr": "kor",
        "fr": "fre",
        "fra": "fre",
        "de": "ger",
        "deu": "ger",
        "es": "spa",
        "pt": "por",
        "it": "ita",
        "ru": "rus",
    }

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._show_sidebar_nav = bool(config.get("show_sidebar_nav", True))
        self._rar_dependency_mode = self._normalize_rar_dependency_mode(config.get("rar_dependency_mode"))
        self._rar_tool_path = self._normalize_text(config.get("rar_tool_path")) or "/usr/local/bin/7z"
        type(self)._rar_dependency_mode = self._rar_dependency_mode
        type(self)._rar_tool_path = self._rar_tool_path
        self._entry_map = {}
        self._save_config()
        self._prepare_rar_dependency()
        self._cleanup_old_sessions()

    def get_state(self) -> bool:
        return bool(self._enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取字幕手传插件状态",
            },
            {
                "path": "/refresh_index",
                "endpoint": self.api_refresh_index,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "兼容旧版刷新索引入口",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "搜索 MoviePilot 本地资源候选",
            },
            {
                "path": "/targets",
                "endpoint": self.api_targets,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取选中媒体的本地文件目标",
            },
            {
                "path": "/prepare_upload",
                "endpoint": self.api_prepare_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "上传字幕并生成匹配预览",
            },
            {
                "path": "/apply_upload",
                "endpoint": self.api_apply_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "应用字幕匹配结果并写入目标目录",
            },
            {
                "path": "/clear_subtitles",
                "endpoint": self.api_clear_subtitles,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空选中目标视频的外挂字幕",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "show_sidebar_nav",
                                            "label": "显示侧边栏入口",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "rar_dependency_mode",
                                            "label": "RAR 解压器处理方式",
                                            "items": [
                                                {"title": "不处理，仅检测", "value": "none"},
                                                {"title": "加载插件时尝试容器内安装", "value": "container_install"},
                                                {"title": "使用宿主机映射文件", "value": "mapped_binary"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "rar_tool_path",
                                            "label": "容器内映射路径",
                                            "placeholder": "/usr/local/bin/7z",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "从 MoviePilot 本地整理记录中搜索已有视频资源；长期建议把宿主机静态 7zz 放到 MoviePilot 部署目录的 tools/7zz，并映射为容器内 /usr/local/bin/7z。",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "show_sidebar_nav": True,
            "rar_dependency_mode": "none",
            "rar_tool_path": "/usr/local/bin/7z",
        }

    def get_page(self) -> List[dict]:
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self.get_state() or not self._show_sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "字幕手传匹配",
                "icon": "mdi-file-upload-outline",
                "section": "organize",
                "permission": "manage",
                "order": 48,
            }
        ]

    def stop_service(self):
        pass

    def _save_config(self) -> None:
        self.update_config(
            {
                "enabled": self._enabled,
                "show_sidebar_nav": self._show_sidebar_nav,
                "rar_dependency_mode": self._rar_dependency_mode,
                "rar_tool_path": self._rar_tool_path,
            }
        )

    def _ok(self, data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    @classmethod
    def _brief_ids(cls, values: Iterable[Any], limit: int = 5) -> str:
        items = [cls._normalize_text(item)[:8] for item in values if cls._normalize_text(item)]
        if len(items) > limit:
            return f"{','.join(items[:limit])},+{len(items) - limit}"
        return ",".join(items)

    @staticmethod
    def _decode_preview_bytes(raw_bytes: bytes) -> str:
        if not raw_bytes:
            return ""
        for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
            try:
                return raw_bytes.decode(encoding)
            except Exception:
                continue
        return raw_bytes.decode("utf-8", errors="ignore")

    @classmethod
    def _normalize_rar_dependency_mode(cls, value: Any) -> str:
        mode = cls._normalize_text(value).lower()
        if mode in cls._rar_dependency_modes:
            return mode
        return "none"

    @staticmethod
    def _is_executable_file(path: Path) -> bool:
        try:
            return path.is_file() and os.access(path, os.X_OK)
        except Exception:
            return False

    def _set_rar_dependency_status(self, state: str, message: str) -> None:
        self._rar_dependency_status = {
            "mode": self._rar_dependency_mode,
            "state": state,
            "message": message,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "tool_path": self._rar_tool_path,
        }

    def _prepare_rar_dependency(self) -> None:
        if self._rar_dependency_mode == "none":
            self._set_rar_dependency_status("skipped", "未启用 RAR 解压器自动处理")
            return

        if self._rar_tool():
            self._set_rar_dependency_status("ready", "已检测到可用 RAR 解压器")
            return

        if self._rar_dependency_mode == "mapped_binary":
            self._set_rar_dependency_status(
                "missing",
                f"未检测到映射文件，请把宿主机 7zz 映射到容器 {self._rar_tool_path}",
            )
            logger.info(
                "[SubtitleManualUpload] RAR 映射模式未检测到工具 path=%s",
                self._rar_tool_path,
            )
            return

        if self._rar_dependency_mode == "container_install":
            self._install_container_rar_tool()
            return

        self._set_rar_dependency_status("skipped", "未知 RAR 依赖处理方式")

    def _install_container_rar_tool(self) -> None:
        logger.info("[SubtitleManualUpload] 开始尝试在容器内安装 RAR 解压器")
        install_script = r"""
set -eu
if command -v unrar >/dev/null 2>&1 || command -v bsdtar >/dev/null 2>&1 || command -v 7z >/dev/null 2>&1 || command -v 7za >/dev/null 2>&1 || command -v 7zz >/dev/null 2>&1; then
  exit 0
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "当前容器没有 apt-get，无法自动安装，请使用宿主机静态 7zz 映射" >&2
  exit 78
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends p7zip-full unrar-free || apt-get install -y --no-install-recommends 7zip unrar-free libarchive-tools
"""
        try:
            completed = subprocess.run(
                ["sh", "-lc", install_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            self._set_rar_dependency_status("failed", "容器内安装 RAR 解压器超时")
            logger.warning("[SubtitleManualUpload] 容器内安装 RAR 解压器超时")
            return
        except subprocess.CalledProcessError as exc:
            stderr = self._decode_preview_bytes(exc.stderr or b"").strip()
            message = stderr[-500:] if stderr else str(exc)
            self._set_rar_dependency_status("failed", f"容器内安装失败: {message}")
            logger.warning(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器失败 returncode=%s error=%s",
                exc.returncode,
                message,
            )
            return

        stdout = self._decode_preview_bytes(completed.stdout or b"").strip()
        tool_path = self._rar_tool()
        if tool_path:
            self._set_rar_dependency_status("ready", f"容器内安装完成，当前工具: {Path(tool_path).name}")
            logger.info(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器完成 tool=%s output_tail=%s",
                Path(tool_path).name,
                stdout[-300:],
            )
            return

        self._set_rar_dependency_status("failed", "安装命令结束，但仍未检测到 unrar、bsdtar、7z、7za 或 7zz")
        logger.warning("[SubtitleManualUpload] 容器内安装后仍未检测到 RAR 解压器")

    @classmethod
    def _normalize_language_suffix(cls, value: Any) -> str:
        suffix = cls._normalize_text(value).strip().lower()
        if not suffix:
            return "und"
        suffix = cls._language_suffix_aliases.get(suffix, suffix)
        return re.sub(r"[^a-z0-9-]", "", suffix) or "und"

    @classmethod
    def _detect_language_profile(cls, file_name: str, raw_bytes: bytes) -> Dict[str, str]:
        lowered = file_name.lower()
        preview = cls._decode_preview_bytes(raw_bytes[:16000])
        has_cjk = len(re.findall(r"[\u4e00-\u9fff]", preview)) >= 20
        has_kana = len(re.findall(r"[\u3040-\u30ff]", preview)) >= 20
        has_hangul = len(re.findall(r"[\uac00-\ud7af]", preview)) >= 20
        has_ascii = len(re.findall(r"[A-Za-z]{3,}", preview)) >= 20

        suffix = "und"
        label = "未知"

        if any(token in lowered for token in ("zh-hant", "zh_tw", "zh-tw", "cht", "繁体", "繁中", "big5")):
            suffix = "chi"
            label = "繁中"
        elif any(token in lowered for token in ("zh-hans", "zh_cn", "zh-cn", "chs", "简体", "简中", "gb")):
            suffix = "chi"
            label = "简中"
        elif any(token in lowered for token in ("zh", "chi", "zho", "cmn", "中文", "中字")) or (has_cjk and not has_kana):
            suffix = "chi"
            label = "中文"
        elif any(token in lowered for token in ("jpn", "japanese", "日文", "日语", ".ja.")) or has_kana:
            suffix = "jpn"
            label = "日文"
        elif any(token in lowered for token in ("kor", "korean", "韩文", "韩语", ".ko.")) or has_hangul:
            suffix = "kor"
            label = "韩文"
        elif any(token in lowered for token in ("eng", "english", "英文", "英语", ".en.")) or has_ascii:
            suffix = "eng"
            label = "英文"
        elif any(token in lowered for token in ("fre", "fra", "french", "français", ".fr.")):
            suffix = "fre"
            label = "法文"
        elif any(token in lowered for token in ("spa", "spanish", "español", ".es.")):
            suffix = "spa"
            label = "西文"
        elif any(token in lowered for token in ("ger", "deu", "german", "deutsch", ".de.")):
            suffix = "ger"
            label = "德文"
        elif any(token in lowered for token in ("por", "portuguese", "português", ".pt.")):
            suffix = "por"
            label = "葡文"
        elif any(token in lowered for token in ("ita", "italian", "italiano", ".it.")):
            suffix = "ita"
            label = "意文"
        elif any(token in lowered for token in ("rus", "russian", ".ru.")):
            suffix = "rus"
            label = "俄文"

        if suffix == "chi" and has_ascii:
            label = f"{label}/双语"

        return {
            "suffix": cls._normalize_language_suffix(suffix),
            "label": label,
        }

    @classmethod
    def _extract_episode_hint(cls, file_name: str) -> Optional[Dict[str, int]]:
        cleaned = str(file_name or "")
        patterns = [
            re.compile(r"(?i)\bS(?P<season>\d{1,2})[\s._-]*E(?P<episode>\d{1,3})\b"),
            re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b"),
            re.compile(r"第\s*(?P<season>\d{1,2})\s*季.*?第\s*(?P<episode>\d{1,3})\s*[集话話]"),
            re.compile(r"第\s*(?P<episode>\d{1,3})\s*[集话話]"),
        ]

        for pattern in patterns:
            match = pattern.search(cleaned)
            if not match:
                continue
            season = cls._safe_int(match.groupdict().get("season"), 0)
            episode = cls._safe_int(match.groupdict().get("episode"), 0)
            if episode:
                return {"season": season, "episode": episode}
        return None

    def _get_session_root(self) -> Path:
        root = self.get_data_path() / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _cleanup_old_sessions(self) -> None:
        root = self._get_session_root()
        expire_before = datetime.now() - timedelta(hours=self._default_session_hours)
        for child in root.iterdir():
            try:
                if not child.is_dir():
                    continue
                if datetime.fromtimestamp(child.stat().st_mtime) < expire_before:
                    shutil.rmtree(child, ignore_errors=True)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 清理旧会话失败 %s: %s", child, exc)

    @classmethod
    def _media_type_text(cls, value: Any) -> str:
        raw = str(getattr(value, "value", value) or "").strip().lower()
        if raw in {"movie", "电影", "mediatype.movie"}:
            return "movie"
        if raw in {"tv", "电视剧", "series", "mediatype.tv"}:
            return "tv"
        return ""

    @classmethod
    def _poster_url(cls, poster_path: Any, prefix: str = "w500") -> str:
        poster = cls._normalize_text(poster_path)
        if not poster:
            return ""
        if poster.startswith(("http://", "https://")):
            return poster
        if not poster.startswith("/"):
            poster = f"/{poster}"
        domain = cls._normalize_text(getattr(settings, "TMDB_IMAGE_DOMAIN", "")) or "image.tmdb.org"
        return f"https://{domain}/t/p/{prefix}{poster}"

    @classmethod
    def _history_type_text(cls, media_type: Any) -> str:
        normalized = cls._media_type_text(media_type)
        if normalized == "movie":
            return "电影"
        if normalized == "tv":
            return "电视剧"
        return cls._normalize_text(media_type)

    @classmethod
    def _number_from_tag(cls, value: Any) -> int:
        match = re.search(r"\d+", cls._normalize_text(value))
        return cls._safe_int(match.group(0), 0) if match else 0

    @classmethod
    def _is_local_video_path(cls, storage: str, path: str) -> bool:
        if cls._normalize_text(storage) != "local" or not path:
            return False
        suffix = Path(path).suffix.lower()
        configured_exts = getattr(settings, "RMT_MEDIAEXT", set()) or set()
        allowed_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in configured_exts
        }
        allowed_exts.update(cls._stream_exts)
        if suffix and allowed_exts and suffix not in allowed_exts:
            return False
        try:
            return Path(path).is_file()
        except Exception:
            return False

    def _build_entry_from_history(self, history: Any) -> Optional[Dict[str, Any]]:
        if not getattr(history, "status", False):
            return None

        raw_fileitem = getattr(history, "dest_fileitem", None)
        fileitem = raw_fileitem if isinstance(raw_fileitem, dict) else {}
        storage = self._normalize_text(fileitem.get("storage") or getattr(history, "dest_storage", "")) or "local"
        path = self._normalize_text(fileitem.get("path") or getattr(history, "dest", ""))
        if not self._is_local_video_path(storage, path):
            return None

        file_path = Path(path)
        filename = self._normalize_text(fileitem.get("name")) or file_path.name
        basename = self._normalize_text(fileitem.get("basename")) or file_path.stem
        media_type = self._media_type_text(getattr(history, "type", ""))
        if not media_type:
            return None

        title = self._normalize_text(getattr(history, "title", ""))
        year = self._normalize_text(getattr(history, "year", ""))
        season = self._number_from_tag(getattr(history, "seasons", ""))
        episode = self._number_from_tag(getattr(history, "episodes", ""))
        if not season or not episode:
            try:
                meta = MetaInfoPath(file_path)
                season = season or self._safe_int(getattr(meta, "begin_season", None) or getattr(meta, "season", None), 0)
                episode = episode or self._safe_int(getattr(meta, "begin_episode", None) or getattr(meta, "episode", None), 0)
            except Exception:
                pass
        episode_hint = self._extract_episode_hint(filename or basename)
        if episode_hint:
            season = season or episode_hint.get("season", 0)
            episode = episode or episode_hint.get("episode", 0)
        if media_type == "tv" and episode and not season:
            season = 1

        tmdb_id = self._safe_int(getattr(history, "tmdbid", 0), 0)
        douban_id = self._normalize_text(getattr(history, "doubanid", ""))
        media_key = self._hash_text(f"{media_type}|{tmdb_id}|{douban_id}|{title}|{year}")
        entry_id = self._hash_text(f"{storage}|{path}")
        if media_type == "tv":
            prefix = f"S{season:02d}E{episode:02d}" if season and episode else basename
            target_label = f"{prefix} · {filename}"
        else:
            target_label = filename or (f"{title} ({year})" if year else title)

        return {
            "id": entry_id,
            "media_key": media_key,
            "media_type": media_type,
            "title": title,
            "year": year,
            "tmdb_id": tmdb_id,
            "douban_id": douban_id,
            "poster_url": self._poster_url(getattr(history, "image", "")),
            "season": season,
            "episode": episode,
            "path": path,
            "basename": basename,
            "filename": filename,
            "storage": storage,
            "library_name": "MoviePilot 媒体库",
            "relative_path": path.replace("\\", "/"),
            "target_label": target_label,
            "writable": True,
            "date": self._normalize_text(getattr(history, "date", "")),
        }

    async def _search_media_candidates(self, keyword: str, media_type: str, limit: int) -> List[Dict[str, Any]]:
        clean_keyword = self._normalize_text(keyword)
        count = max(limit * 80, 200)
        try:
            if clean_keyword:
                histories = TransferHistory.list_by_title(
                    db=None,
                    title=clean_keyword,
                    page=1,
                    count=count,
                    status=True,
                ) or []
            else:
                histories = TransferHistory.list_by_page(
                    db=None,
                    page=1,
                    count=count,
                    status=True,
                ) or []
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取 MoviePilot 本地整理记录失败: {exc}") from exc

        expected_type = self._media_type_text(media_type)
        entries: List[Dict[str, Any]] = []
        seen_paths = set()
        for history in histories:
            entry = self._build_entry_from_history(history)
            if not entry:
                continue
            if expected_type and entry.get("media_type") != expected_type:
                continue
            if entry["path"] in seen_paths:
                continue
            seen_paths.add(entry["path"])
            entries.append(entry)
        candidates = self._group_entries_as_media(entries, limit)
        for media in candidates:
            detail = self._targets_for_media(
                media_type=media.get("media_type"),
                tmdb_id=media.get("tmdb_id"),
                douban_id=media.get("douban_id"),
                title=media.get("title"),
                year=media.get("year"),
                season="all",
            )
            detail_media = detail.get("media") or {}
            media["local_count"] = detail.get("all_target_count", media.get("local_count", 0))
            media["seasons"] = detail.get("seasons", media.get("seasons", []))
            media["season_count"] = len(media["seasons"])
            media["poster_url"] = detail_media.get("poster_url") or media.get("poster_url", "")
        return candidates

    def _group_entries_as_media(self, entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            key = entry["media_key"]
            group = groups.setdefault(
                key,
                {
                    "id": key,
                    "media_id": key,
                    "media_type": entry.get("media_type"),
                    "title": entry.get("title"),
                    "en_title": "",
                    "year": entry.get("year"),
                    "tmdb_id": entry.get("tmdb_id"),
                    "douban_id": entry.get("douban_id"),
                    "poster_url": entry.get("poster_url"),
                    "backdrop_url": "",
                    "overview": "",
                    "vote_average": 0,
                    "local_count": 0,
                    "season_count": 0,
                    "latest_at": entry.get("date", ""),
                    "_entries": [],
                },
            )
            group["_entries"].append(entry)
            group["local_count"] += 1
            if entry.get("poster_url") and not group.get("poster_url"):
                group["poster_url"] = entry["poster_url"]
            if entry.get("date") and entry["date"] > group.get("latest_at", ""):
                group["latest_at"] = entry["date"]

        result = []
        for group in groups.values():
            seasons = self._merge_seasons(group.pop("_entries"))
            group["seasons"] = seasons
            group["season_count"] = len(seasons)
            result.append(group)
        result.sort(key=lambda item: (item.get("latest_at", ""), item.get("title", "")), reverse=True)
        return result[:limit]

    def _merge_seasons(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seasons: Dict[int, Dict[str, Any]] = {}
        for entry in entries:
            season = self._safe_int(entry.get("season"), 0)
            episode = self._safe_int(entry.get("episode"), 0)
            if not season:
                continue
            item = seasons.setdefault(
                season,
                {
                    "season": season,
                    "name": f"第 {season} 季",
                    "episode_count": 0,
                    "poster_url": "",
                    "local_count": 0,
                    "episodes": [],
                    "available": False,
                },
            )
            item["local_count"] += 1
            item["available"] = True
            if episode and episode not in item["episodes"]:
                item["episodes"].append(episode)

        result = list(seasons.values())
        for item in result:
            item["episodes"] = sorted(item.get("episodes") or [])
            item["episode_count"] = len(item["episodes"])
        result.sort(key=lambda item: item.get("season", 0))
        return result

    def _targets_for_media(
        self,
        media_type: str,
        tmdb_id: Any = None,
        douban_id: Any = None,
        title: str = "",
        year: str = "",
        season: Any = None,
    ) -> Dict[str, Any]:
        try:
            clean_type = self._media_type_text(media_type)
            history_type = self._history_type_text(clean_type)
            clean_tmdb_id = self._safe_int(tmdb_id, 0)
            clean_title = self._normalize_text(title)
            clean_year = self._normalize_text(year)
            if clean_tmdb_id and history_type:
                histories = TransferHistory.list_by(
                    db=None,
                    mtype=history_type,
                    tmdbid=clean_tmdb_id,
                ) or []
            elif clean_title and clean_year and history_type:
                histories = TransferHistory.list_by(
                    db=None,
                    mtype=history_type,
                    title=clean_title,
                    year=clean_year,
                ) or []
            elif clean_title:
                histories = TransferHistory.list_by_title(
                    db=None,
                    title=clean_title,
                    page=1,
                    count=500,
                    status=True,
                ) or []
            else:
                histories = []
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取 MoviePilot 本地资源失败: {exc}") from exc

        entries = []
        seen_paths = set()
        for history in histories:
            entry = self._build_entry_from_history(history)
            if not entry:
                continue
            if clean_type and entry.get("media_type") != clean_type:
                continue
            if clean_title and entry.get("title") != clean_title:
                continue
            if clean_year and entry.get("year") != clean_year:
                continue
            if clean_tmdb_id and self._safe_int(entry.get("tmdb_id"), 0) != clean_tmdb_id:
                continue
            if entry["path"] not in seen_paths:
                seen_paths.add(entry["path"])
                entries.append(entry)

        entries.sort(key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("filename", "")))
        media_groups = self._group_entries_as_media(entries, 1)
        media = media_groups[0] if media_groups else {
            "id": self._hash_text(f"{clean_type}|{clean_tmdb_id}|{douban_id}|{clean_title}|{clean_year}"),
            "media_id": "",
            "media_type": clean_type,
            "title": clean_title,
            "year": clean_year,
            "tmdb_id": clean_tmdb_id,
            "douban_id": self._normalize_text(douban_id),
            "poster_url": "",
            "local_count": 0,
            "season_count": 0,
        }
        seasons = self._merge_seasons(entries) if media.get("media_type") == "tv" else []

        season_value = self._normalize_text(season)
        selected_season: Any = "all"
        if media.get("media_type") == "tv" and season_value not in {"", "all", "0"}:
            selected_season = self._safe_int(season_value, 0) or "all"

        visible_entries = entries
        if media.get("media_type") == "tv" and selected_season != "all":
            visible_entries = [entry for entry in entries if self._safe_int(entry.get("season"), 0) == selected_season]

        self._remember_targets(visible_entries)
        return {
            "media": media,
            "seasons": seasons,
            "selected_season": selected_season,
            "targets": [self._target_from_entry(entry) for entry in visible_entries],
            "target_count": len(visible_entries),
            "all_target_count": len(entries),
        }

    def _target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        subtitles = self._subtitle_files_for_target(entry)
        return {
            "id": entry.get("id"),
            "label": entry.get("target_label"),
            "basename": entry.get("basename"),
            "media_type": entry.get("media_type"),
            "title": entry.get("title"),
            "season": entry.get("season", 0),
            "episode": entry.get("episode", 0),
            "year": entry.get("year", ""),
            "library_name": entry.get("library_name"),
            "relative_path": entry.get("relative_path"),
            "storage": entry.get("storage", "local"),
            "writable": entry.get("writable", True),
            "has_subtitle": bool(subtitles),
            "subtitle_count": len(subtitles),
            "subtitles": subtitles,
        }

    def _remember_targets(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if target_id:
                self._entry_map[target_id] = entry

    def _resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        target_id_list = [self._normalize_text(item) for item in target_ids if self._normalize_text(item)]
        target_id_set = set(target_id_list)
        result: Dict[str, Dict[str, Any]] = {}
        for target_id in target_id_list:
            entry = self._entry_map.get(target_id)
            if entry:
                result[target_id] = entry
        missing_ids = target_id_set - set(result.keys())
        if not missing_ids:
            return result

        logger.info(
            "[SubtitleManualUpload] 目标缓存未命中，回查本地整理记录 target_ids=%s missing=%s",
            self._brief_ids(target_id_list),
            len(missing_ids),
        )
        try:
            histories = TransferHistory.list_by_page(db=None, page=1, count=-1, status=True) or []
        except Exception as exc:
            logger.error("[SubtitleManualUpload] 回查本地整理记录失败: %s", exc)
            return result

        for history in histories:
            entry = self._build_entry_from_history(history)
            if not entry:
                continue
            target_id = self._normalize_text(entry.get("id"))
            if target_id in missing_ids:
                self._entry_map[target_id] = entry
                result[target_id] = entry
                missing_ids.remove(target_id)
                if not missing_ids:
                    break
        if missing_ids:
            logger.warning(
                "[SubtitleManualUpload] 仍有目标无法解析 target_ids=%s missing=%s",
                self._brief_ids(target_id_list),
                len(missing_ids),
            )
        return result

    @classmethod
    def _build_destination_name(
        cls,
        target_entry: Dict[str, Any],
        subtitle_info: Dict[str, Any],
    ) -> str:
        basename = cls._normalize_text(target_entry.get("basename")) or "subtitle"
        language_suffix = cls._normalize_language_suffix(subtitle_info.get("language_suffix"))
        ext = cls._normalize_text(subtitle_info.get("ext")) or ".srt"
        if not ext.startswith("."):
            ext = f".{ext}"
        return f"{basename}.{language_suffix}{ext.lower()}"

    @classmethod
    def _subtitle_files_for_target(cls, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        storage = cls._normalize_text(target_entry.get("storage")) or "local"
        if storage != "local":
            return []

        video_path_raw = cls._normalize_text(target_entry.get("path"))
        if not video_path_raw:
            return []

        video_path = Path(video_path_raw)
        media_dir = video_path.parent
        if not media_dir.exists() or not media_dir.is_dir():
            return []

        stem = video_path.stem
        subtitles: List[Dict[str, Any]] = []
        try:
            for sub_file in media_dir.iterdir():
                if not sub_file.is_file():
                    continue
                if sub_file.suffix.lower() not in cls._subtitle_exts:
                    continue
                if sub_file.stem != stem and not sub_file.name.startswith(f"{stem}."):
                    continue
                subtitles.append(
                    {
                        "name": sub_file.name,
                        "path": str(sub_file),
                        "relative_path": str(sub_file).replace("\\", "/"),
                        "ext": sub_file.suffix.lower(),
                        "size": sub_file.stat().st_size,
                        "modified_at": datetime.fromtimestamp(sub_file.stat().st_mtime).isoformat(timespec="seconds"),
                    }
                )
        except Exception as exc:
            logger.warning(
                "[SubtitleManualUpload] 读取外挂字幕失败 video=%s error=%s",
                video_path.name,
                exc,
            )
        subtitles.sort(key=lambda item: item.get("name", ""))
        return subtitles

    def _remove_ext_marks(self, video_path: Path) -> None:
        for sub_file in video_path.parent.iterdir():
            if not sub_file.is_file():
                continue
            if sub_file.suffix.lower() not in self._subtitle_exts:
                continue
            if not sub_file.name.startswith(f"{video_path.stem}."):
                continue
            new_name = sub_file.name.replace(".default.", ".").replace(".forced.", ".")
            if new_name == sub_file.name:
                continue
            target = sub_file.with_name(new_name)
            if target.exists():
                target.unlink()
            sub_file.rename(target)

    @staticmethod
    def _is_upload_file(value: Any) -> bool:
        return isinstance(value, UploadFile)

    @classmethod
    def _rar_tool(cls) -> str:
        configured = cls._normalize_text(getattr(cls, "_rar_tool_path", ""))
        if configured:
            configured_path = Path(configured)
            if cls._is_executable_file(configured_path):
                return str(configured_path)
        for tool in cls._rar_tools:
            found = shutil.which(tool)
            if found:
                return found
        return ""

    @classmethod
    def _rar_python_available(cls) -> bool:
        return importlib.util.find_spec(cls._rar_python_package) is not None

    @classmethod
    def _rarfile_module(cls) -> Any:
        try:
            return __import__(cls._rar_python_package)
        except Exception:
            return None

    @classmethod
    def _run_archive_command(cls, args: List[str], timeout: int = 120) -> bytes:
        try:
            completed = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=timeout,
            )
            return completed.stdout
        except subprocess.CalledProcessError as exc:
            stderr = cls._decode_preview_bytes(exc.stderr or b"").strip()
            raise ValueError(f"压缩包解压失败: {stderr or exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("压缩包解压超时") from exc

    @classmethod
    def _list_rar_members(cls, archive_path: Path, tool_path: str) -> List[str]:
        tool_name = Path(tool_path).name.lower()
        if tool_name == "unrar":
            output = cls._run_archive_command([tool_path, "lb", str(archive_path)])
            return [line.strip() for line in cls._decode_preview_bytes(output).splitlines() if line.strip()]
        if tool_name == "bsdtar":
            output = cls._run_archive_command([tool_path, "-tf", str(archive_path)])
            return [line.strip() for line in cls._decode_preview_bytes(output).splitlines() if line.strip()]
        if tool_name in {"7z", "7za", "7zz"}:
            output = cls._run_archive_command([tool_path, "l", "-slt", str(archive_path)])
            members = []
            for line in cls._decode_preview_bytes(output).splitlines():
                if not line.startswith("Path = "):
                    continue
                member = line.removeprefix("Path = ").strip()
                if member and member != str(archive_path):
                    members.append(member)
            return members
        return []

    @classmethod
    def _read_rar_member(cls, archive_path: Path, member: str, tool_path: str) -> bytes:
        tool_name = Path(tool_path).name.lower()
        if tool_name == "unrar":
            return cls._run_archive_command([tool_path, "p", "-inul", str(archive_path), member])
        if tool_name == "bsdtar":
            return cls._run_archive_command([tool_path, "-xOf", str(archive_path), member])
        if tool_name in {"7z", "7za", "7zz"}:
            return cls._run_archive_command([tool_path, "x", "-so", str(archive_path), member])
        raise ValueError("当前容器缺少可用的 RAR 解压工具")

    @classmethod
    def _extract_rar_subtitle_files_with_rarfile(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        rarfile_module = cls._rarfile_module()
        if not rarfile_module:
            raise ValueError(f"未安装 Python 依赖 {cls._rar_python_package}")

        prepared: List[Dict[str, Any]] = []
        try:
            with rarfile_module.RarFile(str(archive_path)) as archive:
                for member in archive.infolist():
                    if member.isdir():
                        continue
                    member_name = re.split(r"[\\/]", member.filename)[-1]
                    if not member_name or member_name.startswith("."):
                        continue
                    member_ext = Path(member_name).suffix.lower()
                    if member_ext not in cls._subtitle_exts:
                        continue
                    member_bytes = archive.read(member)
                    upload_id = cls._hash_text(
                        f"{source_name}|{member.filename}|{len(member_bytes)}|{datetime.now().timestamp()}"
                    )
                    stored_path = session_dir / f"{upload_id}{member_ext}"
                    stored_path.write_bytes(member_bytes)
                    prepared.append(
                        {
                            "upload_id": upload_id,
                            "source_name": member_name,
                            "archive_name": source_name,
                            "stored_path": str(stored_path),
                            "ext": member_ext,
                        }
                    )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return prepared

    @classmethod
    def _extract_rar_subtitle_files(
        cls,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        if cls._rar_python_available():
            try:
                return cls._extract_rar_subtitle_files_with_rarfile(source_name, archive_path, session_dir)
            except ValueError as exc:
                logger.warning(
                    "[SubtitleManualUpload] rarfile 解析 RAR 失败，将尝试外部命令回退 archive=%s error=%s",
                    source_name,
                    exc,
                )

        tool_path = cls._rar_tool()
        if not tool_path:
            package_note = f"已声明 Python 依赖 {cls._rar_python_package}，但 RAR 内容解压仍需要外部解压程序"
            raise ValueError(f"{package_note}；请在容器安装 unrar、bsdtar、7z、7za 或映射静态 7zz")

        prepared: List[Dict[str, Any]] = []
        members = cls._list_rar_members(archive_path, tool_path)
        for member in members:
            member_name = re.split(r"[\\/]", member)[-1]
            if not member_name or member_name.startswith("."):
                continue
            member_ext = Path(member_name).suffix.lower()
            if member_ext not in cls._subtitle_exts:
                continue
            member_bytes = cls._read_rar_member(archive_path, member, tool_path)
            upload_id = cls._hash_text(
                f"{source_name}|{member}|{len(member_bytes)}|{datetime.now().timestamp()}"
            )
            stored_path = session_dir / f"{upload_id}{member_ext}"
            stored_path.write_bytes(member_bytes)
            prepared.append(
                {
                    "upload_id": upload_id,
                    "source_name": member_name,
                    "archive_name": source_name,
                    "stored_path": str(stored_path),
                    "ext": member_ext,
                }
            )
        return prepared

    @classmethod
    def _extract_subtitle_files(
        cls,
        upload_name: str,
        raw_bytes: bytes,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        source_name = Path(upload_name or "").name
        ext = Path(source_name).suffix.lower()
        prepared: List[Dict[str, Any]] = []

        if ext in cls._subtitle_exts:
            upload_id = cls._hash_text(f"{source_name}|{len(raw_bytes)}|{datetime.now().timestamp()}")
            stored_path = session_dir / f"{upload_id}{ext}"
            stored_path.write_bytes(raw_bytes)
            prepared.append(
                {
                    "upload_id": upload_id,
                    "source_name": source_name,
                    "archive_name": "",
                    "stored_path": str(stored_path),
                    "ext": ext,
                }
            )
            return prepared

        if ext not in cls._archive_exts:
            return prepared

        archive_path = session_dir / source_name
        archive_path.write_bytes(raw_bytes)
        if ext in cls._rar_exts:
            return cls._extract_rar_subtitle_files(source_name, archive_path, session_dir)

        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    member_name = Path(member.filename).name
                    if not member_name or member_name.startswith("."):
                        continue
                    member_ext = Path(member_name).suffix.lower()
                    if member_ext not in cls._subtitle_exts:
                        continue
                    member_bytes = archive.read(member)
                    upload_id = cls._hash_text(
                        f"{source_name}|{member.filename}|{len(member_bytes)}|{datetime.now().timestamp()}"
                    )
                    stored_path = session_dir / f"{upload_id}{member_ext}"
                    stored_path.write_bytes(member_bytes)
                    prepared.append(
                        {
                            "upload_id": upload_id,
                            "source_name": member_name,
                            "archive_name": source_name,
                            "stored_path": str(stored_path),
                            "ext": member_ext,
                        }
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError(f"压缩包损坏或格式不正确: {source_name}") from exc
        return prepared

    @classmethod
    def _suggest_target(
        cls,
        subtitle_info: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not targets:
            return None
        if len(targets) == 1:
            return targets[0]["id"]

        hint = cls._extract_episode_hint(subtitle_info.get("source_name"))
        if not hint:
            return None

        season = hint.get("season", 0)
        episode = hint.get("episode", 0)

        for target in targets:
            if target.get("season", 0) == season and target.get("episode", 0) == episode:
                return target["id"]

        if season == 0:
            candidate_seasons = {target.get("season", 0) for target in targets if target.get("season", 0)}
            if len(candidate_seasons) == 1:
                only_season = next(iter(candidate_seasons))
                for target in targets:
                    if target.get("season", 0) == only_season and target.get("episode", 0) == episode:
                        return target["id"]
        return None

    @classmethod
    def _auto_fill_missing_targets(
        cls,
        preview_items: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
    ) -> None:
        unresolved = [item for item in preview_items if not item.get("target_id")]
        if not unresolved:
            return
        used_target_ids = {
            item.get("target_id")
            for item in preview_items
            if item.get("target_id")
        }
        remaining_targets = [
            target for target in targets if target.get("id") not in used_target_ids
        ]
        if len(unresolved) != len(remaining_targets):
            return
        sorted_targets = sorted(
            remaining_targets,
            key=lambda item: (
                item.get("season", 0),
                item.get("episode", 0),
                item.get("label", ""),
            ),
        )
        sorted_items = sorted(
            unresolved,
            key=lambda item: (
                cls._extract_episode_hint(item.get("source_name") or "") or {}
            ).get("episode", 0),
        )
        for item, target in zip(sorted_items, sorted_targets):
            item["target_id"] = target["id"]

    @classmethod
    def _build_write_operations(
        cls,
        items: List[Dict[str, Any]],
        upload_map: Dict[str, Dict[str, Any]],
        target_entries: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        destination_keys = set()
        operations: List[Dict[str, Any]] = []

        for item in items:
            upload_id = cls._normalize_text(item.get("upload_id"))
            target_id = cls._normalize_text(item.get("target_id"))
            if not upload_id or not target_id:
                raise HTTPException(status_code=400, detail="存在未完成目标选择的字幕项")

            upload_info = upload_map.get(upload_id)
            target_entry = target_entries.get(target_id)
            if not upload_info or not target_entry:
                raise HTTPException(status_code=400, detail="上传项或目标视频不存在，请重新上传")

            storage = cls._normalize_text(target_entry.get("storage")) or "local"
            if storage != "local":
                raise HTTPException(status_code=400, detail=f"当前仅支持写入本地媒体文件，目标存储为: {storage}")

            video_path = Path(target_entry["path"])
            if not video_path.exists():
                raise HTTPException(status_code=400, detail=f"目标视频不存在: {video_path}")

            source_path = Path(upload_info["stored_path"])
            if not source_path.exists():
                raise HTTPException(status_code=400, detail=f"上传缓存文件不存在: {upload_info.get('source_name')}")

            item_ext = cls._normalize_text(item.get("ext")) or upload_info.get("ext") or ".srt"
            item_suffix = cls._normalize_language_suffix(item.get("language_suffix"))
            destination_name = cls._build_destination_name(
                target_entry,
                {
                    "ext": item_ext,
                    "language_suffix": item_suffix,
                },
            )
            unique_key = f"{target_id}|{destination_name}"
            if unique_key in destination_keys:
                raise HTTPException(status_code=400, detail=f"重复映射到同一个目标字幕名: {destination_name}")
            destination_keys.add(unique_key)

            operations.append(
                {
                    "upload_info": upload_info,
                    "target_entry": target_entry,
                    "video_path": video_path,
                    "source_path": source_path,
                    "destination_name": destination_name,
                    "destination_path": video_path.parent / destination_name,
                }
            )
        return operations

    def _write_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        session_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_session(self, session_id: str) -> Tuple[Path, Dict[str, Any]]:
        session_dir = self._get_session_root() / self._normalize_text(session_id)
        session_file = session_dir / "session.json"
        if not session_file.exists():
            raise HTTPException(status_code=404, detail="上传会话不存在或已过期")
        try:
            return session_dir, json.loads(session_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取上传会话失败: {exc}") from exc

    def api_status(self) -> Dict[str, Any]:
        rar_tool = self._rar_tool()
        rar_python = self._rar_python_available()
        return self._ok(
            {
                "enabled": self.get_state(),
                "source": "MoviePilot 本地整理记录",
                "index": {"ready": True, "updated_at": "", "entry_count": 0},
                "archive_support": {
                    "zip": True,
                    "rar": bool(rar_tool),
                    "rar_tool": Path(rar_tool).name if rar_tool else "",
                    "rar_tool_path": rar_tool or self._rar_tool_path,
                    "rar_python": rar_python,
                    "rar_python_package": self._rar_python_package,
                    "dependency_mode": self._rar_dependency_mode,
                    "dependency_status": self._rar_dependency_status,
                },
                "timeline_fixer": check_timeline_fixer_dependencies(),
            }
        )

    def api_refresh_index(self) -> Dict[str, Any]:
        return self._ok(
            {
                "realtime": True,
            },
            message="已改用 MoviePilot 本地整理记录实时读取，无需刷新索引",
        )

    async def api_search(self, request: Request) -> Dict[str, Any]:
        keyword = self._normalize_text(request.query_params.get("keyword"))
        media_type = self._normalize_text(request.query_params.get("media_type")) or "all"
        limit = min(max(self._safe_int(request.query_params.get("limit"), 20), 1), 100)
        medias = await self._search_media_candidates(keyword=keyword, media_type=media_type, limit=limit)
        logger.info(
            "[SubtitleManualUpload] 本地资源搜索完成 keyword=%s media_type=%s result=%s",
            keyword or "<recent>",
            media_type,
            len(medias),
        )
        return self._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "medias": medias,
            }
        )

    def api_targets(self, request: Request) -> Dict[str, Any]:
        media_type = self._normalize_text(request.query_params.get("media_type"))
        tmdb_id = self._normalize_text(request.query_params.get("tmdb_id"))
        douban_id = self._normalize_text(request.query_params.get("douban_id"))
        title = self._normalize_text(request.query_params.get("title"))
        year = self._normalize_text(request.query_params.get("year"))
        season = self._normalize_text(request.query_params.get("season"))
        result = self._targets_for_media(
            media_type=media_type,
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            title=title,
            year=year,
            season=season,
        )
        logger.info(
            "[SubtitleManualUpload] 本地目标读取完成 media=%s year=%s type=%s season=%s targets=%s all_targets=%s",
            title or tmdb_id or douban_id,
            year or "-",
            media_type or "-",
            result.get("selected_season"),
            result.get("target_count"),
            result.get("all_target_count"),
        )
        return self._ok(result)

    async def api_prepare_upload(self, request: Request) -> Dict[str, Any]:
        form = await request.form()
        target_ids_raw = self._normalize_text(form.get("target_ids"))
        if not target_ids_raw:
            logger.warning("[SubtitleManualUpload] 上传预览失败：未提供目标 target_ids")
            raise HTTPException(status_code=400, detail="请先选择目标电影或剧集")

        try:
            target_ids = json.loads(target_ids_raw)
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标参数格式错误 %s", exc)
            raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc
        if not isinstance(target_ids, list) or not target_ids:
            logger.warning("[SubtitleManualUpload] 上传预览失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：目标视频已失效 target_ids=%s",
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        upload_files = [item for item in form.getlist("files") if self._is_upload_file(item)]
        if not upload_files:
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：未收到字幕文件 target_count=%s target_ids=%s",
                len(target_entries),
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="请至少上传一个字幕文件、ZIP 或 RAR")

        logger.info(
            "[SubtitleManualUpload] 开始上传预览 target_count=%s upload_files=%s target_ids=%s",
            len(target_entries),
            len(upload_files),
            self._brief_ids(target_ids),
        )

        session_id = self._hash_text(f"{datetime.now().isoformat()}|{','.join(sorted(map(str, target_ids)))}")[:16]
        session_dir = self._get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        prepared_uploads: List[Dict[str, Any]] = []
        unsupported_files: List[str] = []
        invalid_files: List[Dict[str, str]] = []
        for upload in upload_files:
            file_name = Path(self._normalize_text(upload.filename)).name
            if not file_name:
                continue
            raw_bytes = await upload.read()
            try:
                extracted = self._extract_subtitle_files(file_name, raw_bytes, session_dir)
            except ValueError as exc:
                invalid_files.append(
                    {
                        "name": file_name,
                        "reason": str(exc),
                    }
                )
                continue
            if not extracted:
                unsupported_files.append(file_name)
                continue
            prepared_uploads.extend(extracted)

        if not prepared_uploads:
            shutil.rmtree(session_dir, ignore_errors=True)
            if invalid_files:
                first_reason = invalid_files[0]["reason"]
                logger.warning(
                    "[SubtitleManualUpload] 上传预览失败：压缩包解析失败 invalid=%s unsupported=%s reason=%s",
                    len(invalid_files),
                    len(unsupported_files),
                    first_reason,
                )
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{first_reason}")
            logger.warning(
                "[SubtitleManualUpload] 上传预览失败：没有可用字幕 unsupported=%s",
                len(unsupported_files),
            )
            raise HTTPException(status_code=400, detail="没有解析到可用的字幕文件，请检查文件格式")

        targets = [self._target_from_entry(item) for item in target_entries]
        preview_items: List[Dict[str, Any]] = []
        for prepared in prepared_uploads:
            file_path = Path(prepared["stored_path"])
            raw_bytes = file_path.read_bytes()
            language_profile = self._detect_language_profile(prepared["source_name"], raw_bytes)
            preview_item = {
                "upload_id": prepared["upload_id"],
                "source_name": prepared["source_name"],
                "archive_name": prepared["archive_name"],
                "ext": prepared["ext"],
                "target_id": self._suggest_target(prepared, targets),
                "detected_label": language_profile["label"],
                "language_suffix": language_profile["suffix"],
            }
            preview_items.append(preview_item)

        self._auto_fill_missing_targets(preview_items, targets)
        target_lookup = {item["id"]: item for item in targets if item.get("id")}
        for item in preview_items:
            target = target_lookup.get(item.get("target_id"))
            item["output_name"] = self._build_destination_name(target, item) if target else ""

        session_payload = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_ids": list(target_ids),
            "targets": target_entries,
            "uploads": prepared_uploads,
        }
        self._write_session(session_id, session_payload)

        resolved_count = len([item for item in preview_items if item.get("target_id")])
        message = f"已解析 {len(preview_items)} 个字幕文件，自动匹配 {resolved_count} 个。"
        if unsupported_files:
            message += f" 已忽略 {len(unsupported_files)} 个不支持的文件。"
        if invalid_files:
            message += f" 有 {len(invalid_files)} 个压缩包解析失败。"

        logger.info(
            "[SubtitleManualUpload] 上传预览完成 session=%s subtitles=%s resolved=%s unsupported=%s invalid=%s",
            session_id,
            len(preview_items),
            resolved_count,
            len(unsupported_files),
            len(invalid_files),
        )

        return self._ok(
            {
                "session_id": session_id,
                "targets": targets,
                "items": preview_items,
                "unsupported_files": unsupported_files,
                "invalid_files": invalid_files,
            },
            message=message,
        )

    async def api_apply_upload(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        session_id = self._normalize_text(body.get("session_id"))
        items = body.get("items") or []
        fix_timeline = bool(body.get("fix_timeline"))
        if not session_id or not isinstance(items, list) or not items:
            logger.warning("[SubtitleManualUpload] 写入失败：缺少会话或匹配结果 session=%s", session_id or "-")
            raise HTTPException(status_code=400, detail="缺少上传会话或匹配结果")

        session_dir, session_payload = self._load_session(session_id)
        upload_map = {
            item["upload_id"]: item
            for item in session_payload.get("uploads", [])
            if item.get("upload_id")
        }
        target_entries = {
            item["id"]: item
            for item in session_payload.get("targets", [])
            if item.get("id")
        }
        if not target_entries:
            logger.warning("[SubtitleManualUpload] 写入失败：会话目标为空 session=%s", session_id)
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并上传")

        logger.info(
            "[SubtitleManualUpload] 开始写入字幕 session=%s items=%s targets=%s fix_timeline=%s",
            session_id,
            len(items),
            len(target_entries),
            fix_timeline,
        )
        operations = self._build_write_operations(items, upload_map, target_entries)
        fixed_dir = session_dir / "timeline_fixed"
        for operation in operations:
            operation["write_source_path"] = operation["source_path"]
            operation["timeline_result"] = None
            if fix_timeline:
                fixed_dir.mkdir(parents=True, exist_ok=True)
                fixed_source_path = fixed_dir / f"{operation['upload_info'].get('upload_id')}{operation['source_path'].suffix}"
                try:
                    timeline_result = fix_subtitle_timeline(
                        video_path=operation["video_path"],
                        subtitle_path=operation["source_path"],
                        output_path=fixed_source_path,
                    )
                except Exception as exc:
                    logger.error(
                        "[SubtitleManualUpload] 智能调轴失败 %s -> %s: %s",
                        operation["upload_info"].get("source_name"),
                        operation["destination_name"],
                        exc,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"智能调轴失败: {operation['upload_info'].get('source_name')} - {exc}",
                    ) from exc
                operation["write_source_path"] = fixed_source_path
                operation["timeline_result"] = timeline_result

        written_results = []
        for operation in operations:
            destination_path = operation["destination_path"]
            temp_path = destination_path.with_name(f"{destination_path.name}.mp-uploading")
            if temp_path.exists():
                temp_path.unlink()

            shutil.copyfile(operation["write_source_path"], temp_path)
            temp_path.replace(destination_path)
            timeline_result = operation.get("timeline_result")
            written_results.append(
                {
                    "source_name": operation["upload_info"].get("source_name"),
                    "archive_name": operation["upload_info"].get("archive_name"),
                    "target_label": self._target_from_entry(operation["target_entry"]).get("label"),
                    "output_name": operation["destination_name"],
                    "output_path": str(destination_path),
                    "timeline": timeline_result.to_dict() if timeline_result else {"enabled": False},
                }
            )

        touched_videos: Dict[str, Path] = {
            str(operation["video_path"]): operation["video_path"]
            for operation in operations
        }
        for video_path in touched_videos.values():
            self._remove_ext_marks(video_path)

        shutil.rmtree(session_dir, ignore_errors=True)

        fixed_count = len(
            [
                item
                for item in written_results
                if item.get("timeline", {}).get("enabled") and item.get("timeline", {}).get("applied")
            ]
        )
        message = f"已写入 {len(written_results)} 个字幕文件"
        if fix_timeline:
            message += f"，智能调轴 {fixed_count} 个"

        logger.info(
            "[SubtitleManualUpload] 字幕写入完成 session=%s count=%s fix_timeline=%s fixed=%s",
            session_id,
            len(written_results),
            fix_timeline,
            fixed_count,
        )

        return self._ok(
            {
                "count": len(written_results),
                "written": written_results,
            },
            message=message,
        )

    async def api_clear_subtitles(self, request: Request) -> Dict[str, Any]:
        body = await request.json()
        target_ids = body.get("target_ids") or []
        if isinstance(target_ids, str):
            try:
                target_ids = json.loads(target_ids)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 清空外挂字幕失败：目标参数格式错误 %s", exc)
                raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc

        if not isinstance(target_ids, list) or not target_ids:
            logger.warning("[SubtitleManualUpload] 清空外挂字幕失败：目标列表为空")
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = self._resolve_targets(target_ids)
        if not target_entries:
            logger.warning(
                "[SubtitleManualUpload] 清空外挂字幕失败：目标视频已失效 target_ids=%s",
                self._brief_ids(target_ids),
            )
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

        deleted: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []
        visited_paths = set()
        for target_id in target_ids:
            clean_target_id = self._normalize_text(target_id)
            target_entry = target_entries.get(clean_target_id)
            if not target_entry:
                failed.append({"target_id": clean_target_id, "reason": "目标视频已失效"})
                continue
            if self._normalize_text(target_entry.get("storage")) not in {"", "local"}:
                failed.append({"target_id": clean_target_id, "reason": "当前仅支持清空本地媒体文件的外挂字幕"})
                continue

            target_label = self._target_from_entry(target_entry).get("label")
            for subtitle in self._subtitle_files_for_target(target_entry):
                subtitle_path = Path(subtitle["path"])
                path_key = str(subtitle_path)
                if path_key in visited_paths:
                    continue
                visited_paths.add(path_key)
                try:
                    subtitle_path.unlink()
                    deleted.append(
                        {
                            "target_id": clean_target_id,
                            "target_label": target_label,
                            "name": subtitle_path.name,
                            "path": path_key,
                        }
                    )
                except Exception as exc:
                    logger.error(
                        "[SubtitleManualUpload] 删除外挂字幕失败 target=%s subtitle=%s error=%s",
                        clean_target_id[:8],
                        subtitle_path.name,
                        exc,
                    )
                    failed.append({"target_id": clean_target_id, "reason": f"{subtitle_path.name}: {exc}"})

        logger.info(
            "[SubtitleManualUpload] 清空外挂字幕完成 targets=%s deleted=%s failed=%s",
            len(target_ids),
            len(deleted),
            len(failed),
        )

        message = f"已删除 {len(deleted)} 个外挂字幕"
        if failed:
            message += f"，{len(failed)} 个目标处理失败"

        return self._ok(
            {
                "count": len(deleted),
                "deleted": deleted,
                "failed": failed,
            },
            message=message,
        )
