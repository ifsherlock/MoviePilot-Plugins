# SubtitleManualUpload 主入口瘦身拆分计划

## 结论先行

这不是 `compat.py` 兼容债务。`compat.py`、`compat_core.py`、`compat_services.py` 已经删除；本计划处理的是 `plugins.v2/subtitlemanualupload/__init__.py` 仍然偏厚的问题。

当前 `__init__.py` 约 1106 行，`SubtitleManualUpload` 类里仍有 90 多个方法。它现在承担了五类职责：

- MoviePilot 插件壳：插件元信息、生命周期、表单、路由、侧边栏、入库事件。
- 配置状态：`init_plugin`、`_save_config`、类变量/实例变量同步、缓存重置。
- 运行时通用 helper：文本规范化、哈希、JSON clone、TMDB payload、字幕语言、时间戳、上传文件判断。
- 压缩包/上传会话适配：RAR/7z 工具发现、成员读取、字幕抽取、session root/write/cleanup。
- 服务装配和旧内部 facade：`_subtitle_writer`、`_target_resolver`、`_auto_transfer_service`、`_online_ai_service` 及大量一行代理。

目标是把 `__init__.py` 收缩成插件壳，而不是再造兼容层。最终主入口只保留 MoviePilot 需要直接调用的稳定入口：元信息、`init_plugin`、`get_state`、`get_api`、`get_form`、`get_page`、`get_sidebar_nav`、`stop_service`、`listen_transfer_complete`，以及极少量服务注册入口。

## 来源和当前证据

- 当前文件：`plugins.v2/subtitlemanualupload/__init__.py`
- 当前行数：1106 行。
- 当前已存在模块边界：
  - `api/`：插件 API 编排已拆出。
  - `config_schema.py`：配置 schema 和规范化已拆出。
  - `upload_session.py`：上传会话与压缩包核心能力已拆出。
  - `target_resolver.py`：媒体目标解析、字幕库存、媒体元数据已拆出。
  - `subtitle_writer.py`：字幕写入、调轴、备份/恢复核心已拆出。
  - `subtitle_history.py`、`timeline_tasks.py`、`auto_transfer.py`、`online_ai.py`、`autosub_bridge.py`、`service_factories.py`：领域服务已存在。
- 当前可靠测试面：
  - `tests/test_subtitlemanualupload_cache.py`
  - `tests/test_subtitlemanualupload_online.py`
  - `tests/test_subtitlemanualupload_request_helpers.py`
  - `tests/test_subtitlemanualupload_tongwen.py`
  - `tests/test_timeline_fixer.py`
  - `tests/test_autosubv3_cancel.py`

## 范围

### In Scope

- 继续拆 `__init__.py`，减少主入口行数和方法数量。
- 把通用 helper、配置状态、服务注册、事件处理、AI/AutoSub facade 移到明确模块。
- 迁移测试引用，让测试优先验证公开 API、领域服务和纯函数，而不是继续绑定主入口私有方法。
- 保持所有 API endpoint、插件 ID、配置字段、前端页面入口、现有浏览器工作流不变。

### Out Of Scope

- 不重新设计字幕匹配算法。
- 不更改在线字幕 provider 的策略和排序。
- 不更改前端交互形态，除非测试发现现有行为被拆分破坏。
- 不恢复任何 `compat.py`、动态安装器、mixin 或 inventory 兼容层。
- 不自动 push、merge、发布或清理 Git 历史。

## 目标架构

```text
SubtitleManualUpload (__init__.py)
  -> plugin_metadata / MoviePilot hooks
  -> config_runtime.apply_config / build_save_payload
  -> service_registry.SubtitleManualUploadServices
  -> transfer_event_handler.handle_transfer_complete
  -> api.routes.build_api_routes

api/*
  -> explicit services from owner.services or existing service factory

domain modules
  -> runtime_helpers.py
  -> archive_adapters.py or upload_session.py extensions
  -> service_registry.py
  -> transfer_events.py
  -> online_ai.py / autosub_bridge.py direct ownership
```

