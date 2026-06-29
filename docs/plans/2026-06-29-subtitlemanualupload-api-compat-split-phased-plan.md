# SubtitleManualUpload API 编排分拆与 compat 瘦身计划

## 目标

把 `plugins.v2/subtitlemanualupload/__init__.py` 从“胖 Controller”收缩为 MoviePilot 插件壳：只保留插件元信息、生命周期、配置初始化、事件入口、服务装配和 API 注册。把现有 23 个 API endpoint 按功能领域拆到独立 handler 模块，并把 `compat.py` 从 1794 行旧私有方法兼容层瘦身到只保留少量必要旧测试/旧私有接口兼容别名；若测试和运行代码均不再依赖旧私有入口，则删除 `compat.py`。

## 规格评审

- Ready: yes.
- 阻塞决策: 无。用户明确要求 API 按功能领域分拆，并希望 `compat.py` 最终只剩少量兼容入口甚至可删除。
- 漂移风险: 当前工作树已有版本升级、审查文档和 zip 包改动。执行前必须创建专用分支，并确认这些现有改动是否属于同一工作线；不能安全分离时停止报告。
- 任务级别: L。原因是涉及 API 注册、多个 handler 模块、服务依赖方向、旧私有方法兼容、测试迁移和线上接口合同，天然分阶段且超过 10 个工作单元。

## 来源文件

- `plugins.v2/subtitlemanualupload/__init__.py`
- `plugins.v2/subtitlemanualupload/compat.py`
- `plugins.v2/subtitlemanualupload/auto_transfer.py`
- `plugins.v2/subtitlemanualupload/autosub_bridge.py`
- `plugins.v2/subtitlemanualupload/online_ai.py`
- `plugins.v2/subtitlemanualupload/upload_session.py`
- `plugins.v2/subtitlemanualupload/subtitle_writer.py`
- `plugins.v2/subtitlemanualupload/subtitle_history.py`
- `plugins.v2/subtitlemanualupload/target_resolver.py`
- `plugins.v2/subtitlemanualupload/config_schema.py`
- `tests/test_subtitlemanualupload_cache.py`
- `tests/test_subtitlemanualupload_online.py`
- `tests/test_subtitlemanualupload_tongwen.py`
- `tests/test_timeline_fixer.py`
- `tests/test_autosubv3_cancel.py`

## 执行规则

- 开始前创建专用分支：`codex/subtitlemanualupload-api-compat-split`。
- 开始前做 clean-start commit，或明确记录因既有本地改动无法安全纳入而停止。
- 每个 work unit 只做当前单元，不顺手重构其它模块。
- 每个 work unit 验证通过后再提交，并把 commit hash 记录到 progress JSON。
- 验证失败不得提交。
- 不自动 push、merge、amend。
- 计划文档和 progress JSON 是本地执行材料；是否纳入提交以用户明确要求和仓库规则为准，不能把本地测试 IP、token、cookie、运行日志原文、zip 构建产物提交到 GitHub。
- 阶段验收通过后自动进入下一阶段，不等待用户确认。

## 进度文件

`docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-progress.json`

执行 agent 只能更新 progress JSON 中的 `status`、`verification`、`commit`、`decision_log`、`turn_log`、`residual_risk` 字段，不得改任务定义、验收标准或阶段边界。

## 基线 smoke check

PowerShell:

```powershell
$env:PYTHONPATH='.'
& 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_subtitlemanualupload_cache.py tests/test_subtitlemanualupload_online.py tests/test_subtitlemanualupload_tongwen.py tests/test_timeline_fixer.py tests/test_autosubv3_cancel.py
```

路由合同检查:

```powershell
$env:PYTHONPATH='.'
@'
import importlib.util
from pathlib import Path
p = Path("plugins.v2/subtitlemanualupload/__init__.py")
spec = importlib.util.spec_from_file_location("subtitlemanualupload_contract_check", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
plugin = m.SubtitleManualUpload.__new__(m.SubtitleManualUpload)
routes = plugin.get_api()
print(len(routes))
for item in routes:
    print(item["path"], ",".join(item["methods"]), item.get("auth"), item.get("summary"))
'@ | & 'C:\Users\jaysh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -
```

Hard baseline:

