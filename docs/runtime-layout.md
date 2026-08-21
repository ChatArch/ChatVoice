# 运行目录与数据结构

这一页说明 `pip install "ChatVoice[web]==0.1.6"` 之后，代码安装在哪里、运行数据默认写到哪里，以及 SQLite / 浏览器侧分别保存什么。

## 代码安装位置

`pip install` 安装的是 Python distribution，不需要源码目录即可运行：

```text
<venv>/lib/pythonX.Y/site-packages/chatvoice/
<venv>/bin/chatvoice
```

如果没有虚拟环境，位置由当前 Python 的 `site-packages` 决定。生产建议使用独立 venv，例如：

```text
/opt/chatvoice/.venv/lib/pythonX.Y/site-packages/chatvoice/
/opt/chatvoice/.venv/bin/chatvoice
```

## 默认运行根目录

ChatVoice 的状态目录解析顺序：

1. `CHATVOICE_RUNTIME_ROOT`
2. `CHATVOICE_HOME`
3. `CHATARCH_HOME/chatvoice`
4. `~/.chatarch/chatvoice`

默认结构：

```text
~/.chatarch/chatvoice/
├── data/
│   └── meetings.sqlite3
├── logs/
├── run/
├── temp/
│   └── asr/
└── model-cache/
```

常用覆盖：

```bash
export CHATARCH_HOME=/srv/chatarch
# runtime root => /srv/chatarch/chatvoice

export CHATVOICE_HOME=/srv/chatvoice
# runtime root => /srv/chatvoice
```

SQLite 文件也可以用兼容变量直接指定：

```bash
export CHATVOICE_SQLITE_PATH=/srv/chatvoice/data/meetings.sqlite3
# or legacy-compatible:
export MEETING_DB_PATH=/srv/chatvoice/data/meetings.sqlite3
```

## 后端 SQLite 数据结构

默认数据库：

```text
~/.chatarch/chatvoice/data/meetings.sqlite3
```

核心表：

| Table | 内容 | 备注 |
| --- | --- | --- |
| `accounts` | 受邀账号、显示名、password salt/hash | 不保存明文密码 |
| `auth_sessions` | 登录 session hash、CSRF、过期时间 | cookie 只保存 session token |
| `api_tokens` | automation token id、hash、prefix、scope、撤销/过期时间 | 明文 token 只在创建时返回一次 |
| `meeting_records` | 会议标题、时间、时长、transcript JSON、summary、preview | 原始音频不进数据库 |
| `conversation_records` | 实时对话标题、message JSON、preview | 不保存对话音频 |

转写段落、会议摘要、纪要修改对话、实时对话消息以 JSON 字符串保存到 SQLite `TEXT` 字段。列表数据接口只返回 metadata / preview；详情接口才返回 transcript、summary 或 messages。

## 浏览器本地数据

访客模式数据保存在当前浏览器 IndexedDB：

```text
IndexedDB: speakr-meetings
- guest meetings
- guest summaries and metadata
```

登录账号模式下，会议/对话文本保存到服务端 SQLite。当前会议记录页不提供录音保存/下载功能，也不在浏览器 IndexedDB 中保存录音分片。音频只用于实时 ASR，持久化结果是文字和摘要。详见 [录音保存边界](recording-storage.md)。

## 临时音频与模型缓存

- `temp/asr/`：ASR 上传、转换或 worker 需要的临时文件位置；任务完成后应清理。
- `model-cache/`：可选本地模型缓存目录。推荐生产形态是 `api-server`，把 GPU/模型放在独立 ASR API server 后面，ChatVoice Web 进程只通过 HTTP 调用。
- `logs/`：服务日志建议由 supervisor/平台收集并轮转，不要记录 raw audio、完整 transcript、cookie、Authorization header 或 API key。
- `run/`：PID/socket 等运行时控制文件位置。

## API Key 配置边界

Settings 页面只显示服务端 API key 是否已配置，不会在浏览器保存或提交密钥明文。生产密钥应放在服务端环境或受保护配置文件中：

```bash
export CHATVOICE_ASR_CHANNEL=api-server
export CHATVOICE_ASR_API_URL="https://<asr-service>/v1/transcribe"
# export CHATVOICE_ASR_API_KEY in server-side secret storage
# export DASHSCOPE_API_KEY or OPENAI_API_KEY in server-side secret storage
```

## 高并发 TODO

`0.1.6` 的 packaged legacy storage 仍只支持 SQLite WAL，适合单服务进程、轻并发和内部受控使用：

```bash
chatvoice serve app --workers 1
```

高并发生产部署列入 TODO，不在当前版本实现：在扩展到多 worker / 多节点前，需要把 `accounts`、`auth_sessions`、`api_tokens`、`meeting_records`、`conversation_records` 迁移到 Postgres/MySQL，并增加对应 repository 层和迁移脚本。
