from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.helper.directory import DirectoryHelper
from app.log import logger
from app.plugins import _PluginBase
from app.utils.system import SystemUtils


class SubtitleManualUpload(_PluginBase):
    plugin_name = "字幕手传匹配"
    plugin_desc = "手动上传字幕或 ZIP，匹配电影/剧集并按媒体文件名落盘。"
    plugin_icon = "upload.png"
    plugin_version = "0.1.0"
    plugin_author = "jaysh"
    author_url = "https://github.com/jaysh"
    plugin_config_prefix = "subtitlemanualupload_"
    plugin_order = 48
    auth_level = 1

    _enabled = False
    _show_sidebar_nav = True
    _index_cache: Optional[Dict[str, Any]] = None
    _entry_map: Dict[str, Dict[str, Any]] = {}

    _subtitle_exts = {".ass", ".srt", ".ssa", ".sbv", ".sub", ".vtt", ".webvtt"}
    _archive_exts = {".zip"}
    _default_session_hours = 24
    _default_index_minutes = 30

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._show_sidebar_nav = bool(config.get("show_sidebar_nav", True))
        self._index_cache = None
        self._entry_map = {}
        self._save_config()
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
                "summary": "刷新媒体库索引",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "搜索媒体库中的电影或剧集",
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
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "当前版本面向本地媒体库：先搜索目标电影或剧集，再拖拽字幕或 ZIP 上传并确认匹配结果。",
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
    def _normalize_key(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = text.replace("_", " ")
        text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

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
    def _detect_language_profile(cls, file_name: str, raw_bytes: bytes) -> Dict[str, str]:
        lowered = file_name.lower()
        preview = cls._decode_preview_bytes(raw_bytes[:16000])
        has_cjk = len(re.findall(r"[\u4e00-\u9fff]", preview)) >= 20
        has_ascii = len(re.findall(r"[A-Za-z]{3,}", preview)) >= 20

        suffix = "und"
        label = "未知"

        if any(token in lowered for token in ("zh-hant", "zh_tw", "zh-tw", "cht", "繁体", "繁中", "big5")):
            suffix = "zh-Hant"
            label = "繁中"
        elif any(token in lowered for token in ("zh-hans", "zh_cn", "zh-cn", "chs", "简体", "简中", "gb")):
            suffix = "zh-Hans"
            label = "简中"
        elif any(token in lowered for token in ("zh", "chi", "中文", "中字")) or has_cjk:
            suffix = "zh"
            label = "中文"
        elif any(token in lowered for token in ("eng", "english", "英文", "英语", ".en.")) or has_ascii:
            suffix = "en"
            label = "英文"
        elif any(token in lowered for token in ("jpn", "japanese", "日文", "日语", ".ja.")):
            suffix = "ja"
            label = "日文"
        elif any(token in lowered for token in ("kor", "korean", "韩文", "韩语", ".ko.")):
            suffix = "ko"
            label = "韩文"

        if suffix.startswith("zh") and has_ascii:
            label = f"{label}/双语"

        return {
            "suffix": suffix,
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

    @staticmethod
    def _looks_like_season_dir(dir_name: str) -> bool:
        lowered = str(dir_name or "").strip().lower()
        return bool(re.fullmatch(r"(season|s)\s*[\d一二三四五六七八九十]+", lowered))

    @classmethod
    def _guess_show_title(cls, file_path: Path) -> str:
        parent = file_path.parent
        if cls._looks_like_season_dir(parent.name) and parent.parent:
            return parent.parent.name
        return parent.name

    @classmethod
    def _looks_like_generic_library_dir(cls, dir_name: str) -> bool:
        normalized = cls._normalize_key(dir_name)
        return normalized in {
            "movie",
            "movies",
            "film",
            "films",
            "tv",
            "tvs",
            "show",
            "shows",
            "series",
            "media",
            "library",
            "动漫",
            "动画",
            "电影",
            "电视剧",
        }

    @classmethod
    def _guess_tv_series_title(cls, file_path: Path, parsed_title: str) -> str:
        parent = file_path.parent
        if cls._looks_like_season_dir(parent.name) and parent.parent:
            season_parent_title = cls._strip_episode_tokens(parent.parent.name)
            if season_parent_title:
                return season_parent_title

        guessed_parent = cls._strip_episode_tokens(parent.name)
        if guessed_parent and not cls._looks_like_generic_library_dir(parent.name):
            return guessed_parent

        parsed = cls._strip_episode_tokens(parsed_title)
        if parsed:
            return parsed
        return cls._strip_episode_tokens(file_path.stem)

    @staticmethod
    def _guess_year(text: str) -> str:
        match = re.search(r"(19|20)\d{2}", text or "")
        return match.group(0) if match else ""

    @classmethod
    def _strip_episode_tokens(cls, text: str) -> str:
        value = str(text or "")
        value = re.sub(r"(?i)\bS\d{1,2}[\s._-]*E\d{1,3}\b", " ", value)
        value = re.sub(r"(?i)\b\d{1,2}x\d{1,3}\b", " ", value)
        value = re.sub(r"第\s*\d{1,2}\s*季", " ", value)
        value = re.sub(r"第\s*\d{1,3}\s*[集话話]", " ", value)
        value = re.sub(r"(19|20)\d{2}", " ", value)
        value = re.sub(r"[._\-]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _coerce_media_type(cls, value: Any, file_path: Path) -> str:
        raw = str(getattr(value, "value", value) or "").strip().lower()
        if raw in {"movie", "电影"}:
            return "movie"
        if raw in {"tv", "电视剧"}:
            return "tv"
        hint = cls._extract_episode_hint(file_path.name)
        return "tv" if hint else "movie"

    @classmethod
    def _build_entry(cls, file_path: Path, library_name: str) -> Dict[str, Any]:
        meta = MetaInfoPath(file_path)
        media_type = cls._coerce_media_type(getattr(meta, "type", None), file_path)
        year = cls._normalize_text(getattr(meta, "year", None)) or cls._guess_year(file_path.name)
        season = cls._safe_int(
            getattr(meta, "begin_season", None) or getattr(meta, "season", None),
            0,
        )
        episode = cls._safe_int(
            getattr(meta, "begin_episode", None) or getattr(meta, "episode", None),
            0,
        )

        episode_hint = cls._extract_episode_hint(file_path.name)
        if episode_hint:
            season = season or episode_hint.get("season", 0)
            episode = episode or episode_hint.get("episode", 0)

        title_candidates = [
            getattr(meta, "title", None),
            getattr(meta, "name", None),
            getattr(meta, "cn_name", None),
        ]
        title = next((cls._normalize_text(item) for item in title_candidates if cls._normalize_text(item)), "")
        if media_type == "tv":
            show_title = cls._guess_tv_series_title(file_path, title)
            item_title = show_title
        else:
            item_title = title or cls._strip_episode_tokens(file_path.stem)
            show_title = ""

        item_title = item_title or file_path.stem

        entry_id = cls._hash_text(str(file_path))
        relative_path = str(file_path).replace("\\", "/")
        target_label = f"{item_title} ({year})" if media_type == "movie" and year else item_title
        if media_type == "tv":
            prefix = f"S{season:02d}E{episode:02d}" if season and episode else file_path.stem
            target_label = f"{prefix} · {file_path.name}"

        search_blob = cls._normalize_key(
            " ".join(
                filter(
                    None,
                    [
                        item_title,
                        show_title,
                        year,
                        file_path.name,
                        library_name,
                        relative_path,
                    ],
                )
            )
        )

        group_title = show_title or item_title
        group_key = cls._hash_text(f"{media_type}|{cls._normalize_key(group_title)}|{year}")

        return {
            "id": entry_id,
            "media_type": media_type,
            "title": item_title,
            "group_title": group_title,
            "year": year,
            "season": season,
            "episode": episode,
            "path": str(file_path),
            "basename": file_path.stem,
            "filename": file_path.name,
            "library_name": library_name,
            "relative_path": relative_path,
            "group_key": group_key,
            "group_label": f"{group_title} ({year})" if year else group_title,
            "target_label": target_label,
            "search_blob": search_blob,
        }

    def _get_index_file(self) -> Path:
        return self.get_data_path() / "library_index.json"

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

    def _load_index(self) -> Dict[str, Any]:
        if self._index_cache:
            return self._index_cache

        cache_file = self._get_index_file()
        if cache_file.exists():
            try:
                self._index_cache = json.loads(cache_file.read_text(encoding="utf-8"))
                self._entry_map = {
                    item["id"]: item
                    for item in self._index_cache.get("entries", [])
                    if item.get("id")
                }
                return self._index_cache
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 读取媒体索引失败，准备重建: %s", exc)

        self._index_cache = {
            "updated_at": "",
            "entry_count": 0,
            "entries": [],
        }
        self._entry_map = {}
        return self._index_cache

    def _save_index(self, index_data: Dict[str, Any]) -> Dict[str, Any]:
        cache_file = self._get_index_file()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._index_cache = index_data
        self._entry_map = {
            item["id"]: item
            for item in self._index_cache.get("entries", [])
            if item.get("id")
        }
        return index_data

    def _build_index(self, force: bool = False) -> Dict[str, Any]:
        index_data = self._load_index()
        if not force and index_data.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(index_data["updated_at"])
                if datetime.now() - updated_at < timedelta(minutes=self._default_index_minutes):
                    return index_data
            except Exception:
                pass

        entries: List[Dict[str, Any]] = []
        libraries = DirectoryHelper().get_library_dirs()
        for library in libraries:
            library_name = self._normalize_text(getattr(library, "name", None))
            library_path = self._normalize_text(getattr(library, "library_path", None))
            if not library_name or not library_path:
                continue
            root = Path(library_path)
            if not root.exists():
                logger.warning("[SubtitleManualUpload] 媒体库目录不存在: %s", root)
                continue
            try:
                files = SystemUtils.list_files(root, settings.RMT_MEDIAEXT)
            except Exception as exc:
                logger.warning("[SubtitleManualUpload] 枚举媒体库失败 %s: %s", root, exc)
                continue
            for file_path in files:
                try:
                    entries.append(self._build_entry(Path(file_path), library_name))
                except Exception as exc:
                    logger.warning("[SubtitleManualUpload] 索引媒体文件失败 %s: %s", file_path, exc)

        entries.sort(
            key=lambda item: (
                item.get("media_type", ""),
                self._normalize_key(item.get("group_title")),
                item.get("season", 0),
                item.get("episode", 0),
                item.get("relative_path", ""),
            )
        )
        return self._save_index(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "entry_count": len(entries),
                "entries": entries,
            }
        )

    def _libraries_summary(self) -> List[Dict[str, Any]]:
        libraries = []
        for library in DirectoryHelper().get_library_dirs():
            library_name = self._normalize_text(getattr(library, "name", None))
            library_path = self._normalize_text(getattr(library, "library_path", None))
            if not library_name:
                continue
            libraries.append(
                {
                    "name": library_name,
                    "exists": bool(library_path and Path(library_path).exists()),
                }
            )
        return libraries

    def _target_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
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
        }

    def _search_groups(self, keyword: str, media_type: str, limit: int) -> List[Dict[str, Any]]:
        index_data = self._build_index(force=False)
        entries = index_data.get("entries", [])
        normalized_keyword = self._normalize_key(keyword)
        terms = [term for term in normalized_keyword.split(" ") if term]
        groups: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            current_type = entry.get("media_type")
            if media_type in {"movie", "tv"} and current_type != media_type:
                continue
            haystack = entry.get("search_blob", "")
            if terms and not all(term in haystack for term in terms):
                continue

            group = groups.setdefault(
                entry["group_key"],
                {
                    "group_id": entry["group_key"],
                    "media_type": current_type,
                    "title": entry.get("group_title"),
                    "year": entry.get("year"),
                    "library_names": set(),
                    "targets": [],
                    "score": 0,
                },
            )
            group["library_names"].add(entry.get("library_name"))
            group["targets"].append(self._target_from_entry(entry))

            score = 1
            if normalized_keyword:
                title_key = self._normalize_key(entry.get("group_title"))
                if title_key.startswith(normalized_keyword):
                    score += 100
                if normalized_keyword in title_key:
                    score += 40
                if normalized_keyword in haystack:
                    score += 10
            group["score"] = max(group["score"], score)

        result_groups: List[Dict[str, Any]] = []
        for group in groups.values():
            targets = group["targets"]
            targets.sort(key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("label", "")))
            result_groups.append(
                {
                    "group_id": group["group_id"],
                    "media_type": group["media_type"],
                    "title": group["title"],
                    "year": group["year"],
                    "library_names": sorted(name for name in group["library_names"] if name),
                    "target_count": len(targets),
                    "targets": targets,
                    "summary": f"{len(targets)} 集" if group["media_type"] == "tv" else f"{len(targets)} 个版本",
                    "score": group["score"],
                }
            )

        result_groups.sort(
            key=lambda item: (
                -item.get("score", 0),
                self._normalize_key(item.get("title")),
                item.get("year", ""),
            )
        )
        return result_groups[:limit]

    def _resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        self._build_index(force=False)
        result: Dict[str, Dict[str, Any]] = {}
        for target_id in target_ids:
            entry = self._entry_map.get(str(target_id))
            if entry:
                result[str(target_id)] = entry
        return result

    @classmethod
    def _build_destination_name(
        cls,
        target_entry: Dict[str, Any],
        subtitle_info: Dict[str, Any],
    ) -> str:
        basename = cls._normalize_text(target_entry.get("basename")) or "subtitle"
        language_suffix = cls._normalize_text(subtitle_info.get("language_suffix")) or "und"
        ext = cls._normalize_text(subtitle_info.get("ext")) or ".srt"
        if not ext.startswith("."):
            ext = f".{ext}"
        return f"{basename}.{language_suffix}{ext.lower()}"

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

            video_path = Path(target_entry["path"])
            if not video_path.exists():
                raise HTTPException(status_code=400, detail=f"目标视频不存在: {video_path}")

            source_path = Path(upload_info["stored_path"])
            if not source_path.exists():
                raise HTTPException(status_code=400, detail=f"上传缓存文件不存在: {upload_info.get('source_name')}")

            item_ext = cls._normalize_text(item.get("ext")) or upload_info.get("ext") or ".srt"
            item_suffix = cls._normalize_text(item.get("language_suffix")) or "und"
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
        index_data = self._load_index()
        return self._ok(
            {
                "enabled": self.get_state(),
                "libraries": self._libraries_summary(),
                "index": {
                    "ready": bool(index_data.get("updated_at")),
                    "updated_at": index_data.get("updated_at", ""),
                    "entry_count": index_data.get("entry_count", 0),
                },
            }
        )

    def api_refresh_index(self) -> Dict[str, Any]:
        index_data = self._build_index(force=True)
        return self._ok(
            {
                "updated_at": index_data.get("updated_at", ""),
                "entry_count": index_data.get("entry_count", 0),
            },
            message="媒体库索引已刷新",
        )

    def api_search(self, request: Request) -> Dict[str, Any]:
        keyword = self._normalize_text(request.query_params.get("keyword"))
        media_type = self._normalize_text(request.query_params.get("media_type")) or "all"
        limit = min(max(self._safe_int(request.query_params.get("limit"), 20), 1), 100)
        groups = self._search_groups(keyword=keyword, media_type=media_type, limit=limit)
        return self._ok(
            {
                "keyword": keyword,
                "media_type": media_type,
                "groups": groups,
            }
        )

    async def api_prepare_upload(self, request: Request) -> Dict[str, Any]:
        form = await request.form()
        target_ids_raw = self._normalize_text(form.get("target_ids"))
        if not target_ids_raw:
            raise HTTPException(status_code=400, detail="请先选择目标电影或剧集")

        try:
            target_ids = json.loads(target_ids_raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"目标参数格式错误: {exc}") from exc
        if not isinstance(target_ids, list) or not target_ids:
            raise HTTPException(status_code=400, detail="请至少选择一个目标视频")

        target_entries = list(self._resolve_targets(target_ids).values())
        if not target_entries:
            raise HTTPException(status_code=400, detail="未找到目标视频，请刷新索引后重试")

        upload_files = [item for item in form.getlist("files") if self._is_upload_file(item)]
        if not upload_files:
            raise HTTPException(status_code=400, detail="请至少上传一个字幕文件或 ZIP")

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
                raise HTTPException(status_code=400, detail=f"没有解析到可用字幕文件，{first_reason}")
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

        session_payload = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_ids": list(target_ids),
            "uploads": prepared_uploads,
        }
        self._write_session(session_id, session_payload)

        resolved_count = len([item for item in preview_items if item.get("target_id")])
        message = f"已解析 {len(preview_items)} 个字幕文件，自动匹配 {resolved_count} 个。"
        if unsupported_files:
            message += f" 已忽略 {len(unsupported_files)} 个不支持的文件。"
        if invalid_files:
            message += f" 有 {len(invalid_files)} 个压缩包解析失败。"

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
        if not session_id or not isinstance(items, list) or not items:
            raise HTTPException(status_code=400, detail="缺少上传会话或匹配结果")

        session_dir, session_payload = self._load_session(session_id)
        upload_map = {
            item["upload_id"]: item
            for item in session_payload.get("uploads", [])
            if item.get("upload_id")
        }
        target_entries = self._resolve_targets(session_payload.get("target_ids", []))
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索并上传")

        operations = self._build_write_operations(items, upload_map, target_entries)
        written_results = []
        for operation in operations:
            destination_path = operation["destination_path"]
            temp_path = destination_path.with_name(f"{destination_path.name}.mp-uploading")
            if temp_path.exists():
                temp_path.unlink()
            shutil.copyfile(operation["source_path"], temp_path)
            temp_path.replace(destination_path)
            written_results.append(
                {
                    "source_name": operation["upload_info"].get("source_name"),
                    "archive_name": operation["upload_info"].get("archive_name"),
                    "target_label": self._target_from_entry(operation["target_entry"]).get("label"),
                    "output_name": operation["destination_name"],
                    "output_path": str(destination_path),
                }
            )

        touched_videos: Dict[str, Path] = {
            str(operation["video_path"]): operation["video_path"]
            for operation in operations
        }
        for video_path in touched_videos.values():
            self._remove_ext_marks(video_path)

        shutil.rmtree(session_dir, ignore_errors=True)

        return self._ok(
            {
                "count": len(written_results),
                "written": written_results,
            },
            message=f"已写入 {len(written_results)} 个字幕文件",
        )