主入口允许知道“有哪些服务”，但不应该知道 RAR 成员怎么读、TMDB payload 怎么拼、在线 AI 字幕 override 怎么构造、自动入库队列怎么 claim。

## 执行规则

- 建议分支：`codex/subtitlemanualupload-init-shell-slimming`
- 每个 verified work unit 单独提交。
- 提交前必须检查 `git status --short` 和实际 diff。
- 不提交 zip、截图、`.tmp-test-data/`、本地计划草稿、隐私配置。
- 不 push、merge、amend，除非用户明确要求。
- 执行者只能更新 progress JSON 的 status、verification、commit、turn_log、residual_risk 字段。

## Baseline Smoke

```powershell
$env:PYTHONPATH='.'
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest `
  tests/test_subtitlemanualupload_cache.py `
  tests/test_subtitlemanualupload_online.py `
  tests/test_subtitlemanualupload_tongwen.py `
  tests/test_timeline_fixer.py `
  tests/test_autosubv3_cancel.py
```

## Frontend Build Check

```powershell
$env:PATH='C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' build
```

工作目录：`plugins.v2/subtitlemanualupload`

## Phase 1: 建立主入口瘦身门禁

### 目标

先把 `__init__.py` 的剩余职责变成可度量 inventory，避免后续“感觉已经拆了”。

### 影响文件

- 新增 `scripts/subtitlemanualupload_init_inventory.py`
- 新增 `tests/test_subtitlemanualupload_init_inventory.py`
- 可能更新 `docs/plans/...progress.json`

### Work Units

1.1 新增 `__init__.py` inventory 脚本。

- 输出总行数、类方法数、MoviePilot hook 方法、纯 helper 方法、archive 方法、service factory 方法、一行 delegate 方法、事件/AI/AutoSub 方法。
- 输出每个方法的 source/test 引用位置。
- 输出 `delete_or_move_candidates`，但只作为审计，不自动改代码。

1.2 新增 inventory 测试。

- 断言脚本输出 JSON。
- 断言不存在 `compat.py`、`compat_core.py`、`compat_services.py`、`SubtitleManualUploadCompatMixin`。
- 断言 inventory 能识别当前主入口 method count 和 line count。

### Acceptance

- `python scripts/subtitlemanualupload_init_inventory.py --details` exits 0 and prints valid JSON.
- `pytest tests/test_subtitlemanualupload_init_inventory.py -q` exits 0.
- Baseline smoke exits 0.

### 失败模式

如果没有 inventory，后续可能把一行 delegate 留在主入口里，误以为已经完成。此阶段用脚本把剩余职责可视化。

### Commit Boundary

提交 inventory 门禁和测试。

## Phase 2: 拆配置运行态和生命周期初始化

### 目标

让 `init_plugin` 不再手写几十个字段赋值、类变量同步和缓存重置。

### 新模块建议

- `plugins.v2/subtitlemanualupload/config_runtime.py`

### 技术细节

新增函数或 dataclass：

- `apply_runtime_config(owner, normalized_config) -> None`
- `sync_class_runtime_config(owner_cls, owner) -> None`
- `reset_runtime_state(owner) -> None`
- `build_save_config_payload(owner) -> dict`

`init_plugin` 保留流程：

```python
normalized_config = normalize_plugin_config(...)
apply_runtime_config(self, normalized_config)
sync_class_runtime_config(type(self), self)
reset_runtime_state(self)
self._restore_persisted_local_cache()
self._restore_persisted_match_history_cache()
type(self)._archive_dependency_service(self._set_rar_dependency_status).prepare_rar_dependency()
```

`_save_config` 改为：

```python
self.update_config(build_save_config_payload(self))
```

### Work Units

2.1 提取配置赋值和类变量同步。

2.2 提取运行时缓存重置。

2.3 提取保存配置 payload。

### Acceptance

- `pytest tests/test_subtitlemanualupload_cache.py::test_init_plugin_normalizes_legacy_auto_transfer_strategy -q` exits 0.
- `pytest tests/test_subtitlemanualupload_cache.py::test_get_form_contains_default_config -q` exits 0, if exact node exists; otherwise run the nearest `get_form` config tests from `tests/test_subtitlemanualupload_cache.py`.
- `pytest tests/test_subtitlemanualupload_cache.py tests/test_subtitlemanualupload_online.py -q` exits 0.
- Inventory shows `init_plugin` line count reduced and `_save_config` no longer owns field-by-field payload construction.

### 失败模式

配置字段漏同步到 class variable 会破坏 classmethod helper 和服务工厂。验收必须覆盖 `init_plugin` 后 class/instance 值一致。

### Commit Boundary

提交配置运行态拆分。

## Phase 3: 拆通用 runtime helper

### 目标

把纯函数从插件类移到模块，减少测试对 `SubtitleManualUpload._xxx` 的依赖。

### 新模块建议

- `plugins.v2/subtitlemanualupload/runtime_helpers.py`

### 迁移对象

- `_ok`
- `_safe_int`
- `_normalize_text`
- `_hash_text`
- `_brief_ids`
- `_decode_preview_bytes`
- `_timestamp_iso`
- `_cache_loaded_at`
- `_json_clone`
- `_is_upload_file`
- `_poster_url`
- `_tmdb_detail_payload`
- `_tmdb_aliases`
- `_entry_path_is_valid`
- `_entry_filesystem_signature`
- `_entry_matches_keyword`
- `_is_stream_path`

### 技术细节

- 纯函数直接导出，服务工厂和测试改为 import 新模块。
- 需要 `settings`、`extract_title_aliases`、`stream_exts` 的 helper 不隐式读取 owner；通过参数注入。
- 如果某个 API 路由仍需要 owner 响应格式，路由应调用 `ok_response(data, message)`，不要再调用 `owner._ok`。

### Work Units

3.1 提取无外部依赖的纯 helper。

3.2 提取需要 settings/常量/函数注入的 helper。

3.3 迁移测试引用，删除主入口上的同名 private helper 或保留极少量过渡 wrapper。

### Acceptance

- `rg -n "SubtitleManualUpload\\._(safe_int|normalize_text|hash_text|json_clone|tmdb_aliases|tmdb_detail_payload)" tests -g "*.py"` 不再出现需要迁移的测试绑定。
- `pytest tests/test_subtitlemanualupload_request_helpers.py tests/test_subtitlemanualupload_cache.py -q` exits 0.
- Baseline smoke exits 0.
- Inventory shows runtime helper group no longer是主入口主要方法来源。

### 失败模式

把 helper 改成隐式读 owner 会制造新的第二套事实来源。所有 helper 都应通过参数表达依赖。

### Commit Boundary

提交 runtime helper 拆分。

## Phase 4: 拆压缩包和上传会话适配层

### 目标

让主入口不再知道 RAR/7z 工具、命令执行、成员列表、成员读取和压缩包字幕抽取细节。

### 影响模块

- `upload_session.py`
- 新增可选 `archive_adapters.py`
- `service_factories.py`
- `tests/test_subtitlemanualupload_cache.py`

### 技术细节

优先扩展 `upload_session.py` 中已有的 `ArchiveDependencyService` 和 extraction 函数。如果函数组合太长，新增：

```python
class ArchiveSubtitleExtractor:
    def extract_subtitle_files(upload_name, raw_bytes, session_dir) -> list[dict]
