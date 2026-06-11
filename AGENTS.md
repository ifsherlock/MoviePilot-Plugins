# AGENTS.md

本文件给后续 Codex / Agent 接手本仓库时使用。重点记录 `SubtitleManualUpload`（字幕匹配）近期重构的开发思路、稳定不变量、避坑点、测试路径、打包发布流程，以及可用的 MoviePilot MCP 快捷操作。

## 基本原则

- 面向用户默认中文回复，先给结论，再给必要证据和路径。
- 做代码改动前先看 `git status --short --branch` 和实际 diff，保留用户已有改动。
- 不提交 `release_zips/`、`.tmp-test-data/`、`.pytest_cache/`、`node_modules/`、`__pycache__/`、日志、临时采样数据、API Key、Cookie、Token、账号密码或本地内网配置。
- 功能改动默认要同步版本、README 更新记录、前端 dist 构建产物；纯文档改动不需要升插件版本。
- 手动编辑文件使用 `apply_patch`。搜索优先用 `rg` / `rg --files`。
- 修改前端后必须跑 `npm run build`，并把新 hash 的 `dist/` 产物强制加入暂存区。
- 能做根因修复就不要叠加静默兜底；失败要在日志/API 返回里清晰暴露。

## 当前重点插件

路径：`plugins.v2/subtitlemanualupload`

核心文件：

- `__init__.py`：MoviePilot 插件入口、配置表单、API 路由、匹配历史、自动入库队列、调轴任务。
- `online_subtitle.py`：兼容导出层，保留旧导入路径。
- `online_subtitles/service.py`：在线字幕 provider 统一调度、合并、排序、去重和错误聚合。
- `online_subtitles/providers/`：`assrt.py`、`opensubtitles.py`、`subhd.py`、`zimuku.py`。
- `online_subtitles/common.py`：标题/关键词/匹配/下载通用逻辑。
- `online_subtitles/captcha/`：SubHD SVG 和 Zimuku BMP 验证码识别。
- `timeline_fixer.py`：智能调轴。
- `tongwen.py` 与 `resources/tongwen/`：繁转简。
- `src/components/AppPage.vue`：主页面、匹配历史、在线搜索、队列和 AI/调轴状态展示。
- `src/components/Config.vue`：插件配置页。

## 字幕搜索重构思路

本轮重构目标不是单纯多接几个站，而是把原先难维护的在线搜索逻辑拆成 provider 架构，同时保持旧接口兼容。

必须保持兼容的接口：

- `/online_status`
- `/online_search`
- `/online_search_provider`
- `/online_download_preview`

新增但不破坏旧行为的接口：

- `/match_history`
- `/timeline_tasks`
- `/timeline_fix_existing`
- `/auto_transfer_queue`

搜索策略不变量：

- `OpenSubtitles`：优先 `tmdb_id`，失败后回到本项目已有英文标题/区域感知标题方案，再低频尝试 `imdb_id`。语言范围保持中、日、英、韩等现有逻辑。
- `ASSRT/伪射手`：继续官方 API 的标题关键词搜索，不引入 ID 搜索。
- `SubHD`：有 `douban_id` 优先走豆瓣 ID 对应页面；没有则用中文标题、英文标题、季集关键词；仍失败才尝试补豆瓣/IMDb ID。
- `Zimuku`：以中文/英文标题和季集关键词搜索为主，解析 `/subs/{id}.html` 候选页后再按标题、年份、季集过滤；豆瓣链接只作为辅助证据。
- `imdb_id` 不是核心路径。当前插件数据来自 MoviePilot，不从 Emby/NFO 读取，通常拿不到 IMDb；只有已有准确豆瓣条目时，才可从豆瓣详情页解析 `IMDb:` 字段并缓存。
- SubHD/Zimuku 仅作为手动在线搜索和下载源接入；无人值守自动入库默认只用 ASSRT/OpenSubtitles，避免验证码和站点波动拖垮入库。

## 入库监测与历史缓存思路

匹配历史采用“长期缓存 + 文件系统签名校验”：

- 缓存签名需要包含视频文件存在性、视频 stat、父目录 mtime。
- 本地缓存恢复、刷新、合并和读取都必须过滤失效 local 路径。
- 删除媒体库文件后，历史不应继续展示旧目标。
- 同路径重新入库时，size/mtime 签名变化后不能被短期去重误拦。

自动入库队列：

