import copy
import os
import tempfile
import time
import traceback
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

import psutil
import srt

from ..core.models import ResolvedSource, UserInterruptException


class AsrService:
    def __init__(
        self,
        logger,
        event,
        is_current_task_cancelled: Callable[[], bool],
        raise_if_task_cancelled: Callable[[], None],
        is_chinese_lang: Callable[[str], bool],
        faster_whisper_model_path: Callable[[], Any],
        faster_whisper_model: Callable[[], Any],
        huggingface_proxy: Callable[[], bool],
        proxy_config: Callable[[], dict],
        max_segment_duration: Callable[[], Any],
        max_segment_chars: Callable[[], Any],
        html_parser: Callable[[str], Any],
    ):
        self._logger = logger
        self._event = event
        self._is_current_task_cancelled = is_current_task_cancelled
        self._raise_if_task_cancelled = raise_if_task_cancelled
        self._is_chinese_lang = is_chinese_lang
        self._faster_whisper_model_path = faster_whisper_model_path
        self._faster_whisper_model = faster_whisper_model
        self._huggingface_proxy = huggingface_proxy
        self._proxy_config = proxy_config
        self._max_segment_duration = max_segment_duration
        self._max_segment_chars = max_segment_chars
        self._html_parser = html_parser

    def do_speech_recognition(self, audio_lang, audio_file, video_file=None, skip_chinese=False):
        lang = audio_lang
        video_name = os.path.basename(video_file) if video_file else os.path.basename(audio_file)
        self._logger.info(f"[Whisper音频提取文本] 开始处理: {video_name}")
        try:
            from faster_whisper import WhisperModel, download_model
            self._logger.info(f"[Whisper音频提取文本] {video_name} - 加载模型中...")
            cache_dir = os.path.join(self._faster_whisper_model_path(), "cache")
            if not os.path.exists(cache_dir):
                os.mkdir(cache_dir)
            os.environ["HF_HUB_CACHE"] = cache_dir
            if self._huggingface_proxy():
                proxy = self._proxy_config()
                os.environ["HTTP_PROXY"] = proxy['http']
                os.environ["HTTPS_PROXY"] = proxy['https']

            max_retries = 3
            model = None
            for attempt in range(max_retries):
                try:
                    model_path = download_model(self._faster_whisper_model(), local_files_only=False, cache_dir=cache_dir)
                    if model_path is None:
                        raise ValueError("模型下载返回空路径")
                    model = WhisperModel(
                        model_path,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=psutil.cpu_count(logical=False),
                    )
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        self._logger.warn(f"[Whisper音频提取文本] {video_name} - 模型下载失败（第{attempt+1}次），30秒后重试... 错误: {e}")
                        time.sleep(30)
                    else:
                        self._logger.error(f"[Whisper音频提取文本] {video_name} - 模型下载失败，已重试{max_retries}次。请检查：1) 网络连接 2) 代理配置 3) HuggingFace访问。错误: {e}")
                        return False, None

            try:
                segments, info = model.transcribe(
                    audio_file,
                    language=lang if lang != 'auto' else None,
                    word_timestamps=True,
                    vad_filter=True,
                    temperature=0,
                    beam_size=5,
                )
                self._logger.info(f"[Whisper音频提取文本] {video_name} - 检测到语言：{info.language}（置信度 {info.language_probability:.2%}）")

                detected_lang = info.language
                if lang == 'auto':
                    lang = detected_lang

                if skip_chinese and self._is_chinese_lang(lang):
                    self._logger.info(f"[Whisper音频提取文本] {video_name} - 检测到中文且已开启中文视频不翻译，立即跳过后续字幕提取")
                    return "skip_chinese", lang

                self._logger.info(f"[Whisper音频提取文本] {video_name} - 开始提取字幕内容，语言：{lang}")
                extract_start_time = time.time()
            except ValueError as e:
                if "max() iterable argument is empty" in str(e):
                    self._logger.info(f"[Whisper音频提取文本] {video_name} - 音频文件中未检测到任何语言内容，标记为无声音")
                    return None, None
                raise e

            seg_list = list(segments)
            total_duration = seg_list[-1].end if seg_list else 0
            total_count = len(seg_list)
            subs = []
            idx = 0
            last_pct = 0
            for segment in seg_list:
                if self._event.is_set() or self._is_current_task_cancelled():
                    self._logger.info(f"[Whisper音频提取文本] {video_name} - 用户中断，停止提取")
                    raise UserInterruptException("用户中断当前任务")
                pct = int(segment.end / total_duration * 100) if total_duration > 0 else 0
                if pct >= last_pct + 10:
                    self._logger.info(f"[Whisper音频提取文本] {video_name} - 提取进度：{pct}%（{segment.end:.1f}s / {total_duration:.1f}s）")
                    last_pct = pct
                if segment.words:
                    for word in segment.words:
                        idx += 1
                        subs.append(srt.Subtitle(
                            index=idx,
                            start=timedelta(seconds=word.start),
                            end=timedelta(seconds=word.end),
                            content=word.word,
                        ))
                else:
                    idx += 1
                    subs.append(srt.Subtitle(
                        index=idx,
                        start=timedelta(seconds=segment.start),
                        end=timedelta(seconds=segment.end),
                        content=segment.text,
                    ))
            subs = self.merge_srt(subs)

            extract_elapsed = time.time() - extract_start_time
            self._logger.info(f"[Whisper音频提取文本] {video_name} - 提取完成，共处理 {total_count} 段，合并后 {idx} 条字幕，耗时 {extract_elapsed:.1f} 秒")

            if total_duration > 0:
                ratio = extract_elapsed / total_duration
                if ratio >= 0.8:
                    self._logger.warning(f"[Whisper音频提取文本] {video_name} - 提取耗时过长（{extract_elapsed:.1f}秒 / 视频{total_duration:.1f}秒 = {ratio:.0%}），强烈建议：1) 使用更快模型（tiny/base）2) 启用GPU加速 3) 检查CPU负载")
                elif ratio >= 0.6:
                    self._logger.warning(f"[Whisper音频提取文本] {video_name} - 提取耗时较长（{extract_elapsed:.1f}秒 / 视频{total_duration:.1f}秒 = {ratio:.0%}），建议：1) 使用更快模型（tiny/base）2) 启用GPU加速")
                elif ratio >= 0.3:
                    self._logger.info(f"[Whisper音频提取文本] {video_name} - 提取速度可优化（{extract_elapsed:.1f}秒 / 视频{total_duration:.1f}秒 = {ratio:.0%}），可考虑使用更快模型（tiny/base）")

            if not subs:
                self._logger.info(f"[Whisper音频提取文本] {video_name} - 提取的字幕内容为空，标记为无声音")
                return None, None

            self._raise_if_task_cancelled()
            self.save_srt(f"{audio_file}.srt", subs)
            self._logger.info(f"[Whisper音频提取文本] {video_name} - 音轨转字幕完成")
            return True, lang
        except ImportError:
            self._logger.warn("[Whisper音频提取文本] faster-whisper 未安装，不进行处理")
            return False, None
        except UserInterruptException:
            raise
        except Exception as e:
            traceback.print_exc()
            self._logger.error(f"[Whisper音频提取文本] {video_name} - 处理异常：{e}")
            return False, None

    def generate_from_audio(
        self,
        video_file,
        subtitle_file,
        audio_index,
        audio_lang,
        ffmpeg_factory,
        copy_file: Callable[[Path, Path], None],
        skip_chinese=False,
    ):
        tempdir = tempfile.gettempdir()
        for file in os.listdir(tempdir):
            if file.startswith('autosub-'):
                os.remove(os.path.join(tempdir, file))

        with tempfile.NamedTemporaryFile(prefix='autosub-', suffix='.wav', delete=True) as audio_file:
            self._logger.info(f"[GenSub Step 5a] 提取音频：{audio_file.name}")
            ffmpeg_factory().extract_wav_from_video(video_file, audio_file.name, audio_index)
            self._logger.info("[GenSub Step 5a] 提取音频完成")
            self._logger.info("[GenSub Step 5b] 开始Whisper识别")

            self._logger.info(f"[GenSub Step 5] 开始Whisper识别, 语言 {audio_lang}")
            ret, lang = self.do_speech_recognition(audio_lang, audio_file.name, video_file, skip_chinese=skip_chinese)
            if ret == "skip_chinese":
                return ret, lang, None
            if ret:
                self._logger.info(f"生成字幕成功，原始语言：{lang}")
                self._raise_if_task_cancelled()
                output_path = Path(f"{subtitle_file}.{lang}.srt")
                copy_file(Path(f"{audio_file.name}.srt"), output_path)
                self._logger.info(f"复制字幕文件：{subtitle_file}.{lang}.srt")
                os.remove(f"{audio_file.name}.srt")
                return ret, lang, (output_path, ResolvedSource.ASR.value)
            return ret, lang, None

    @staticmethod
    def load_srt(file_path):
        with open(file_path, 'r', encoding="utf8") as f:
            srt_text = f.read()
        return list(srt.parse(srt_text))

    @staticmethod
    def save_srt(file_path, srt_data):
        with open(file_path, 'w', encoding="utf8") as f:
            f.write(srt.compose(srt_data))

    def merge_srt(self, subtitle_data, max_duration=None, max_chars=None):
        if max_duration is None:
            max_duration = self._max_segment_duration() or 8.0
        if max_chars is None:
            max_chars = self._max_segment_chars() or 30

        subtitle_data = copy.deepcopy(subtitle_data)
        merged_subtitle = []
        sentence_end = True
        end_tokens = ('.', '!', '?', '。', '！', '？', '。"', '！"', '？"', '."', '!"', '?"')
        soft_break_tokens = (',', ';', ':', '，', '；', '：', '、')

        def text_len(value):
            return len((value or "").replace(" ", ""))

        def duration_seconds(item):
            return (item.end - item.start).total_seconds()

        def should_soft_break(item):
            content = item.content.rstrip()
            return (
                content.endswith(soft_break_tokens)
                and (duration_seconds(item) >= max_duration * 0.55 or text_len(content) >= max_chars * 0.65)
            )

        def append_or_extend(item):
            nonlocal sentence_end
            if not merged_subtitle or sentence_end:
                merged_subtitle.append(item)
                sentence_end = False
                return

            current = merged_subtitle[-1]
            candidate_duration = (item.end - current.start).total_seconds()
            candidate_chars = text_len(current.content) + text_len(item.content)
            force_split = candidate_duration > max_duration or candidate_chars > max_chars
            if force_split:
                merged_subtitle.append(item)
                sentence_end = False
                return

            current.content = f"{current.content} {item.content}".strip()
            current.end = item.end

        for item in subtitle_data:
            content = item.content.replace('\n', ' ').strip()
            parse = self._html_parser(content)
            if parse is not None:
                content = parse.xpath('string(.)')
            if content == '':
                continue
            item.content = content

            if self.is_noisy_subtitle(content):
                merged_subtitle.append(item)
                sentence_end = True
                continue

            append_or_extend(item)

            current = merged_subtitle[-1]
            if content.endswith(end_tokens):
                sentence_end = True
            elif should_soft_break(current):
                sentence_end = True
            elif duration_seconds(current) >= max_duration:
                sentence_end = True
            elif text_len(current.content) >= max_chars:
                sentence_end = True
            else:
                sentence_end = False

        for index, item in enumerate(merged_subtitle, 1):
            item.index = index
        return merged_subtitle

    @staticmethod
    def is_noisy_subtitle(content):
        noisy_tokens = [('(', ')'), ('[', ']'), ('{', '}'), ('【', '】'), ('♪', '♪'), ('♫', '♫'), ('♪♪', '♪♪')]
        return any(content.startswith(t[0]) and content.endswith(t[1]) for t in noisy_tokens)
