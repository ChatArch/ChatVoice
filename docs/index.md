# ChatVoice 文档

从语音记录到清晰的下一步。ChatVoice 提供 Speakr 网页、命令行和 Python 接口；按你的目标选择入口，不必从头阅读整套文档。

<div class="grid cards" markdown>

- :material-rocket-launch: **先把服务跑起来**

    ---
    安装、无模型体验、真实 ASR 选择与第一份会议记录。

    [快速上手](quickstart.md)

- :material-microphone: **录音与整理纪要**

    ---
    理解暂停、继续、摘要、手工编辑和对话改写。

    [网页使用](web-guide.md)

- :material-checkbox-marked-outline: **把想法转为 Todo**

    ---
    由你点击转换，继续对话完善，保留标准 Markdown。

    [Markdown Todo](markdown-todo.md)

- :material-cog: **配置模型与部署**

    ---
    分清 ASR、文本、TTS、实时语音和声音复刻的设置。

    [配置参考](configuration.md) · [部署](deployment.md)

- :material-console: **接入脚本或其他应用**

    ---
    查看真实命令拓扑、HTTP 协议与可导入的 Python 接口。

    [CLI 树](cli-tree.md) · [HTTP 接口](api-access.md) · [Python 接口树](interface-tree.md)

- :material-shield-check: **理解边界与验证**

    ---
    看清保存什么、需要什么权限，以及失败时如何检查。

    [数据保留](recording-storage.md) · [排障](troubleshooting.md) · [测试](testing.md)

</div>

## 按角色选择

| 角色 | 推荐阅读顺序 |
| --- | --- |
| 网页使用者 | 网页使用 → Markdown Todo / 声音复刻 |
| 服务部署者 | 快速上手 → 配置参考 → 部署与启动 → 排障 |
| 集成开发者 | 能力地图 → CLI 树 / HTTP 接口 / Python 接口树 |
| 贡献者 | Python 接口树 → 开发与验证 |

## 核心边界

- 账号记录保存在服务端，访客记录保存在当前浏览器。
- 会议录音不进入长期音频档案；摘要、Todo 和文字记录可以保存。
- Todo 仅在用户主动转换时生成，不自动执行任务。
- 安装包、配置字段存在、模型列表可读与真实功能可用，是不同层次的状态。

[查看能力地图](capability-map.md)
