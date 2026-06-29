# SubtitleManualUpload 模块化分拆执行计划

## 目标

把 `plugins.v2/subtitlemanualupload/__init__.py` 从 7293 行的主业务聚合类，收缩为 MoviePilot 插件入口与 API 薄适配层。拆分完成后，插件入口应主要负责：

- 插件元数据、生命周期、配置加载和服务装配。
- `get_api()` 路由注册，API handler 只做请求解析和调用服务。
- `listen_transfer_complete()` 事件入口。
- `get_form()`、`get_page()`、`get_sidebar_nav()` 等 MoviePilot 框架入口。

首轮目标不是重写算法，而是按边界搬迁、补齐测试、保持前端 API 和现有行为兼容。完成后 `__init__.py` 目标体量为 1200-1800 行；若 `auto_transfer` 与 API 薄化完成良好，可进一步压到 800-1100 行。

## 来源文档

- `C:/Users/jaysh/Documents/Codex/2026-06-28/https-github-com-clone-fan-moviepilot/outputs/subtitlemanualupload_module_split_plan.md`
- `C:/Users/jaysh/Documents/moviepilot-plugins/docs/subtitlemanualupload/代码审查.md`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `plugins.v2/subtitlemanualupload/online_subtitles/`
- `plugins.v2/subtitlemanualupload/timeline_fixer.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`
- `tests/test_timeline_fixer.py`
- `tests/test_subtitlemanualupload_tongwen.py`

## 规格审查

执行就绪：是。

阻塞缺口：无。当前方向足够明确：做模块化分拆，不改前端接口，不重写匹配算法，不改变 MoviePilot 插件对外行为。

漂移风险：

- 当前工作区最初由 ZIP 展开，现已初始化为本地 Git 仓库并创建执行分支；远端跟踪 `origin/main`。
- `pytest` 当前不在 Codex bundled Python 中，需要执行前安装或使用已有项目环境。
- 计划文档、进度账本和 `product.md` 是本地执行材料，不应默认提交到 GitHub，除非用户明确要求。
- 前端 `Config.vue` 仍保留默认值兜底；后端拆出 `config_schema.py` 后必须避免后端默认值继续分散。

任务规模：L 级 phased plan。原因：涉及后端主类、配置、文件系统安全边界、AI 联动、自动入库、测试装载方式和前端 API 合同，天然跨阶段且超过 10 个可验证工作单元。

## 执行规则

- 当前执行分支：`split/subtitlemanualupload-module-split`。
- 开始实现前必须确认不在 `main` 分支：`git branch --show-current` 输出必须是 `split/subtitlemanualupload-module-split`。
- 开始实现前建立 clean-start commit；若只存在本地计划文档未跟踪变更，clean-start commit 可为空提交。
- 每个完成并验证通过的 work unit 单独提交，提交信息使用中文。
- 每次 `git add`、`git commit` 前必须运行 `git status --short --branch` 和实际 diff 检查，确认只包含该 work unit 的源码、测试或公开文档。
- 不要提交内部执行计划草稿、本地进度账本、用户本地测试 IP、账号、密码、Cookie、Token、AppSecret、构建产物、缓存或日志。
- 验证失败时不得提交。
- 不自动 push、merge、amend。合并回主分支必须由用户 review 后决定。
- 每个任务完成后只更新 progress 文件中的状态、证据、commit 和日志字段，不改任务定义或验收标准。
- 阶段验收全部通过后自动进入下一阶段，不等待用户确认。

## 进度文件

进度账本：`docs/plans/2026-06-29-subtitlemanualupload-module-split-progress.json`

执行者每轮必须先读进度账本，再读当前任务。进度账本是本地执行证据，不默认纳入源码提交。

## 基线 Smoke Check

实现前和每个阶段结束至少执行：

```powershell
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe' branch --show-current
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile plugins.v2/subtitlemanualupload/__init__.py
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q plugins.v2/subtitlemanualupload
```