```

`SubtitleManualUpload` 不再暴露：

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
- `_extract_subtitle_files`

`UploadSessionService` 或 extractor 接收明确依赖：

- subtitle/archive extension sets
- hash function
- decode function
- resource limits
- archive dependency service
- logger

### Work Units

4.1 新增 archive extractor 或扩展 UploadSessionService。

4.2 更新 service factory 注入，移除 owner archive private callback。

4.3 迁移压缩包测试到 `upload_session.py`/extractor。

### Acceptance

- `rg -n "_extract_rar_subtitle_files|_extract_7z_subtitle_files|_run_archive_command|_list_rar_members|_read_rar_member" plugins.v2/subtitlemanualupload/__init__.py tests -g "*.py"` 不出现主入口方法定义或测试直接绑定。
- `pytest tests/test_subtitlemanualupload_cache.py -q` exits 0.
- Baseline smoke exits 0.

### 失败模式

RAR/7z 工具可用性和资源限制是安全边界，不能用宽泛 try/except 静默吞错。测试必须保留资源限制、路径穿越、防超限和缺工具提示。

### Commit Boundary

提交压缩包适配拆分。

## Phase 5: 拆服务注册和一行 delegate

### 目标

把 `_subtitle_writer()`、`_target_resolver()`、`_auto_transfer_service()` 等服务装配从主入口移到稳定 registry，并减少 `_xxx -> service.xxx` 一行代理。

### 新模块建议

- `plugins.v2/subtitlemanualupload/service_registry.py`

### 技术细节

新增：

```python
class SubtitleManualUploadServices:
    def __init__(self, owner): ...
    def upload_session(self): ...
    def subtitle_inventory(self): ...
    def writer(self): ...
    def history(self): ...
    def target_resolver(self): ...
    def auto_transfer(self): ...
    def online_ai(self): ...
    def autosub_bridge(self): ...
