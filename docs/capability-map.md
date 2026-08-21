# 能力地图

这个页面校对 `ChatVoice` 当前有哪些一等能力、哪些能力已经验证，以及哪些事情不属于当前包。

## 当前能力

<div class="grid cards" markdown>

- **包化 Web 服务**

    `ChatVoice[web]` 安装后可以通过 `chatvoice serve app` 启动当前 Speakr FastAPI + browser 服务。

- **Fresh-start 账号与 API Token**

    `chatvoice accounts add` 可在 packaged runtime 数据库里创建受邀账号；登录后可在网页设置面板生成 API Token，CLI 也可创建/列出/撤销 token metadata。

- **数据读取 API / CLI**

    `GET /api/data/...` 与 `chatvoice data ...` 可用 bearer token 读取会议转写、会议摘要和实时对话文本记录。

- **API-first ASR provider**

    默认生产方向是 `api-server`：后端通过 HTTP API 调云 ASR 或自建 GPU ASR server，不把 GPU runtime 绑死在 Web 进程里。

- **运行目录与部署计划**

    `chatvoice paths` 和 `chatvoice service plan` 回读 ChatArch home 下的数据、日志、运行和缓存目录。

- **健康检查**

    `chatvoice health status` 读取运行中服务的 `/api/status`。

</div>

## 状态表

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| CLI 基础入口 | 已实现 | `--help`、`--version`、`--tree`。 |
| 运行目录 | 已实现 | 默认 `<chatarch-home>/chatvoice/`，可由 runtime-home overrides 调整。 |
| packaged Web 启动 | 已实现 | `chatvoice serve app` 调用 `chatvoice.web.server:create_app`。 |
| 受邀账号 CLI | 已实现 | `chatvoice accounts add/list`，密码只从环境变量读取。 |
| API Token 管理 | 已实现 | 网页设置面板 + CLI token lifecycle；服务端只存 token hash。 |
| 数据读取 API/CLI | 已实现 | Bearer token 读取会议、摘要和 realtime conversations。 |
| ASR API provider | 已实现 | `CHATVOICE_ASR_CHANNEL=api-server` + the ASR API URL setting。 |
| 本地合同 smoke | 已实现 | `CHATVOICE_ASR_CHANNEL=stub-local` 可无 GPU/云凭据启动全链路。 |
| 本地 FunASR 兼容通道 | 保留 | `funasr-gpu` / `funasr-cpu` 仍可用，但生产建议改成外部 ASR API server。 |
| SQLite WAL 存储 | 已实现 | 单服务进程、轻并发默认；`api_tokens` 表只保存 hash/prefix/metadata。 |
| Postgres/MySQL 存储 | 未实现 | 已在 plan/doctor 中检测外部 URL，但 v0.1.7 packaged legacy storage 仍只支持 SQLite。 |

## 不在当前范围

- 不把 GPU 模型下载、CUDA/PyTorch 安装和 Web 服务打成一个默认进程。
- 不在 v0.1.7 里宣称 MySQL/Postgres 已经完成；高并发数据库迁移需要单独版本。
- 不输出 token、cookie、Authorization header 或原始录音；完整 transcript 只通过用户显式调用的数据读取接口返回。
- 不用 `kill` / `kill -9` 管理服务；重启类命令要先有 supervisor/graceful 方案。
