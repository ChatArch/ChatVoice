# ChatVoice 文档

ChatVoice 是 ChatArch 系列 Python 包，用于把 Speakr 录音、转写、会议纪要和语音工作区能力打包成可安装、可启动、可维护、可通过 API 读取数据的服务。

站点入口：<https://arch.gh.wzhecnu.cn/ChatVoice/>

## 按场景选择文档

| 场景 | 文档 |
| --- | --- |
| 通过 PyPI 包安装并启动服务 | [部署与启动](deployment.md) |
| 查看安装位置、运行目录和 SQLite/IndexedDB 数据结构 | [运行目录与数据结构](runtime-layout.md) |
| 理解当前版本为什么不保存原始录音 | [录音保存边界](recording-storage.md) |
| 生成 API Token 并读取会议/摘要数据 | [API 访问](api-access.md) |
| 回读真实命令树和命令边界 | [CLI 树](cli-tree.md) |
| 校对当前包有哪些一等能力和边界 | [能力地图](capability-map.md) |
| 从 Python 代码调用包能力 | [Python 接口树](interface-tree.md) |

## 核心入口

<div class="grid cards" markdown>

- **部署与启动**

    从 `python -m pip install "ChatVoice[web]==0.1.8"` 到 `chatvoice serve app`，说明运行目录、账号创建、ASR API provider、数据库并发边界。

    [查看部署教程](deployment.md)

- **API 访问**

    说明网页登录、API Token 生命周期，以及 `chatvoice data ...` 读取会议转写、会议摘要和实时对话记录。

    [查看 API 访问](api-access.md)

- **运行目录与数据结构**

    说明 `site-packages` 安装位置、`~/.chatarch/chatvoice` 默认运行目录、SQLite 表结构、IndexedDB、`temp/asr` 和 `model-cache`。

    [查看运行目录](runtime-layout.md)

- **录音保存边界**

    说明会议记录页只保存文字和摘要，不保存原始录音；如果未来要做纯录音，应作为单独能力设计。

    [查看录音保存边界](recording-storage.md)

- **CLI 树**

    从命令行入口开始，记录真实已实现命令、命令状态和交互约定。

    [查看 CLI 树](cli-tree.md)

- **能力地图**

    用于 review 当前包的能力边界，避免把规划写成已实现功能。

    [查看能力地图](capability-map.md)

- **Python 接口树**

    保持命令行是薄入口，实质能力放在可 import 的 Python 接口中。

    [查看接口树](interface-tree.md)

</div>

## 0.1.8 部署边界

- Web 服务由 `chatvoice serve app` 启动 packaged FastAPI app。
- Fresh start 可通过 `chatvoice accounts add` 创建受邀账号，不依赖源码根目录脚本。
- 登录后可在页面生成 API Token；CLI 可用 token 读取会议、摘要和实时对话数据。
- 会议记录页不提供原始录音保存或下载；服务器只保存文字、摘要和元数据。
- ASR 生产推荐通过 `api-server` 调云服务或自建 GPU ASR server。
- `stub-local` 只用于无凭据/无 GPU 的合同 smoke。
- v0.1.8 默认 SQLite WAL，适合单服务进程轻并发；高并发数据库迁移需单独版本。

## 本地预览文档

```bash
python -m pip install -e ".[docs]"
mkdocs serve
```

英文首页见站点语言入口：<https://arch.gh.wzhecnu.cn/ChatVoice/en/>。
