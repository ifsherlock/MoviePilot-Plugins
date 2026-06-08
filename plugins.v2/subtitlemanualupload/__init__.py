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

from app.chain.media import MediaChain
from app.chain.tmdb import TmdbChain
from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import MediaType


class SubtitleManualUpload(_PluginBase):
    plugin_name = "字幕手传匹配"
    plugin_desc = "手动上传字幕或 ZIP，匹配电影/剧集并按媒体文件名落盘。"
    plugin_icon = "upload.png"
    plugin_version = "0.1.1"
    plugin_author = "jaysh"
    author_url = "https://github.com/jaysh"
    plugin_config_prefix = "subtitlemanualupload_"
    plugin_order = 48
    auth_level = 1

    _enabled = False
    _show_sidebar_nav = True
    _entry_map: Dict[str, Dict[str, Any]] = {}

    _subtitle_exts = {".ass", ".srt", ".ssa", ".sbv", ".sub", ".vtt", ".webvtt"}
    _archive_exts = {".zip"}
    _default_session_hours = 24

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._show_sidebar_nav = bool(config.get("show_sidebar_nav", True))
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
                "summary": "兼容旧版刷新索引入口",
            },
            {
                "path": "/search",
                "endpoint": self.api_search,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "使用 MoviePilot 搜索媒体候选",
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
                                            "text": "先用 MoviePilot 搜索媒体并展示封面，再读取已入库文件；剧集可选择季度后上传字幕或 ZIP。",
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
    def _media_type_enum(cls, value: Any) -> Optional[MediaType]:
        media_type = cls._media_type_text(value)
        if media_type == "movie":
            return MediaType.MOVIE
        if media_type == "tv":
            return MediaType.TV
        return None

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

    @staticmethod
    def _model_dump(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return {}

    def _media_from_info(self, mediainfo: Any) -> Dict[str, Any]:
        data = self._model_dump(mediainfo)
        media_type = self._media_type_text(data.get("type") or getattr(mediainfo, "type", None))
        title = self._normalize_text(data.get("title") or getattr(mediainfo, "title", ""))
        year = self._normalize_text(data.get("year") or getattr(mediainfo, "year", ""))
        tmdb_id = data.get("tmdb_id") or getattr(mediainfo, "tmdb_id", None)
        douban_id = self._normalize_text(data.get("douban_id") or getattr(mediainfo, "douban_id", ""))
        poster_path = data.get("poster_path") or getattr(mediainfo, "poster_path", "")
        media_id = self._normalize_text(data.get("media_id") or getattr(mediainfo, "media_id", ""))
        if not media_id and tmdb_id:
            media_id = f"tmdb:{tmdb_id}"
        return {
            "id": self._hash_text(f"{media_type}|{tmdb_id}|{douban_id}|{title}|{year}"),
            "media_id": media_id,
            "media_type": media_type,
            "title": title,
            "en_title": self._normalize_text(data.get("en_title") or getattr(mediainfo, "en_title", "")),
            "year": year,
            "tmdb_id": tmdb_id,
            "douban_id": douban_id,
            "poster_path": poster_path,
            "poster_url": self._poster_url(poster_path),
            "backdrop_url": self._poster_url(data.get("backdrop_path") or getattr(mediainfo, "backdrop_path", ""), "w780"),
            "overview": self._normalize_text(data.get("overview") or getattr(mediainfo, "overview", "")),
            "vote_average": data.get("vote_average") or getattr(mediainfo, "vote_average", None) or 0,
        }

    def _resolve_mediainfo(
        self,
        media_type: str,
        tmdb_id: Any = None,
        douban_id: Any = None,
        title: str = "",
        year: str = "",
    ) -> Any:
        mtype = self._media_type_enum(media_type)
        if not mtype:
            raise HTTPException(status_code=400, detail="媒体类型必须是 movie 或 tv")

        chain = MediaChain()
        clean_tmdb_id = self._safe_int(tmdb_id, 0)
        clean_douban_id = self._normalize_text(douban_id)
        if clean_tmdb_id:
            mediainfo = chain.recognize_media(mtype=mtype, tmdbid=clean_tmdb_id, cache=True)
            if mediainfo:
                return mediainfo
        if clean_douban_id:
            mediainfo = chain.recognize_media(mtype=mtype, doubanid=clean_douban_id, cache=True)
            if mediainfo:
                return mediainfo

        clean_title = self._normalize_text(title)
        if clean_title:
            try:
                _, medias = chain.search(title=clean_title)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"MoviePilot 搜索媒体失败: {exc}") from exc
            for media in medias or []:
                if self._media_type_text(getattr(media, "type", "")) != self._media_type_text(media_type):
                    continue
                media_year = self._normalize_text(getattr(media, "year", ""))
                if year and media_year and media_year != self._normalize_text(year):
                    continue
                return media

        raise HTTPException(status_code=404, detail="未能识别选中的媒体，请重新搜索后选择")

    async def _search_media_candidates(self, keyword: str, media_type: str, limit: int) -> List[Dict[str, Any]]:
        clean_keyword = self._normalize_text(keyword)
        if not clean_keyword:
            return []

        try:
            _, medias = await MediaChain().async_search(title=clean_keyword)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"MoviePilot 搜索媒体失败: {exc}") from exc

        result: List[Dict[str, Any]] = []
        expected_type = self._media_type_text(media_type)
        for media in medias or []:
            item = self._media_from_info(media)
            if expected_type and item.get("media_type") != expected_type:
                continue
            if not item.get("title") or not item.get("media_type"):
                continue
            result.append(item)
            if len(result) >= limit:
                break
        return result

    def _build_entry_from_fileitem(self, fileitem: Any, mediainfo: Any) -> Optional[Dict[str, Any]]:
        path = self._normalize_text(getattr(fileitem, "path", None))
        if not path:
            return None

        file_path = Path(path)
        basename = self._normalize_text(getattr(fileitem, "basename", None)) or file_path.stem
        filename = self._normalize_text(getattr(fileitem, "name", None)) or file_path.name
        storage = self._normalize_text(getattr(fileitem, "storage", None)) or "local"
        media_type = self._media_type_text(getattr(mediainfo, "type", None))
        title = self._normalize_text(getattr(mediainfo, "title", ""))
        year = self._normalize_text(getattr(mediainfo, "year", ""))

        season = 0
        episode = 0
        try:
            meta = MetaInfoPath(file_path)
            season = self._safe_int(getattr(meta, "begin_season", None) or getattr(meta, "season", None), 0)
            episode = self._safe_int(getattr(meta, "begin_episode", None) or getattr(meta, "episode", None), 0)
        except Exception:
            pass

        episode_hint = self._extract_episode_hint(filename or basename)
        if episode_hint:
            season = season or episode_hint.get("season", 0)
            episode = episode or episode_hint.get("episode", 0)
        if media_type == "tv" and episode and not season:
            season = 1

        entry_id = self._hash_text(f"{storage}|{path}")
        if media_type == "tv":
            prefix = f"S{season:02d}E{episode:02d}" if season and episode else basename
            target_label = f"{prefix} · {filename}"
        else:
            target_label = filename or (f"{title} ({year})" if year else title)

        return {
            "id": entry_id,
            "media_type": media_type,
            "title": title,
            "year": year,
            "season": season,
            "episode": episode,
            "path": path,
            "basename": basename,
            "filename": filename,
            "storage": storage,
            "library_name": "MoviePilot 媒体库",
            "relative_path": path.replace("\\", "/"),
            "target_label": target_label,
            "writable": storage == "local",
        }

    def _season_catalog(self, tmdb_id: Any) -> Dict[int, Dict[str, Any]]:
        clean_tmdb_id = self._safe_int(tmdb_id, 0)
        if not clean_tmdb_id:
            return {}
        try:
            seasons = TmdbChain().tmdb_seasons(tmdbid=clean_tmdb_id) or []
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] 获取 TMDB 季信息失败 %s: %s", clean_tmdb_id, exc)
            return {}

        result: Dict[int, Dict[str, Any]] = {}
        for season in seasons:
            season_number = self._safe_int(getattr(season, "season_number", None), -1)
            if season_number < 0:
                continue
            poster_path = getattr(season, "poster_path", "")
            result[season_number] = {
                "season": season_number,
                "name": self._normalize_text(getattr(season, "name", "")) or f"第 {season_number} 季",
                "episode_count": self._safe_int(getattr(season, "episode_count", None), 0),
                "poster_url": self._poster_url(poster_path),
                "local_count": 0,
                "episodes": [],
                "available": False,
            }
        return result

    def _merge_seasons(self, entries: List[Dict[str, Any]], tmdb_id: Any) -> List[Dict[str, Any]]:
        seasons = self._season_catalog(tmdb_id)
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
        mediainfo = self._resolve_mediainfo(
            media_type=media_type,
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            title=title,
            year=year,
        )
        media = self._media_from_info(mediainfo)

        try:
            fileitems = MediaChain().media_files(mediainfo) or []
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取 MoviePilot 媒体库文件失败: {exc}") from exc

        entries = []
        for fileitem in fileitems:
            entry = self._build_entry_from_fileitem(fileitem, mediainfo)
            if entry:
                entries.append(entry)

        entries.sort(key=lambda item: (item.get("season", 0), item.get("episode", 0), item.get("filename", "")))
        seasons = self._merge_seasons(entries, media.get("tmdb_id")) if media.get("media_type") == "tv" else []

        selected_season = self._safe_int(season, 0)
        if media.get("media_type") == "tv" and not selected_season:
            available_seasons = [item["season"] for item in seasons if item.get("available")]
            selected_season = available_seasons[0] if available_seasons else 0

        visible_entries = entries
        if media.get("media_type") == "tv" and selected_season:
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
        }

    def _remember_targets(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            target_id = self._normalize_text(entry.get("id"))
            if target_id:
                self._entry_map[target_id] = entry

    def _resolve_targets(self, target_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
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
        return self._ok(
            {
                "enabled": self.get_state(),
                "source": "MoviePilot MediaChain",
                "index": {"ready": True, "updated_at": "", "entry_count": 0},
            }
        )

    def api_refresh_index(self) -> Dict[str, Any]:
        return self._ok(
            {
                "realtime": True,
            },
            message="已改用 MoviePilot 实时媒体搜索，无需刷新索引",
        )

    async def api_search(self, request: Request) -> Dict[str, Any]:
        keyword = self._normalize_text(request.query_params.get("keyword"))
        media_type = self._normalize_text(request.query_params.get("media_type")) or "all"
        limit = min(max(self._safe_int(request.query_params.get("limit"), 20), 1), 100)
        medias = await self._search_media_candidates(keyword=keyword, media_type=media_type, limit=limit)
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
        return self._ok(result)

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
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并选择季度/文件")

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
        target_entries = {
            item["id"]: item
            for item in session_payload.get("targets", [])
            if item.get("id")
        }
        if not target_entries:
            raise HTTPException(status_code=400, detail="目标视频已失效，请重新搜索媒体并上传")

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
