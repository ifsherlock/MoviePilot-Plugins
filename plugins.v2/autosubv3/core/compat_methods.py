import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import iso639
import srt
from app.core.config import settings
from app.core.context import MediaInfo
from app.log import logger
from app.utils.system import SystemUtils

from .config_schema import normalize_generation_mode, normalize_overwrite_policy, normalize_source_policy, normalize_text, normalize_trigger
from .models import (
    GenerationMode,
    OverwritePolicy,
    ResolvedSource,
    SourcePolicy,
    TaskItem,
    TaskSource,
    TaskStatus,
    TriggerType,
    UserInterruptException,
)
from ..ffmpeg import Ffmpeg
from ..monitoring.monitor_service import MonitorService
from ..pipeline.asr_service import AsrService
from ..pipeline.source_resolver import SourceResolver
from ..pipeline.subtitle_output import SubtitleOutputService
from ..pipeline.translation_service import TranslationService
from ..storage.task_store import TaskStore


class AutoSubv3CompatMixin:
    def load_tasks(self) -> Dict[str, TaskItem]:
        return self._get_task_store().load_tasks()

    @staticmethod
    def _serialize_task(task: TaskItem) -> dict:
        return TaskStore.serialize_task(task)

    def save_tasks(self):
        self._get_task_store().save_tasks(self._tasks)

    @staticmethod
    def _ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
        return {"success": True, "message": message, "data": data}

    def _set_subtitle_output_mode(self, value: str):
        self._subtitle_output_mode = value

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return normalize_text(value)

    @staticmethod
    def _enum_value(enum_cls: Any, value: Any, default: str) -> str:
        text = str(value or "").strip()
        try:
            return enum_cls(text).value
        except Exception:
            return default

    @classmethod
    def _normalize_generation_mode(cls, value: Any) -> str:
        return normalize_generation_mode(value)

    @classmethod
    def _normalize_trigger(cls, value: Any) -> str:
        return normalize_trigger(value)

    @classmethod
    def _normalize_source_policy(cls, value: Any, default: str = SourcePolicy.AUTO.value) -> str:
        return normalize_source_policy(value, default)

    @classmethod
    def _normalize_overwrite_policy(cls, value: Any, default: str = OverwritePolicy.SKIP.value) -> str:
        return normalize_overwrite_policy(value, default)

    @staticmethod
    def _source_label(source: TaskSource) -> str:
        return {
            TaskSource.MANUAL: "手动添加",
            TaskSource.EVENT: "入库触发",
            TaskSource.SUBTITLE_MANUAL_UPLOAD: "字幕匹配联动",
        }.get(source, getattr(source, "value", str(source)))

    @staticmethod
    def _source_policy_label(source_policy: Any) -> str:
        return {
            SourcePolicy.AUTO.value: "自动选择",
            SourcePolicy.MATCHED_EXTERNAL.value: "字幕匹配外挂",
            SourcePolicy.LOCAL_EXTERNAL.value: "本地外挂",
            SourcePolicy.EMBEDDED.value: "视频内嵌字幕",
            SourcePolicy.ASR.value: "音轨 ASR",
            SourcePolicy.REUSE.value: "沿用原任务",
        }.get(str(source_policy or ""), str(source_policy or ""))

    @staticmethod
    def _resolved_source_label(resolved_source: Any) -> str:
        return {
            ResolvedSource.AUTO.value: "自动选择",
            ResolvedSource.MATCHED_EXTERNAL.value: "字幕匹配外挂",
            ResolvedSource.LOCAL_EXTERNAL.value: "本地外挂",
            ResolvedSource.EMBEDDED.value: "视频内嵌字幕",
            ResolvedSource.ASR.value: "音轨 ASR",
        }.get(str(resolved_source or ""), str(resolved_source or ""))

    @staticmethod
    def _generation_mode_label(value: Any) -> str:
        return {
            GenerationMode.FALLBACK.value: "独立入库监控关闭",
            GenerationMode.MONITOR.value: "独立入库监控开启",
            GenerationMode.MIXED.value: "独立入库监控开启",
        }.get(str(value or ""), str(value or ""))

    @staticmethod
    def _status_label(status: TaskStatus) -> str:
        return {
            TaskStatus.PENDING: "等待中",
            TaskStatus.IN_PROGRESS: "处理中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.IGNORED: "已忽略",
            TaskStatus.NO_AUDIO: "无声音跳过",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "已取消",
        }.get(status, getattr(status, "value", str(status)))

    @staticmethod
    def _status_message(status: TaskStatus) -> str:
        return {
            TaskStatus.PENDING: "任务已进入等待队列",
            TaskStatus.IN_PROGRESS: "正在生成字幕",
            TaskStatus.COMPLETED: "字幕生成完成",
            TaskStatus.IGNORED: "已按插件规则跳过，通常是字幕已存在或文件不满足处理条件",
            TaskStatus.NO_AUDIO: "视频未检测到有效音轨，已跳过",
            TaskStatus.FAILED: "字幕生成失败，请查看 AI字幕生成(联动版) 日志",
            TaskStatus.CANCELLED: "用户已取消",
        }.get(status, "")

    @staticmethod
    def _source_policy_for_resolved_source(resolved_source: Any) -> str:
        return {
            ResolvedSource.ASR.value: SourcePolicy.ASR.value,
            ResolvedSource.EMBEDDED.value: SourcePolicy.EMBEDDED.value,
            ResolvedSource.LOCAL_EXTERNAL.value: SourcePolicy.LOCAL_EXTERNAL.value,
            ResolvedSource.MATCHED_EXTERNAL.value: SourcePolicy.MATCHED_EXTERNAL.value,
        }.get(str(resolved_source or ""), "")

    def _queue_positions(self) -> Dict[str, int]:
        return self._get_queue_worker().positions()

    def _task_counts(self) -> Dict[str, int]:
        return self._get_task_service().task_counts()

    def _task_to_api(self, task: TaskItem, queue_positions: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        return self._get_task_service().task_to_api(task, queue_positions)

    def _status_payload(self) -> Dict[str, Any]:
        return self._get_task_service().status_payload()

    def api_status(self) -> Dict[str, Any]:
        return self._get_task_api().api_status()

    def submit_tasks(
        self,
        paths: List[str],
        source: str = TaskSource.MANUAL.value,
        subtitle_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
    ) -> Dict[str, Any]:
        return self._get_task_service().submit_tasks(
            paths,
            source=source,
            subtitle_overrides=subtitle_overrides,
            trigger=trigger,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
        )

    async def api_submit(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_submit(request)

    def cancel_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._get_task_service().cancel_tasks(task_ids=task_ids, paths=paths)

    async def api_cancel(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_cancel(request)

    def delete_tasks(self, task_ids: Optional[List[str]] = None, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        return self._get_task_service().delete_tasks(task_ids=task_ids, paths=paths)

    async def api_delete(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_delete(request)

    def restart_tasks(
        self,
        task_ids: Optional[List[str]] = None,
        source_policy: str = SourcePolicy.REUSE.value,
        overwrite_policy: str = OverwritePolicy.BACKUP_REPLACE.value,
    ) -> Dict[str, Any]:
        return self._get_task_service().restart_tasks(
            task_ids=task_ids,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
        )

    async def api_restart(self, request) -> Dict[str, Any]:
        return await self._get_task_api().api_restart(request)

    def tasks_payload(self, paths: Optional[List[str]] = None, limit: int = 300) -> Dict[str, Any]:
        return self._get_task_service().tasks_payload(paths=paths, limit=limit)

    def api_tasks(self, request) -> Dict[str, Any]:
        return self._get_task_api().api_tasks(request)

    def load_skipped_videos(self) -> Dict[str, dict]:
        """加载无声音跳过的视频记录"""
        return self._get_task_store().load_skipped_videos()

    def save_skipped_videos(self, skipped: Dict[str, dict]):
        """保存无声音跳过的视频记录"""
        self._get_task_store().save_skipped_videos(skipped)

    def add_skipped_video(self, video_file: str):
        """添加无声音跳过的视频记录"""
        self._get_task_store().add_skipped_video(video_file)

    def is_video_skipped(self, video_file: str) -> bool:
        """检查视频是否因无声音已被跳过"""
        return self._get_task_store().is_video_skipped(video_file)

    @staticmethod
    def _AutoSubv3__is_chinese_lang(lang: str) -> bool:
        if not lang:
            return False
        return lang.lower() in ('zh', 'chi', 'chs', 'cht', 'zh-cn', 'zh-tw', 'zh-hk', 'chinese')

    @staticmethod
    def _AutoSubv3__subtitle_content_looks_chinese(subs: List[srt.Subtitle]) -> bool:
        text = "\n".join(str(getattr(item, "content", "") or "") for item in subs[:80])
        if not text.strip():
            return False
        chinese_chars = len(re.findall(r"[\u3400-\u9fff]", text))
        latin_chars = len(re.findall(r"[A-Za-z]", text))
        return chinese_chars >= 8 and chinese_chars >= latin_chars

    def load_skip_chinese_videos(self):
        return self._get_task_store().load_skip_chinese_videos()

    def save_skip_chinese_videos(self, skipped):
        self._get_task_store().save_skip_chinese_videos(skipped)

    def add_skip_chinese_video(self, video_file: str):
        self._get_task_store().add_skip_chinese_video(video_file)

    def is_video_skip_chinese(self, video_file: str) -> bool:
        return self._get_task_store().is_video_skip_chinese(video_file)

    def add_task(
        self,
        video_file: str,
        source: TaskSource,
        force_generate: bool = False,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        trigger: str = TriggerType.MANUAL.value,
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
        rerun_of: str = "",
        source_name: str = "",
        output_variant: str = "",
        reuse_output_path: str = "",
        reuse_source_lang: str = "",
    ):
        return self._get_task_service().add_task(
            video_file,
            source,
            force_generate=force_generate,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            trigger=trigger,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
            rerun_of=rerun_of,
            source_name=source_name,
            output_variant=output_variant,
            reuse_output_path=reuse_output_path,
            reuse_source_lang=reuse_source_lang,
        )

    def clear_tasks(self):
        self._tasks = {task_id: task for task_id, task in self._tasks.items() if task.status in [
            TaskStatus.PENDING, TaskStatus.IN_PROGRESS
        ]}
        self.save_tasks()
        self.save_skipped_videos({})
        logger.info("插件历史任务已清除")

    def _AutoSubv3__is_duplicate_task(self, video_file: str) -> bool:
        return self._get_task_service().is_duplicate_task(video_file)

    def _consume_tasks(self):
        self._get_queue_worker().consume()

    def _add_monitor_task(self, file_path: str):
        return self._get_monitor_service().add_monitor_task(file_path)

    def _run_at_once(self, path_list: List[str]):
        return self._get_monitor_service().run_at_once(path_list)

    def _AutoSubv3__check_asr(self):
        return self._get_monitor_service().check_asr()

    @staticmethod
    def _is_subtitle_manual_upload_source(source: Any) -> bool:
        if isinstance(source, TaskSource):
            return source == TaskSource.SUBTITLE_MANUAL_UPLOAD
        return str(source or "").strip() == TaskSource.SUBTITLE_MANUAL_UPLOAD.value

    def _is_current_task_cancelled(self) -> bool:
        return self._get_queue_worker().is_current_task_cancelled()

    def _raise_if_task_cancelled(self):
        self._get_queue_worker().raise_if_task_cancelled()

    @staticmethod
    def _AutoSubv3__subtitle_lang_suffix(source_lang: Any, output_mode: str = "bilingual") -> str:
        return SubtitleOutputService.subtitle_lang_suffix(source_lang, output_mode)

    @classmethod
    def _AutoSubv3__translated_subtitle_path(cls, file_path: str, source_lang: Any = "", output_mode: str = "bilingual") -> str:
        return SubtitleOutputService.translated_subtitle_path(file_path, source_lang, output_mode)

    @staticmethod
    def _variant_for_source(resolved_source: Any) -> str:
        return SubtitleOutputService.variant_for_source(resolved_source)

    @classmethod
    def _AutoSubv3__translated_subtitle_path_with_variant(
        cls,
        file_path: str,
        source_lang: Any = "",
        output_mode: str = "bilingual",
        output_variant: str = "ai",
    ) -> str:
        variant = cls._normalize_text(output_variant) or "ai"
        suffix = SubtitleOutputService.subtitle_lang_suffix(source_lang, output_mode)
        return f"{file_path}.{suffix}.{variant}.srt"

    def _prepare_output_path(
        self,
        file_path: str,
        source_lang: Any,
        output_mode: str,
        resolved_source: str,
        overwrite_policy: str,
        inherited_variant: str = "",
        inherited_output_path: str = "",
    ) -> Tuple[str, str]:
        return self._get_subtitle_output().prepare_output_path(
            file_path,
            source_lang,
            output_mode,
            resolved_source,
            overwrite_policy,
            inherited_variant=inherited_variant,
            inherited_output_path=inherited_output_path,
        )

    @staticmethod
    def _backup_existing_file(path: str, suffix: str = ".mp-ai-bk") -> str:
        return SubtitleOutputService.backup_existing_file(path, suffix)

    def _copy_source_asset(self, task_id: str, source_path: str, source_name: str = "") -> str:
        return self._get_subtitle_output().copy_source_asset(task_id, source_path, source_name)

    def _AutoSubv3__process_autosub(
        self,
        video_file,
        *,
        source: TaskSource = TaskSource.MANUAL,
        force_generate: bool = False,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        source_policy: str = SourcePolicy.AUTO.value,
        overwrite_policy: str = OverwritePolicy.SKIP.value,
        output_variant: str = "",
        reuse_output_path: str = "",
        reuse_source_lang: str = "",
    ) -> TaskStatus:
        return self._get_generation_pipeline().process_autosub(
            video_file,
            source=source,
            force_generate=force_generate,
            source_subtitle_path=source_subtitle_path,
            source_subtitle_lang=source_subtitle_lang,
            source_policy=source_policy,
            overwrite_policy=overwrite_policy,
            output_variant=output_variant,
            reuse_output_path=reuse_output_path,
            reuse_source_lang=reuse_source_lang,
        )

    def _AutoSubv3__do_speech_recognition(self, audio_lang, audio_file, video_file=None):
        return self._get_asr_service().do_speech_recognition(
            audio_lang,
            audio_file,
            video_file,
            skip_chinese=bool(self._skip_chinese),
        )

    def _AutoSubv3__generate_subtitle(
        self,
        video_file,
        subtitle_file,
        enable_asr=True,
        *,
        source_subtitle_path: str = "",
        source_subtitle_lang: str = "",
        source_policy: str = SourcePolicy.AUTO.value,
    ):
        """
        生成字幕
        :param video_file: 视频文件
        :param subtitle_file: 字幕文件, 不包含后缀
        :return: 生成成功返回True，字幕语言,字幕路径，否则返回False, None, None
        """
        policy = self._normalize_source_policy(source_policy)
        if policy == SourcePolicy.REUSE.value:
            policy = SourcePolicy.AUTO.value
        source_path = self._normalize_text(source_subtitle_path)
        if source_path and policy in (SourcePolicy.AUTO.value, SourcePolicy.MATCHED_EXTERNAL.value):
            subtitle_path = Path(source_path)
            if not subtitle_path.exists() or subtitle_path.suffix.lower() != ".srt":
                logger.error(f"[GenSub] 指定字幕不可用或不是 SRT：{source_path}")
                return False, None, None
            lang = self._normalize_text(source_subtitle_lang) or "en"
            logger.info(f"[GenSub] 使用联动指定字幕：{subtitle_path.name} lang={lang}")
            return True, lang, (subtitle_path, ResolvedSource.MATCHED_EXTERNAL.value)

        # 获取文件元数据
        logger.info(f"[GenSub] 获取视频元数据：{video_file}")
        video_meta = Ffmpeg().get_video_metadata(video_file)
        if not video_meta:
            logger.error(f"[GenSub] 获取视频元数据失败，跳过后续处理")
            return False, None, None
        logger.info(f"[GenSub] 获取视频元数据成功")
        # 获取字幕语言偏好
        if self._translate_preference == "english_only":
            prefer_subtitle_langs = ['en', 'eng']
            strict = True
        elif self._translate_preference == "english_first":
            prefer_subtitle_langs = ['en', 'eng']
            strict = False
        else:  # self.translate_preference == "origin_first"
            prefer_subtitle_langs = None
            strict = False

        # 从视频文件音轨获取语言信息
        logger.info(f"[GenSub Step 2] 获取音轨信息")
        ret, audio_index, audio_lang = self._AutoSubv3__get_video_prefer_audio(video_meta, prefer_lang=prefer_subtitle_langs)
        if not ret:
            logger.info(f"字幕源偏好：{self._translate_preference} 获取音轨元数据失败")
            return False, None, None

        # 如果开启了自动语言检测，直接设置为auto，跳过metadata的语言信息
        if self._auto_detect_language:
            logger.info("已开启自动语言检测，将使用whisper模型自动识别语言")
            audio_lang = 'auto'
        elif not iso639.find(audio_lang) or not iso639.to_iso639_1(audio_lang):
            logger.info(f"字幕源偏好：{self._translate_preference} 未从音轨元数据中获取到语言信息")
            audio_lang = 'auto'

        # 当字幕源偏好为origin_first时，优先使用音轨语言
        if self._translate_preference == "origin_first":
            prefer_subtitle_langs = ['en', 'eng'] if audio_lang == 'auto' else [audio_lang,
                                                                                iso639.to_iso639_1(audio_lang)]

        def get_sub_path():
            video_dir, _ = os.path.split(video_file)
            return os.path.join(video_dir, exist_sub_name)

        external_sub_exist, external_sub_lang, exist_sub_name = False, None, None
        if policy in (SourcePolicy.AUTO.value, SourcePolicy.LOCAL_EXTERNAL.value):
            logger.info(f"[GenSub Step 3] 检查外挂字幕")
            logger.info(f"使用 {prefer_subtitle_langs} 匹配已有外挂字幕文件 ...")
            external_sub_exist, external_sub_lang, exist_sub_name = self._AutoSubv3__external_subtitle_exists(
                video_file,
                prefer_subtitle_langs,
                only_srt=True,
                strict=strict,
            )
            if policy == SourcePolicy.LOCAL_EXTERNAL.value:
                if not external_sub_exist:
                    logger.info("[GenSub] 已指定本地外挂字幕，但未找到可用 SRT")
                    return False, None, None
                logger.info(f"[GenSub] 使用本地外挂字幕：{exist_sub_name} lang={external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)

        inner_sub_exist, subtitle_index, inner_sub_lang = False, None, None
        if policy in (SourcePolicy.AUTO.value, SourcePolicy.EMBEDDED.value):
            logger.info(f"[GenSub Step 4] 检查内嵌字幕")
            logger.info(f"使用 {prefer_subtitle_langs} 匹配内嵌字幕文件 ...")
            inner_sub_exist, subtitle_index, inner_sub_lang, = self._AutoSubv3__get_video_prefer_subtitle(
                video_meta,
                prefer_subtitle_langs,
                strict=strict,
            )
            if policy == SourcePolicy.EMBEDDED.value and not inner_sub_exist:
                logger.info("[GenSub] 已指定视频内嵌字幕，但未找到可用字幕轨")
                return False, None, None

        extract_subtitle = False
        if policy == SourcePolicy.ASR.value:
            logger.info("[GenSub] 已指定音轨 ASR，跳过外挂和内嵌字幕")
        elif policy == SourcePolicy.EMBEDDED.value:
            extract_subtitle = True
        elif self._translate_preference == "english_only":
            if external_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 外挂字幕存在，字幕语言 {external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)
            elif inner_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 内嵌字幕存在，字幕语言 {inner_sub_lang}")
                extract_subtitle = True
            else:
                logger.info(f"字幕源偏好：{self._translate_preference} 未匹配到外挂或内嵌字幕,需要使用asr提取")
        else:  # english_first/origin_first
            if external_sub_exist and external_sub_lang in prefer_subtitle_langs:
                logger.info(f"字幕源偏好：{self._translate_preference} 外挂字幕存在，字幕语言 {external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)
            elif inner_sub_exist and inner_sub_lang in prefer_subtitle_langs:
                logger.info(f"字幕源偏好：{self._translate_preference} 内嵌字幕存在，字幕语言 {inner_sub_lang}")
                extract_subtitle = True
            elif external_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 外挂字幕存在，字幕语言 {external_sub_lang}")
                return True, iso639.to_iso639_1(external_sub_lang), (get_sub_path(), ResolvedSource.LOCAL_EXTERNAL.value)
            elif inner_sub_exist:
                logger.info(f"字幕源偏好：{self._translate_preference} 内嵌字幕存在，字幕语言 {inner_sub_lang}")
                extract_subtitle = True
            else:
                logger.info(f"字幕源偏好：{self._translate_preference} 未匹配到外挂或内嵌字幕,需要使用asr提取")
        # 提取内嵌字幕
        if extract_subtitle:
            return SourceResolver.extract_embedded_subtitle(
                video_file,
                subtitle_file,
                subtitle_index,
                inner_sub_lang,
                Ffmpeg,
                logger,
            )
        # 使用asr音轨识别字幕
        if audio_lang != 'auto':
            audio_lang = iso639.to_iso639_1(audio_lang)

        if not enable_asr and policy != SourcePolicy.ASR.value:
            logger.info(f"未开启语音识别，且无已有字幕文件，跳过后续处理")
            return False, None, None
        if policy == SourcePolicy.ASR.value and not self._AutoSubv3__check_asr():
            logger.info("已指定音轨 ASR，但 ASR 依赖或 Whisper 配置不可用")
            return False, None, None

        ret, lang, output = self._get_asr_service().generate_from_audio(
            video_file,
            subtitle_file,
            audio_index,
            audio_lang,
            Ffmpeg,
            SystemUtils.copy,
            skip_chinese=bool(self._skip_chinese),
        )
        if ret == "skip_chinese":
            logger.info(f"视频识别为中文且已开启中文视频不翻译，跳过字幕生成：{video_file}")
            self.add_skip_chinese_video(video_file)
            return False, "skip_chinese", None
        if ret:
            return ret, lang, output
        if ret is None:
            logger.info(f"视频无声音，跳过字幕生成：{video_file}")
            self.add_skipped_video(video_file)
            return False, None, None
        logger.error("生成字幕失败")
        return False, None, None

    @staticmethod
    def _AutoSubv3__get_library_files(in_path, exclude_path=None):
        """
        获取目录媒体文件列表
        """
        yield from MonitorService.library_files(in_path, settings.RMT_MEDIAEXT, exclude_path)

    @staticmethod
    def _AutoSubv3__load_srt(file_path):
        return AsrService.load_srt(file_path)

    @staticmethod
    def _AutoSubv3__save_srt(file_path, srt_data):
        AsrService.save_srt(file_path, srt_data)

    def _AutoSubv3__merge_srt(self, subtitle_data, max_duration=None, max_chars=None):
        return self._get_asr_service().merge_srt(subtitle_data, max_duration, max_chars)

    @staticmethod
    def _AutoSubv3__get_video_prefer_audio(video_meta, prefer_lang=None):
        return SourceResolver.get_video_prefer_audio(video_meta, prefer_lang, logger)

    @staticmethod
    def _AutoSubv3__get_video_prefer_subtitle(video_meta, prefer_lang=None, strict=False, only_srt=True):
        return SourceResolver.get_video_prefer_subtitle(video_meta, prefer_lang, strict, only_srt, logger)

    @staticmethod
    def _AutoSubv3__is_noisy_subtitle(content):
        return AsrService.is_noisy_subtitle(content)

    @staticmethod
    def _AutoSubv3__normalize_subtitle_text_line(value: Any) -> str:
        return TranslationService.normalize_subtitle_text_line(value)

    def _AutoSubv3__format_translated_content(self, original: Any, translated: Any) -> str:
        return self._get_translation_service().format_translated_content(original, translated)

    def _AutoSubv3__get_context(self, all_subs: list, target_indices: List[int], is_batch: bool) -> str:
        return self._get_translation_service().get_context(all_subs, target_indices, is_batch)

    def _AutoSubv3__process_items(self, all_subs: list, items: list) -> list:
        return self._get_translation_service().process_items(
            all_subs,
            items,
            process_batch=self._AutoSubv3__process_batch,
            process_single=self._AutoSubv3__process_single,
        )

    def _AutoSubv3__translate_to_zh(self, text: str, context: str = None, max_retries: int = None) -> str:
        return self._get_translation_service().translate_to_zh(text, context, max_retries)

    def _AutoSubv3__process_batch(self, all_subs: list, batch: list) -> list:
        return self._get_translation_service().process_batch(
            all_subs,
            batch,
            process_single=self._AutoSubv3__process_single,
            translate_to_zh=self._AutoSubv3__translate_to_zh,
        )

    def _AutoSubv3__process_single(self, all_subs: List[srt.Subtitle], item: srt.Subtitle) -> srt.Subtitle:
        return self._get_translation_service().process_single(
            all_subs,
            item,
            translate_to_zh=self._AutoSubv3__translate_to_zh,
        )

    def _AutoSubv3__enforce_translation_quality(self) -> Tuple[int, int, float]:
        return self._get_translation_service().enforce_translation_quality()

    def _AutoSubv3__translate_zh_subtitle(self, source_lang: str, source_subtitle: str, dest_subtitle: str,
                                  output_mode: str = None):
        """
        翻译字幕为中文
        :param source_lang: 源语言
        :param source_subtitle: 源字幕文件路径
        :param dest_subtitle: 目标字幕文件路径
        :param output_mode: 输出模式，'bilingual'=双语（翻译+原文），'chinese_only'=纯中文
        """
        self._stats = TranslationService.initial_stats()
        return self._get_translation_service().translate_zh_subtitle(
            source_lang,
            source_subtitle,
            dest_subtitle,
            output_mode,
            translate_parallel=self._AutoSubv3__translate_parallel,
            process_single=self._AutoSubv3__process_single,
        )

    def _AutoSubv3__translate_parallel(self, valid_subs: list):
        return self._get_translation_service().translate_parallel(
            valid_subs,
            translate_to_zh=self._AutoSubv3__translate_to_zh,
        )

    @staticmethod
    def _AutoSubv3__external_subtitle_exists(video_file, prefer_langs=None, only_srt=False, strict=True):
        return SubtitleOutputService.external_subtitle_exists(video_file, prefer_langs, only_srt, strict)

    def _AutoSubv3__target_subtitle_exists(self, video_file):
        return self._get_subtitle_output().target_subtitle_exists(video_file)