若 `pytest` 不存在，先执行：

```powershell
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install pytest
```

安装依赖后执行定向测试：

```powershell
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_subtitlemanualupload_tongwen.py tests/test_subtitlemanualupload_online.py tests/test_subtitlemanualupload_cache.py tests/test_timeline_fixer.py -q
```

前端构建检查：

```powershell
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' --dir plugins.v2/subtitlemanualupload install
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' --dir plugins.v2/subtitlemanualupload build
```

## 实现面地图

### 现有核心文件

- `plugins.v2/subtitlemanualupload/__init__.py`：主插件类，当前包含生命周期、配置、API、缓存、目标解析、字幕解包、写盘、调轴任务、在线字幕下载预览、AI 联动、自动入库队列和历史操作。
- `plugins.v2/subtitlemanualupload/online_subtitle.py`：兼容导出层，当前由测试直接加载，不要第一轮删除。
- `plugins.v2/subtitlemanualupload/online_subtitles/service.py`：在线字幕搜索服务入口。
- `plugins.v2/subtitlemanualupload/online_subtitles/common.py`：在线字幕模型、关键词、匹配、网络客户端等公共逻辑。
- `plugins.v2/subtitlemanualupload/timeline_fixer.py`：智能调轴核心算法，已独立。
- `plugins.v2/subtitlemanualupload/tongwen.py`：繁转简工具，已独立。
- `plugins.v2/subtitlemanualupload/src/components/AppPage.vue`：前端主页面，当前 5419 行，本轮只做 API 兼容检查，不做组件化。
- `plugins.v2/subtitlemanualupload/src/components/Config.vue`：前端配置页，当前保留默认值兜底。

### 新增模块

```text
plugins.v2/subtitlemanualupload/
  config_schema.py
  subtitle_language.py
  upload_session.py
  target_resolver.py
  subtitle_writer.py
  subtitle_history.py
  autosub_bridge.py
  online_ai.py
  auto_transfer.py
```

### 边界约定

- `__init__.py` 可以持有 MoviePilot 框架对象、插件状态、API handler 和服务实例。
- `subtitle_language.py` 不读取插件状态，不依赖 MoviePilot。
- `config_schema.py` 提供唯一后端默认配置、枚举、归一化和表单构建。
- `upload_session.py` 只负责会话目录、上传/下载字节落地、ZIP/RAR/7Z 解包和 session JSON，不知道 MoviePilot DB。
- `target_resolver.py` 只负责把 MoviePilot 整理历史和事件转换为本地媒体目标，并枚举目标旁边可操作外挂字幕。
- `subtitle_writer.py` 负责构建写入操作、备份、原子替换、删除、恢复和调用调轴/繁简转换；它只能写入或删除目标视频同目录下经解析确认的字幕。
- `autosub_bridge.py` 是 AI字幕生成(联动版) 的适配器，只按当前目标视频路径过滤任务。
- `online_ai.py` 编排在线外语字幕下载、ASS/SSA 转 SRT、调轴后提交 AI，不直接搜索 provider。
- `auto_transfer.py` 负责入库自动字幕队列、限流、整季包缓存、自动搜索写入和 AI 兜底。

## 数据流

```text
MoviePilot API/Event
  -> SubtitleManualUpload.__init__.py
  -> target_resolver.MediaTargetResolver
  -> upload_session.UploadSessionService
  -> online_subtitles.OnlineSubtitleSearchService
  -> subtitle_language / subtitle_match selection helpers
  -> subtitle_writer.SubtitleWriter
       -> timeline_fixer.fix_subtitle_timeline
       -> tongwen.convert_subtitle_file_to_simplified
  -> autosub_bridge.AutoSubBridge / online_ai.OnlineAiService
  -> response payload / auto_transfer task state
```

## 阶段 0：仓库和基线准备

目标：确认执行分支、测试依赖和当前行为基线，为后续分拆提供回归保护。