- Focused pytest command exits 0.
- Route contract command prints exactly 23 routes.
- The 23 route paths, methods, auth, and summaries match the pre-refactor snapshot recorded in the progress file.

## 当前结构观察

- `__init__.py` 当前 1746 行，50 个类方法。
- `get_api()` 当前集中声明 23 个 API 路由。
- `__init__.py` 中 API handler 分布：
  - 状态/缓存/队列: `api_status`、`api_refresh_index`、`api_auto_transfer_queue`
  - 本地目录: `api_search`、`api_targets`、`api_match_history`
  - 时间轴: `api_timeline_tasks`、`api_timeline_fix_existing`
  - 上传/写盘: `api_prepare_upload`、`api_apply_upload`、`api_clear_subtitles`、`api_delete_subtitle`、`api_restore_subtitle_backup`
  - 在线字幕: `api_online_status`、`api_online_manual_links`、`api_online_search`、`api_online_search_provider`、`api_online_download_preview`
  - AI 字幕: `api_ai_submit`、`api_ai_tasks`、`api_ai_cancel`、`api_ai_restart`、`api_online_ai_submit`
- `compat.py` 当前 1794 行，192 个方法；大约 80 个方法是服务工厂或转发壳，另有 RAR 依赖、TMDB 缓存、时间轴任务、自动入库、目标补全等残余逻辑。
- `auto_transfer.py` 仍大量通过 `owner._xxx()` 调回兼容层，这是 `compat.py` 不能立即删除的主要原因。

## 目标架构

```text
MoviePilot
  -> SubtitleManualUpload.__init__.py
       - plugin metadata
       - init_plugin / stop_service / event listener
       - get_form / get_page / sidebar
       - build_api_routes(self)
       - service factory or service registry

  -> api/routes.py
       - owns the 23 endpoint definitions
       - no business logic

  -> api/status_api.py
  -> api/catalog_api.py
  -> api/timeline_api.py
  -> api/upload_api.py
  -> api/online_api.py
  -> api/ai_api.py
       - parse Request
       - validate request body/query/form
       - call existing services
       - format _ok response
       - preserve route behavior

  -> services/modules
       - target_resolver.py
       - subtitle_writer.py
       - upload_session.py
       - autosub_bridge.py
       - online_ai.py
       - auto_transfer.py

  -> compat.py
       - final state: deleted, or <= 350 lines / <= 45 methods
       - only backward-compatible aliases for tests or legacy private callers
```

## API 分拆边界

### `api/routes.py`

Owns only route declarations:

- Function: `build_api_routes(owner) -> List[Dict[str, Any]]`
- Must keep all current route dictionaries unchanged except endpoint callable location.
- Must not parse requests, access plugin state, or call services.

### `api/status_api.py`

Owns:

- `status()`
- `refresh_index()`
- `auto_transfer_queue(request)`

Uses:

- owner `_rar_tool`, `_rar_python_available`, `_cache_status`, `_auto_transfer_queue_summary`, `_autosub_status`, `_auto_transfer_service`.

Does not own:

- RAR dependency installation.
- Cache persistence internals.
- Queue worker implementation.

### `api/catalog_api.py`

Owns:

- `search(request)`
- `targets(request)`
- `match_history(request)`

Uses:

- `LocalMediaCatalog.search_media_candidates`
- `MediaTargetResolver.targets_for_media`
- `SubtitleHistory` or owner-compatible history access.

Does not own:

- TransferHistory query mechanics.
- TMDB detail hydration logic.
- cache mutation logic beyond calling services.

### `api/timeline_api.py`

Owns:

- `timeline_tasks(request)`
- `timeline_fix_existing(request)`
- `existing_timeline_operations(...)` helper if it remains endpoint-specific.

Uses:

- `SubtitleHistory.existing_timeline_operations`
- `SubtitleWriter.run_existing_timeline_fix`
- `check_timeline_fixer_dependencies`
- timeline task store abstraction.

Does not own:

- Low-level timeline alignment algorithm.
- Subtitle write operation generation.

### `api/upload_api.py`

Owns:

- `prepare_upload(request)`
- `apply_upload(request)`
- `clear_subtitles(request)`
- `delete_subtitle(request)`
- `restore_subtitle_backup(request)`
- `build_preview_response_from_uploads(...)`

