# SubtitleManualUpload

MoviePilot V2 插件，提供手动上传字幕并匹配改名的页面。

当前能力：

- 从 MoviePilot 本地整理记录中搜索电影或剧集，只展示本地真实存在的视频资源。
- 第一层搜索/选择本地电影或剧集；选中剧集后进入每集列表。
- 剧集支持横向季度卡片，可切换单季或“全部季”。
- 每集列表支持全选/反选、单集上传、锁定集数、CC 图标查看已有外挂字幕。
- 批量上传会弹出拖拽上传卡片，自动匹配字幕、目标视频和最终改名结果；锁定集数会被跳过。
- 支持批量清空选中集的外挂字幕，仅删除与视频同名开头的外挂字幕文件。
- `.strm` 会按本地视频目标参与统计和匹配。
- 上传字幕文件：`.srt`、`.ass`、`.ssa`、`.sbv`、`.sub`、`.vtt`、`.webvtt`。
- 上传 `.zip` 压缩包并自动解包其中的字幕文件。
- 新增轻量 Python RAR 依赖 `rarfile` 声明；上传 `.rar` 压缩包时仍需要容器内 `unrar`、`bsdtar`、`7z`、`7za` 或 `7zz` 负责实际解包，缺失时会明确提示。
- 上传弹窗内可点开“RAR 不能解压？查看处理方式”，查看临时安装、插件加载时自动安装或宿主机静态 `7zz` 映射说明。
- 插件设置可选择 RAR 解压器处理方式：不处理、加载插件时尝试容器内安装、使用宿主机映射文件。
- 写入前可选“智能调轴”：优先用视频内置文本字幕做基准，没有内置字幕时用 `ffmpeg` 抽取音频并通过 FFT 互相关计算整体偏移。
- 按目标视频文件名生成外挂字幕名并直接落盘。

命名策略：

- 默认生成 `视频文件名.语言标识.字幕后缀`。
- 语言标识使用媒体服务器常用的 ISO 639 三字母码，例如中文 `chi`、英文 `eng`、日文 `jpn`、韩文 `kor`。
- 例如：`Episode.Name.S01E01.chi.ass`。

限制说明：

- 当前版本只支持可从 MoviePilot 本地媒体库读取到的本地视频文件。
- `rarfile` 是最轻量的 Python RAR 封装层，但不是纯 Python 解压器；RAR5/压缩内容仍依赖外部解压程序。
- 临时测试可在插件设置中选择“加载插件时尝试容器内安装”，或进入 MoviePilot 容器安装 `p7zip-full` / `unrar-free` / `unrar`；容器重建后可能失效。
- 长期建议在宿主机安装静态 `7zz` 并映射为容器内 `/usr/local/bin/7z`；普通系统 `7z` 可能还要一并映射动态库，静态 `7zz` 更省心。
- 智能调轴依赖容器内 `ffmpeg`、`ffprobe`、`numpy`、`pysubs2`；插件会通过 `requirements.txt` 声明 `pysubs2`，缺失时页面会禁用调轴开关。
- 当前版本不支持 `.7z` 作为上传压缩包。
- 当前版本会去掉同目录里已有字幕文件名中的 `.default` / `.forced` 标记，但不会自动新增这些标记。

宿主机静态 7zz 一键脚本：

```bash
curl -fsSLo /tmp/mp-7zz.sh \
  https://raw.githubusercontent.com/ifsherlock/MoviePilot-Plugins/main/plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh
sudo bash /tmp/mp-7zz.sh
```

脚本默认安装到 `/opt/bin/7zz`，然后按提示给 MoviePilot 服务增加映射：

```yaml
volumes:
  - /opt/bin/7zz:/usr/local/bin/7z:ro
```
