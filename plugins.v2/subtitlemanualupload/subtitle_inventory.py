from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .target_normalizers import NormalizeText, SafeInt, is_stream_path

DetectLanguageProfile = Callable[[str, bytes], Dict[str, Any]]
NormalizeLanguageSuffix = Callable[[Any], str]
LanguageSuffixCheck = Callable[[Any], bool]
SubtitleBackupPath = Callable[[Path], Path]


class SubtitleInventory:
    def __init__(
        self,
        *,
        subtitle_exts: Iterable[str],
        stream_exts: Iterable[str],
        embedded_text_codecs: Iterable[str],
        embedded_image_codecs: Iterable[str],
        embedded_probe_cache: "OrderedDict[str, List[Dict[str, Any]]]",
        embedded_probe_cache_max_size: int,
        trust_transfer_history_paths: bool,
        normalize_text: NormalizeText,
        normalize_language_suffix: NormalizeLanguageSuffix,
        detect_language_profile: DetectLanguageProfile,
        is_chinese_language_suffix: LanguageSuffixCheck,
        safe_int: SafeInt,
        subtitle_backup_path: SubtitleBackupPath,
        subprocess_module: Any,
        logger_warning: Callable[..., None],
    ) -> None:
        self._subtitle_exts = set(subtitle_exts)
        self._stream_exts = set(stream_exts)
        self._embedded_text_codecs = set(embedded_text_codecs)
        self._embedded_image_codecs = set(embedded_image_codecs)
        self._embedded_probe_cache = embedded_probe_cache
        self._embedded_probe_cache_max_size = embedded_probe_cache_max_size
        self._trust_transfer_history_paths = trust_transfer_history_paths
        self._normalize_text = normalize_text
        self._normalize_language_suffix = normalize_language_suffix
        self._detect_language_profile = detect_language_profile
        self._language_suffix_is_chinese = is_chinese_language_suffix
        self._safe_int = safe_int
        self._subtitle_backup_path = subtitle_backup_path
        self._subprocess = subprocess_module
        self._logger_warning = logger_warning

    def subtitle_files_for_target(self, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        storage = self._normalize_text(target_entry.get("storage")) or "local"
        if storage != "local":
            return []
        if self._trust_transfer_history_paths:
            return []

        video_path_raw = self._normalize_text(target_entry.get("path"))
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
                if sub_file.suffix.lower() not in self._subtitle_exts:
                    continue
                if sub_file.stem != stem and not sub_file.name.startswith(f"{stem}."):
                    continue
                try:
                    raw_bytes = sub_file.read_bytes()
                except Exception:
                    raw_bytes = b""
                language_profile = self._detect_language_profile(sub_file.name, raw_bytes)
                backup_path = self._subtitle_backup_path(sub_file)
                subtitles.append(
                    {
                        "name": sub_file.name,
                        "path": str(sub_file),
                        "relative_path": str(sub_file).replace("\\", "/"),
                        "ext": sub_file.suffix.lower(),
                        "language_suffix": language_profile.get("suffix", ""),
                        "language_category": language_profile.get("category", ""),
                        "backup_path": str(backup_path) if backup_path.exists() else "",
                        "backup_available": backup_path.exists(),
                        "size": sub_file.stat().st_size,
                        "modified_at": datetime.fromtimestamp(sub_file.stat().st_mtime).isoformat(timespec="seconds"),
                    }
                )
        except Exception as exc:
            self._logger_warning(
                "[SubtitleManualUpload] 读取外挂字幕失败 video=%s error=%s",
                video_path.name,
                exc,
            )
        subtitles.sort(key=lambda item: item.get("name", ""))
        return subtitles

    def embedded_subtitle_tracks_for_target(self, target_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        storage = self._normalize_text(target_entry.get("storage")) or "local"
        path_text = self._normalize_text(target_entry.get("path"))
        if storage != "local" or not path_text or self._is_stream_path(path_text):
            return []
        if self._trust_transfer_history_paths:
            return []

        video_path = Path(path_text)
        if not video_path.is_file():
            return []

        cache_key = self.embedded_subtitle_probe_cache_key(video_path)
        if cache_key:
            cached = self._embedded_probe_cache.get(cache_key)
            if cached is not None:
                self._embedded_probe_cache.move_to_end(cache_key)
                return [dict(item) for item in cached]

        try:
            completed = self._subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "s",
                    "-show_entries",
                    "stream=index,codec_name,disposition:stream_tags=language,title",
                    "-of",
                    "json",
                    str(video_path),
                ],
                stdout=self._subprocess.PIPE,
                stderr=self._subprocess.PIPE,
                text=True,
                check=True,
                timeout=8,
            )
            payload = json.loads(completed.stdout or "{}")
        except FileNotFoundError:
            self._logger_warning("[SubtitleManualUpload] ffprobe 不可用，无法检查内嵌字幕 video=%s", video_path.name)
            return []
        except self._subprocess.TimeoutExpired:
            self._logger_warning("[SubtitleManualUpload] 检查内嵌字幕超时 video=%s", video_path.name)
            return []
        except Exception as exc:
            self._logger_warning("[SubtitleManualUpload] 检查内嵌字幕失败 video=%s error=%s", video_path.name, exc)
            return []

        tracks: List[Dict[str, Any]] = []
        for stream in payload.get("streams") or []:
            if not isinstance(stream, dict):
                continue
            disposition = stream.get("disposition") if isinstance(stream.get("disposition"), dict) else {}
            if disposition.get("forced"):
                continue
            tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
            codec = self._normalize_text(stream.get("codec_name")).lower()
            language = self._normalize_text(tags.get("language"))
            title = self._normalize_text(tags.get("title"))
            usable = self.embedded_subtitle_track_is_usable(codec, title, disposition)
            if not usable:
                suffix = "und"
            else:
                suffix = self.embedded_subtitle_language_suffix(language, title)
                if suffix == "und":
                    sampled_suffix = self.embedded_subtitle_sample_language_suffix(
                        video_path,
                        stream.get("index"),
                        codec,
                    )
                    if self._language_suffix_is_chinese(sampled_suffix):
                        suffix = sampled_suffix
            is_chinese = usable and self._language_suffix_is_chinese(suffix)
            tracks.append(
                {
                    "index": stream.get("index"),
                    "codec": codec,
                    "language": language,
                    "title": title,
                    "language_suffix": suffix,
                    "is_chinese": is_chinese,
                }
            )
        if cache_key:
            self._embedded_probe_cache[cache_key] = [dict(item) for item in tracks]
            self._embedded_probe_cache.move_to_end(cache_key)
            while len(self._embedded_probe_cache) > self._embedded_probe_cache_max_size:
                self._embedded_probe_cache.popitem(last=False)
        return tracks

    def embedded_subtitle_language_suffix(self, language: Any, title: Any = "") -> str:
        language_text = self._normalize_text(language).strip().lower()
        title_text = self._normalize_text(title).strip().lower()
        normalized_language = self._normalize_language_suffix(language_text)
        if normalized_language.startswith("zh-hans"):
            return "chi"
        if normalized_language.startswith("zh-hant"):
            return "cht"
        if re.search(r"繁中|繁体|繁體|traditional|zh[-_ ]?hant|zh[-_ ]?tw", language_text):
            return "cht"
        if re.search(r"简中|简体|簡體|simplified|zh[-_ ]?hans|zh[-_ ]?cn", language_text):
            return "chi"
        if re.search(r"chinese|mandarin|cantonese|中文|汉语|漢語|普通话|普通話|粤语|粵語", language_text):
            return "chi"
        if normalized_language != "und":
            return normalized_language
        if not title_text:
            return "und"
        if re.search(r"繁中|繁体|繁體|traditional|zh[-_ ]?hant|zh[-_ ]?tw", title_text):
            return "cht"
        if re.search(r"简中|简体|簡體|simplified|zh[-_ ]?hans|zh[-_ ]?cn", title_text):
            return "chi"
        if re.search(r"中文字幕|中字|中文|汉语|漢語|普通话|普通話", title_text):
            return "chi"
        return "und"

    def embedded_subtitle_probe_cache_key(self, video_path: Path) -> str:
        try:
            stat = video_path.stat()
        except Exception:
            return ""
        return f"{video_path}|{stat.st_size}|{stat.st_mtime_ns}"

    def embedded_subtitle_track_is_usable(
        self,
        codec: Any,
        title: Any = "",
        disposition: Optional[Dict[str, Any]] = None,
    ) -> bool:
        codec_text = self._normalize_text(codec).lower()
        if codec_text in self._embedded_image_codecs:
            return False
        disposition = disposition if isinstance(disposition, dict) else {}
        if disposition.get("forced") or disposition.get("comment"):
            return False
        title_text = self._normalize_text(title).strip().lower()
        if not title_text:
            return True
        return not bool(
            re.search(
                r"forced|signs?|songs?|commentary|comment|sdh|closed captions?|"
                r"特效|歌词|注释|旁白|强制|強制",
                title_text,
            )
        )

    def embedded_subtitle_sample_language_suffix(self, video_path: Path, stream_index: Any, codec_name: Any) -> str:
        codec = self._normalize_text(codec_name).lower()
        if codec not in self._embedded_text_codecs:
            return "und"
        index = self._safe_int(stream_index, -1)
        if index < 0:
            return "und"
        try:
            completed = self._subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(video_path),
                    "-map",
                    f"0:{index}",
                    "-f",
                    "srt",
                    "-",
                ],
                stdout=self._subprocess.PIPE,
                stderr=self._subprocess.PIPE,
                check=True,
                timeout=8,
            )
        except Exception:
            return "und"
        if not completed.stdout:
            return "und"
        return self._detect_language_profile(f"embedded.{codec}.srt", completed.stdout[:20000]).get("suffix", "und")

    def remove_ext_marks(self, video_path: Path) -> None:
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

    def _is_stream_path(self, path: Any) -> bool:
        return is_stream_path(path, normalize_text=self._normalize_text, stream_exts=self._stream_exts)



__all__ = [name for name in globals() if not name.startswith("__")]
