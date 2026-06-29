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

## 后续计划：API 编排分拆与 compat 瘦身

新增计划文件：

- `docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-phased-plan.md`
- `docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-progress.json`

目标：

- 将 `__init__.py` 从胖 Controller 收缩为插件壳，只保留元信息、生命周期、配置初始化、事件入口、服务装配和 API 注册。
- 将 23 个插件 API 按 `status`、`catalog`、`timeline`、`upload`、`online`、`ai` 六个领域拆分到 `plugins.v2/subtitlemanualupload/api/`。
- 将 `compat.py` 从迁移兼容层瘦身为少量旧私有接口 alias；如果 inventory 证明没有必要兼容入口，则删除。

## 约束

- 不重写匹配算法。
- 不改前端 API endpoint 名称。
- 不删除 `online_subtitle.py` 兼容入口。
- 不自动 push、merge 或发布。
- 计划文档和进度账本默认作为本地执行材料，不提交到 GitHub，除非用户明确要求。

## 后续计划：compat.py 完全移除

新增计划文件：

- `docs/plans/2026-06-29-subtitlemanualupload-compat-removal-phased-plan.md`
- `docs/plans/2026-06-29-subtitlemanualupload-compat-removal-progress.json`

目标：

- 彻底删除 `compat.py`、`compat_core.py`、`compat_services.py`，让 `SubtitleManualUpload` 不再继承兼容 mixin。
- 将旧 `_xxx` 私有兼容入口迁移到 API request helpers、目标解析、字幕写入、上传会话、自动入库、在线 AI 等真实归属模块。
- 使用 inventory 脚本作为删除门禁，并在最后加入真实 Chrome 登录态浏览器验收。
