import os
import time
import traceback
from typing import Any

from app.schemas.types import NotificationType

from ..core.models import OverwritePolicy, ResolvedSource, SourcePolicy, TaskSource, TaskStatus, UserInterruptException


class GenerationPipeline:
    def __init__(self, plugin, logger):
        self._plugin = plugin
        self._logger = logger

    def process_autosub(
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
        plugin = self._plugin
        if not video_file:
            self._logger.error("[Step 0] video_file 为空")
            return TaskStatus.FAILED
        self._logger.info(f"[Step 1] 检查文件大小：{video_file}")
        if os.path.getsize(video_file) < plugin._file_size * 1024 * 1024:
            self._logger.info(f"[Step 1] 文件小于最小大小 {plugin._file_size}MB，跳过")
            return TaskStatus.IGNORED
        self._logger.info("[Step 2] 检查是否已标记为无声音跳过")
        if plugin.is_video_skipped(video_file):
            if force_generate:
                self._logger.info(f"[Step 2] 显式重新生成：忽略无声音历史跳过记录：{video_file}")
            else:
                self._logger.info(f"[Step 2] 视频已标记为无声音跳过：{video_file}")
                return TaskStatus.NO_AUDIO
        self._logger.info("[Step 3] 开始正式处理")
        start_time = time.time()
        file_path, file_ext = os.path.splitext(video_file)
        file_name = os.path.basename(video_file)
        linked_force_generate = force_generate or plugin._is_subtitle_manual_upload_source(source)
        if plugin._skip_chinese and plugin.is_video_skip_chinese(video_file):
            if linked_force_generate:
                self._logger.info("[Step 3] 联动强制生成：跳过中文视频历史忽略记录")
            else:
                self._logger.info(f"[Step 3] 视频已标记为中文跳过翻译：{video_file}")
                message = f" 媒体: {file_name}\n 中文视频跳过翻译"
                if plugin._send_notify:
                    plugin.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                return TaskStatus.IGNORED

        try:
            plugin._raise_if_task_cancelled()
            self._logger.info(f"[Step 4] 判断目的字幕是否已存在：{video_file}")
            if not linked_force_generate and plugin._AutoSubv3__target_subtitle_exists(video_file):
                self._logger.warn("[Step 4] 字幕文件已经存在，不进行处理")
                return TaskStatus.IGNORED
            if linked_force_generate:
                self._logger.info(f"[Step 4] 联动强制生成：跳过已有外挂/内嵌字幕检查 source={source.value if isinstance(source, TaskSource) else source}")
            self._logger.info("[Step 5] 生成字幕")
            ret, lang, gen_sub_path = plugin._AutoSubv3__generate_subtitle(
                video_file,
                file_path,
                plugin._enable_asr,
                source_subtitle_path=source_subtitle_path,
                source_subtitle_lang=source_subtitle_lang,
                source_policy=source_policy,
            )
            resolved_source = ResolvedSource.AUTO.value
            if isinstance(gen_sub_path, tuple):
                gen_sub_path, resolved_source = gen_sub_path
            if plugin._current_processing_task:
                plugin._current_processing_task.resolved_source = resolved_source or ""
                plugin._current_processing_task.source_lang = lang or ""
                if reuse_source_lang and lang and plugin._normalize_text(reuse_source_lang).lower() != plugin._normalize_text(lang).lower():
                    self._logger.info(
                        "重跑沿用原输出路径，检测语言发生变化 old=%s new=%s output=%s",
                        reuse_source_lang,
                        lang,
                        reuse_output_path or "-",
                    )
            plugin._raise_if_task_cancelled()
            if not ret:
                if plugin.is_video_skipped(video_file):
                    message = f" 媒体: {file_name}\n 无声音跳过"
                    if plugin._send_notify:
                        plugin.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                    return TaskStatus.NO_AUDIO
                if lang == "skip_chinese" or plugin.is_video_skip_chinese(video_file):
                    message = f" 媒体: {file_name}\n 中文视频跳过翻译"
                    if plugin._send_notify:
                        plugin.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                    return TaskStatus.IGNORED
                message = f" 媒体: {file_name}\n 生成字幕失败，跳过后续处理"
                if plugin._send_notify:
                    plugin.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
                return TaskStatus.FAILED

            self._logger.info("[Step 6] 翻译字幕（如果需要）")
            translated_to_zh = False
            if plugin._translate_zh:
                self._logger.info("开始翻译字幕为中文 ...")
                translated_subtitle, output_variant = plugin._prepare_output_path(
                    file_path,
                    lang,
                    plugin._subtitle_output_mode,
                    resolved_source,
                    overwrite_policy,
                    inherited_variant=output_variant,
                    inherited_output_path=reuse_output_path,
                )
                normalized_overwrite = plugin._normalize_overwrite_policy(overwrite_policy)
                if os.path.exists(translated_subtitle):
                    if normalized_overwrite == OverwritePolicy.SKIP.value:
                        self._logger.info(f"目标字幕已存在，按覆盖策略跳过：{translated_subtitle}")
                        if plugin._current_processing_task:
                            plugin._current_processing_task.output_path = translated_subtitle
                            plugin._current_processing_task.output_variant = output_variant
                        return TaskStatus.IGNORED
                    if normalized_overwrite == OverwritePolicy.BACKUP_REPLACE.value:
                        backup_path = plugin._backup_existing_file(translated_subtitle)
                        self._logger.info(f"覆盖前备份 AI 字幕：{backup_path}")
                plugin._AutoSubv3__translate_zh_subtitle(
                    lang,
                    gen_sub_path,
                    translated_subtitle,
                    output_mode=plugin._subtitle_output_mode,
                )
                plugin._raise_if_task_cancelled()
                self._logger.info(f"翻译字幕完成：{os.path.basename(translated_subtitle)}")
                if plugin._current_processing_task:
                    plugin._current_processing_task.output_path = translated_subtitle
                    plugin._current_processing_task.output_variant = output_variant
                translated_to_zh = True

            end_time = time.time()
            message = f" 媒体: {file_name}\n 处理完成\n 字幕原始语言: {lang}\n "
            if translated_to_zh:
                message += "字幕翻译语言: zh\n "
            message += f"耗时：{round(end_time - start_time, 2)}秒"
            self._logger.info(f"自动字幕生成 处理完成：{message}")
            self._logger.info("")
            self._logger.info("")
            if plugin._send_notify:
                plugin.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
            return TaskStatus.COMPLETED
        except UserInterruptException:
            self._logger.info(f"用户中断当前任务：{video_file}")
            self._logger.info("")
            self._logger.info("")
            return TaskStatus.CANCELLED
        except Exception as e:
            self._logger.error(f"自动字幕生成 处理异常：{e}")
            end_time = time.time()
            message = f" 媒体: {file_name}\n 处理失败\n 耗时：{round(end_time - start_time, 2)}秒"
            if plugin._send_notify:
                plugin.post_message(mtype=NotificationType.Plugin, title="【自动字幕生成】", text=message)
            self._logger.error(traceback.format_exc())
            self._logger.info("")
            self._logger.info("")
            return TaskStatus.FAILED
