from typing import Dict, List

from .models import TaskItem, TaskSource, TaskStatus


def build_legacy_page(tasks: Dict[str, TaskItem]) -> List[dict]:
    # 加载任务并按添加时间倒序排列
    sorted_tasks = sorted(
        tasks.items(),
        key=lambda x: x[1].add_time,
        reverse=True
    )

    status_classes = {
        TaskStatus.PENDING: "text-info",
        TaskStatus.IN_PROGRESS: "text-warning",
        TaskStatus.COMPLETED: "text-success",
        TaskStatus.IGNORED: "text-muted",
        TaskStatus.NO_AUDIO: "text-muted",
        TaskStatus.FAILED: "text-error",
        TaskStatus.CANCELLED: "text-muted"
    }

    rows = []
    for task_id, task in sorted_tasks:
        source_label = {
            TaskSource.MANUAL: "手动添加",
            TaskSource.EVENT: "入库触发",
            TaskSource.SUBTITLE_MANUAL_UPLOAD: "字幕匹配联动",
        }.get(task.source, task.source)

        status_text = {
            TaskStatus.PENDING: "等待中",
            TaskStatus.IN_PROGRESS: "处理中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.IGNORED: "已忽略",
            TaskStatus.NO_AUDIO: "无声音跳过",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "已取消"
        }.get(task.status, task.status)

        status_class = status_classes.get(task.status, "")

        add_time_str = task.add_time.strftime("%Y-%m-%d %H:%M:%S")
        complete_time_str = (
            task.complete_time.strftime("%Y-%m-%d %H:%M:%S")
            if task.complete_time else "-"
        )

        rows.append({
            "component": "tr",
            "props": {"class": "text-sm"},
            "content": [
                {"component": "td", "text": add_time_str},
                {"component": "td", "text": task.video_file},
                {"component": "td", "text": source_label},
                {"component": "td", "text": complete_time_str},
                {
                    "component": "td",
                    "props": {"class": status_class},
                    "text": status_text
                },
            ],
        })

    return [
        {
            "component": "VRow",
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12},
                    "content": [
                        {
                            "component": "VTable",
                            "props": {"hover": True},
                            "content": [
                                {
                                    "component": "thead",
                                    "content": [
                                        {
                                            "component": "th",
                                            "props": {"class": "text-start ps-4"},
                                            "text": "添加时间"
                                        },
                                        {
                                            "component": "th",
                                            "props": {"class": "text-start ps-4"},
                                            "text": "视频文件"
                                        },
                                        {
                                            "component": "th",
                                            "props": {"class": "text-start ps-4"},
                                            "text": "来源"
                                        },
                                        {
                                            "component": "th",
                                            "props": {"class": "text-start ps-4"},
                                            "text": "完成时间"
                                        },
                                        {
                                            "component": "th",
                                            "props": {"class": "text-start ps-4"},
                                            "text": "状态"
                                        },
                                    ]
                                },
                                {"component": "tbody", "content": rows}
                            ]
                        }
                    ]
                }
            ]
        }
    ]