- 自动字幕处理通过队列展示状态，不要让入库事件同步卡死。
- ASSRT 和 OpenSubtitles 分别按每源 5 次/分钟限速。
- 批量剧集入库时，同一 `media_key/tmdb_id + season` 先 debounce 聚合。
- 优先搜索整季包并缓存解包结果，后续同季集数优先从整季包抽取匹配字幕。
- 整季包未命中或无法匹配时，再按单集排队搜索。

智能调轴：

- 历史页调轴走 `/timeline_fix_existing`，状态统一由 `/timeline_tasks` 展示。
- `.strm` 目标必须跳过调轴。
- 调轴失败不要伪造成成功，要能在任务状态里看到 `failed` 和原因。

## 前端交互不变量

- 在线搜索弹窗里用户点 `X` 应等同停止等待，外层搜索按钮不能继续转圈。
- “下载并提交 AI 翻译”不走下载匹配预览，应跳到 AI 字幕生成状态卡，不要继续引导用户落单英文字幕。
- 普通在线下载仍进入匹配预览，不能被 AI 逻辑影响。
- 匹配历史中的单字幕操作要明显可见；“调轴 / 删除”按钮应有背景框、紧凑间距、右对齐。
- 媒体详情内的匹配历史与总匹配历史能力保持一致。
- 首页和历史页封面优先使用 `poster_thumb_url` / TMDB w185 小图，并保留懒加载、异步解码和坏图占位。

## 常见避坑

- 字幕语言后缀应从字幕扩展名前向前匹配，例如 `xxx.eng.srt`，不要从整段文件名任意匹配，否则 `KORSUB...eng.srt` 会被误判为韩语。
- OpenSubtitles 用户名可能误填邮箱；下载登录逻辑要明确提示账号密码需求，不能把 API Key 当登录 token。
- SubHD `/down/{sid}` 的 `sid` 不一定是纯数字，可能是短码；不要用过窄正则。
- SubHD API 可能返回 `success/pass/url/msg` 但 `url` 为空，需要尝试解析 API HTML/url、跳转页和 `/down` 页面下载 href，同时记录脱敏诊断字段。
- Zimuku 默认域名应优先 `https://zmk.pw`；旧默认 `https://zimuku.org` 可自动迁移，但用户手动配置的非默认地址不要覆盖。
- 豆瓣限流严重，标题搜豆瓣只能低频兜底，必须缓存，不要每次搜索都请求。
- MoviePilot MCP 或插件配置查询可能返回账号、密码、内网地址等敏感信息；不要在最终回复、文档、commit、issue 里原样输出。
- `release_zips/` 是本地安装包产物，永远不要提交。
- `dist/` 在根 `.gitignore` 下通常被忽略，前端构建后新增 hash 文件需要 `git add -f`。

## 测试路径

常用定向验证：

```powershell
python -m pytest tests/test_subtitlemanualupload_cache.py tests/test_subtitlemanualupload_online.py -q
```

繁转简验证：

```powershell
python -m pytest tests/test_subtitlemanualupload_tongwen.py -q
```

前端构建：

```powershell
npm run build
```

执行目录：

```powershell
cd plugins.v2/subtitlemanualupload
```

Python 语法检查：

```powershell
python -m py_compile plugins.v2/subtitlemanualupload/__init__.py
python -m py_compile plugins.v2/subtitlemanualupload/online_subtitles/providers/subhd.py
python -m py_compile plugins.v2/subtitlemanualupload/online_subtitles/providers/zimuku.py
```

提交前检查：

```powershell
git status --short --branch
git diff --check
git diff --stat
git diff --cached --check
git diff --cached --name-status
```

测试覆盖重点：

- 缓存：删除视频后 `_match_history_items` 不返回旧历史；同路径重新入库不被去重拦截。
- 调轴：单字幕、选中多集、整季/全部批量调轴都生成任务；`.strm` 跳过；失败显示 failed。
- 队列：批量 TV 入库聚合同季任务，优先整季包，失败后单集兜底；按源限速计算 `next_run_at`。
- Provider：OpenSubtitles 请求顺序和语言参数；SubHD 豆瓣 ID/标题搜索/下载兜底；Zimuku `zmk.pw`、候选页、下载和验证码。
- UI：搜索取消状态、AI 翻译跳转、历史按钮可见性、移动端排版。

## 版本、提交与打包

功能改动发布时同步以下位置：

