# 字幕匹配

MoviePilot V2 插件，提供手动上传字幕并匹配改名的页面。

当前能力：

- 从 MoviePilot 本地整理记录中搜索电影或剧集，只展示本地真实存在的视频资源。
- 第一层搜索/选择本地电影或剧集；选中剧集后进入每集列表。
- 剧集支持横向季度卡片，可切换单季或“全部季”。
- 每集列表支持全选/反选、单集上传、锁定集数、CC 图标查看已有外挂字幕。
- 批量上传会弹出拖拽上传卡片，自动匹配字幕、目标视频和最终改名结果；生成预览后隐藏上传文件列表，锁定集数会被跳过。
- 支持在线字幕搜索：剧集可搜索本季/选中集字幕包，单集可点放大镜搜索；自动来源为 SubHD、Zimuku、射手网(伪) API 和 OpenSubtitles API。
- 在线字幕下载后会进入同一个匹配预览流程，确认语言后缀、集数和文件名后再写入，不会直接落盘。
- 自动搜索失败时，弹窗右侧仍提供 SubHD、Zimuku、射手网(伪)、OpenSubtitles 的手动搜索链接，可下载后回到本页手动上传。
- OpenSubtitles 默认搜索中文、英文、日文等多语言字幕；英文字幕结果可下载后提交给 `AI字幕生成(联动版)` 执行翻译。
- 可联动 `AI字幕生成(联动版)`：在整季工具栏或单集行点击 AI 图标提交生成任务，并在字幕匹配页面查看排队、生成、完成、忽略或失败状态。
- 在线搜索默认不使用 MoviePilot 系统代理，由容器自身网络出口决定；如需代理可在插件设置中手动开启。
- 插件设置可维护字幕站点根地址，以及射手网(伪) / OpenSubtitles API 地址和 API Key，域名、反代地址或 API 入口变化时无需更新插件版本。
- 匹配预览支持批量修改语言后缀，单条字幕仍可独立修正。
- 可选写入前繁体转简体：开启后仅处理中文后缀字幕，使用 Tongwen 词组和单字字典离线转换。
- 可选监听 MoviePilot 入库完成事件自动搜索字幕：默认关闭；仅在目标无外挂字幕、单个高置信结果且能明确匹配时自动写入。
- 支持批量清空选中集的外挂字幕，仅删除与视频同名开头的外挂字幕文件。
- `.strm` 会按本地视频目标参与统计和匹配。
- 上传字幕文件：`.srt`、`.ass`、`.ssa`、`.sbv`、`.sub`、`.vtt`、`.webvtt`。
- 上传 `.zip` 压缩包并自动解包其中的字幕文件。
- 新增轻量 Python RAR 依赖 `rarfile` 声明；上传 `.rar` 压缩包时仍需要容器内 `unrar`、`bsdtar`、`7z`、`7za` 或 `7zz` 负责实际解包，缺失时会明确提示。
- 上传弹窗内可点开“RAR 不能解压？查看处理方式”，查看两套处理方案：容器内临时安装，或宿主机通过国内镜像下载静态 `7zz` 后映射到容器。
- 插件设置可选择 RAR 解压器处理方式：不处理、加载插件时尝试容器内安装、使用宿主机映射文件。
- 写入前可选“智能调轴”：优先用视频内置文本字幕做基准，没有内置字幕时用 `ffmpeg` 抽取音频并通过 FFT 互相关计算整体偏移；该功能可能占用 CPU 并造成短暂卡顿。
- 按目标视频文件名生成外挂字幕名并直接落盘。

命名策略：

- 默认生成 `视频文件名.语言标识.字幕后缀`。
- 语言标识使用媒体服务器常用的 ISO 639 三字母码，例如中文 `chi`、英文 `eng`、日文 `jpn`、韩文 `kor`。
- 例如：`Episode.Name.S01E01.chi.ass`。

限制说明：

- 当前版本只支持可从 MoviePilot 本地媒体库读取到的本地视频文件。
- SubHD 默认地址为 `https://subhd.tv`，优先使用豆瓣 ID 自动搜索，没有 ID 时使用标题关键词搜索，站点波动时可手动跳转。
- Zimuku 默认地址为 `https://zimuku.org`，使用标题关键词搜索候选字幕页，站点波动时可手动跳转。
- 射手网(伪) 配置 API Key 后访问 `https://api.assrt.net` 官方接口；未配置时不参与自动搜索。
- OpenSubtitles 配置 API Key 后访问 `https://api.opensubtitles.com/api/v1` 搜索中文、英文、日文字幕；下载时由插件使用 OpenSubtitles 用户名和密码后台登录换取 token。
- 自定义站点地址只填写根地址，例如 `https://subhd.tv` 或反代入口；插件会按各站当前路径拼接搜索页。
- `rarfile` 是最轻量的 Python RAR 封装层，但不是纯 Python 解压器；RAR5/压缩内容仍依赖外部解压程序。
- 临时测试可在插件设置中选择“加载插件时尝试容器内安装”，或进入 MoviePilot 容器安装 `p7zip-full` / `unrar-free` / `unrar`；容器重建后可能失效。
- 长期建议在宿主机把静态 `7zz` 放到 MoviePilot 部署目录的 `tools/7zz`，设置可执行权限，并映射为容器内 `/usr/local/bin/7z`；脚本默认优先使用清华/中科大 Gentoo distfiles 镜像下载，普通系统 `7z` 可能还要一并映射动态库，静态 `7zz` 更省心。
- 智能调轴依赖容器内 `ffmpeg`、`ffprobe`、`numpy`、`pysubs2`；插件会通过 `requirements.txt` 声明 `pysubs2`，缺失时页面会禁用调轴开关。
- 当前版本不支持 `.7z` 作为上传压缩包。
- 当前版本会去掉同目录里已有字幕文件名中的 `.default` / `.forced` 标记，但不会自动新增这些标记。

宿主机静态 7zz 一键脚本：

```bash
curl -fsSLo /tmp/mp-7zz.sh \
  https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh
sudo bash /tmp/mp-7zz.sh
```

脚本下载顺序为：清华 Gentoo distfiles 镜像、中科大 Gentoo distfiles 镜像、7-Zip 官方站、GitHub Release；如果需要固定下载源，可以设置 `DOWNLOAD_URL` 覆盖。

脚本会优先自动识别运行中的 MoviePilot 容器挂载目录；如果无法确认，会提示输入 MoviePilot 的宿主机映射目录，直接回车则使用默认目录。飞牛常见会落在 `/vol1/1000/docker/moviepilot/tools/7zz`，群晖常见会落在 `/volume1/docker/moviepilot/tools/7zz`；如果识别不到，默认使用 `/volume1/docker/moviepilot/tools/7zz`。脚本会把二进制文件安装为 `0755` 权限。

然后按脚本输出的实际路径给 MoviePilot 服务增加映射，例如：

```yaml
volumes:
  - /volume1/docker/moviepilot/tools/7zz:/usr/local/bin/7z:ro
```

如果你的 MoviePilot 路径比较特殊，可以手动指定宿主机 MoviePilot 目录：

```bash
sudo env MP_HOST_ROOT=/volume1/docker/moviepilot bash /tmp/mp-7zz.sh
```

也可以直接指定二进制文件完整路径：

```bash
sudo env INSTALL_PATH=/volume1/docker/moviepilot/tools/7zz bash /tmp/mp-7zz.sh
```

如需手动指定下载源：
```bash
sudo env DOWNLOAD_URL=https://example.com/7zz.tar.xz bash /tmp/mp-7zz.sh
```