涉及文件：

- `docs/plans/2026-06-29-subtitlemanualupload-module-split-progress.json`
- 测试环境，不修改业务源码。

任务：

### 0.1 确认分支和 clean-start

- 运行 `git branch --show-current`，确认分支为 `split/subtitlemanualupload-module-split`。
- 运行 `git status --short --branch`，确认只存在预期本地计划文档。
- 创建 clean-start commit；若没有可提交源码变更，使用空提交。

验收：

- `git branch --show-current` 输出 `split/subtitlemanualupload-module-split`。
- `git log --oneline -1` 显示中文 clean-start commit。
- progress 记录 commit hash。

### 0.2 建立测试基线

- 确认 Python 编译检查可运行。
- 若缺少 `pytest`，安装到 Codex bundled Python 或记录使用的替代 Python 环境。
- 执行字幕插件定向测试，记录失败项；若失败是环境依赖导致，记录阻断证据，不改源码绕过。

验收：

- `py_compile` 和 `compileall` 退出码为 0。
- `pytest tests/test_subtitlemanualupload_tongwen.py tests/test_subtitlemanualupload_online.py tests/test_subtitlemanualupload_cache.py tests/test_timeline_fixer.py -q` 已执行并记录退出码。
- 若 pytest 因缺少外部二进制或包失败，progress 记录具体缺口和后续处理方式。

阶段接受条件：

- 分支和 clean-start 已完成。
- 基线检查结果写入 progress。
- 继续进入阶段 1，不等待用户确认。

## 阶段 1：拆配置契约与语言纯函数

目标：先迁移低耦合纯逻辑，减少主类静态工具方法和配置重复风险。

涉及文件：

- `plugins.v2/subtitlemanualupload/config_schema.py`
- `plugins.v2/subtitlemanualupload/subtitle_language.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `plugins.v2/subtitlemanualupload/src/components/Config.vue`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_tongwen.py`

任务：

### 1.1 新建 `subtitle_language.py`

迁移或封装以下职责：

- `_normalize_language_suffix`
- `_language_suffix_from_filename`
- `_detect_language_profile`
- `_is_chinese_language_suffix`
- `_autosub_lang_from_suffix`
- `_auto_language_bucket`
- 语言优先级中用到的格式/语言归一化辅助函数。

保留兼容方法：`SubtitleManualUpload` 上原有同名方法仍可调用，但实现委托给新模块，避免一次性改动所有测试。

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/subtitle_language.py` 退出 0。
- 语言相关测试继续通过：`pytest tests/test_subtitlemanualupload_cache.py -q -k "language or bilingual or autosub_lang or suffix"`。
- `rg -n "_detect_language_profile|_language_suffix_from_filename|_normalize_language_suffix" plugins.v2/subtitlemanualupload/__init__.py` 显示主类只保留兼容委托或少量调用。

### 1.2 新建 `config_schema.py`

迁移或封装以下职责：

- 后端默认配置。
- provider、RAR、调轴、自动入库策略枚举。
- 配置归一化函数。
- `get_form()` 的 schema 构建。
- `init_plugin()` 使用的配置迁移逻辑中与字段归一化相关的部分。

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/config_schema.py` 退出 0。
- `SubtitleManualUpload.get_form()` 仍返回 `(form, default_config)`，默认字段包含 `online_providers`、`timeline_max_offset_seconds`、`rar_dependency_mode`、`opensubtitles_api_url`。
- `Config.vue` 的默认值与 `config_schema.py` 的默认配置无冲突；若前端保留兜底默认值，计划中记录它只是兜底，不作为后端事实源。

### 1.3 补齐/迁移配置和语言测试

- 将直接访问主类私有语言函数的测试逐步改为测试新模块，同时保留主类兼容方法的轻量回归测试。
- 增加默认配置一致性测试：后端默认配置必须覆盖前端配置页当前使用的关键字段。