```

主入口保留：

```python
@property
def services(self) -> SubtitleManualUploadServices:
    ...
```

迁移方向：

- API modules 直接通过 `owner.services.writer()` 等获取服务。
- 测试优先 mock `owner.services` 或服务工厂，不再 mock 大量 `owner._xxx`。
- 只保留 MoviePilot 或外部插件真实会调用的入口；内部一行代理应删除。

### Work Units

5.1 建立 service registry，替换服务工厂 wrapper。

5.2 迁移 API modules 和 tests 的服务访问。

5.3 删除主入口一行 service delegate。

### Acceptance

- `rg -n "def _(filter_existing_local_entries|merge_local_entries_cache|restore_persisted_local_cache|start_background_cache_refresh|load_local_entries|group_entries_as_media|resolve_targets|match_history_items|timeline_task_for_target_id|autosub_status|get_session_root|write_operations_to_disk|auto_transfer_queue_summary)" plugins.v2/subtitlemanualupload/__init__.py` 无命中或仅保留有明确外部调用证据的方法。
- API route contract remains 23 endpoints: `pytest tests/test_subtitlemanualupload_cache.py::test_plugin_api_route_contract_is_stable -q` exits 0.
- `pytest tests/test_subtitlemanualupload_cache.py tests/test_subtitlemanualupload_online.py -q` exits 0.
- Baseline smoke exits 0.

### 失败模式

如果 API modules 和 services 同时维护两套访问方式，会形成新的事实来源。迁移后每项服务只能有一个装配入口：service registry。

### Commit Boundary

提交服务注册拆分。

## Phase 6: 拆入库事件和自动入库入口

### 目标

`listen_transfer_complete` 和 `stop_service` 保留为 MoviePilot hook，但实际解析事件、合并本地缓存、入队、日志应迁到事件处理模块或 `AutoTransferService`。

### 新模块建议

- `plugins.v2/subtitlemanualupload/transfer_events.py`

### 技术细节

新增：

```python
def handle_transfer_complete(owner, event, *, logger) -> dict:
    ...
```

或把事件解析能力合并进 `AutoTransferService`：

```python
service.handle_transfer_complete(event)
```

主入口只做：

```python
if not self.get_state():
    return