- `plugins.v2/subtitlemanualupload/__init__.py` 的 `plugin_version`
- `plugins.v2/subtitlemanualupload/package.json`
- 根 `package.json`
- 根 `package.v2.json`
- `plugins.v2/subtitlemanualupload/README.md` 更新记录

前端改动后：

```powershell
cd plugins.v2/subtitlemanualupload
npm run build
```

新 hash dist 文件需要强制加入，例如：

```powershell
git add -f plugins.v2/subtitlemanualupload/dist/assets
git add plugins.v2/subtitlemanualupload/dist/index.html
```

打包要求：

- 只打单插件包，ZIP 根目录必须是 `SubtitleManualUpload/`。
- 不生成合包。
- 不提交 `release_zips/`。
- 排除 `node_modules`、`__pycache__`、`.pytest_cache`、`.tmp-test-data`。
- 打包后用 `tar -tf <zip>` 校验根目录和排除项。

推荐提交信息使用中文，例如：

```powershell
git commit -m "优化匹配历史字幕操作按钮"
git push origin feature/subtitle-search-refactor
```

## MoviePilot MCP 快捷操作

优先用 MCP 做只读排查，减少手工进 UI。敏感配置查询后只总结状态，不复述账号、密码、Cookie、Token、完整内网地址。

安全的常用只读操作：

- `query_installed_plugins`：确认 `SubtitleManualUpload` / `AutoSubv3` 是否安装、启用、版本是否正确。
- `query_plugin_capabilities`：查看已安装插件注册的 slash commands 和定时服务。
- `query_downloaders`：确认下载器是否存在和启用；注意结果可能含敏感配置，最终回复必须脱敏。
- `query_download_tasks`：查看下载任务状态、hash、标签，辅助判断字幕包是否下载中或已完成。
- `query_transfer_history`：按标题或状态排查入库转移成功/失败记录。
- `query_workflows`：查看 MoviePilot 工作流状态。
- `query_schedulers`：查看定时任务状态和下一次运行时间。
- `query_directory_settings`：查看下载目录/媒体库目录配置摘要。
- `query_library_exists` / `query_library_latest`：确认媒体服务器里目标是否存在。
- `query_subscribes` / `query_subscribe_history`：排查订阅是否触发过对应媒体。

低风险触发操作，但执行前要先说明目的：

- `run_scheduler`：手动触发某个已知定时任务。
- `run_slash_command`：执行已确认的 slash command。
- `reload_plugin`：修改插件配置后重新加载指定插件。

需要明确用户同意的修改/破坏性操作：

- `update_plugin_config`、`update_system_settings`、`update_site`、`update_subscribe`
- `delete_download`、`delete_transfer_history`、`delete_subscribe`
- `transfer_file`、`add_download`、`add_subscribe`
- 任何会写配置、删任务、删历史、移动/复制文件的 MCP 调用

本轮已确认 MoviePilot MCP 可查到：

- `SubtitleManualUpload` 已安装并处于启用状态。
- `AutoSubv3` 已安装并处于启用状态。
- MCP 能查询插件能力、下载器、工作流等排查入口。

## 推荐排查流程

在线字幕搜索失败：

1. 看插件日志里 provider 名称、关键词、候选数、HTTP 状态和最终 host。
2. 查 `online_subtitles/providers/<provider>.py` 对应搜索和下载路径。
3. 跑 `tests/test_subtitlemanualupload_online.py` 中对应 provider 用例。
4. 手动确认站点域名、验证码、下载页结构是否变化。
5. 修 provider，不改 API 响应契约。

入库自动字幕失败：

1. 用 MCP 查入库/转移历史和插件安装状态，最终回复脱敏。
2. 看 `/auto_transfer_queue` 摘要和失败原因。
3. 确认自动入库只走 ASSRT/OpenSubtitles。
4. 对剧集优先检查整季包缓存和 season 聚合逻辑。
5. 跑 `tests/test_subtitlemanualupload_cache.py`。

历史页或调轴状态异常：

1. 查 `/match_history` 是否过滤掉已删除 local 路径。
2. 查 `/timeline_tasks` 是否显示对应 target 状态。
3. 确认 `.strm` 被跳过。
4. 修改后跑缓存和调轴相关测试。

前端按钮/状态异常：

1. 先定位 `src/components/AppPage.vue` 的状态变量和 API 调用。
2. 避免只改视觉不处理 loading/cancel 状态。
3. 修改后跑 `npm run build`，并提交 dist hash 变化。