验收：

- `pytest tests/test_subtitlemanualupload_tongwen.py tests/test_subtitlemanualupload_cache.py -q -k "language or config or strategy or suffix or bilingual"` 退出 0。
- `compileall` 退出 0。

阶段接受条件：

- 阶段 1 所有任务验收通过。
- 阶段 1 每个 work unit 都有提交 hash。
- 主类语言与配置职责减少，但 API 行为不变。

## 阶段 2：拆上传会话和压缩包安全边界

目标：把 ZIP/RAR/7Z、上传会话、在线下载预览共用的解包入口拆出，补上资源上限，降低压缩包风险。

涉及文件：

- `plugins.v2/subtitlemanualupload/upload_session.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `tests/test_subtitlemanualupload_cache.py`

任务：

### 2.1 新建 `upload_session.py`

迁移或封装：

- `_get_session_root`
- `_cleanup_old_sessions`
- `_extract_subtitle_files`
- `_archive_suffix_from_content`
- `_normalize_online_download_name`
- `_write_session`
- `_load_session`

主类保留兼容委托。

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/upload_session.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "extract or archive or online_download_name or session or 7z or rar"` 退出 0。

### 2.2 拆 RAR/7Z 工具检测和执行器

迁移或封装：

- `_rar_tool`
- `_sevenzip_tool`
- `_rar_python_available`
- `_rarfile_module`
- `_run_archive_command`
- `_list_rar_members`
- `_read_rar_member`
- `_extract_rar_subtitle_files_with_rarfile`
- `_extract_rar_subtitle_files`
- `_extract_7z_subtitle_files`
- `_extract_command_archive_subtitle_files`

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "rar or 7z or archive"` 退出 0。
- 代码中执行外部命令的超时仍显式存在，不能被静默吞掉。

### 2.3 增加解包资源限制

新增具名常量并在 `upload_session.py` 中执行：

- 单次上传/在线下载内容大小上限。
- 单个压缩包成员数量上限。
- 单成员解压大小上限。
- 总解压大小上限。
- 支持字幕文件数量上限。

错误必须通过 `ValueError` 或 `HTTPException` 暴露给调用方，不允许静默跳过整个包。

验收：

- 新增测试覆盖成员数量超限、总大小超限、单文件超限。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "archive or extract or limit"` 退出 0。

### 2.4 接回 API 预览入口

让 `api_prepare_upload`、`api_online_download_preview`、`_download_online_results_to_uploads` 使用 `UploadSessionService`，前端请求/响应结构不变。

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "prepare_upload or online_download_preview or online_ai_submit"` 退出 0。
- `rg -n "api_prepare_upload|api_online_download_preview" plugins.v2/subtitlemanualupload/__init__.py` 显示 API handler 仍存在。

阶段接受条件：

- 所有解包路径走同一服务。
- 资源限制有测试。
- 阶段 2 每个 work unit 都有提交 hash。

## 阶段 3：拆媒体目标解析和字幕枚举

目标：把 MoviePilot 整理历史、入库事件、目标缓存、外挂/内嵌字幕枚举拆出，形成可复用的目标事实来源。

涉及文件：

- `plugins.v2/subtitlemanualupload/target_resolver.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `tests/test_subtitlemanualupload_cache.py`

任务：

### 3.1 新建 `target_resolver.py` 的本地目标模型

迁移或封装：

- `_build_entry_from_history`
- `_entries_from_transfer_event`
- `_transfer_event_paths`
- `_target_from_entry`
- `_targets_for_media`
- `_merge_seasons`
- `_media_type_text`
- `_poster_url`
- `_history_type_text`

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/target_resolver.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "transfer_event or target or media or merge_seasons"` 退出 0。

### 3.2 迁移本地资源缓存和搜索

迁移或封装：

- `_load_local_entries`
- `_refresh_local_cache`
- `_cache_status`
- `_persist_local_cache`
- `_restore_persisted_local_cache`
- `_group_entries_as_media`
- `_search_media_candidates`
- `_resolve_targets`
- `_cached_unlocked_targets`

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "cache or search or resolve_targets or local_entries"` 退出 0。
- 缓存文件路径仍位于插件 data path 下，不进入源码目录。