Uses:

- `UploadSessionService`
- `SubtitleWriter`
- `MediaTargetResolver`
- lock helper for target IDs.

Does not own:

- Archive extraction implementation.
- Disk write implementation.
- Timeline fix implementation.

### `api/online_api.py`

Owns:

- `online_status()`
- `online_manual_links(request)`
- `online_search(request)`
- `online_search_provider(request)`
- `online_download_preview(request)`
- `download_online_results_to_uploads(...)` if it is only used by endpoint flow.

Uses:

- `OnlineSubtitleSearchService`
- `UploadSessionService`
- `OnlineAiService` only for the `submit_ai_translate` branch in `online_download_preview`.
- online rate limiter abstraction.

Does not own:

- Provider implementations.
- AI task submission internals.

### `api/ai_api.py`

Owns:

- `ai_submit(request)`
- `online_ai_submit(request)`
- `ai_cancel(request)`
- `ai_restart(request)`
- `ai_tasks(request)`

Uses:

- `AutoSubBridge`
- `OnlineAiService`
- target lock and target resolution helper.

Does not own:

- AutoSubv3 plugin internals.
- Online subtitle download.

## Compat 瘦身策略

### 保留原则

`compat.py` 只允许保留满足以下任一条件的方法：

- 测试仍直接调用的旧私有方法，且迁移该测试会降低覆盖价值。
- MoviePilot 或其它插件可能通过旧私有方法调用的稳定兼容入口。
- 作为短期桥接的 one-line delegate，且有明确后续删除依据。

### 删除或迁移原则

- 纯 normalizer 移到 `config_schema.py`、`subtitle_language.py` 或 `target_resolver.py`，测试改测目标模块。
- 上传、RAR、7z、会话读写移到 `upload_session.py`，compat 只保留必要 alias。
- 写盘、备份、删除、恢复、调轴写入移到 `subtitle_writer.py`，compat 只保留必要 alias。
- 本地媒体缓存、TMDB 补全、目标解析、字幕枚举移到 `target_resolver.py` 或新 `media_cache.py`。
- AI 提交/取消/重启移到 `autosub_bridge.py`。
- 在线字幕 AI 准备和 ASS/SSA 转 SRT 移到 `online_ai.py`.
- 自动入库队列和整季包缓存移到 `auto_transfer.py`，并逐步用显式依赖替代 `owner._xxx()`。

### 最终验收目标

- `compat.py` 被删除；或
- `compat.py` <= 350 行，AST 方法数 <= 45，且文件头说明它只承载旧私有 API 兼容。

## 阶段计划

### Phase 1: 基线合同与 API 路由骨架

Goal: 建立可比较的路由合同，并把路由表从 `__init__.py` 移到 `api/routes.py`，不搬业务逻辑。

Surfaces:

- `plugins.v2/subtitlemanualupload/__init__.py`
- `plugins.v2/subtitlemanualupload/api/__init__.py`
- `plugins.v2/subtitlemanualupload/api/routes.py`
- `tests/test_subtitlemanualupload_cache.py` or new focused route contract test

Tasks:

1.1 Record route contract snapshot.

- Capture current `get_api()` path, methods, auth, summary order.
- Add or update a test that asserts the 23-route contract.
- Do not move handlers yet.

Verification:

- Focused pytest command exits 0.
- Route contract test fails if any path/method/auth/summary changes.

1.2 Extract `build_api_routes(owner)`.

- Create `api/routes.py`.
- Move only route declaration dictionaries there.
- `SubtitleManualUpload.get_api()` returns `build_api_routes(self)`.
- Endpoint callables may still point to owner methods in this phase.

Verification:

- Focused pytest command exits 0.
- Route contract command prints 23 unchanged routes.

Acceptance:

- `get_api()` in `__init__.py` is <= 5 non-comment logical lines.
- Route path/method/auth/summary/order match the Phase 1.1 snapshot.
- No endpoint behavior is moved in Phase 1.

Commit boundary: commit Phase 1.1 and Phase 1.2 separately after verification.

### Phase 2: 状态、目录、时间轴 API handler 分拆

Goal: Move read-heavy and low-write API handlers first, keeping behavior stable and reducing `__init__.py` without touching upload/write/AI flows.

