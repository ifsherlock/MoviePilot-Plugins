# MoviePilot-Plugins

同时维护 MoviePilot V2 与 V3 的个人插件仓库，目前主要维护字幕匹配和 AI 字幕生成。

## 展示图

![插件界面](images/plugin-preview.svg)

![字幕批量搜索](images/subtitle-batch-search.png)

## 开发初衷

这个仓库主要想把 MoviePilot 里的字幕处理做成一条顺手的链路：本地媒体库、在线字幕、手动上传、智能匹配、调轴、AI 翻译都能接起来。
它不是 ChineseSubFinder 的复刻，而是在 MoviePilot 插件体系里延续“少折腾文件，多专注观影”的使用体验。

## 插件列表

| 插件 | V2 版本 | V3 版本 | 主要功能 |
| --- | --- | --- | --- |
| 海拉鲁字幕大师 | 0.1.91 | 1.2.7 | 字幕搜索、下载、上传、匹配、改名、调轴、入库自动处理 |
| AI字幕生成(联动版) | 3.5.60 | 4.0.1 | 音轨识别、字幕提取、AI 翻译、任务队列、联动字幕匹配 |

## 字幕匹配

从 MoviePilot 本地整理记录中选择电影或剧集，完成字幕上传、在线搜索、批量匹配和落盘改名。

完整配置和额外 STRM 使用方法见：[海拉鲁字幕大师功能使用教学](docs/SubtitleManualUpload功能使用教学.md)。

主要功能：

- 支持电影、单集、整季维度的字幕匹配。
- 支持 `.srt`、`.ass`、`.ssa`、`.sbv`、`.sub`、`.vtt`、`.webvtt`。
- 支持 ZIP/RAR 字幕包解析。
- 支持 SubHD、Zimuku、ASSRT、OpenSubtitles 等在线字幕来源。
- 支持语言和格式偏好，自动选择合适字幕入库。
- 支持繁体转简体、智能调轴、匹配历史管理。
- 支持入库后自动搜索字幕。
- 可联动 AI字幕生成(联动版)，把英文或外语字幕提交翻译。

## AI字幕生成(联动版)

用于从音轨、内嵌字幕或外挂字幕生成中文字幕，也可以接收“字幕匹配”提交的在线英文字幕。

主要功能：

- 支持 faster-whisper 语音识别。
- 支持优先使用外挂字幕或内嵌字幕。
- 支持 OpenAI 兼容接口翻译。
- 支持双语字幕或纯中文字幕输出。
- 支持批量任务、任务状态查看、取消和重新生成。
- 支持与“字幕匹配”互相联动。

## 安装方式

在 MoviePilot 第三方插件仓库中添加本仓库地址：

```text
https://github.com/ifsherlock/MoviePilot-Plugins
```

如只测试字幕链路，建议同时安装：

- 字幕匹配
- AI字幕生成(联动版)

## 注意事项

- 字幕站点和 API 可能变化，在线下载不能保证所有来源始终可用。
- RAR 解压依赖容器内或宿主机可用的解压工具。
- 智能调轴依赖 `ffmpeg`、`ffprobe`、`numpy`、`pysubs2` 等环境能力；V3 已内置 Python 3.14 Linux amd64/arm64 的 WebRTC VAD wheel。
- AI 翻译质量取决于模型、提示词和原字幕质量。

## 致谢

本仓库基于 MoviePilot 插件机制开发。

参考项目和源代码：

- [MoviePilot](https://github.com/jxxghp/MoviePilot)
- [MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins)
- [ChineseSubFinder](https://github.com/ChineseSubFinder/ChineseSubFinder)
- [allanpk716/chinesesubfinder](https://github.com/allanpk716/chinesesubfinder)

主要依赖库：

- `faster-whisper`
- `openai`
- `httpx`
- `watchdog`
- `pillow`
- `pysubs2`
- `rarfile`
- `webrtcvad-wheels`
- `numpy`
