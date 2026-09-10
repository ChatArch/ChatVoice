# Python 接口树

CLI 是下列 Python 能力的薄入口。配置、服务端处理和远端数据读取各自有清晰边界；函数签名以已安装包为准。

| 场景 | 模块 |
| --- | --- |
| 本地账号、路径与数据库备份 | `accounts`、`paths`、`backup` |
| 启动或检查服务 | `service`、`health`、`doctor`、`web.server` |
| 调用已有服务 | `client.ChatVoiceClient` 与客户端函数 |
| 嵌入模型适配与 Todo 转换 | `text_api`、`tts_api`、`todo_markdown` |

## 路径、账号与备份

```text
chatvoice
├── paths
│   ├── RuntimePaths / state_paths() / state_root()  # 解析运行路径
│   ├── ensure_runtime_dirs()                      # 创建运行目录
│   └── database_settings()                        # 脱敏存储状态
├── accounts
│   ├── create_account(account, password, display_name=None)
│   └── list_accounts()
└── backup
    ├── dump_database(output, *, overwrite=False)
    └── import_database(input_path, *, backup_current=True)
```

```python
from chatvoice.paths import state_paths
from chatvoice.backup import dump_database

paths = state_paths()
result = dump_database(paths.root / "backup.sqlite3")
```

备份示例会写文件；导入需要先停止服务。[数据布局与恢复](runtime-layout.md)。

## 服务入口

```text
chatvoice
├── service.render_service_plan(*, host, port, workers)  # 只生成计划
├── service.serve_app(*, host, port, reload, workers)     # 启动服务
├── web.server.create_app()                             # FastAPI 应用工厂
├── health.get_status(base_url, *, timeout)              # HTTP 状态读取
├── doctor.run_doctor()                                 # 本机检查
└── asr.get_asr_channels()                              # 识别配置摘要
```

应用工厂沿用包的配置与数据根目录，不代表独立沙箱。嵌入前先设置需要的进程环境。

## 远端客户端

```text
chatvoice.client
├── ChatVoiceClient(base_url, timeout)
│   ├── login(account, password)
│   ├── create_token(...) / list_tokens() / revoke_token(token_id)
│   ├── list_meetings(token) / get_meeting(token, meeting_id)
│   └── list_conversations(token) / get_conversation(token, conversation_id)
├── create_remote_token(...) / list_remote_tokens(...) / revoke_remote_token(...)
├── list_remote_meetings(base_url, token) / get_remote_meeting(base_url, token, meeting_id)
└── list_remote_conversations(base_url, token) / get_remote_conversation(base_url, token, conversation_id)
```

```python
import os
from chatvoice.client import get_remote_meeting

meeting = get_remote_meeting(
    "https://speakr.example.com",
    os.environ["CHATVOICE_DATA_READ"],
    "MEETING_ID",
)
print(meeting.get("todo_markdown", ""))
```

读取 Token 需要匹配 scope。`ChatVoiceApiError` 提供可检查的 `status_code`；不要把含私人记录的异常正文公开记录。

## 模型与 Todo 模块

```text
chatvoice
├── config.ChatVoiceConfig                           # ChatEnv 类型注册
├── text_api
│   ├── resolve_text_settings(values, purpose, *, req_model=None)
│   ├── complete_text(settings, messages, ...)
│   └── stream_text(settings, messages, ...)
├── tts_api
│   ├── resolve_tts_settings(values)
│   └── synthesize(settings, text, *, voice=None, format='mp3')
└── todo_markdown
    ├── generate_todo(summary, call_model)
    └── revise_todo(summary, current_todo, instruction, messages, call_model)
```

Todo 函数不自行保存数据；`call_model` 是调用者提供的函数，接收 `transcript`、`instruction` 两个关键字参数，返回含 `content`、`model` 的字典。模块检查格式和长度，不声称能证明语义真实性。普通集成优先调用已部署服务的 [Todo HTTP 接口](api-access.md#todo)，避免依赖网页模块的私有函数。

## CLI 对应关系

| CLI | Python |
| --- | --- |
| `paths` / `doctor` | `state_paths` / `run_doctor` |
| `serve app` / `service plan` | `serve_app` / `render_service_plan` |
| `accounts add/list` | `create_account` / `list_accounts` |
| `tokens create/list/revoke` | 对应 `*_remote_token*` 客户端函数 |
| `data meeting(s)/conversation(s)` | 对应 `get_remote_*` / `list_remote_*` |
| `data dump/import` | `dump_database` / `import_database` |

[完整 CLI 树](cli-tree.md) · [能力边界](capability-map.md)
