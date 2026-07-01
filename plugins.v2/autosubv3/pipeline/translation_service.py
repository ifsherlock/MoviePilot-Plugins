import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, List, Tuple

import srt

from ..core.models import TranslationQualityException, UserInterruptException


class TranslationService:
    @staticmethod
    def initial_stats() -> dict:
        return {'total': 0, 'batch_success': 0, 'batch_fail': 0, 'line_fallback': 0, 'translated': 0, 'failed': 0}

    def __init__(
        self,
        logger,
        load_srt: Callable[[str], list],
        save_srt: Callable[[str, list], None],
        is_chinese_lang: Callable[[str], bool],
        subtitle_content_looks_chinese: Callable[[List[srt.Subtitle]], bool],
        raise_if_task_cancelled: Callable[[], None],
        openai: Callable[[], Any],
        stats: Callable[[], dict],
        output_mode: Callable[[], str],
        set_output_mode: Callable[[str], None],
        skip_chinese: Callable[[], bool],
        enable_batch: Callable[[], bool],
        batch_size: Callable[[], int],
        parallel_workers: Callable[[], int],
        context_window: Callable[[], int],
        max_retries: Callable[[], int],
        max_translation_failure_rate: Callable[[], float],
    ):
        self._logger = logger
        self._load_srt = load_srt
        self._save_srt = save_srt
        self._is_chinese_lang = is_chinese_lang
        self._subtitle_content_looks_chinese = subtitle_content_looks_chinese
        self._raise_if_task_cancelled = raise_if_task_cancelled
        self._openai = openai
        self._stats = stats
        self._output_mode = output_mode
        self._set_output_mode = set_output_mode
        self._skip_chinese = skip_chinese
        self._enable_batch = enable_batch
        self._batch_size = batch_size
        self._parallel_workers = parallel_workers
        self._context_window = context_window
        self._max_retries = max_retries
        self._max_translation_failure_rate = max_translation_failure_rate

    @staticmethod
    def normalize_subtitle_text_line(value: Any) -> str:
        text = str(value or "")
        text = text.replace("\\N", " ").replace("\\n", " ").replace("\r", "\n")
        text = re.sub(r"\s*\n+\s*", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def format_translated_content(self, original: Any, translated: Any, output_mode: str = None) -> str:
        trans = self.normalize_subtitle_text_line(translated)
        origin = self.normalize_subtitle_text_line(original)
        if (output_mode or self._output_mode()) == 'chinese_only':
            return trans
        if not origin:
            return trans
        if not trans:
            return origin
        return f"{trans}\n{origin}"

    def get_context(self, all_subs: list, target_indices: List[int], is_batch: bool) -> str:
        context_window = self._context_window()
        min_idx = max(0, min(target_indices) - context_window)
        max_idx = min(len(all_subs) - 1, max(target_indices) + context_window) if is_batch else min(target_indices)

        context = []
        for idx in range(min_idx, max_idx + 1):
            status = "[待译]" if idx in target_indices else ""
            content = all_subs[idx].content.replace('\n', ' ').strip()
            context.append(f"{status}{content}")
        return "\n".join(context)

    def translate_to_zh(self, text: str, context: str = None, max_retries: int = None) -> str:
        self._raise_if_task_cancelled()
        if max_retries is None:
            max_retries = self._max_retries()
        return self._openai().translate_to_zh(text, context, max_retries=max_retries)

    def process_items(self, all_subs: list, items: list, process_batch=None, process_single=None) -> list:
        if self._enable_batch() and len(items) > 1:
            return (process_batch or self.process_batch)(all_subs, items)
        return [(process_single or self.process_single)(all_subs, item) for item in items]

    def process_batch(self, all_subs: list, batch: list, process_single=None, translate_to_zh=None) -> list:
        indices = [all_subs.index(item) for item in batch]
        context = self.get_context(all_subs, indices, is_batch=True) if self._context_window() > 0 else None
        batch_text = '\n'.join([item.content for item in batch])
        translate = translate_to_zh or self.translate_to_zh

        try:
            ret, result = translate(batch_text, context)
            if not ret:
                raise Exception(result)

            translated = [line.strip() for line in result.split('\n') if line.strip()]
            if len(translated) != len(batch):
                raise Exception(f"批次行数不匹配 {len(translated)}/{len(batch)}")

            for item, trans in zip(batch, translated):
                item.content = self.format_translated_content(item.content, trans)
            self._stats()['batch_success'] += 1
            self._stats()['translated'] += len(batch)
            return batch
        except UserInterruptException:
            raise
        except Exception as e:
            self._logger.warning(f"[翻译] 批量翻译失败：{e}，降级逐行翻译")
            self._stats()['batch_fail'] += 1
            single = process_single or self.process_single
            return [single(all_subs, item) for item in batch]

    def process_single(self, all_subs: List[srt.Subtitle], item: srt.Subtitle, translate_to_zh=None) -> srt.Subtitle:
        idx = all_subs.index(item)
        context = self.get_context(all_subs, [idx], is_batch=False) if self._context_window() > 0 else None
        success, trans = (translate_to_zh or self.translate_to_zh)(item.content, context)

        if success:
            item.content = self.format_translated_content(item.content, trans)
            self._stats()['line_fallback'] += 1
            self._stats()['translated'] += 1
            return item

        if self._output_mode() == 'chinese_only':
            item.content = "[翻译失败]"
        else:
            item.content = self.format_translated_content(item.content, "[翻译失败]")
        self._stats()['failed'] += 1
        return item

    def enforce_translation_quality(self) -> Tuple[int, int, float]:
        stats = self._stats()
        total = int(stats.get('total') or 0)
        if total <= 0:
            return 0, 0, 0.0
        translated = int(stats.get('translated') or stats.get('line_fallback') or 0)
        translated = max(0, min(translated, total))
        failed = total - translated
        failure_rate = failed / total
        threshold = self._max_translation_failure_rate()
        if failure_rate > threshold:
            message = (
                f"翻译失败率过高：失败 {failed}/{total} 条（{failure_rate:.0%}），"
                f"超过阈值 {threshold:.0%}，已停止输出字幕文件"
            )
            self._logger.error(f"[翻译] {message}")
            raise TranslationQualityException(message)
        return translated, failed, failure_rate

    def translate_zh_subtitle(
        self,
        source_lang: str,
        source_subtitle: str,
        dest_subtitle: str,
        output_mode: str = None,
        translate_parallel=None,
        process_single=None,
    ):
        subs = self._load_srt(source_subtitle)
        valid_subs = subs
        configured_output_mode = output_mode or self._output_mode() or 'bilingual'
        effective_output_mode = configured_output_mode
        chinese_source = self._is_chinese_lang(source_lang) or self._subtitle_content_looks_chinese(valid_subs)
        if not self._skip_chinese() and chinese_source:
            self._logger.info("检测字幕内容为中文，强制使用纯中文字幕输出模式")
            effective_output_mode = 'chinese_only'
        previous_output_mode = self._output_mode()
        self._set_output_mode(effective_output_mode)

        try:
            if not valid_subs:
                self._logger.warning("字幕文件为空或没有有效的字幕条目，跳过翻译")
                self._save_srt(dest_subtitle, [])
                return

            self._stats()['total'] = len(valid_subs)
            translate_start_time = time.time()
            if self._enable_batch():
                processed = (translate_parallel or self.translate_parallel)(valid_subs)
            else:
                self._logger.info(f"[翻译] 逐条模式 - 共 {len(valid_subs)} 条（效果更好，速度较慢）")
                single = process_single or self.process_single
                processed = [single(valid_subs, item) for item in valid_subs]
            self._raise_if_task_cancelled()
            translated_count, failed_count, failure_rate = self.enforce_translation_quality()
            self._save_srt(dest_subtitle, processed)

            translate_elapsed = time.time() - translate_start_time
            speed = len(valid_subs) / translate_elapsed if translate_elapsed > 0 else 0

            stats = self._stats()
            batch_success_count = stats['batch_success']
            batch_fail_count = stats['batch_fail']
            line_fallback_count = stats['line_fallback']

            log_msg = f"[翻译] 完成 - 总计 {stats['total']} 条，耗时 {translate_elapsed:.1f} 秒，速度 {speed:.1f} 条/秒"
            if self._enable_batch():
                log_msg += f"，批量成功 {batch_success_count} 批"
                if batch_fail_count > 0:
                    log_msg += f"，批量失败 {batch_fail_count} 批（降级成功 {line_fallback_count} 条）"
            log_msg += f"，翻译成功 {translated_count} 条，失败 {failed_count} 条，失败率 {failure_rate:.0%}"
            self._logger.info(log_msg)

            if self._enable_batch() and batch_fail_count > 0:
                fail_rate = batch_fail_count / (batch_success_count + batch_fail_count) if (batch_success_count + batch_fail_count) > 0 else 0
                if fail_rate > 0.5:
                    self._logger.warning("[翻译] 批量失败率过高（%.0f%%），建议检查：1) LLM API稳定性 2) 降低batch_size 3) 检查prompt格式" % (fail_rate * 100))
        finally:
            self._set_output_mode(previous_output_mode)

    def translate_parallel(self, valid_subs: list, translate_to_zh=None):
        total = len(valid_subs)
        batch_size = self._batch_size()
        workers = self._parallel_workers()

        batches = []
        for i in range(0, total, batch_size):
            batch_items = valid_subs[i:i + batch_size]
            batch_map = {}
            for j, item in enumerate(batch_items):
                batch_map[i + j] = item
            batches.append((i, batch_map))

        self._logger.info(f"[翻译] 并行模式 - 共 {len(batches)} 批次，每批 {batch_size} 条，并发 {workers} 线程")
        results = {}

        def process_batch(batch_start_idx, batch_map, stats):
            self._raise_if_task_cancelled()
            batch_list = list(batch_map.values())
            indices = list(batch_map.keys())

            try:
                batch_texts = [item.content.strip() for item in batch_list]
                ret, translations = self._openai().translate_batch_to_zh(batch_texts)
                self._raise_if_task_cancelled()
                if ret and translations and all(t is not None for t in translations):
                    for item, trans in zip(batch_list, translations):
                        item.content = self.format_translated_content(item.content, trans)
                    stats["batch_ok"] += 1
                    stats["line_ok"] += len(translations)
                    return {gidx: batch_map[gidx] for gidx in indices}
            except UserInterruptException:
                raise
            except Exception as e:
                self._logger.debug(f"批次 {batch_start_idx} 批量翻译异常，降级单行：{e}")

            line_ok_count = 0
            translate = translate_to_zh or self.translate_to_zh
            for gidx in indices:
                self._raise_if_task_cancelled()
                item = batch_map[gidx]
                context = self.get_context(valid_subs, [gidx], is_batch=False) if self._context_window() > 0 else None
                success, trans = translate(item.content, context, max_retries=1)
                if success:
                    line_ok_count += 1
                    item.content = self.format_translated_content(item.content, trans)
                else:
                    if self._output_mode() == 'chinese_only':
                        item.content = "[翻译失败]"
                    else:
                        item.content = self.format_translated_content(item.content, "[翻译失败]")
            stats["line_ok"] += line_ok_count
            stats["batch_fail"] += 1
            self._logger.info(f"[翻译] 批次 {batch_start_idx} 降级逐行完成：{line_ok_count}/{len(indices)} 条成功")
            return {gidx: batch_map[gidx] for gidx in indices}

        stats = {"batch_ok": 0, "batch_fail": 0, "line_ok": 0}
        last_report_pct = -10

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_batch, start_idx, bmap, stats): start_idx
                       for start_idx, bmap in batches}

            for future in as_completed(futures):
                self._raise_if_task_cancelled()
                batch_results = future.result()
                results.update(batch_results)
                done_count = len(results)
                pct = int(done_count / total * 100) if total > 0 else 0
                if pct >= last_report_pct + 10:
                    self._logger.info(f"[翻译] 进度: {pct}% ({done_count}/{total}) - 已完成 {done_count} 条")
                    last_report_pct = pct

        processed = [results[i] for i in sorted(results.keys())]
        self._stats()['batch_success'] = stats["batch_ok"]
        self._stats()['batch_fail'] = stats["batch_fail"]
        self._stats()['line_fallback'] = stats["line_ok"]
        self._stats()['translated'] = stats["line_ok"]
        self._stats()['failed'] = max(0, total - stats["line_ok"])
        return processed
