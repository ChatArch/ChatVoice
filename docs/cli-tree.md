# CLI 树

`chatvoice --tree` 是每次 CLI 更新都要同步回读的真实命令契约。CLI 只做参数解析和展示，实际能力放在可 import 的 Python 函数中。

可导入 Python 函数映射见 [接口树](interface-tree.md)。部署教程见 [部署与启动](deployment.md)。

## 当前已实现命令

```text
chatvoice  # ChatVoice command line interface
├── --help  # Show help for the current command.
├── --version  # Show package version.
├── --tree  # Print the registered CLI tree.
├── paths [--json]  # Show resolved ChatVoice runtime paths
├── doctor [--json]  # Check local ChatVoice service readiness without secrets
├── serve  # Start packaged ChatVoice services
│   └── app [--host HOST] [--port PORT] [--reload] [--workers WORKERS] [--dry-run] [--json]  # Start the packaged Speakr web application
├── health  # Read health from a running ChatVoice service
│   └── status [--url URL] [--timeout TIMEOUT] [--json]  # Read the /api/status endpoint
├── asr  # Inspect ASR provider configuration
│   └── channels [--json]  # List ASR channels and API-provider readiness
└── service  # Plan and inspect ChatVoice service deployment
    └── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a sanitized service deployment plan
```

## 基础入口

```bash
chatvoice --help
chatvoice --version
chatvoice --tree
chatvoice paths --json
chatvoice doctor --json
```

## 启动服务

```bash
python -m pip install "ChatVoice[web]==0.0.2"
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

如果接自建 GPU ASR server 或云 ASR：

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

## 状态约定

| 状态 | 含义 |
| --- | --- |
| 已实现 | 命令、函数和测试已经存在 |
| 已验证 | 已通过本地测试、构建或发布后 smoke |
| 规划 / checkpoint | 只保留边界说明；实现前不要写操作教程 |

## 更新清单

- 每个实质 CLI 命令都要能映射到 Python 函数、类或 service 层。
- 新增命令后同步更新 README、CLI 树、接口树、能力地图、测试和部署文档。
- 涉及远端状态或服务重启的命令必须先有 dry-run / plan / readback 边界。
- 不在 CLI 或日志中输出 token、cookie、Authorization header、原始录音或完整 transcript。
