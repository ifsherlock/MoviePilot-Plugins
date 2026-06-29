from __future__ import annotations

from typing import Any, Dict, List


def build_api_routes(owner: Any) -> List[Dict[str, Any]]:
    from .catalog_api import CatalogApi
    from .online_api import OnlineApi
    from .status_api import StatusApi
    from .timeline_api import TimelineApi
    from .upload_api import UploadApi

    catalog_api = CatalogApi(owner)
    online_api = OnlineApi(owner)
    status_api = StatusApi(owner)
    timeline_api = TimelineApi(owner)
    upload_api = UploadApi(owner)
    return [
        {
            "path": "/status",
            "endpoint": status_api.status,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "获取字幕匹配插件状态",
        },
        {
            "path": "/refresh_index",
            "endpoint": status_api.refresh_index,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "兼容旧版刷新索引入口",
        },
        {
            "path": "/search",
            "endpoint": catalog_api.search,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "搜索 MoviePilot 本地资源候选",
        },
        {
            "path": "/targets",
            "endpoint": catalog_api.targets,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "读取选中媒体的本地文件目标",
        },
        {
            "path": "/match_history",
            "endpoint": catalog_api.match_history,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "读取字幕匹配历史",
        },
        {
            "path": "/timeline_tasks",
            "endpoint": timeline_api.timeline_tasks,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "查询智能调轴任务状态",
        },
        {
            "path": "/timeline_fix_existing",
            "endpoint": timeline_api.timeline_fix_existing,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "对匹配历史中的外挂字幕执行智能调轴",
        },
        {
            "path": "/auto_transfer_queue",
            "endpoint": status_api.auto_transfer_queue,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "查询入库自动字幕处理队列",
        },
        {
            "path": "/prepare_upload",
            "endpoint": upload_api.prepare_upload,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "上传字幕并生成匹配预览",
        },
        {
            "path": "/apply_upload",
            "endpoint": upload_api.apply_upload,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "应用字幕匹配结果并写入目标目录",
        },
        {
            "path": "/clear_subtitles",
            "endpoint": upload_api.clear_subtitles,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "清空选中目标视频的外挂字幕",
        },
        {
            "path": "/delete_subtitle",
            "endpoint": upload_api.delete_subtitle,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "删除单个已匹配外挂字幕",
        },
        {
            "path": "/restore_subtitle_backup",
            "endpoint": upload_api.restore_subtitle_backup,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "恢复智能调轴前的字幕备份",
        },
        {
            "path": "/ai_submit",
            "endpoint": owner.api_ai_submit,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "提交 AI 字幕生成任务",
        },
        {
            "path": "/ai_tasks",
            "endpoint": owner.api_ai_tasks,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "查询当前资源的 AI 字幕生成任务状态",
        },
        {
            "path": "/ai_cancel",
            "endpoint": owner.api_ai_cancel,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "取消 AI 字幕生成任务",
        },
        {
            "path": "/ai_restart",
            "endpoint": owner.api_ai_restart,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "重新生成 AI 字幕任务",
        },
        {
            "path": "/online_status",
            "endpoint": online_api.online_status,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "获取在线字幕源状态",
        },
        {
            "path": "/online_manual_links",
            "endpoint": online_api.online_manual_links,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "生成在线字幕站手动搜索链接",
        },
        {
            "path": "/online_search",
            "endpoint": online_api.online_search,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "搜索在线字幕",
        },
        {
            "path": "/online_search_provider",
            "endpoint": online_api.online_search_provider,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "搜索单个在线字幕源",
        },
        {
            "path": "/online_ai_submit",
            "endpoint": owner.api_online_ai_submit,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "提交在线外语字幕到 AI 翻译状态队列",
        },
        {
            "path": "/online_download_preview",
            "endpoint": online_api.online_download_preview,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "下载在线字幕并生成匹配预览",
        },
    ]
