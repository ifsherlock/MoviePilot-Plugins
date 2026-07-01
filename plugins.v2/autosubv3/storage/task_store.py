from datetime import datetime
from typing import Any, Callable, Dict

from ..core.models import (
    OverwritePolicy,
    SourcePolicy,
    TaskItem,
    TaskSource,
    TaskStatus,
    TriggerType,
)


class TaskStore:
    def __init__(self, get_data: Callable[[str], Any], save_data: Callable[[str, Any], None], logger: Any):
        self._get_data = get_data
        self._save_data = save_data
        self._logger = logger

    def load_tasks(self) -> Dict[str, TaskItem]:
        raw_tasks = self._get_data("tasks") or {}
        tasks = {}
        for task_id, task_dict in raw_tasks.items():
            try:
                task = TaskItem(
                    task_id=task_dict["task_id"],
                    video_file=task_dict["video_file"],
                    source=TaskSource(task_dict["source"]),
                    add_time=datetime.fromisoformat(task_dict["add_time"]),
                    force_generate=bool(task_dict.get("force_generate", False)),
                    source_subtitle_path=task_dict.get("source_subtitle_path", ""),
                    source_subtitle_lang=task_dict.get("source_subtitle_lang", ""),
                    trigger=task_dict.get("trigger") or TriggerType.MANUAL.value,
                    source_policy=task_dict.get("source_policy") or SourcePolicy.AUTO.value,
                    resolved_source=task_dict.get("resolved_source", ""),
                    source_asset_path=task_dict.get("source_asset_path", ""),
                    source_lang=task_dict.get("source_lang", ""),
                    output_path=task_dict.get("output_path", ""),
                    output_variant=task_dict.get("output_variant", ""),
                    reuse_output_path=task_dict.get("reuse_output_path", ""),
                    reuse_source_lang=task_dict.get("reuse_source_lang", ""),
                    overwrite_policy=task_dict.get("overwrite_policy") or OverwritePolicy.SKIP.value,
                    rerun_of=task_dict.get("rerun_of", ""),
                    status=TaskStatus(task_dict["status"]),
                    complete_time=datetime.fromisoformat(task_dict["complete_time"])
                    if task_dict.get("complete_time") else None,
                    error_message=task_dict.get("error_message", ""),
                    cancel_requested=bool(task_dict.get("cancel_requested", False)),
                )
                tasks[task_id] = task
            except Exception as exc:
                self._logger.error(f"恢复任务失败：{exc}")
        return tasks

    @staticmethod
    def serialize_task(task: TaskItem) -> dict:
        return {
            "task_id": task.task_id,
            "video_file": task.video_file,
            "source": task.source.value,
            "add_time": task.add_time.isoformat() if task.add_time else None,
            "force_generate": bool(task.force_generate),
            "source_subtitle_path": task.source_subtitle_path or "",
            "source_subtitle_lang": task.source_subtitle_lang or "",
            "trigger": task.trigger or TriggerType.MANUAL.value,
            "source_policy": task.source_policy or SourcePolicy.AUTO.value,
            "resolved_source": task.resolved_source or "",
            "source_asset_path": task.source_asset_path or "",
            "source_lang": task.source_lang or "",
            "output_path": task.output_path or "",
            "output_variant": task.output_variant or "",
            "reuse_output_path": task.reuse_output_path or "",
            "reuse_source_lang": task.reuse_source_lang or "",
            "overwrite_policy": task.overwrite_policy or OverwritePolicy.SKIP.value,
            "rerun_of": task.rerun_of or "",
            "status": task.status.value,
            "complete_time": task.complete_time.isoformat() if task.complete_time else None,
            "error_message": task.error_message or "",
            "cancel_requested": bool(task.cancel_requested),
        }

    def save_tasks(self, tasks: Dict[str, TaskItem]):
        tasks_dict = {task_id: self.serialize_task(task) for task_id, task in tasks.items()}
        self._save_data("tasks", tasks_dict)

    def load_skipped_videos(self) -> Dict[str, dict]:
        return self._get_data("skipped_videos") or {}

    def save_skipped_videos(self, skipped: Dict[str, dict]):
        self._save_data("skipped_videos", skipped)

    def add_skipped_video(self, video_file: str):
        skipped = self.load_skipped_videos()
        skipped[video_file] = {
            "skip_time": datetime.now().isoformat(),
            "reason": "no_audio",
        }
        self.save_skipped_videos(skipped)
        self._logger.info(f"已记录无声音视频：{video_file}")

    def is_video_skipped(self, video_file: str) -> bool:
        return video_file in self.load_skipped_videos()

    def load_skip_chinese_videos(self) -> Dict[str, dict]:
        return self._get_data("skip_chinese_videos") or {}

    def save_skip_chinese_videos(self, skipped: Dict[str, dict]):
        self._save_data("skip_chinese_videos", skipped)

    def add_skip_chinese_video(self, video_file: str):
        skipped = self.load_skip_chinese_videos()
        skipped[video_file] = {
            "skip_time": datetime.now().isoformat(),
            "reason": "chinese",
        }
        self.save_skip_chinese_videos(skipped)
        self._logger.info(f"已记录中文视频跳过：{video_file}")

    def is_video_skip_chinese(self, video_file: str) -> bool:
        return video_file in self.load_skip_chinese_videos()