self.services.auto_transfer().handle_transfer_complete(event)
```

### Work Units

6.1 迁移入库事件解析和缓存合并。

6.2 迁移自动入库 stop/queue hook 测试。

### Acceptance

- `pytest tests/test_subtitlemanualupload_cache.py::test_listen_transfer_complete_uses_auto_transfer_service_directly -q` exits 0, or renamed equivalent test exits 0.
- `pytest tests/test_subtitlemanualupload_cache.py::test_auto_transfer_queue_stop_service_marks_pending_queue_stopped -q` exits 0.
- `rg -n "def listen_transfer_complete|def stop_service" plugins.v2/subtitlemanualupload/__init__.py` 仍存在，但方法体只做 hook gate 和 delegate。
- Baseline smoke exits 0.

### 失败模式

入库事件可能重复触发。去重、批处理和日志必须仍由同一服务维护，不能在主入口和服务里各做一次。

### Commit Boundary

提交入库事件拆分。

## Phase 7: 拆在线 AI / AutoSub facade

### 目标

把主入口底部 `_submit_online_ai_translate`、`_submit_autosub_for_entries`、`_restart_autosub_for_entries` 等 facade 从 `__init__.py` 迁到 `online_ai.py` 和 `autosub_bridge.py` 的直接调用边界。

### 技术细节

优先让 API modules 调用服务：

```python
owner.services.online_ai().submit_online_ai_translate(...)
owner.services.autosub_bridge().restart_autosub_for_entries(...)
```

迁移对象：

- `_online_ai_candidate_items`
- `_load_pysubs2_file`
- `_convert_ass_to_ai_srt`
- `_ai_ready_prepared_uploads`
- `_prepare_online_ai_subtitle_overrides`
- `_submit_online_ai_translate`
- `_submit_autosub_for_entries`
- `_cancel_autosub_for_entries`
- `_restart_autosub_for_entries`
- `_filter_restart_task_ids_by_targets`
- `_selected_external_subtitle_override_for_entries`

### Work Units

7.1 迁移 online AI helper 到 `OnlineAiService` 或纯函数。

7.2 迁移 AutoSub bridge facade 到 API/service 直接调用。

7.3 更新 tests，去除对主入口私有 AI/AutoSub facade 的依赖。

### Acceptance

- `rg -n "def _(online_ai_candidate_items|convert_ass_to_ai_srt|submit_online_ai_translate|submit_autosub_for_entries|restart_autosub_for_entries|selected_external_subtitle_override_for_entries)" plugins.v2/subtitlemanualupload/__init__.py` 无命中。
- `pytest tests/test_autosubv3_cancel.py tests/test_subtitlemanualupload_cache.py -q` exits 0.
- Baseline smoke exits 0.

### 失败模式

AI 任务取消/重启是跨插件边界，错误必须清楚返回给前端，不能被服务迁移吞掉。

### Commit Boundary

提交在线 AI / AutoSub facade 拆分。

## Phase 8: 最终收口、浏览器验收和发布准备

### 目标

确认 `__init__.py` 已变成插件壳，并用真实浏览器验证主要用户路径。

### Hard Acceptance

- `plugins.v2/subtitlemanualupload/__init__.py` 行数不超过 450 行。
- `SubtitleManualUpload` 类方法数量不超过 25 个。
- `rg -n "compat.py|compat_core|compat_services|SubtitleManualUploadCompatMixin|install_compat_" plugins.v2/subtitlemanualupload tests scripts -g "*.py"` 无命中。
- API route contract still has 23 endpoints.
- Baseline smoke exits 0.
- Plugin directory `pnpm build` exits 0.
- 本地 zip 可生成但不提交。

### Browser Test Plan

#### Setup

- 使用可见 Chrome，沿用用户登录态。
- 通过 CDP 接入，不读取 Cookie、LocalStorage、SessionStorage、密码、token。
- 如果前端包或后端 zip 被安装，必须验证加载的 `remoteEntry.js` 与本地 dist hash 一致。

#### Cases

1. 插件入口
   - 打开 `https://mp.jaysherlock.top:5443/#/plugin-app/SubtitleManualUpload/main`
   - 验证页面显示 `字幕匹配`、资源选择、资源数量。
   - 记录 `remoteEntry.js`、`status`、`auto_transfer_queue`、`search` 响应状态。

