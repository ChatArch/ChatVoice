# API 访问

ChatVoice 0.1.8 提供从 packaged service 读取会议和对话数据的闭环：先用受邀账号登录，再生成 API Token，最后用 bearer token 调 `/api/data/...` 或 `chatvoice data ...`。

## 访问模型

| 入口 | 凭证 | 用途 |
| --- | --- | --- |
| 浏览器登录 | HttpOnly session cookie + CSRF token | 保存会议、对话、网页创建/撤销 API Token |
| 浏览器声音复刻 | HttpOnly session cookie + CSRF token | 上传参考音频并创建一次性 VoiceClone job |
| API Token | Bearer token | 自动化读取会议转写、会议摘要和实时对话文本 |
| 游客模式 | 浏览器 IndexedDB | 本机试用；不写后端数据库，也不能生成 API Token |

Token 明文只在创建时返回一次。后端 SQLite 只保存 hash、prefix、scope、创建时间、过期时间、撤销时间和最近使用时间。

## Fresh-start 本地流程

安装并启动服务：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.8"
chatvoice service plan --ensure-dirs --json
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

另开一个 shell，在同一 runtime 下创建受邀账号：

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

浏览器打开 `http://127.0.0.1:18087/`，登录账号，创建或打开会议并生成摘要。

## 从网页生成 Token

1. 点击右上角 **识别设置**。
2. 在 **API Token** 面板填写名称和可选有效期。
3. 点击 **生成 Token**。
4. 立即复制返回值；关闭后只能看到 token metadata，不能再次查看明文。
5. 如需停用，点击 token 行上的 **撤销**。

## 从 CLI 生成 / 查看 / 撤销 Token

CLI 通过网页登录接口创建 token，因此需要账号密码。密码只从环境变量读取：

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
chatvoice tokens list --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice tokens revoke <token-id> --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
```

## 读取会议和对话数据

把创建时显示的一次性 token 放入 `--token-env` 指定的环境变量：

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data meeting <meeting-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversation <conversation-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

对应 HTTP 入口：

```text
GET /api/data/meetings
GET /api/data/meetings/{meeting_id}
GET /api/data/conversations
GET /api/data/conversations/{conversation_id}
```

列表接口只返回 metadata / preview；详情接口才返回会议 transcript、summary 或实时对话 messages，避免普通轮询把完整文本打进日志。

## 声音复刻 job API

声音复刻不是 bearer-token 数据读取接口；它是登录会话内的交互式网页能力。浏览器用 HttpOnly session cookie 和 CSRF token 提交 multipart 表单：

```text
GET    /api/voice-clone/status
POST   /api/voice-clone/jobs
GET    /api/voice-clone/jobs/{job_id}
GET    /api/voice-clone/jobs/{job_id}/audio
DELETE /api/voice-clone/jobs/{job_id}
```

`POST /api/voice-clone/jobs` 字段：

```text
text              要让复刻声音说出的新文本
lang              ZH / EN / JA / ES / AR 等语言代码
duration_factor   语速倍率，默认 1
reference_audio   用户上传或录制的授权参考音频文件
```

这个接口只代理本地 VoiceClone sidecar，不把 provider secret 发给浏览器；生成结果是临时 job audio，不创建 voice profile，也不进入会议历史。完整网页流程见 [声音复刻使用指南](voice-cloning.md)。

请求需要：

```text
Authorization: Bearer <api-token>
```

## Scope 和边界

当前支持 scope：

```text
read:meetings
read:conversations
```

边界：

- API Token 只能读数据，不能写会议、改摘要或管理账号。
- 创建 token 时省略 `scopes` 会使用两个默认 read scope；显式传空列表会被拒绝。
- Token 被撤销或过期后立即不可用。
- 详情数据读取接口会返回转写文本和摘要内容；不要把输出贴入公共日志或 PR。
- 原始录音文件仍不进入后端数据库，也不通过这些数据接口返回。
