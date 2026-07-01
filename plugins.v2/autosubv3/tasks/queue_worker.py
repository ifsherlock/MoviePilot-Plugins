import queue
import threading
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Set

from ..core.models import TaskItem, TaskStatus, UserInterruptException


class QueueWorker:
    def __init__(
        self,
        event: Any,
        tasks_provider: Callable[[], Dict[str, TaskItem]],
        save_tasks: Callable[[], None],
        process_task: Callable[..., TaskStatus],
        status_message: Callable[[TaskStatus], str],
        logger: Any,
        get_current_task: Optional[Callable[[], Optional[TaskItem]]] = None,
        set_current_task: Optional[Callable[[Optional[TaskItem]], None]] = None,
        task_queue: Optional[queue.Queue] = None,
        consumer_thread: Optional[threading.Thread] = None,
    ):
        self._event = event
        self._tasks_provider = tasks_provider
        self._save_tasks = save_tasks
        self._process_task = process_task
        self._status_message = status_message
        self._logger = logger
        self._get_current_task = get_current_task
        self._set_current_task_callback = set_current_task
        self.task_queue = task_queue
        self.consumer_thread = consumer_thread

    @property
    def current_task(self) -> Optional[TaskItem]:
        if self._get_current_task:
            return self._get_current_task()
        return getattr(self, "_current_task", None)

    @current_task.setter
    def current_task(self, task: Optional[TaskItem]):
        if self._set_current_task_callback:
            self._set_current_task_callback(task)
        else:
            self._current_task = task

    def sync_legacy_handles(
        self,
        task_queue: Optional[queue.Queue] = None,
        consumer_thread: Optional[threading.Thread] = None,
    ):
        if task_queue is not None and task_queue is not self.task_queue:
            self.task_queue = task_queue
        if consumer_thread is not None and consumer_thread is not self.consumer_thread:
            self.consumer_thread = consumer_thread

    def start(self):
        if not self.task_queue:
            self.task_queue = queue.Queue()
        if not self.consumer_thread or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self.consume, daemon=True)
            self.consumer_thread.start()
        return self.task_queue, self.consumer_thread

    def stop(self):
        if self.consumer_thread and self.consumer_thread.is_alive():
            self._logger.info("正在停止当前任务...")
            self.consumer_thread.join()
        if self.task_queue:
            while not self.task_queue.empty():
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            self._logger.info("任务队列已清空")

    def enqueue(self, task: TaskItem):
        if not self.task_queue:
            self.task_queue = queue.Queue()
        self.task_queue.put(task)

    def queue_size(self) -> int:
        return self.task_queue.qsize() if self.task_queue else 0

    def positions(self) -> Dict[str, int]:
        positions: Dict[str, int] = {}
        current_task = self.current_task
        if current_task:
            positions[current_task.task_id] = 0
        if not self.task_queue:
            return positions
        try:
            with self.task_queue.mutex:
                for index, task in enumerate(list(self.task_queue.queue), start=1):
                    positions[task.task_id] = index
        except Exception:
            return positions
        return positions

    def remove_pending(self, task_ids: Set[str], reason: str = "任务") -> int:
        if not task_ids or not self.task_queue:
            return 0
        try:
            with self.task_queue.mutex:
                kept_tasks = [task for task in self.task_queue.queue if task.task_id not in task_ids]
                removed_count = len(self.task_queue.queue) - len(kept_tasks)
                self.task_queue.queue = type(self.task_queue.queue)(kept_tasks)
                self.task_queue.unfinished_tasks = max(0, self.task_queue.unfinished_tasks - removed_count)
                if self.task_queue.unfinished_tasks == 0:
                    self.task_queue.all_tasks_done.notify_all()
                return removed_count
        except Exception as exc:
            self._logger.warning("[AutoSubv3] 从队列移除%s失败: %s", reason, exc)
            return 0

    def is_duplicate(self, video_file: str) -> bool:
        if not self.task_queue:
            return False
        with self.task_queue.mutex:
            for task in self.task_queue.queue:
                if task.video_file == video_file and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) and not task.cancel_requested:
                    return True
            current_task = self.current_task
            if (
                self.consumer_thread
                and current_task
                and current_task.video_file == video_file
                and current_task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
                and not current_task.cancel_requested
            ):
                return True
        return False

    def is_current_task_cancelled(self) -> bool:
        task = self.current_task
        return bool(task and (task.cancel_requested or task.status == TaskStatus.CANCELLED))

    def raise_if_task_cancelled(self):
        if self._event.is_set() or self.is_current_task_cancelled():
            raise UserInterruptException("用户中断当前任务")

    def consume(self):
        while not self._event.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:
                    continue
                if task.cancel_requested or task.status == TaskStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    task.complete_time = task.complete_time or datetime.now()
                    task.error_message = task.error_message or "用户已取消"
                    self._tasks_provider()[task.task_id] = task
                    self._save_tasks()
                    self.task_queue.task_done()
                    continue
                self.current_task = task
                self._logger.info(f"开始处理任务 {task.task_id}: {task.video_file}")
                task.status = TaskStatus.IN_PROGRESS
                task.error_message = ""
                self._tasks_provider()[task.task_id] = task
                self._save_tasks()
                result_status = self._process_task(
                    task.video_file,
                    source=task.source,
                    force_generate=task.force_generate,
                    source_subtitle_path=task.source_subtitle_path,
                    source_subtitle_lang=task.source_subtitle_lang,
                    source_policy=task.source_policy,
                    overwrite_policy=task.overwrite_policy,
                    output_variant=task.output_variant,
                    reuse_output_path=task.reuse_output_path,
                    reuse_source_lang=task.reuse_source_lang,
                )
                if task.cancel_requested or task.status == TaskStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    task.complete_time = task.complete_time or datetime.now()
                    task.error_message = task.error_message or "用户已取消"
                else:
                    task.status = result_status
                    task.complete_time = datetime.now()
                    task.error_message = "" if task.status == TaskStatus.COMPLETED else self._status_message(task.status)
                self._tasks_provider()[task.task_id] = task
                self._save_tasks()
                self.task_queue.task_done()
                self.current_task = None
            except queue.Empty:
                continue
            except Exception as exc:
                self._logger.error(f"消费任务时发生异常: {exc}")
                self._logger.error(traceback.format_exc())
                current_task = self.current_task
                if current_task:
                    if current_task.cancel_requested or current_task.status == TaskStatus.CANCELLED:
                        current_task.status = TaskStatus.CANCELLED
                        current_task.complete_time = current_task.complete_time or datetime.now()
                        current_task.error_message = current_task.error_message or "用户已取消"
                    else:
                        current_task.status = TaskStatus.FAILED
                        current_task.complete_time = datetime.now()
                        current_task.error_message = str(exc)
                    self._tasks_provider()[current_task.task_id] = current_task
                    self._save_tasks()
                self.current_task = None
        self._logger.info("消费线程已退出")
