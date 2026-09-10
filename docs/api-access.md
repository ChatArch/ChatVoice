# API 访问

通过受邀账号登录 ChatVoice，创建 API Token，再从数据接口或 `chatvoice data` 读取自己的会议与对话。

## 登录后端与前端边界

ChatVoice 依赖 `ChatLogin>=0.1.1,<0.2.0` 的认证/会话核心，保留自己的 HTML、CSS、原生 JavaScript 和登录/访客弹窗，不注入默认登录模板。宿主适配层沿用 `accounts`、`auth_sessions`、原账号 ID 和 PBKDF2 材料，不新增用户库、不强制改密码。

原 `/api/auth/*`、JSON 字段和 Cookie 契约保持兼容。已有账号映射为普通用户，不新增 Web Admin。会议/对话 owner 检查和 API Token scope 仍由 ChatVoice 负责；访客 IndexedDB 记录不会自动上传。发布包不等于重启服务或迁移生产数据。

## 访问模型

系统语音支持[独立 TTS 协议配置](tts-models.md)：`POST /api/tts` 仍接受 text、可选 voice 和 mp3/wav；默认音色取配置首项，响应使用 `X-TTS-Provider/Model/Voice`。`GET /api/status` 新增安全 `tts` 对象；配置错误返回 503，上游失败返回固定脱敏 502。数据访问、鉴权和复刻接口不变。

| 入口 | 凭证 | 用途 |
| --- | --- | --- |
| 浏览器登录 | HttpOnly session cookie + CSRF | 保存会议/对话、创建和撤销 API Token |
| 浏览器声音复刻 | HttpOnly session cookie + CSRF | 授权参考音频和一次性 VoiceClone job |
| 数据 API Token | Bearer 认证方案 | 自动化读取自己被 scope 允许的文本/标签/摘要 |
| 访客模式 | 浏览器 IndexedDB | 本机试用，不写入后端账户记录，不创建 API Token |

Token 明文仅在创建时返回一次。SQLite 保存摘要、前缀、scope、创建/到期/撤销与最近使用时间，不保存明文 Token。

## Fresh-start 本地流程

```bash
python -m pip install "ChatVoice[web]==0.1.16"
chatvoice service plan --ensure-dirs --json
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

在同一运行目录对应的另一个 shell 中创建受邀账号：

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

测试入口是 `http://127.0.0.1:18087/`。`stub-local` 用于不调用真实模型的接口测试；正式转写和摘要需要单独配置服务器端模型服务。不要把这个回环地址当作已部署公网入口。

## 从网页生成 Token

在设置的 API Token 区域创建令牌，指定名称和有效期。复制创建时显示的唯一明文；关闭后只查看元数据。退出登录和切换存储模式时不要保留一次性 Token 显示。

## 从 CLI 生成 / 查看 / 撤销 Token

```bash
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
chatvoice tokens list --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice tokens revoke <token-id> --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
```

密码由环境变量传递，不放进命令行参数值。创建输出含一次性 Token，不应粘贴到公共日志或 PR。

## 读取会议和对话数据

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data meeting <meeting-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversation <conversation-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

HTTP 客户端在 `Authorization` 请求头中使用 `Bearer` 认证方案，凭证是已创建的数据 API Token。

```text
GET /api/data/meetings
GET /api/data/meetings/{meeting_id}
GET /api/data/conversations
GET /api/data/conversations/{conversation_id}
```

会议列表返回元数据/预览和 `tags`，详情再返回转写与摘要。对话详情返回 realtime messages。不要把完整正文用于普通轮询日志。

## 声音复刻 job API

这不是数据 Bearer Token 接口。网页使用登录 Cookie 和 CSRF，提交 multipart 表单：

```text
GET    /api/voice-clone/status
POST   /api/voice-clone/jobs
GET    /api/voice-clone/jobs/{job_id}
GET    /api/voice-clone/jobs/{job_id}/audio
DELETE /api/voice-clone/jobs/{job_id}
```

创建字段为 `text`、`lang`、`duration_factor` 与 `reference_audio`。接口代理本地 sidecar；provider secret 不发送给浏览器。生成音频是临时 job 产物，不创建 voice profile，也不进入会议历史。参见 [声音复刻使用指南](voice-cloning.md)。

## Scope 和边界

- 支持 `read:meetings` 和 `read:conversations`。
- Token 只读，不能写会议、改摘要或管理账号；省略 scopes 使用两个默认读权限，显式空数组被拒绝。
- 到期或撤销后立即不可用，读取仍按 Token owner 隔离。
- 会议标签为去重字符串数组，旧数据缺失标签时返回 `[]`。
- 原始录音不进入后端数据库，也不通过数据接口返回。
