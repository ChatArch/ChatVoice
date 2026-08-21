# CLI 树

`chatvoice --tree` 是每次 CLI 更新都要同步回读的真实命令契约。CLI 只做参数解析和展示，实际能力放在可 import 的 Python 函数中。

可导入 Python 函数映射见 [接口树](interface-tree.md)。部署教程见 [部署与启动](deployment.md)。API Token 与数据读取见 [API 访问](api-access.md)。

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
├── accounts  # Manage invited accounts in the local service database
│   ├── add ACCOUNT [--display-name DISPLAY-NAME] [--password-env PASSWORD-ENV] [--json]  # Create one invited account from the packaged runtime
│   └── list [--json]  # List invited account metadata without password material
├── tokens  # Manage service API tokens for automation
│   ├── create [--url URL] --account ACCOUNT [--password-env PASSWORD-ENV] [--name NAME] [--expires-days EXPIRES-DAYS] [--scope SCOPES] [--timeout TIMEOUT] [--json]  # Create a one-time-visible API token after account login
│   ├── list [--url URL] --account ACCOUNT [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # List API token metadata without revealing token values
│   └── revoke TOKEN-ID [--url URL] --account ACCOUNT [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # Revoke an API token by id
├── data  # Read meeting and conversation data from a running service
│   ├── meetings [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List meeting metadata; use data meeting for transcript and summary
│   ├── meeting MEETING-ID [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one meeting with transcript and summary
│   ├── conversations [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List realtime conversation metadata; use data conversation for messages
│   └── conversation CONVERSATION-ID [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one realtime conversation with messages
└── service  # Plan and inspect ChatVoice service deployment
    └── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a sanitized service deployment plan
```

## Fresh-start 服务入口

```bash
python -m pip install "ChatVoice[web]==0.1.5"
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

## 账号、Token 和数据读取

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json

read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
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
- 不在普通诊断、日志或 PR 说明中输出 token、cookie、Authorization header、原始录音或完整 transcript；数据导出命令只在用户显式调用时返回记录内容。
