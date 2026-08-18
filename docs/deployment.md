# 部署与启动

这一页说明 v0.0.2 发布后，如何只通过 Python 包搭起一套 ChatVoice / Speakr 服务流程。

## 最小安装

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.0.2"
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

## 启动 Web 服务

```bash
chatvoice serve app --host 127.0.0.1 --port 18087
```

打开：

```text
http://127.0.0.1:18087/
```

生产入口建议放在受控反向代理后面；API key 只放服务端环境变量，不进入浏览器、命令参数、Git、日志或文档。

## ASR provider：API 优先

v0.0.2 的生产推荐方式是 **ChatVoice 后端通过 API 调用 ASR 服务**。这个 ASR 服务可以是：

- 云服务 API，凭 API key 调用；
- 自建 GPU ASR server，对外暴露 HTTP API；
- 内网 GPU 节点上的服务，由反向代理或内网地址承接。

配置：

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.   # 可选；不要写进 argv
chatvoice serve app --host 127.0.0.1 --port 18087
```

ChatVoice 会把上传音频以 multipart `file` 字段 POST 到 the ASR API URL setting，并在有 key 时发送：

```text
Authorization: Bearer <server-side bearer token>
```

ASR API 返回 JSON 时，ChatVoice 会优先读取这些字段：

```text
corrected_text
text
transcript
raw_text
data.text
result.text
```

如果暂时没有 ASR API，可以用合同 smoke 通道启动完整 Web 流程：

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

`stub-local` 只证明上传、WebSocket、UI、存储和服务路径打通，不代表真实识别质量。

## 可选本地 GPU 兼容通道

`funasr-gpu` / `funasr-cpu` 仍保留为兼容通道，但不作为默认部署建议。更灵活的做法是把 GPU runtime 独立成 ASR API server，然后让 ChatVoice 用 `api-server` 调它。这样 Web 服务、GPU worker、模型缓存和扩容可以分开维护。

## 数据库与并发边界

v0.0.2 packaged Web app 默认使用 SQLite WAL：

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

这适合单服务进程、轻并发和受控内部使用。当前版本的安全边界是：

- `chatvoice serve app --workers 1`；
- 不要用多 worker / 多节点同时写同一个 SQLite 文件；
- 高并发生产部署应把存储层迁移到 Postgres/MySQL 这类外部数据库后再扩多 worker；
- an external database URL setting 会被 `doctor` / `service plan` 检测并报告，但 v0.0.2 的 packaged legacy storage 仍只真正支持 SQLite。

回读：

```bash
chatvoice doctor --json
chatvoice service plan --json
```

## 健康检查

```bash
chatvoice health status --url http://127.0.0.1:18087 --json
```

对应服务端接口：

```text
GET /api/status
GET /api/asr/channels
POST /api/asr
WS  /ws/asr/stream
```
