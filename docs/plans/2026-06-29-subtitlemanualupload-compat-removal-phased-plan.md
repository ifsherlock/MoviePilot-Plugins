# SubtitleManualUpload compat.py 完全移除计划

## 目标

彻底移除 `plugins.v2/subtitlemanualupload/compat.py` 以及仅为动态挂载旧私有方法而存在的 `compat_core.py`、`compat_services.py`。完成后 `SubtitleManualUpload` 不再继承 `SubtitleManualUploadCompatMixin`，运行时代码不再通过 owner 的旧 `_xxx` 兼容入口互相回调，领域能力由明确的 API helper、服务、纯函数或构造参数承载。

## 规格评审

- Ready: yes.
- 阻塞决策: 无。用户明确确认前一轮建议都是针对 `compat.py` 的拆解迁移，并要求生成详尽执行计划，包含真实浏览器测试方案。
- 漂移风险: 当前工作区有本地计划草稿、`product.md`、代码审查 Markdown、zip 包等未提交内容。执行前必须只基于源码和公开文档创建清晰分支/提交边界，不得把本地计划草稿、测试 IP、登录态、zip 产物提交。
- 任务级别: L。原因是工作跨 API helper、自动入库、目标解析、字幕写入、AI/在线字幕、动态兼容安装、测试和真实浏览器验收，超过 10 个可验证工作单元。

## 来源文件