Surfaces:

- `api/status_api.py`
- `api/catalog_api.py`
- `api/timeline_api.py`
- `api/routes.py`
- `__init__.py`
- tests covering cache/search/timeline

Tasks:

2.1 Extract status and queue handlers.

- Move `api_status`, `api_refresh_index`, `api_auto_transfer_queue` into `StatusApi`.
- Route endpoints become `StatusApi(owner).status`, `StatusApi(owner).refresh_index`, `StatusApi(owner).auto_transfer_queue`.
- Keep response envelopes exactly the same.

Verification:

- Focused pytest command exits 0.
- Manual route contract check remains unchanged.

2.2 Extract catalog handlers.

- Move `api_search`, `api_targets`, `api_match_history` into `CatalogApi`.
- Preserve query parameter names: `keyword`, `media_type`, `page`, `page_size`, `limit`, `tmdb_id`, `douban_id`, `title`, `year`, `season`.
- Preserve log message semantics without adding sensitive path dumps.

Verification:

- Focused pytest command exits 0.
- Add or keep tests for search pagination and targets resolution.

2.3 Extract timeline handlers.

- Move `api_timeline_tasks`, `api_timeline_fix_existing`, `_existing_timeline_operations`, `_run_existing_timeline_fix` into `TimelineApi` or a timeline API service.
- Keep background thread behavior and task status fields unchanged.

Verification:

- Focused pytest command exits 0.
- Timeline tests continue to pass.

Acceptance:

- No status/catalog/timeline `api_*` implementation remains in `__init__.py`.
- `__init__.py` line count is reduced by at least 180 lines from 1746.
- Route contract remains unchanged.

Commit boundary: one commit per task.

### Phase 3: 上传、预览、写盘 API handler 分拆

Goal: Move the highest user-facing write path into `api/upload_api.py` while preserving archive handling, preview, write, delete, restore, and lock behavior.

Surfaces:

- `api/upload_api.py`
- `upload_session.py`
- `subtitle_writer.py`
- `__init__.py`
- upload/write/delete/restore tests in `tests/test_subtitlemanualupload_cache.py`

Tasks:

3.1 Extract upload preview flow.

- Move `api_prepare_upload` and `_build_preview_response_from_uploads` into `UploadApi`.
- Keep form field names unchanged: `target_ids`, `files`.
- Keep unsupported/invalid file response behavior unchanged.

Verification:

- Focused pytest command exits 0.
- Add or preserve tests for empty targets, invalid JSON target IDs, unsupported upload, valid archive/subtitle preview.

3.2 Extract apply write flow.

- Move `api_apply_upload` into `UploadApi`.
- Preserve body fields: `session_id`, `items`, `fix_timeline`, `allow_risky_offset`, `locked_target_ids`.
- Keep lock skip behavior unchanged.

Verification:

- Focused pytest command exits 0.
- Tests prove locked targets are skipped and valid write calls `SubtitleWriter.apply_upload_session`.

3.3 Extract subtitle management endpoints.

- Move `api_clear_subtitles`, `api_delete_subtitle`, `api_restore_subtitle_backup` into `UploadApi`.
- Preserve all error messages and locked target checks.

Verification:

- Focused pytest command exits 0.
- Tests cover clear/delete/restore invalid target and locked target paths.

Acceptance:

- No upload/write/delete/restore `api_*` implementation remains in `__init__.py`.
- Route contract remains unchanged.
- Existing write-path tests pass without weakening assertions.

Commit boundary: one commit per task.

### Phase 4: 在线字幕与 AI API handler 分拆

Goal: Move online subtitle and AI task endpoints into dedicated domain handlers, keeping online-to-AI translation and AutoSubv3 bridge behavior intact.

Surfaces:

- `api/online_api.py`
- `api/ai_api.py`
- `online_subtitle.py`
- `online_ai.py`
- `autosub_bridge.py`
- `__init__.py`
- online and AutoSubv3 tests

Tasks:

4.1 Extract online status/search handlers.

- Move `api_online_status`, `api_online_manual_links`, `api_online_search`, `api_online_search_provider` into `OnlineApi`.
- Keep provider normalization and rate limit behavior unchanged.

Verification:

