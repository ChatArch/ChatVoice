# HTTP 接口

网页操作、账号数据和模型处理是不同的接口边界。使用自己的服务根地址；下文路径均为相对路径。

| 接口组 | 授权方式 | 主要用途 |
| --- | --- | --- |
| 会话与账号 | 账号登录后使用 Cookie；写操作验证 CSRF | 受邀账号会话 |
| 会议/对话存储 | Cookie + 所有权检查；写操作需 `X-CSRF-Token` | 保存自己的记录 |
| 数据导出 | Bearer Token 与对应 scope | 程序化只读导出 |
| 文本/ASR/TTS 处理 | 当前可供访客调用；服务端持有模型密钥 | 转换内容，不代表已保存记录 |
| 声音复刻任务 | 账号会话、任务所有权，创建/删除需 CSRF | 授权声音的一次性生成 |
| 会中助手 | 账号 Cookie + 所有权检查；写操作需 CSRF | 预览版材料与快速回答 |

!!! warning "公开入口需要访问与额度控制"
    模型处理接口不是 Bearer 数据导出接口。部署者应限制滥用并核实上游额度，不要把“密钥未暴露给浏览器”误当成无限制开放模型调用。

## 共享登录组件 {#login-ui}

ChatVoice 使用 `ChatLogin>=0.1.2,<0.2.0` 内建的 `ChatVoiceAuth`，直接复用旧账号/会话 schema、密码材料与 Cookie；不另建用户库。宿主只保留连接、HTTP 响应与业务权限映射。

`/login` 使用共享 `LoginUI` 的表单、CSS 和脚本，并提供声笺品牌覆盖。需要其他主题或宿主模板时，通过 Python 入口配置，无需编辑 site-packages：

```python
from chatlogin.ui import LoginUI
from chatvoice.web import create_app

app = create_app(login_ui=LoginUI(
    title="我的语音工作台", palette="forest", layout="split",
    appearance="system", guest_url="/?mode=guest",
))
```

登录前先保存当前草稿并等待 IndexedDB 事务完成。事务中止、保存失败、录音或实时对话尚未结束时，不离开当前页面。访客记录不自动上传，密码、会话和 CSRF 不写入浏览器持久存储。

