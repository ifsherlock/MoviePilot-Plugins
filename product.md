# SubtitleManualUpload 模块化分拆

## 当前目标

参考 `subtitlemanualupload_module_split_plan.md`，将 `plugins.v2/subtitlemanualupload/__init__.py` 拆成清晰模块，主入口最终只保留 MoviePilot 插件生命周期、API 注册、事件入口和服务装配。

## 执行分支

`split/subtitlemanualupload-module-split`

## 计划文件

- `docs/plans/2026-06-29-subtitlemanualupload-module-split-phased-plan.md`
- `docs/plans/2026-06-29-subtitlemanualupload-module-split-progress.json`

## 阶段摘要

1. 仓库和基线准备。
2. 拆配置契约与语言纯函数。
3. 拆上传会话和压缩包安全边界。
4. 拆媒体目标解析和字幕枚举。
5. 拆字幕写入、删除、恢复和历史操作。
6. 拆 AI 联动与在线外语 AI 编排。
7. 拆自动入库队列并收缩主入口。
8. 前端 API 合同、构建和最终审计。

## 约束

- 不重写匹配算法。
- 不改前端 API endpoint 名称。
- 不删除 `online_subtitle.py` 兼容入口。
- 不自动 push、merge 或发布。
- 计划文档和进度账本默认作为本地执行材料，不提交到 GitHub，除非用户明确要求。