- Focused pytest command exits 0.
- Online provider tests continue to pass.

4.2 Extract online download preview.

- Move `api_online_download_preview` and `_download_online_results_to_uploads` into `OnlineApi`.
- Preserve captcha, invalid archive, unsupported file, and `submit_ai_translate` branches.

Verification:

- Focused pytest command exits 0.
- Tests cover selected result validation and AI translate branch.

4.3 Extract AI task handlers.

- Move `api_ai_submit`, `api_online_ai_submit`, `api_ai_cancel`, `api_ai_restart`, `api_ai_tasks` into `AiApi`.
- Move thin helpers `_cancel_autosub_for_entries`, `_restart_autosub_for_entries`, `_filter_restart_task_ids_by_targets`, `_selected_external_subtitle_override_for_entries`, `_submit_autosub_for_entries` into `AiApi` or `autosub_bridge.py` if they are no longer used outside AI endpoints.

Verification:

- Focused pytest command exits 0.
- AutoSubv3 cancel/restart tests continue to pass.

Acceptance:

- No online or AI `api_*` implementation remains in `__init__.py`.
- `__init__.py` line count is <= 900.
- Route contract remains unchanged.

Commit boundary: one commit per task.

### Phase 5: compat.py inventory and low-risk alias removal

Goal: Make `compat.py` measurable and remove aliases that are no longer called by source or tests after API extraction.

Surfaces:

- `compat.py`
- tests that call old private methods
- optional helper script under `scripts/` or one-off documented command in progress evidence

Tasks:

5.1 Generate compat inventory.

- Use AST to list every `SubtitleManualUploadCompatMixin` method, size, call sites in `plugins.v2/subtitlemanualupload` and `tests`.
- Classify methods as `required-runtime`, `required-test`, `delegate-only`, `move-to-service`, `delete-now`.
- Record classification summary in progress evidence; do not commit generated temp output.

Verification:

- Inventory command completes and reports method count.
- Focused pytest command exits 0.

5.2 Delete unused delegate aliases.

- Remove methods classified `delete-now`.
- Update any imports or route references exposed by the removal.
- Do not move behavior in this task.

Verification:

- Focused pytest command exits 0.
- AST method count in `compat.py` decreases from baseline.

5.3 Move direct tests from compat aliases to target modules.

- For tests that call a one-line compat alias but can call the extracted module directly, update tests to target `upload_session.py`, `subtitle_writer.py`, `target_resolver.py`, `autosub_bridge.py`, `online_ai.py`, or `config_schema.py`.
- Keep tests that intentionally verify legacy private compatibility.

Verification:

- Focused pytest command exits 0.
- Inventory shows fewer `required-test` compat methods.

Acceptance:

- `compat.py` method count is at least 25 percent lower than the Phase 5.1 baseline.
- No source call fails due to removed aliases.
- Route contract remains unchanged.

Commit boundary: one commit per task.

### Phase 6: Move residual compat logic to owning modules

Goal: Move real logic still living in `compat.py` into domain modules so compat becomes mostly aliases.

Surfaces:

- `compat.py`
- `upload_session.py`
- `target_resolver.py`
- `subtitle_history.py`
- `subtitle_writer.py`
- `auto_transfer.py`
- `online_ai.py`
- tests

Tasks:

6.1 Move archive/RAR dependency logic.

- Move `_prepare_rar_dependency`, `_install_container_rar_tool`, `_set_rar_dependency_status`, archive extraction alias bodies, and tool discovery wrappers into `upload_session.py` or a new `archive_dependency.py`.
- `compat.py` may retain aliases only if tests or legacy callers need them.

Verification:

- Focused pytest command exits 0.
- Tests cover RAR unavailable, command extraction, Python `rarfile` extraction where existing fixtures allow.

6.2 Move target/cache/TMDB residual logic.

- Move `_merge_local_entries_cache`, `_start_background_cache_refresh`, `_tmdb_detail_for_media`, `_tmdb_detail_payload`, `_english_title_from_tmdb_values`, `_tmdb_aliases`, `_flatten_media_values`, `_auto_media_for_entry`, `_chinese_category_evidence`, `_is_chinese_transfer_media`, `_suggest_target`, `_auto_fill_missing_targets` to `target_resolver.py`, `LocalMediaCatalog`, or a new `media_metadata.py`.
- Preserve cache keys and data shapes.

