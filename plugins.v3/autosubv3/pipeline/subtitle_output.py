import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Tuple

import iso639

from ..core.models import OverwritePolicy, ResolvedSource


class SubtitleOutputService:
    def __init__(
        self,
        get_data_path: Callable[[], Path],
        normalize_text: Callable[[Any], str],
        normalize_overwrite_policy: Callable[[Any], str],
        get_video_prefer_subtitle: Callable[..., tuple],
        translate_zh: Callable[[], bool],
        translate_preference: Callable[[], str],
        ffmpeg_factory: Callable[[], Any],
    ):
        self._get_data_path = get_data_path
        self._normalize_text = normalize_text
        self._normalize_overwrite_policy = normalize_overwrite_policy
        self._get_video_prefer_subtitle = get_video_prefer_subtitle
        self._translate_zh = translate_zh
        self._translate_preference = translate_preference
        self._ffmpeg_factory = ffmpeg_factory

    @staticmethod
    def subtitle_lang_suffix(source_lang: Any, output_mode: str = "bilingual") -> str:
        lang = str(source_lang or "").strip().lower().replace("_", "-")
        primary = lang.split("-")[0]
        aliases = {
            "zh": "chi",
            "zho": "chi",
            "chi": "chi",
            "cmn": "chi",
            "cn": "chi",
            "ja": "jp",
            "jpn": "jp",
            "jp": "jp",
            "en": "eng",
            "eng": "eng",
            "ko": "kr",
            "kor": "kr",
            "kr": "kr",
        }
        source_suffix = aliases.get(primary) or aliases.get(lang) or primary[:3] or "und"
        if output_mode == "chinese_only" or source_suffix in {"chi", "und"}:
            return "chi"
        return f"chi&{source_suffix}"

    @classmethod
    def translated_subtitle_path(cls, file_path: str, source_lang: Any = "", output_mode: str = "bilingual") -> str:
        return f"{file_path}.{cls.subtitle_lang_suffix(source_lang, output_mode)}.ai.srt"

    @staticmethod
    def variant_for_source(resolved_source: Any) -> str:
        return {
            ResolvedSource.ASR.value: "aiasr",
            ResolvedSource.EMBEDDED.value: "aiembedded",
            ResolvedSource.MATCHED_EXTERNAL.value: "aimatch",
            ResolvedSource.LOCAL_EXTERNAL.value: "ailocal",
        }.get(str(resolved_source or ""), "ai")

    def translated_subtitle_path_with_variant(
        self,
        file_path: str,
        source_lang: Any = "",
        output_mode: str = "bilingual",
        output_variant: str = "ai",
    ) -> str:
        variant = self._normalize_text(output_variant) or "ai"
        return f"{file_path}.{self.subtitle_lang_suffix(source_lang, output_mode)}.{variant}.srt"

    def prepare_output_path(
        self,
        file_path: str,
        source_lang: Any,
        output_mode: str,
        resolved_source: str,
        overwrite_policy: str,
        inherited_variant: str = "",
        inherited_output_path: str = "",
    ) -> Tuple[str, str]:
        policy = self._normalize_overwrite_policy(overwrite_policy)
        variant = self._normalize_text(inherited_variant)
        inherited_path = self._normalize_text(inherited_output_path)
        if inherited_path and policy == OverwritePolicy.BACKUP_REPLACE.value:
            return inherited_path, variant or "ai"
        if not variant and policy == OverwritePolicy.NEW_VARIANT.value:
            variant = self.variant_for_source(resolved_source)
        if not variant:
            variant = "ai"
        return self.translated_subtitle_path_with_variant(file_path, source_lang, output_mode, variant), variant

    @staticmethod
    def backup_existing_file(path: str, suffix: str = ".mp-ai-bk") -> str:
        if not path or not os.path.exists(path):
            return ""
        backup_path = f"{path}{suffix}"
        if os.path.exists(backup_path):
            return backup_path
        shutil.copy2(path, backup_path)
        return backup_path

    def copy_source_asset(self, task_id: str, source_path: str, source_name: str = "") -> str:
        source = self._normalize_text(source_path)
        if not source:
            return ""
        src = Path(source)
        if not src.exists() or src.suffix.lower() != ".srt":
            raise ValueError("指定字幕文件不存在或不是 SRT")
        safe_name = self._normalize_text(source_name) or src.name
        safe_name = re.sub(r"[\\/:*?\"<>|]+", "_", safe_name)
        asset_dir = Path(self._get_data_path()) / "task_assets" / task_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        dest = asset_dir / safe_name
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        return str(dest)

    @staticmethod
    def external_subtitle_exists(video_file, prefer_langs=None, only_srt=False, strict=True):
        video_dir, video_name = os.path.split(video_file)
        video_name, video_ext = os.path.splitext(video_name)

        if prefer_langs and type(prefer_langs) == str:
            prefer_langs = [prefer_langs]

        metadata_flags = ["default", "forced", "foreign", "sdh", "cc", "hi", "机翻", "ai"]
        language_aliases = {
            "chs": "zh",
            "zhs": "zh",
            "zh-cn": "zh",
            "zh-hans": "zh",
            "chi": "zh",
            "zho": "zh",
            "cn": "zh",
            "eng": "en",
            "jp": "ja",
            "jpn": "ja",
            "kr": "ko",
            "kor": "ko",
        }
        if only_srt:
            subtitle_extensions = [".srt"]
        else:
            subtitle_extensions = [".srt", ".sub", ".ass", ".ssa", ".vtt"]

        def parse_props(props):
            parts = props.split(".")
            if len(parts) < 1:
                return None, []

            cur_subtitle_lang = None
            cur_metadata = []
            for i in range(len(parts) - 1, -1, -1):
                part = parts[i].strip()
                lower_part = part.lower()
                if lower_part in metadata_flags:
                    cur_metadata.append(lower_part)
                elif cur_subtitle_lang is None:
                    composite_langs = [
                        language_aliases.get(item.strip().lower()) or item.strip().lower()
                        for item in re.split(r"[&+]", lower_part)
                        if item.strip()
                    ]
                    if any(item == "zh" for item in composite_langs):
                        cur_subtitle_lang = "zh"
                        continue
                    normalized = language_aliases.get(lower_part)
                    if normalized:
                        cur_subtitle_lang = normalized
                        continue
                    try:
                        iso639.to_iso639_1(part)
                    except Exception:
                        continue
                    else:
                        cur_subtitle_lang = iso639.to_iso639_1(part)

            return cur_subtitle_lang, cur_metadata

        second_lang = None
        second_file = None
        for file in os.listdir(video_dir):
            if not file.startswith(video_name):
                continue

            _, ext = os.path.splitext(file)
            if ext.lower() not in subtitle_extensions:
                continue

            props_str = file[len(video_name) + 1: -len(ext)] if file.startswith(video_name + ".") else ""
            subtitle_lang, metadata = parse_props(props_str)

            if not subtitle_lang:
                continue

            if prefer_langs:
                if subtitle_lang in prefer_langs:
                    return True, subtitle_lang, file
                second_lang = subtitle_lang
                second_file = file
            else:
                return True, subtitle_lang, file
        if not strict and second_lang:
            return True, second_lang, second_file
        return False, None, None

    def target_subtitle_exists(self, video_file) -> bool:
        if self._translate_zh():
            prefer_langs = ['zh', 'chi', 'zh-CN', 'chs', 'zhs', 'zh-Hans', 'zhong', 'simp', 'cn']
            strict = True
        else:
            if self._translate_preference() == "english_first":
                prefer_langs = ['en', 'eng']
                strict = False
            elif self._translate_preference() == "english_only":
                prefer_langs = ['en', 'eng']
                strict = True
            else:
                prefer_langs = None
                strict = False

        exist, lang, _ = self.external_subtitle_exists(video_file, prefer_langs, strict=strict)
        if exist:
            return True

        video_meta = self._ffmpeg_factory().get_video_metadata(video_file)
        if not video_meta:
            return False
        ret, subtitle_index, subtitle_lang = self._get_video_prefer_subtitle(
            video_meta,
            prefer_lang=prefer_langs,
            only_srt=False,
        )
        if ret and subtitle_lang in prefer_langs:
            return True

        return False