### 3.3 迁移外挂字幕枚举和内嵌字幕探测

迁移或封装：

- `_subtitle_files_for_target`
- `_embedded_subtitle_tracks_for_target`
- `_embedded_subtitle_language_suffix`
- `_embedded_subtitle_probe_cache_key`
- `_embedded_subtitle_track_is_usable`
- `_embedded_subtitle_sample_language_suffix`
- `_remove_ext_marks`

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "embedded or subtitle_files or existing_chinese"` 退出 0。
- 删除候选仍必须来自目标视频同目录和同名前缀枚举结果。

### 3.4 接回搜索与目标 API

让 `api_search`、`api_targets`、`api_match_history` 中的目标读取使用 `MediaTargetResolver`，响应结构不变。

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "api_search or api_targets or match_history"` 退出 0。
- 前端 `AppPage.vue` 中调用的 `/search`、`/targets`、`/match_history` 仍存在于 `get_api()`。

阶段接受条件：

- 主类不再直接承载媒体目标解析算法。
- 本地目标、外挂字幕、内嵌字幕探测都有定向测试。
- 阶段 3 每个 work unit 都有提交 hash。

## 阶段 4：拆字幕匹配、写盘、删除和历史操作

目标：把文件系统写入和删除边界从主插件类拆出，让所有字幕落盘、备份、恢复路径集中校验。

涉及文件：

- `plugins.v2/subtitlemanualupload/subtitle_writer.py`
- `plugins.v2/subtitlemanualupload/subtitle_history.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `tests/test_subtitlemanualupload_cache.py`

任务：

### 4.1 新建 `subtitle_writer.py`

迁移或封装：

- `_build_destination_name`
- `_build_write_operations`
- `_write_operations_to_disk`
- `_backup_subtitle_if_needed`
- `_subtitle_backup_path`
- `_maybe_convert_operation_to_simplified`
- `_timeline_result_blocks_auto_write`
- `_timeline_rejection_message`
- `_run_timeline_fix`
- `_existing_timeline_operations`
- `_run_existing_timeline_fix`

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/subtitle_writer.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "write_operations or apply_upload or timeline_fix_existing or backup"` 退出 0。

### 4.2 集中删除和恢复安全边界

迁移或封装：

- `api_clear_subtitles` 内的删除策略。
- `api_delete_subtitle` 内的单文件删除策略。
- `api_restore_subtitle_backup` 内的备份恢复策略。

API handler 可保留在主类，但只调用 writer/history service。

验收：

- 删除路径必须来自 `target_resolver` 枚举结果或历史签名校验结果。
- 新增或保留测试覆盖：非目标目录字幕不可删除、锁定目标不可删除、备份不存在时明确失败。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "clear_subtitles or delete_subtitle or restore"` 退出 0。

### 4.3 新建 `subtitle_history.py`

迁移或封装：

- `_match_history_signature`
- `_persist_match_history_cache`
- `_restore_persisted_match_history_cache`
- `_invalidate_match_history_cache`
- `_filter_match_history_items`
- 历史字幕调轴入口需要的历史目标和字幕解析。

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/subtitle_history.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "match_history or history or signature or timeline_fix_existing"` 退出 0。

### 4.4 接回上传写入 API