2. 资源搜索和详情
   - 搜索或选择 `百万英镑 (1954)`。
   - 验证目标详情、本地路径、目标操作按钮、AI 状态 strip 可见。
   - 不点击上传、写入、删除、恢复、调轴。

3. 外挂字幕列表
   - 点击展开外挂字幕。
   - 验证 `.srt` 条目和状态标签可见。

4. 在线字幕搜索和预览
   - 点击单集 `搜索此集在线字幕`。
   - 验证 `online_status`、`online_manual_links`、`online_search_provider` 是 2xx。
   - 选择 OpenSubtitles 结果，点击 `下载并生成预览`。
   - 验证 `online_download_preview` 是 2xx，页面出现 `已解析` / `自动匹配` / 预览结果。
   - 不点击 `写入字幕`、`提交 AI 翻译`。

5. AI 状态
   - 点击 `AI：...点击查看当前资源任务`。
   - 验证状态弹窗或任务状态区域渲染，无 console runtime error。

6. 响应式冒烟
   - 视口：1440x1000、768x1000、390x900。
   - 验证插件标题和资源/目标内容可见，不是空白页。

### Browser Acceptance

- 插件相关 UI 触发 API 的 accepted paths 均为 2xx。
- `requestfailed` 不包含 `/api/v1/plugin/SubtitleManualUpload/` 或插件 `remoteEntry.js`。
- Console 无插件 runtime error。
- 不点击写入、删除、恢复、重启、提交 AI。
- 截图保存到 `.tmp-test-data/`，不提交。

### Commit Boundary

提交最终收口和公开版本更新。zip、截图、本地计划不提交。

## Decision Log

- Decision: 后续拆分命名为主入口瘦身，不再叫兼容债务。
  Reason: compat 三文件和动态安装器已删除；剩余问题是职责集中。
  Rejected: 继续以 compat debt 命名。风险是误导执行者恢复兼容层或制造新 alias。

- Decision: 先加 inventory，再拆代码。
  Reason: 当前 `__init__.py` 仍有 90 多个方法，必须用脚本追踪真实收缩。
  Rejected: 手工按行数拆。风险是漏掉测试对私有方法的绑定。

- Decision: service registry 是唯一服务装配入口。
  Reason: 避免主入口、API modules、service_factories 各维护一套服务事实。
  Rejected: 在每个 API module 内手写工厂。风险是依赖注入漂移。

- Decision: 真实浏览器验收仍走可见 Chrome。
  Reason: MoviePilot 需要登录态，且前端缓存会让旧包误通过。
  Rejected: 只跑 Playwright headless。风险是测不到真实已安装插件包。

## /goal Starter

```text
/goal Implement docs/plans/2026-06-30-subtitlemanualupload-init-shell-slimming-phased-plan.md by following its execution ledger.

Each turn:
1. Read docs/plans/2026-06-30-subtitlemanualupload-init-shell-slimming-progress.json, then the current task in the plan.
2. Run `git log --oneline -15` and the smoke check named in the plan; repair a broken state before starting new work.
3. Work only on the current work unit.
4. After verification passes: update the progress file status/evidence/log fields only, commit that unit, record the commit hash. Never commit on failed verification. Never push, merge, or amend.
5. When a phase's acceptance checks all pass, record it and continue to the next phase without asking for approval.

Done when __init__.py is reduced to a MoviePilot plugin shell, all acceptance checks and browser checks are proven, and residual risk is recorded.
```