Verification:

- Focused pytest command exits 0.
- Tests prove search cache, target resolution, Chinese media detection, and auto-fill target behavior.

6.3 Move timeline task state helpers.

- Move `_set_timeline_task`, `_timeline_task_summary`, `_timeline_tasks_for_entries`, `_timeline_task_for_target_id`, `_cleanup_timeline_tasks` into a new `timeline_tasks.py` or `TimelineApi` support object.
- Keep owner state fields if needed, but centralize all mutation logic outside compat.

Verification:

- Focused pytest command exits 0.
- Tests prove empty timeline task summary and target task mapping.

Acceptance:

- `compat.py` contains no method longer than 15 lines except documented legacy compatibility shims.
- `compat.py` line count is <= 800.
- Route contract remains unchanged.

Commit boundary: one commit per task.

### Phase 7: Break owner._xxx dependency loops in AutoTransferService

Goal: Replace broad `owner._xxx()` callbacks in `auto_transfer.py` with explicit injected collaborators, so `compat.py` is not required for auto-transfer runtime.

Surfaces:

- `auto_transfer.py`
- `compat.py`
- `__init__.py`
- API modules that construct services
- tests around auto transfer

Tasks:

7.1 Define auto-transfer collaborator interface.

- Introduce a small dependency object or dataclass passed to `AutoTransferService`.
- Include only required collaborators: online service factory, target mapping, subtitle extraction, write operations, AI submit, online AI override preparation, language/format selectors, rate limiter, logger, time/threading.
- Do not change behavior in this task; keep owner fallback only if needed during migration.

Verification:

- Focused pytest command exits 0.
- Type/import check by `py_compile` for `auto_transfer.py`, `compat.py`, and `__init__.py` exits 0.

7.2 Migrate AutoTransferService call sites to collaborators.

- Replace internal `owner._xxx()` calls with explicit collaborator calls where the dependency exists.
- Remove fallback paths once tests prove coverage.
- Keep shared mutable queue/cache state on owner only where it is true plugin state.

Verification:

- Focused pytest command exits 0.
- Auto-transfer tests cover online success, fallback to AI, existing Chinese subtitle skip, embedded subtitle skip, season package cache, dedupe queue.

7.3 Remove no-longer-needed auto-transfer compat aliases.

- Remove `_auto_*` aliases that are no longer called by source or tests, except intentionally preserved legacy private methods.
- Update tests to call `AutoTransferService` directly for service behavior.

Verification:

- Focused pytest command exits 0.
- Inventory shows remaining compat methods are only legacy aliases.

Acceptance:

- `auto_transfer.py` no longer requires `owner._extract_subtitle_files`, `owner._write_operations_to_disk`, `owner._submit_autosub_for_entries`, or `owner._prepare_online_ai_subtitle_overrides`.
- `compat.py` line count is <= 500.
- Route contract remains unchanged.

Commit boundary: one commit per task.

### Phase 8: Final compat deletion or minimal compatibility shell

Goal: Reach the final desired state: delete `compat.py` if no remaining required callers exist, or reduce it to a documented minimal compatibility shell.

Surfaces:

- `compat.py`
- `__init__.py`
- tests
- docs if public developer notes need an update

Tasks:

8.1 Decide final compat state from inventory.

- If zero source/test runtime call sites require old private methods, delete `compat.py` and remove mixin inheritance.
- If required legacy call sites remain, keep `compat.py` with only documented aliases.
- Record the decision in progress `decision_log`.

Verification:

- Focused pytest command exits 0.
- Route contract remains unchanged.

8.2 Final size and contract audit.

- Run line/method count script for `__init__.py` and `compat.py`.
- Run focused pytest command.
- Run route contract check.
- Run `py_compile` on all `plugins.v2/subtitlemanualupload/*.py` files and `plugins.v2/subtitlemanualupload/online_subtitles/**/*.py`.

Verification:

- All commands exit 0.
- `__init__.py` <= 700 lines.
- `compat.py` deleted, or `compat.py` <= 350 lines and <= 45 methods.

8.3 Update docs and residual risk.

