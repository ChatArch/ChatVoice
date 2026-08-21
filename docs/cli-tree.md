# CLI 树

`chatvoice --tree` 与 `chatvoice --tree-brief` 由共享的 `chatstyle.add_tree_option()` 从真实 Click 注册表渲染。完整树保留参数签名，简洁树保留相同节点与用途但省略签名。CLI 只做参数解析和展示，实际能力放在可 import 的 Python 函数中。

可导入 Python 函数映射见 [接口树](interface-tree.md)。部署教程见 [部署与启动](deployment.md)。API Token 与数据读取见 [API 访问](api-access.md)。

## 当前已实现命令

```text
chatvoice
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── accounts  # Manage invited accounts in the local service database.
│   ├── add <ACCOUNT> [--display-name DISPLAY-NAME] [--password-env PASSWORD-ENV] [--json]  # Create one invited account; writes the local service database.
│   └── list [--json]  # List invited account metadata; read-only, without passwords.
├── asr  # Inspect ASR provider configuration; no secret values.
│   └── channels [--json]  # List ASR channel readiness; read-only and secret-safe.
├── data  # Read meeting and conversation records from a running service.
│   ├── conversation <CONVERSATION-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one realtime conversation; outputs stored messages.
│   ├── conversations [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List realtime conversation metadata; read-only output.
│   ├── meeting <MEETING-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one meeting; outputs its transcript and summary.
│   └── meetings [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List meeting metadata; read-only text or JSON output.
├── doctor [--json]  # Check local service readiness; read-only and secret-safe.
├── health  # Read health from a running ChatVoice service; no writes.
│   └── status [--url URL] [--timeout TIMEOUT] [--json]  # Read /api/status; returns redacted text or JSON.
├── paths [--json]  # Show resolved runtime paths; read-only text or JSON output.
├── serve  # Start packaged ChatVoice services; long-running side effects.
│   └── app [--host HOST] [--port PORT] [--reload] [--workers WORKERS] [--dry-run] [--json]  # Start the Speakr web app; --dry-run only prints a safe plan.
├── service  # Plan and inspect ChatVoice service deployment.
│   └── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a safe plan; --ensure-dirs creates runtime directories.
└── tokens  # Manage service API tokens; remote credential side effects.
    ├── create [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--name NAME] [--expires-days EXPIRES-DAYS] [--scope SCOPES] [--timeout TIMEOUT] [--json]  # Create a remote token; prints its secret value exactly once.
    ├── list [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # List remote token metadata; read-only, without token values.
    └── revoke <TOKEN-ID> [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # Revoke a remote API token by id; destructive credential write.
```

## 简洁命令树

```text
chatvoice
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── accounts  # Manage invited accounts in the local service database.
│   ├── add  # Create one invited account; writes the local service database.
│   └── list  # List invited account metadata; read-only, without passwords.
├── asr  # Inspect ASR provider configuration; no secret values.
│   └── channels  # List ASR channel readiness; read-only and secret-safe.
├── data  # Read meeting and conversation records from a running service.
│   ├── conversation  # Read one realtime conversation; outputs stored messages.
│   ├── conversations  # List realtime conversation metadata; read-only output.
│   ├── meeting  # Read one meeting; outputs its transcript and summary.
│   └── meetings  # List meeting metadata; read-only text or JSON output.
├── doctor  # Check local service readiness; read-only and secret-safe.
├── health  # Read health from a running ChatVoice service; no writes.
│   └── status  # Read /api/status; returns redacted text or JSON.
├── paths  # Show resolved runtime paths; read-only text or JSON output.
├── serve  # Start packaged ChatVoice services; long-running side effects.
│   └── app  # Start the Speakr web app; --dry-run only prints a safe plan.
├── service  # Plan and inspect ChatVoice service deployment.
│   └── plan  # Render a safe plan; --ensure-dirs creates runtime directories.
└── tokens  # Manage service API tokens; remote credential side effects.
    ├── create  # Create a remote token; prints its secret value exactly once.
    ├── list  # List remote token metadata; read-only, without token values.
    └── revoke  # Revoke a remote API token by id; destructive credential write.
```

## Fresh-start 服务入口

```bash
python -m pip install "ChatVoice[web]==0.1.8"
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