## 健康、会话与数据 {#records}

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/heartbeat` | 服务版本、数据库状态、ASR 心跳与预热状态 |
| `GET /api/status` | 脱敏配置/模型/语音后端状态 |
| `GET /login` | 可定制的 ChatLogin 共享登录页 |
| `POST /api/auth/login` | `account` 或 `username`、`password`，可选安全本地 `next`；返回用户、CSRF 和回跳信息，并设置会话 Cookie |
| `GET /api/auth/session` | 当前会话状态 |
| `POST /api/auth/logout` | 退出会话；需 CSRF |
| `POST /api/auth/register` | 自助注册关闭，返回 403 |
| `GET /api/meetings` | 当前账号会议元数据列表 |
| `GET/PUT/DELETE /api/meetings/{id}` | 当前账号会议详情/保存/删除 |
| `GET /api/conversations` | 当前账号实时对话元数据 |
| `GET/PUT/DELETE /api/conversations/{id}` | 实时对话详情/保存/删除 |

会议保存包含标题、时间、时长、标签、转写片段、摘要、完善对话，以及 `todo_markdown`、`todo_chat_messages`。详情返回正文，列表保持轻量。旧客户端省略 Todo 字段不会清空既有值，显式空字符串/空列表可以清空。

## 文本处理 {#text}

| 方法与路径 | 请求关键字段 | 返回 |
| --- | --- | --- |
| `POST /api/meeting-title` | `transcript`，可选 `model` | `title`、`model` |
| `POST /api/meeting-notes/polish` | `transcript`、可选 `instruction`/`model` | `content`、`model` |
| `POST /api/meeting-notes/revise/stream` | `transcript`、`current_summary`、`instruction`、可选 `messages`/`model` | SSE：`meta`、`delta`、`done` 或 `error` |

纪要修改流的 `delta.text` 使用画布/回复分隔标记；消费者必须等待明确 `done`，不能把连接断开当成完成。失败时保留当前正文。

## 会中助手预览 {#copilot}

启用 `CHATVOICE_COPILOT_ENABLED=1` 后开放：

| 方法与路径 | 说明 |
| --- | --- |
| `GET /copilot` | 中文优先的会中助手页面 |
| `GET /api/copilot/status` | 启用状态、材料限制、后台准备策略 |
| `GET /api/copilot/materials` | 当前账号材料列表 |
| `POST /api/copilot/materials` | multipart `file`；支持 TXT/MD/PDF/DOCX，需 CSRF |
| `DELETE /api/copilot/materials/{id}` | 删除自己的材料，需 CSRF |
| `POST /api/copilot/answer/stream` | SSE 快速回答，需 CSRF |
| `POST /api/copilot/prepare` | 可选后台准备；未启用自动准备时返回 409 |

回答流事件为 `meta`、`delta`、`done` 或 `error`。`meta.evidence` 是检索到的材料片段，不是外部验证引用；调用方必须等待 `done.completion_marker == "copilot.answer.done"`。请求绑定 `request_id`、`transcript_revision`、`material_revision`，迟到或失效结果应由客户端丢弃。

## Markdown Todo {#todo}

生成只处理传入摘要；不会自动创建会议记录。

```http
POST /api/meeting-notes/todo
Content-Type: application/json
```

```json
{"summary":"先整理核心结论，再撰写初稿并检查引用。"}
```

返回 `content`（完整 Markdown）和 `model`。没有明确行动时可返回“暂无明确待办。”，不强行生成任务。

继续对话修改：

```http
POST /api/meeting-notes/todo/revise
Content-Type: application/json
```

```json
{
  "summary": "整理研究结果并撰写文章。",
  "current_todo": "# Todo\n- [x] 确认主题\n- [ ] 撰写初稿",
  "instruction": "把撰写初稿拆成两个步骤，保留完成状态。",
  "messages": []
}
```

返回完整 `content`、简短 `reply` 和 `model`。摘要/正文各不超过 20000 字符，修改要求不超过 2000 字符，对话最多 12 条，每条为 `role: user|assistant` 与 `text`。当前 Todo 正文由调用方通过原会议保存接口写入。

## 语音处理 {#audio}

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/asr/channels` | 当前可选识别通道 |
| `POST /api/asr` | multipart：`file`、可选 `channel`/`correct`；返回 `raw_text`、`corrected_text`、`channel`、`meta` |
| `WS /ws/asr/stream` | 网页使用的有界 PCM16 流；不是通用云 ASR 协议 |
| `POST /api/tts` | JSON：`text`、可选 `voice`、`format`（`mp3` / `wav`）；返回音频 |
| `GET /api/realtime/models` | 实时模型选择列表，不代表生成权限 |
| `WS /ws/realtime?model={id}` | 当前 Qwen 实时语音代理 |

独立 TTS 响应提供 `X-TTS-Provider`、`X-TTS-Model`、`X-TTS-Voice` 等元数据。必须核对实际音频内容，而不仅是 HTTP 200。

VoiceClone 使用 `GET /api/voice-clone/status`、`POST /api/voice-clone/jobs`、`GET/DELETE /api/voice-clone/jobs/{id}` 和 `GET /api/voice-clone/jobs/{id}/audio`。[声音复刻指南](voice-cloning.md)说明授权和临时任务边界。

创建复刻任务使用 multipart 字段 `reference_audio`、`text`、可选 `lang` / `duration_factor`。声音授权确认由网页流程执行；此 API 没有 `consent` 字段，调用者仍需保证参考声音使用授权。

## API Token 与导出 {#tokens}

网页设置可创建和撤销 Token。也可用命令行：

```bash
chatvoice tokens create --url https://speakr.example.com --account member@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name export --expires-days 30 --scope read:meetings --json
chatvoice data meetings --url https://speakr.example.com --token-env CHATVOICE_DATA_READ --json
chatvoice data meeting MEETING_ID --url https://speakr.example.com --token-env CHATVOICE_DATA_READ --json
```

将创建结果中的一次性密钥安全提供给 `CHATVOICE_DATA_READ`；不要把它写进公共日志。`read:meetings` 对应 `/api/data/meetings[/{id}]`，`read:conversations` 对应 `/api/data/conversations[/{id}]`。Token 不能跨账号或扩大 scope。

| 状态码 | 常见含义 |
| --- | --- |
| 401 | 未登录、会话/Token 失效 |
| 403 | CSRF、权限或明确关闭的操作 |
| 404 | 记录不存在，或不属于当前用户 |
| 422 | 请求形状或长度不合法 |
| 503 | 所需模型配置不完整或能力未配置 |
| 502 | 上游失败、响应无效或模型结果不完整 |

[Python 客户端](interface-tree.md) · [排障](troubleshooting.md)