让 `api_apply_upload`、历史调轴、删除、恢复使用新 writer/history service；保持响应 payload 字段不变。

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "apply_upload or timeline_fix_existing or delete_subtitle or restore_subtitle_backup"` 退出 0。
- `api_apply_upload` 仍支持 `fix_timeline` 和高风险调轴确认参数。

阶段接受条件：

- 所有写、删、恢复逻辑集中在 writer/history 服务。
- 文件系统安全不变量有测试。
- 阶段 4 每个 work unit 都有提交 hash。

## 阶段 5：拆 AI 联动与在线外语 AI 编排

目标：把 AI字幕生成(联动版) 适配、在线外语字幕调轴后提交 AI 的编排从主类拆出。

涉及文件：

- `plugins.v2/subtitlemanualupload/autosub_bridge.py`
- `plugins.v2/subtitlemanualupload/online_ai.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_autosubv3_cancel.py`

任务：

### 5.1 新建 `autosub_bridge.py`

迁移或封装：

- `_autosub_plugin`
- `_autosub_status`
- `_autosub_task_summary`
- `_autosub_tasks_for_entries`
- `_submit_autosub_for_entries`
- `_cancel_autosub_for_entries`
- `_restart_autosub_for_entries`
- `_filter_restart_task_ids_by_targets`
- `_selected_external_subtitle_override_for_entries`

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/autosub_bridge.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py tests/test_autosubv3_cancel.py -q -k "ai_submit or ai_cancel or ai_restart or autosub"` 退出 0。
- 任务过滤仍按当前目标视频路径执行，不操作陌生任务。

### 5.2 新建 `online_ai.py`

迁移或封装：

- `_autosub_lang_from_suffix` 若未在阶段 1 完成。
- `_online_ai_candidate_items`
- `_load_pysubs2_file`
- `_convert_ass_to_ai_srt`
- `_ai_ready_prepared_uploads`
- `_prepare_online_ai_subtitle_overrides`
- `_submit_online_ai_translate`

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/online_ai.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "online_ai or online_ai_submit or ass_to_srt or low_confidence"` 退出 0。
- 在线外语字幕仍必须先调轴，通过后才提交 AI。

### 5.3 接回 AI API

让 `api_ai_submit`、`api_ai_tasks`、`api_ai_cancel`、`api_ai_restart`、`api_online_ai_submit`、`api_online_download_preview` 中的 AI 路径调用 bridge/online_ai 服务。

验收：

- `get_api()` 仍注册 `/ai_submit`、`/ai_tasks`、`/ai_cancel`、`/ai_restart`、`/online_ai_submit`、`/online_download_preview`。
- `pytest tests/test_subtitlemanualupload_cache.py tests/test_autosubv3_cancel.py -q -k "ai or online_ai"` 退出 0。

阶段接受条件：

- AI 插件交互集中在 `autosub_bridge.py`。
- 在线外语字幕 AI 编排集中在 `online_ai.py`。
- 阶段 5 每个 work unit 都有提交 hash。

## 阶段 6：拆自动入库队列并收缩主入口

目标：把自动入库后台任务、限流、整季包缓存、自动写入策略拆成独立生命周期服务，并最终整理主类。

涉及文件：

- `plugins.v2/subtitlemanualupload/auto_transfer.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `tests/test_subtitlemanualupload_cache.py`

任务：

### 6.1 新建 `auto_transfer.py` 队列服务

迁移或封装：

- `_transfer_auto_key`
- `_claim_transfer_auto_entries`
- `_auto_transfer_entry_key`
- `_auto_transfer_group_key`
- `_trim_auto_transfer_tasks_locked`
- `_enqueue_transfer_auto_entries`
- `_ensure_transfer_auto_worker`
- `_update_auto_transfer_task`
- `_claim_next_auto_transfer_batch`
- `_auto_wait_online_rate_limit`
- `_auto_transfer_rate_status`
- `_auto_transfer_queue_summary`
- `_auto_transfer_queue_snapshot`
- `_auto_transfer_queue_loop`
- `_process_transfer_auto_task_batch`
- `_process_transfer_auto_subtitles`

验收：

- `python -m py_compile plugins.v2/subtitlemanualupload/auto_transfer.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "auto_transfer_queue or rate_limit"` 退出 0。
- 后台线程可退出，`stop_service()` 能停止或标记服务不再处理新任务。