- Update local review notes or README only if user-facing architecture notes changed.
- Record residual risks: no API route behavior change intended; real online provider behavior still depends on remote provider availability; destructive write paths are covered by tests and should not be live-triggered during refactor verification unless user approves.

Verification:

- Diff review shows no secrets, tokens, local IP lists, zip artifacts, cache files, logs, or build outputs staged.
- Focused pytest command exits 0 after docs update if docs are changed.

Acceptance:

- Final route contract exactly matches baseline 23 routes.
- `__init__.py` is plugin shell + lifecycle + API registration only.
- `compat.py` final state meets deletion/minimal-shell rule.
- Focused pytest command exits 0 and evidence is recorded.

Commit boundary: one commit per task.

## 测试计划

- Primary regression: focused pytest command in this plan.
- Route contract: exact 23-route snapshot check.
- Static import/compile: `py_compile` for all plugin Python files.
- Size checks: AST method count and line count for `__init__.py` and `compat.py`.
- No live destructive check in default plan: do not trigger real subtitle writes, deletes, online downloads, or AI generation against the user's production MP unless the user explicitly asks.

## 失败模式与处理

- Failure: route dict order or summary changes silently. Recovery: route contract test fails; restore exact route snapshot before continuing.
- Failure: handler extraction loses auth mode. Recovery: route contract test checks `auth` field for all routes.
- Failure: `compat.py` alias removed while tests or `auto_transfer.py` still call it. Recovery: inventory and pytest fail; either migrate caller to owning service or restore alias as documented legacy compatibility.
- Failure: `auto_transfer.py` collaborator migration changes queue/cache semantics. Recovery: auto-transfer tests must cover dedupe, season cache, fallback, skip rules, and queue summaries before alias deletion.
- Failure: online provider tests become flaky due to network. Recovery: keep unit tests mocked; do not require live provider calls for acceptance.

## 不在范围内

- 不改 23 个 endpoint 的 path、method、auth、summary 或响应合同。
- 不改前端 API 调用路径。
- 不重写字幕匹配算法。
- 不重写 AutoSubv3。
- 不做真实线上字幕写盘、删除、AI 生成任务。
- 不提交 zip 包、运行日志、缓存文件、密钥或本地隐私配置。

## 决策记录

1. Decision: API handler 按领域拆为 status、catalog、timeline、upload、online、ai。
   Reason: 与用户要求一致，且每组 endpoint 有清晰服务依赖和独立验收面。
   Rejected: 按 HTTP method 拆分；会把一个业务流程拆散，降低可维护性。

2. Decision: `routes.py` 只拥有路由表，不拥有业务逻辑。
   Reason: 让 route contract 可单独测试，避免 API 注册和 handler 实现互相缠绕。
   Rejected: 每个 handler 模块各自声明路由；容易打乱 23 个路由的顺序和合同。

3. Decision: `compat.py` 分两步瘦身，先删无用 alias，再移动残余逻辑。
   Reason: 直接删除风险高，`auto_transfer.py` 和测试仍依赖旧私有入口。
   Rejected: 一次性删除 compat；会把行为迁移、测试迁移和依赖注入混在一个不可审计的大 diff。

4. Decision: AutoTransferService 最后迁移到显式 collaborator。
   Reason: 它是当前 `owner._xxx()` 回调最多的模块，先稳定 API handler 再改服务依赖方向更安全。
   Rejected: 优先重写 auto_transfer；会在 API 合同未稳定时扩大风险。

## /goal starter

```text
/goal Implement docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-phased-plan.md by following its execution ledger.

Each turn:
1. Read docs/plans/2026-06-29-subtitlemanualupload-api-compat-split-progress.json, then the current task in the plan.
2. Run `git log --oneline -15` and the smoke check named in the plan; repair a broken state before starting new work.
3. Work only on the current work unit.
4. After verification passes: update the progress file status/evidence/log fields only, commit that unit, record the commit hash. Never commit on failed verification. Never push, merge, or amend.
5. When a phase's acceptance checks all pass, record it and continue to the next phase without asking for approval.

Done when every item in the plan is complete, every acceptance check is proven, and the progress file records final status and residual risk.

Stop and report if a product decision is missing, the plan conflicts with the latest direction, or the worktree holds unrelated changes that cannot be safely separated.
```