- `product.md`
- `docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-phased-plan.md`
- `docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-progress.json`
- `scripts/subtitlemanualupload_compat_inventory.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `plugins.v2/subtitlemanualupload/compat.py`
- `plugins.v2/subtitlemanualupload/compat_core.py`
- `plugins.v2/subtitlemanualupload/compat_services.py`
- `plugins.v2/subtitlemanualupload/api/*.py`
- `plugins.v2/subtitlemanualupload/auto_transfer.py`
- `plugins.v2/subtitlemanualupload/online_ai.py`
- `plugins.v2/subtitlemanualupload/autosub_bridge.py`
- `plugins.v2/subtitlemanualupload/subtitle_writer.py`
- `plugins.v2/subtitlemanualupload/subtitle_history.py`
- `plugins.v2/subtitlemanualupload/target_resolver.py`
- `plugins.v2/subtitlemanualupload/upload_session.py`
- `plugins.v2/subtitlemanualupload/subtitle_language.py`
- `plugins.v2/subtitlemanualupload/online_subtitle.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`
- `tests/test_subtitlemanualupload_tongwen.py`
- `tests/test_timeline_fixer.py`
- `tests/test_autosubv3_cancel.py`

## 执行规则

- 开始前创建或确认专用分支：`codex/subtitlemanualupload-compat-removal`。
- 开始前运行 smoke check，并记录当前 inventory、测试和构建状态。
- 每个 work unit 只做当前单元，不顺手重构无关功能。
- 每个 work unit 验证通过后提交，并把 commit hash 记录到 progress JSON。
- 验证失败不得提交。
- 不自动 push、merge、amend。
- 不提交本地计划草稿、zip 包、测试截图、登录态、token、cookie、内网地址清单或运行日志全文。
- 阶段验收通过后自动进入下一阶段，不等待用户确认。
- 执行 agent 只能更新 progress JSON 中的 `status`、`verification`、`commit`、`decision_log`、`turn_log`、`residual_risk` 字段，不得改任务定义、验收标准或阶段边界。

## 进度文件

`docs/plans/2026-06-29-subtitlemanualupload-compat-removal-progress.json`

## 基线 smoke check

PowerShell:

```powershell
$env:PYTHONPATH='.'
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_subtitlemanualupload_cache.py tests/test_subtitlemanualupload_online.py tests/test_subtitlemanualupload_tongwen.py tests/test_timeline_fixer.py tests/test_autosubv3_cancel.py
```

前端构建:

```powershell
$env:PATH='C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' build
```

兼容层 inventory:

```powershell
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/subtitlemanualupload_compat_inventory.py --details
```

Hard baseline:

- Focused pytest exits 0.
- Vite build exits 0.
- Inventory output records `compat.py` current method count, source reference count, dynamic install references, and test reference count.
- `git status --short` is inspected before staging.

## 当前结构观察

- `compat.py` 当前约 256 行、22 个显式方法，其中 11 个是纯代理方法。
- `compat.py` 仍通过 `install_compat_core_methods`、`install_compat_service_factories`、`install_compat_archive_methods`、`install_legacy_service_delegates` 动态挂载旧私有入口。
- 当前 inventory 摘要显示 `source_referenced_count` 仍非零；在删除前必须先让源码引用归零，并让 inventory 排除 `compat.py` 自身内部调用造成的假阳性。
- `api/ai_api.py`、`api/online_api.py`、`api/upload_api.py`、`api/timeline_api.py` 仍调用 `_target_ids_from_body`、`_locked_target_ids_from_body`、`_filter_unlocked_target_ids`、`_ensure_target_not_locked`、`_results_from_body` 等 request helper。
- `auto_transfer.py`、`online_ai.py`、`subtitle_writer.py`、`subtitle_history.py`、`target_resolver.py` 仍通过 owner 回调若干 `_xxx` 方法。
- 上一轮真实 Chrome 测试已证明 `字幕匹配 v0.1.71/0.1.72` 的资源列表、搜索、外挂字幕展开、在线搜索、在线预览和 AI 状态链路可用；本计划必须把这些路径固化为最终浏览器验收。

## 目标架构

```text
MoviePilot
  -> SubtitleManualUpload.__init__.py
       - plugin metadata
       - lifecycle / config / events
       - service registry
       - API route registration
       - no compat mixin inheritance

  -> api/request_helpers.py
       - parse target ids, locked ids, selected results, online keywords
       - owns request/body normalization that is endpoint-specific

  -> target_resolver.py / subtitle_writer.py / upload_session.py
       - own target cache, subtitle inventory, session load, write operation helpers
       - accept explicit dependencies instead of calling owner._compat_alias()

  -> auto_transfer.py / online_ai.py / autosub_bridge.py
       - receive explicit callbacks or service objects
       - no hidden dependency on compat.py

  -> compat.py / compat_core.py / compat_services.py
       - deleted
```

## 数据和依赖流

```text
API request
  -> api/*_api.py
  -> api/request_helpers.py
  -> domain service method
  -> owner._ok(response)

Auto transfer event
  -> SubtitleManualUpload event handler
  -> AutoTransferService(callbacks/services)
  -> target_resolver / online_subtitle / subtitle_writer / autosub_bridge

Browser test
  -> visible Chrome login by user
  -> Playwright connectOverCDP
  -> UI operations only
  -> network listener records plugin endpoint 200s
  -> no token/cookie/localStorage inspection
```

## Phase 1: Inventory 和删除门禁加固

### 目标

让 inventory 成为后续删除的唯一量化门禁，能区分运行时代码引用、测试引用、`compat.py` 内部自引用、动态安装入口和可删除候选。

### 实现面

- `scripts/subtitlemanualupload_compat_inventory.py`
- `plugins.v2/subtitlemanualupload/compat.py`
- `plugins.v2/subtitlemanualupload/compat_core.py`
- `plugins.v2/subtitlemanualupload/compat_services.py`
- `tests/test_subtitlemanualupload_cache.py`

### Work units

1.1 加固 inventory 分类。

- 排除 `compat.py` 自身内部调用造成的 source hit。
- 单独统计 `compat_core.py` 和 `compat_services.py` 的动态挂载方法名。
- 输出 `runtime_refs`、`test_refs`、`dynamic_installs`、`delete_blockers`。
- 失败模式: inventory 把内部自引用当作运行时依赖，导致永远无法删除。验收要证明内部自引用不计入 source blocker。

1.2 为删除门禁加测试。

- 增加一个轻量测试，验证 inventory 输出 JSON 可解析，且至少包含 `runtime_refs`、`dynamic_installs`、`delete_blockers`。
- 不要求此阶段 blocker 为 0，只要求分类可信。
- 失败模式: 后续执行者手工判断 compat 状态，遗漏动态挂载入口。验收要用脚本输出阻止这种漂移。

### Acceptance

- `scripts/subtitlemanualupload_compat_inventory.py --details` exits 0 and prints valid JSON.
- 输出中 `runtime_refs` 不包含 `compat.py` 自身行号。
- 输出中能列出 `compat_core.py` / `compat_services.py` 动态安装的旧私有方法。
- Focused pytest smoke check exits 0。

### Commit boundary

提交 inventory 加固和测试，记录 commit hash。

## Phase 2: API request helper 去 compat 化

### 目标

API handler 不再调用 owner 上的 `_target_ids_from_body`、`_locked_target_ids_from_body`、`_filter_unlocked_target_ids`、`_ensure_target_not_locked`、`_results_from_body`、`_online_keywords`。

### 实现面

- 新增 `plugins.v2/subtitlemanualupload/api/request_helpers.py`
- `plugins.v2/subtitlemanualupload/api/ai_api.py`
- `plugins.v2/subtitlemanualupload/api/online_api.py`
- `plugins.v2/subtitlemanualupload/api/upload_api.py`
- `plugins.v2/subtitlemanualupload/api/timeline_api.py`
- `plugins.v2/subtitlemanualupload/compat.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`

### Work units

2.1 提取目标 ID 和锁定解析。

- 新 helper 提供 `target_ids_from_body(body, normalize_text)`、`locked_target_ids_from_body(body, normalize_text)`、`filter_unlocked_target_ids(...)`、`ensure_target_not_locked(...)`。
- API 模块直接导入 helper，不再经 owner 调用。
- 保持错误状态码 423 和错误文案不变。
- 失败模式: 锁定目标被批量操作绕过。验收必须覆盖锁定目标跳过和单目标 423。

2.2 提取 selected results 和在线搜索关键词。

- 新 helper 提供 `results_from_body(body)`。
- 在线关键词 helper接收 `manual_keyword`、`media`、`targets`、`scope` 和 `build_search_keywords`，不依赖 owner。
- 失败模式: 手动关键词优先级变化，导致在线字幕搜索命中变差。验收必须覆盖手动关键词在第一位。

2.3 删除 compat.py 中对应 API helper。

- 当源码不再引用这些方法后，从 `compat.py` 删除对应显式方法。
- 若测试仍直接调用旧私有方法，迁移测试到新 helper 或通过 API 路由测试。
- 失败模式: 旧测试继续绑定私有方法，让兼容债务伪装成需求。验收要让 inventory 对这些方法无 runtime blocker。

### Acceptance

- `rg -n "_target_ids_from_body|_locked_target_ids_from_body|_filter_unlocked_target_ids|_ensure_target_not_locked|_results_from_body|_online_keywords" plugins.v2/subtitlemanualupload -g "*.py"` 不再显示 `owner.` 或 `SubtitleManualUploadCompatMixin` 中的方法定义。
- API route contract 仍为 23 个端点，路径、方法、auth、summary 不变。
- Focused pytest smoke check exits 0。
- Inventory 中 API request helper 类 delete blocker 为 0。

### Commit boundary

提交 API request helper 迁移，记录 commit hash。

## Phase 3: 目标缓存、字幕库存和写入 helper 归位

### 目标

把 `_remember_targets`、`_subtitle_files_for_target`、`_embedded_subtitle_tracks_for_target`、`_target_has_chinese_subtitle`、`_auto_target_has_chinese_subtitle`、`_load_session`、`_timeline_cache_dir` 从兼容层迁回真实服务。

### 实现面

- `plugins.v2/subtitlemanualupload/target_resolver.py`
- `plugins.v2/subtitlemanualupload/subtitle_writer.py`
- `plugins.v2/subtitlemanualupload/subtitle_history.py`
- `plugins.v2/subtitlemanualupload/upload_session.py`
- `plugins.v2/subtitlemanualupload/timeline_tasks.py`
- `plugins.v2/subtitlemanualupload/compat_services.py`
- `plugins.v2/subtitlemanualupload/compat.py`
- `tests/test_subtitlemanualupload_cache.py`

### Work units

3.1 目标记忆缓存归到目标解析服务。

- 为目标缓存建立唯一 owner：优先 `MediaTargetResolver` 或独立 `TargetEntryCache`。
- `subtitle_history.py` 和 `target_resolver.py` 不再调用 `owner._remember_targets`。
- 失败模式: 历史页或资源详情拿不到刚加载过的 target entry。验收必须覆盖搜索后详情、历史回填、目标缓存容量淘汰。

3.2 字幕库存和中文字幕判断归到 subtitle inventory / language helper。

- 让调用方直接使用 `_subtitle_inventory()` 或注入的 inventory 服务。
- `target_has_chinese_subtitle` 成为 `subtitle_language.py` 或 inventory 纯函数。
- 失败模式: 入库自动处理误以为已有中文字幕或漏判内嵌中文字幕。验收必须覆盖外挂中文、内嵌中文、非中文外挂三种。

3.3 session 和 timeline cache 路径归到服务。

- `SubtitleWriter` 不再通过 owner `_load_session` / `_timeline_cache_dir`。
- `UploadSessionService.load_session` 和 timeline task store 接收 `data_path` / `normalize_text`。
- 失败模式: 上传预览可生成但写入阶段找不到 session。验收必须覆盖 prepare -> apply 的 session 读取路径，但不要在真实线上浏览器测试中点击写盘。

3.4 删除 compat.py 中对应方法和动态服务工厂残留。

- 删除已经没有 runtime/test 引用的显式方法。
- 如果 `compat_services.py` 只剩为这些方法服务的动态安装函数，同步删除对应安装块。

### Acceptance

- `rg -n "_remember_targets|_subtitle_files_for_target|_embedded_subtitle_tracks_for_target|_target_has_chinese_subtitle|_auto_target_has_chinese_subtitle|_load_session|_timeline_cache_dir" plugins.v2/subtitlemanualupload -g "*.py"` 不再显示 `owner.` 兼容调用或 `compat.py` 方法定义。
- 自动入库中文跳过、目标缓存、上传 session、调轴缓存相关测试通过。
- Focused pytest smoke check exits 0。
- Inventory 中本阶段方法 delete blocker 为 0。

### Commit boundary

提交目标/字幕/会话迁移，记录 commit hash。

## Phase 4: 自动入库、在线 AI 和写入操作去 owner 私有回调

### 目标

`auto_transfer.py`、`online_ai.py`、`autosub_bridge.py`、`subtitle_writer.py` 不再依赖兼容层的 `_auto_media_for_entry`、`_is_chinese_transfer_media`、`_suggest_target`、`_auto_fill_missing_targets`、`_build_destination_name`、`_build_write_operations`、`_is_chinese_language_suffix`、`_auto_subtitle_sort_key`、`_normalize_online_download_name`。

### 实现面

- `plugins.v2/subtitlemanualupload/auto_transfer.py`
- `plugins.v2/subtitlemanualupload/online_ai.py`
- `plugins.v2/subtitlemanualupload/autosub_bridge.py`
- `plugins.v2/subtitlemanualupload/subtitle_writer.py`
- `plugins.v2/subtitlemanualupload/subtitle_language.py`
- `plugins.v2/subtitlemanualupload/upload_session.py`
- `plugins.v2/subtitlemanualupload/target_resolver.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`

### Work units

4.1 自动入库媒体识别和中文判断显式化。

- `AutoTransferService` 构造参数接收媒体识别服务或函数集合，而不是 owner `_xxx`。
- 保持旧策略 alias 迁移逻辑不变。
- 失败模式: 中文媒体跳过策略失效，自动入库误触发在线搜索/AI。验收必须覆盖中文媒体跳过和 legacy strategy alias。

4.2 目标建议和批量补全显式化。

- 自动入库、在线 AI、上传预览都直接调用 `target_resolver` 的纯函数/服务方法。
- 不通过 `owner._suggest_target` / `owner._auto_fill_missing_targets`。
- 失败模式: 剧集包字幕无法自动匹配到正确集数。验收必须覆盖整季包和单集字幕提示。

4.3 写入操作和目标文件名生成显式化。

- `SubtitleWriter` 拥有或直接导入 `build_destination_name`、`build_write_operations`。
- 其它模块调用 writer 服务，不再调用 owner `_build_*`。
- 失败模式: 语言后缀、双语后缀或覆盖备份策略变化。验收必须覆盖 `.eng.srt`、双语后缀、备份/恢复、已有字幕覆盖保护。

4.4 自动字幕排序和在线下载名规范化显式化。

- `auto_subtitle_sort_key` 由 `subtitle_language.py` 或 AutoTransfer 配置对象直接提供。
- `normalize_online_download_name` 由 `upload_session.py` 直接提供。
- 失败模式: 自动入库选择了低优先级语言/格式，或在线压缩包扩展名误判。验收必须覆盖语言优先级、格式优先级、压缩包真实格式识别。

4.5 删除 compat.py 中对应方法。

- 删除本阶段所有显式方法。
- 更新 tests，避免直接调用旧私有入口。

### Acceptance

- `rg -n "_auto_media_for_entry|_is_chinese_transfer_media|_suggest_target|_auto_fill_missing_targets|_build_destination_name|_build_write_operations|_is_chinese_language_suffix|_auto_subtitle_sort_key|_normalize_online_download_name" plugins.v2/subtitlemanualupload -g "*.py"` 不再显示 `owner.` 兼容调用或 `compat.py` 方法定义。
- Auto-transfer、online、writer 相关测试通过。
- Focused pytest smoke check exits 0。
- Inventory 中本阶段方法 delete blocker 为 0。

### Commit boundary

提交自动入库/在线 AI/写入迁移，记录 commit hash。

## Phase 5: 动态 compat_core / compat_services 消除

### 目标

删除通过 `install_compat_core_methods`、`install_compat_service_factories`、`install_compat_archive_methods`、`install_legacy_service_delegates` 动态挂载的方法，把仍然必要的能力移到显式模块、显式方法或服务注册表。

### 实现面

- `plugins.v2/subtitlemanualupload/compat_core.py`
- `plugins.v2/subtitlemanualupload/compat_services.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `plugins.v2/subtitlemanualupload/config_schema.py`
- `plugins.v2/subtitlemanualupload/upload_session.py`
- `plugins.v2/subtitlemanualupload/subtitle_writer.py`
- `plugins.v2/subtitlemanualupload/target_resolver.py`
- `plugins.v2/subtitlemanualupload/online_subtitle.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`

### Work units

5.1 服务工厂显式化。

- 把 `_local_media_catalog()`、`_target_resolver()`、`_subtitle_writer()`、`_upload_session_service()`、`_auto_transfer_service()`、`_autosub_bridge()` 等工厂从动态安装变成 `SubtitleManualUpload` 的显式方法或一个轻量 service registry。
- 失败模式: 多个服务实例持有不同缓存，形成第二套事实来源。验收必须覆盖同一 owner 生命周期内服务复用。

5.2 core helper 显式化。

- 把 normalize/safe int/response helper/TMDB helper/rate limit helper 等动态安装方法迁到明确归属。
- 对确实属于插件壳的保留在 `__init__.py`，但必须是显式方法，不再由 compat 模块安装。
- 失败模式: 错误被宽泛默认值吞掉。验收要保留原有错误返回和日志行为。

5.3 archive helper 显式化或归入 `upload_session.py`。

- 压缩包解包、RAR/7Z 工具检测由 `upload_session.py` 或专门 archive helper 承担。
- 失败模式: ZIP/RAR/7Z 预览路径行为不一致。验收必须覆盖 ZIP 和 7Z/RAR 可用性降级提示。

5.4 legacy service delegate 清零。

- `LEGACY_INSTANCE_SERVICE_DELEGATES` 不再需要时删除。
- 若还有旧测试直接调用 delegate，迁移到服务或 API 路由。

### Acceptance

- `rg -n "install_compat_|LEGACY_INSTANCE_SERVICE_DELEGATES|SubtitleManualUploadCompatMixin|from \\.compat" plugins.v2/subtitlemanualupload -g "*.py"` 无运行时代码命中。
- `compat_core.py` 和 `compat_services.py` 没有被源码导入。
- Focused pytest smoke check exits 0。
- Inventory 显示 dynamic install blocker 为 0。

### Commit boundary

提交动态兼容安装移除，记录 commit hash。

## Phase 6: 删除 compat.py 并收紧测试合同

### 目标

删除 `compat.py`、`compat_core.py`、`compat_services.py`，让 inventory 变成删除已完成的审计工具或同步删除该脚本。

### 实现面

- `plugins.v2/subtitlemanualupload/compat.py`
- `plugins.v2/subtitlemanualupload/compat_core.py`
- `plugins.v2/subtitlemanualupload/compat_services.py`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `scripts/subtitlemanualupload_compat_inventory.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`

### Work units

6.1 删除 mixin 继承和 compat 文件。

- `SubtitleManualUpload` 直接继承 `_PluginBase`。
- 删除 `from .compat import SubtitleManualUploadCompatMixin`。
- 删除 `compat.py`、`compat_core.py`、`compat_services.py`。
- 失败模式: import 时才发现动态方法缺失。验收必须包含 import/route contract 测试。

6.2 重写或删除 compat inventory 脚本。

- 如果删除后仍保留脚本，则它应报告 compat 文件不存在且状态为 `removed`。
- 如果删除脚本，则同步删除引用它的测试/文档。
- 失败模式: 计划/测试继续指向不存在工具。验收必须搜索无 stale 路径。

6.3 私有入口测试迁移。

- 所有测试只允许验证公开 API、服务对象或纯函数，不再直接验证 compat 私有入口。
- 失败模式: 测试仍鼓励未来恢复兼容壳。验收必须搜索 `CompatMixin` 和被删除 `_xxx` 名称。

### Acceptance

- `Test-Path plugins.v2/subtitlemanualupload/compat.py` 为 `False`。
- `rg -n "compat.py|SubtitleManualUploadCompatMixin|install_compat_|from \\.compat|compat_core|compat_services" plugins.v2 tests scripts docs/plans -g "*.py" -g "*.md" -g "*.json"` 不出现需要修复的运行时或测试引用；历史计划文件中的文字引用可作为历史记录保留，但新计划/progress 不得把它们当作现存文件。
- `python -m pytest ...` focused smoke check exits 0。
- Vite build exits 0。
- Route contract 仍为 23 个端点。

### Commit boundary

提交 compat 文件删除，记录 commit hash。

## Phase 7: 真实浏览器验收和发布准备

### 目标

用真实登录后的 Chrome 会话验证插件关键路径，确认删除兼容层没有破坏线上 MoviePilot 插件行为。

### 实现面

- `plugins.v2/subtitlemanualupload/dist/`
- `plugins.v2/subtitlemanualupload/package.json`
- `plugins.v2/subtitlemanualupload/README.md`
- `plugins.v2/subtitlemanualupload/__init__.py`
- `package.json`
- `package.v2.json`
- `README.md`
- Chrome visible session with remote debugging
- `.tmp-test-data/` screenshots and local evidence, not committed

### Browser setup

1. 启动可见 Chrome，不使用 headless 让用户可以手动输入账号密码。

```powershell
$profile = Resolve-Path -LiteralPath '.tmp-test-data' | Select-Object -ExpandProperty Path
$userData = Join-Path $profile 'chrome-mp-profile'
New-Item -ItemType Directory -Force -Path $userData | Out-Null
$args = @('--remote-debugging-port=9222', "--user-data-dir=$userData", '--no-first-run', '--no-default-browser-check', 'https://mp.jaysherlock.top:5443/')
Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList $args
```

2. 用户在可见 Chrome 里登录后，执行 agent 通过 CDP 接管。

```powershell
$env:NODE_PATH='C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\.pnpm\node_modules'
@'
const { chromium } = require('C:/Users/jaysh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const page = browser.contexts().flatMap(c => c.pages()).find(p => p.url().includes('mp.jaysherlock.top'));
  console.log(page.url(), await page.title());
  await browser.close();
})();
'@ | & 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
```

3. 不读取 Cookie、LocalStorage、SessionStorage、账号、密码或 token。API 验证通过 UI 操作触发，并用 network listener 记录 endpoint、method、status。

### Browser test cases

7.1 登录和插件入口。

- 页面从登录后 dashboard 进入。
- 点击左侧「插件」。
- 找到 `字幕匹配` 卡片，版本号是新版本。
- 打开插件页面，确认「资源选择」「匹配历史」入口存在。
- 截图: `.tmp-test-data/mp-subtitle-plugin-entry.png`。
- 失败模式: 插件可安装但前端 remoteEntry 加载失败。验收必须检查 console error 和 requestfailed 为空或仅为非插件外部资源。

7.2 本地资源索引和搜索。

- 插件页面显示媒体/视频统计。
- 搜索 `百万英镑` 或一个当前库内稳定存在的电影名。
- 打开资源详情，看到至少一个本地目标。
- 截图: `.tmp-test-data/mp-subtitle-resource-selected.png`。
- 期望 API: `/status`、`/search`、`/targets` 由 UI 触发且返回 200。
- 失败模式: 目标缓存迁移后列表能搜到但详情无法解析目标路径。验收必须看到目标路径和目标数量。

7.3 外挂字幕和调轴状态。

- 点击「展开外挂字幕」。
- 页面显示已有外挂字幕列表、语言/文件名、调轴/恢复/删除按钮状态。
- 不点击「删除」「恢复」「写入字幕」。
- 期望 API: `/match_history` 或目标详情相关请求返回 200。
- 失败模式: 字幕库存 helper 迁移后无法列出已有外挂字幕。验收必须看到外挂字幕数量或明确空态。

7.4 在线字幕搜索。

- 点击「搜索此集在线字幕」。
- 自动搜索完成后显示 provider 状态。
- 期望 API: `/online_status`、`/online_manual_links`、`/online_search_provider` 返回 200。
- 验收 provider 至少包括已配置的 `射手网(伪)`、`OpenSubtitles`、`SubHD` 中可用项；若源站网络异常，页面必须显示可理解错误，不得静默失败。
- 截图: `.tmp-test-data/mp-subtitle-online-search.png`。

7.5 在线下载预览，不写盘。

- 选择一个在线字幕结果。
- 点击「下载并生成预览」。
- 页面进入匹配预览，显示“已解析 N 个字幕文件，自动匹配 M 个”或等价确认信息。
- 期望 API: `/online_download_preview` 返回 200。
- 禁止点击「写入字幕」。
- 截图: `.tmp-test-data/mp-subtitle-online-preview.png`。
- 失败模式: 下载成功但上传会话读取失败。验收必须看到预览项、语言后缀和目标文件名。

7.6 AI 状态只读检查。

- 关闭预览，点击 `AI：...` 状态按钮。
- 页面显示 AI 字幕生成状态和任务来源。
- 期望 API: `/ai_tasks` 返回 200。
- 禁止点击「重新生成」「提交 AI 翻译」。
- 截图: `.tmp-test-data/mp-subtitle-ai-status.png`。

7.7 响应式冒烟。

- 在 Chrome CDP 里依次设置 viewport: `1440x960`、`768x1024`、`390x844`。
- 每个 viewport 至少检查插件页面不出现明显横向滚动、主操作按钮可见、在线搜索弹窗不遮挡确认按钮。
- 截图: `.tmp-test-data/mp-subtitle-responsive-1440.png`、`...-768.png`、`...-390.png`。

### Browser acceptance

- 所有插件相关 UI 触发的 API 响应状态为 2xx。
- Console 中没有插件 JS runtime error。
- Request failures 不包含 `/api/v1/plugin/SubtitleManualUpload/` 或插件 `remoteEntry.js`。
- 页面截图存在并能证明入口、资源详情、在线搜索、在线预览、AI 状态。
- 测试过程中没有执行写盘、删除、恢复、重新生成、提交 AI 翻译。

### 发布准备

- 若浏览器验收通过，版本号提升一个 patch。
- 更新 `__init__.py`、插件 `package.json`、根 `package.json`、根 `package.v2.json`、根 `README.md`、插件 `README.md`。
- 生成本地 zip 安装包，但不提交 zip。
- 运行 focused pytest 和 Vite build。
- 提交版本更新。

### Commit boundary

提交浏览器验收后的版本更新和公开文档，记录 commit hash。截图和 zip 不提交。

## 总体验收

- `compat.py`、`compat_core.py`、`compat_services.py` 已删除，且运行时代码不再导入。
- `SubtitleManualUpload` 不再继承 compat mixin。
- 23 个插件 API 端点合同不变。
- Focused pytest smoke check exits 0。
- Vite build exits 0。
- 真实 Chrome 浏览器验收通过，并记录截图路径和 API 2xx 摘要。
- 版本号、版本历史、插件包版本号一致。
- Progress JSON 记录每个 work unit 的状态、验证证据、commit hash 和残余风险。

## Not In Scope

- 不重写字幕匹配算法。
- 不改插件前端主交互设计。
- 不改变现有 API endpoint 名称、方法、auth 或 response shape。
- 不删除 `online_subtitle.py` 兼容入口，除非另开计划确认依赖已清零。
- 不自动 push、merge、amend。
- 不提交 zip 包、截图、日志全文、登录态或本地测试资料。

## 决策记录

- Decision: 使用 L 级 phased plan。
  Reason: 涉及多个领域模块、动态兼容安装、测试迁移和真实浏览器验收，跨阶段执行更安全。
  Rejected: 单次大改删除 compat。风险是 import 才发现动态方法缺失，且难以定位行为回归。

- Decision: 先加固 inventory，再迁移代码。
  Reason: 当前 inventory 会把部分内部引用和动态挂载混在一起，不能作为删除门禁。
  Rejected: 直接按 rg 手工删除。风险是漏掉动态安装方法。

- Decision: 浏览器验收只做非写盘路径。
  Reason: 能覆盖在线搜索、预览、AI 状态和主要 API 链路，同时避免误删字幕或重启 AI 任务。
  Rejected: 在线上环境点击写入/删除/恢复。风险是破坏真实媒体库文件。

## /goal starter

```text
/goal Implement docs/plans/2026-06-29-subtitlemanualupload-compat-removal-phased-plan.md by following its execution ledger.

Each turn:
1. Read docs/plans/2026-06-29-subtitlemanualupload-compat-removal-progress.json, then the current task in the plan.
2. Run `git log --oneline -15` and the smoke check named in the plan; repair a broken state before starting new work.
3. Work only on the current work unit.
4. After verification passes: update the progress file status/evidence/log fields only, commit that unit, record the commit hash. Never commit on failed verification. Never push, merge, or amend.
5. When a phase's acceptance checks all pass, record it and continue to the next phase without asking for approval.

Done when compat.py, compat_core.py, and compat_services.py are removed, all acceptance checks and browser checks are proven, and residual risk is recorded.
```