### 6.2 迁移自动搜索写入策略

迁移或封装：

- `_auto_search_keywords_for_entry`
- `_auto_search_providers`
- `_auto_search_write_subtitle`
- `_auto_search_and_write_entry`
- `_auto_submit_ai_for_entry`
- `_auto_process_transfer_entry`
- `_auto_process_transfer_group`
- `_auto_search_write_season_package`
- `_auto_write_from_season_cache`
- `_store_auto_season_package_cache`
- `_load_auto_season_package_cache`
- `_select_auto_subtitle_items`
- `_auto_write_prepared_uploads_for_entries`
- `_auto_prepared_items_for_targets`

验收：

- `pytest tests/test_subtitlemanualupload_cache.py -q -k "auto_transfer or auto_search or season_package or existing_chinese"` 退出 0。
- `online_source_only` 不提交 AI，`ai_source_only` 不搜索在线字幕，legacy strategy alias 仍正确迁移。

### 6.3 接回入库事件和队列 API

让 `listen_transfer_complete`、`api_auto_transfer_queue` 使用 `AutoTransferService`。

验收：

- `get_api()` 仍注册 `/auto_transfer_queue`。
- `pytest tests/test_subtitlemanualupload_cache.py -q -k "auto_transfer_queue or transfer_event"` 退出 0。

### 6.4 收缩 `__init__.py` 与服务装配

- `init_plugin()` 只读取配置、初始化状态、构造服务对象。
- `get_api()` 仅注册 endpoints。
- API handler 只解析请求体、锁定目标、调用服务、返回结果。
- 删除已迁移后不再使用的私有方法和重复常量。

验收：

- `__init__.py` 不超过 1800 行；若保留更多兼容委托，必须在 progress 记录原因。
- `python -m py_compile plugins.v2/subtitlemanualupload/__init__.py` 退出 0。
- `pytest tests/test_subtitlemanualupload_tongwen.py tests/test_subtitlemanualupload_online.py tests/test_subtitlemanualupload_cache.py tests/test_timeline_fixer.py tests/test_autosubv3_cancel.py -q` 退出 0。

阶段接受条件：

- 自动入库独立为服务。
- 主入口体量达到目标或有明确残余理由。
- 阶段 6 每个 work unit 都有提交 hash。

## 阶段 7：前端 API 合同、构建和最终审计

目标：确认前端无需改接口即可使用新后端；做最终结构审计和文档更新。

涉及文件：

- `plugins.v2/subtitlemanualupload/src/components/AppPage.vue`
- `plugins.v2/subtitlemanualupload/src/components/Config.vue`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `docs/subtitlemanualupload/代码审查.md` 可追加最终复审，不提交内部执行账本。

任务：

### 7.1 API 合同静态检查

- 列出前端调用的所有后端 API。
- 对照 `get_api()` 注册路径，确认没有缺失。
- 检查响应字段名是否仍满足前端读取路径。

验收：

- `rg -n "pluginBase|api\\.get|api\\.post|/online_|/ai_|/prepare_upload|/apply_upload|/targets|/search" plugins.v2/subtitlemanualupload/src/components/AppPage.vue` 的调用项全部能在 `get_api()` 中找到对应 endpoint。
- progress 记录 API 合同检查摘要。

### 7.2 前端构建检查

执行：

```powershell
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' --dir plugins.v2/subtitlemanualupload install
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' --dir plugins.v2/subtitlemanualupload build
```

验收：

- `pnpm build` 退出 0。
- 若构建产物 `dist/` 变化，按项目既有发布习惯决定是否提交；提交前必须确认不是临时构建产物禁区。

### 7.3 全量回归和结构审计

- 执行所有定向 Python 测试。
- 统计 Python 文件行数和 `__init__.py` 方法数。
- 检查是否存在重复事实源、隐藏兜底、宽泛吞错、路径误删风险。

