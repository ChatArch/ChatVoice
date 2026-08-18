# Python 接口树

`ChatVoice` 的 CLI 保持薄入口；实质能力放在可 import 的 Python 函数、类或 service 层里。

## 包入口

```python
from chatvoice import __version__
```

## 已实现接口

```text
chatvoice
├── accounts.py
│   ├── create_account(account, password, display_name=None)  # 本地创建受邀账号，不返回密码材料
│   └── list_accounts()                                      # 列出账号元数据
├── client.py
│   ├── ChatVoiceClient                                      # cookie/CSRF/Bearer HTTP client
│   ├── create_remote_token(base_url, account, password, ...) # 登录后创建一次性显示的 API token
│   ├── list_remote_tokens(base_url, account, password)       # 读取 token metadata
│   ├── revoke_remote_token(base_url, account, password, id)  # 撤销 token
│   ├── list_remote_meetings(base_url, token)                 # Bearer 读取会议/摘要列表
│   ├── get_remote_meeting(base_url, token, meeting_id)       # Bearer 读取单条会议
│   ├── list_remote_conversations(base_url, token)            # Bearer 读取实时对话列表
│   └── get_remote_conversation(base_url, token, id)          # Bearer 读取单条实时对话
├── asr.py
│   ├── configured_api_endpoint()                            # 读取 ASR API URL，不输出 key
│   ├── default_asr_channel()                                # 解析默认 ASR channel
│   └── get_asr_channels()                                   # 返回脱敏 channel map
├── paths.py
│   ├── state_root()                                         # 解析 ChatVoice state root
│   ├── state_paths()                                        # 返回 RuntimePaths
│   ├── ensure_runtime_dirs()                                # 创建 data/logs/run/temp/cache 目录
│   └── database_settings()                                  # 返回脱敏 DB/concurrency 摘要
├── service.py
│   ├── render_service_plan()                                # 生成部署 plan，不启动服务
│   └── serve_app()                                          # 通过 uvicorn 启 packaged app
├── health.py
│   └── get_status()                                         # 读取 /api/status
├── doctor.py
│   └── run_doctor()                                         # 本地 readiness 摘要
└── web/server.py
    └── create_app()                                         # FastAPI app factory
```

## CLI 到 Python API 映射

| CLI | Python API |
| --- | --- |
| `chatvoice paths` | `chatvoice.paths.state_paths()` |
| `chatvoice doctor` | `chatvoice.doctor.run_doctor()` |
| `chatvoice serve app --dry-run` | `chatvoice.service.render_service_plan()` |
| `chatvoice serve app` | `chatvoice.service.serve_app()` |
| `chatvoice health status` | `chatvoice.health.get_status()` |
| `chatvoice asr channels` | `chatvoice.asr.get_asr_channels()` |
| `chatvoice accounts add` | `chatvoice.accounts.create_account()` |
| `chatvoice accounts list` | `chatvoice.accounts.list_accounts()` |
| `chatvoice tokens create` | `chatvoice.client.create_remote_token()` |
| `chatvoice tokens list` | `chatvoice.client.list_remote_tokens()` |
| `chatvoice tokens revoke` | `chatvoice.client.revoke_remote_token()` |
| `chatvoice data meetings` | `chatvoice.client.list_remote_meetings()` |
| `chatvoice data meeting` | `chatvoice.client.get_remote_meeting()` |
| `chatvoice data conversations` | `chatvoice.client.list_remote_conversations()` |
| `chatvoice data conversation` | `chatvoice.client.get_remote_conversation()` |
| `chatvoice service plan` | `chatvoice.service.render_service_plan()` |

## 更新清单

- 每个实质 CLI 命令都要能映射到 importable API。
- 文档里的函数签名应和代码一致。
- 对外诊断输出默认不要泄漏 token、cookie、内部 URL、原始录音或完整 transcript。
- 涉及数据库或服务重启的 API 要先暴露 plan/readback，再加 mutation。
