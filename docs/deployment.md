# 部署与启动

这一页说明 v0.1.1 发布后，如何只通过 Python 包搭起一套 ChatVoice / Speakr 服务流程：安装、创建账号、启动服务、生成 API Token、读取会议/摘要数据。

## 最小安装

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.1"
```

安装后先回读真实 CLI 树和运行目录：

```bash
chatvoice --tree
chatvoice paths --json
chatvoice service plan --ensure-dirs --json
```

默认运行目录在 ChatArch home 下：

```text
<chatarch-home>/chatvoice/
├── data/          # SQLite 数据库默认位置
├── logs/
├── run/
├── temp/
└── model-cache/
```

## 创建受邀账号

`ChatVoice[web]` 安装后，不需要源码根目录脚本；直接用 packaged CLI 创建账号。密码只从环境变量读取：

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

## 启动 Web 服务

无凭据/无 GPU 的合同 smoke：

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

打开：

```text
http://127.0.0.1:18087/
```

生产入口建议放在受控反向代理后面；API key 只放服务端环境变量，不进入浏览器、命令参数、Git、日志或文档。

## ASR provider：API 优先

v0.1.1 的生产推荐方式是 **ChatVoice 后端通过 API 调用 ASR 服务**。这个 ASR 服务可以是：

- 云服务 API，凭 API key 调用；
- 自建 GPU ASR server，对外暴露 HTTP API；
- 内网 GPU 节点上的服务，由反向代理或内网地址承接。

配置：

```bash
export CHATVOICE_ASR_CHANNEL=api-server
export CHATVOICE_ASR_API_URL="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

ChatVoice 会把上传音频以 multipart `file` 字段 POST 到 `CHATVOICE_ASR_API_URL`，并从 ASR JSON 响应里读取 `corrected_text`、`text`、`transcript`、`raw_text`、`data.text` 或 `result.text`。

`funasr-gpu` / `funasr-cpu` 仍保留为兼容通道，但不作为默认部署建议。更灵活的做法是把 GPU runtime 独立成 ASR API server，然后让 ChatVoice 用 `api-server` 调它。

Meeting summary 生成同样是 server-side model 边界：会议纪要模型/provider 只在服务端环境或配置存储中设置，浏览器和数据 API 只读取已保存的 summary 文本。

## 生成 Token 并读取数据

网页登录后，在 **识别设置 → API Token** 里生成 Token；Token 明文只显示一次。也可以从 CLI 创建：

```bash
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
```

把 Token 放到 `--token-env` 指定的环境变量后即可读取会议/摘要/对话：

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

更多说明见 [API 访问](api-access.md)。

## 数据库与并发边界

v0.1.1 packaged Web app 默认使用 SQLite WAL：

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

这适合单服务进程、轻并发和受控内部使用。当前版本的安全边界是：

- `chatvoice serve app --workers 1`；
- 不要用多 worker / 多节点同时写同一个 SQLite 文件；
- 高并发生产部署应把存储层迁移到 Postgres/MySQL 这类外部数据库后再扩多 worker；
- an external database URL setting 会被 `doctor` / `service plan` 检测并报告，但 v0.1.1 的 packaged legacy storage 仍只真正支持 SQLite。

回读：

```bash
chatvoice doctor --json
chatvoice service plan --json
```

## 健康检查

```bash
chatvoice health status --url http://127.0.0.1:18087 --json
```

核心服务端接口：

```text
GET /api/status
GET /api/asr/channels
POST /api/asr
WS  /ws/asr/stream
GET /api/data/meetings
GET /api/data/conversations
```