验收：

- `pytest tests/test_subtitlemanualupload_tongwen.py tests/test_subtitlemanualupload_online.py tests/test_subtitlemanualupload_cache.py tests/test_timeline_fixer.py tests/test_autosubv3_cancel.py -q` 退出 0。
- `compileall` 退出 0。
- `__init__.py` 行数和职责摘要写入 progress。

### 7.4 最终提交边界检查

- 运行 `git status --short --branch`。
- 运行 `git diff --stat` 和相关 diff。
- 确认没有计划草稿、progress、本地缓存、构建临时文件、密钥或隐私配置进入暂存区。

验收：

- 最后一个源码提交 hash 记录在 progress。
- progress 记录残余风险和未提交本地执行材料。
- 不 push、不 merge。

阶段接受条件：

- 所有阶段任务完成。
- 所有验收命令有证据。
- progress final status 标记 complete。

## 不在范围内

- 不改前端交互和视觉布局。
- 不重写在线字幕 provider 匹配算法。
- 不删除 `online_subtitle.py` 兼容入口。
- 不把 `online_subtitles/common.py` 继续拆细；这可作为后续独立计划。
- 不迁移到 ChineseSubFinder。
- 不自动 push、merge 或发布插件新版本。

## 关键失败模式与处理

- 压缩包炸弹或超大在线下载：`upload_session.py` 必须在解包前和解包过程中按大小/数量限制失败，并把错误返回调用方。
- 删除陌生字幕文件：删除只能基于目标枚举或历史签名校验结果，不能直接信任请求 body 的任意路径。
- AI 任务误操作其他资源：`autosub_bridge.py` 必须按当前目标视频路径过滤 task。
- 自动入库后台线程失控：`auto_transfer.py` 必须可停止、可限流、可记录失败，不伪造成功。
- 配置默认漂移：后端事实源在 `config_schema.py`，前端默认值只是兜底。
- 循环导入：服务通过构造参数注入依赖，避免新模块互相 import 主插件类。

## 决策日志

| 决策 | 理由 | 拒绝方案 | 来源 |
|---|---|---|---|
| 采用 L 级 phased plan | 跨多个后端服务、测试和前端 API 合同，预计多轮执行 | 单层 checklist 容易丢阶段边界 | `spec-to-goal-plan` |
| 保留 API endpoint 名称 | 降低前端和 MoviePilot 插件注册风险 | 同步改前端接口 | 分拆方案、现有 `get_api()` |
| 主类保留兼容委托一段时间 | 减少测试和调用点一次性迁移风险 | 一次性删除所有私有方法 | 现有测试大量直接调用主类私有方法 |
| 先拆纯函数和文件系统边界 | 风险低且能建立服务边界 | 先拆自动入库大块 | 分拆方案与结构审查 |
| 计划和 progress 默认不提交 | 遵守本地 Git 规则，避免提交内部执行材料 | 把执行账本纳入每个源码提交 | AGENTS Git 规则 |

## /goal 启动语

```text
/goal Implement docs/plans/2026-06-29-subtitlemanualupload-module-split-phased-plan.md by following its execution ledger.

Each turn:
1. Read docs/plans/2026-06-29-subtitlemanualupload-module-split-progress.json, then the current task in the plan.
2. Run `git log --oneline -15` and the smoke check named in the plan; repair a broken state before starting new work.
3. Work only on the current work unit.
4. After verification passes: update the progress file status/evidence/log fields only, commit that unit, record the commit hash. Never commit on failed verification. Never push, merge, or amend.
5. When a phase's acceptance checks all pass, record it and continue to the next phase without asking for approval.

Done when every item in the plan is complete, every acceptance check is proven, and the progress file records final status and residual risk.

Stop and report if a product decision is missing, the plan conflicts with the latest direction, or the worktree holds unrelated changes that cannot be safely separated.
```
