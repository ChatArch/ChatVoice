# 能力地图

这个页面校对 `ChatVoice` 当前有哪些一等能力、哪些能力已经验证，以及哪些事情不属于当前包。

## 当前能力

<div class="grid cards" markdown>

- **包化 Web 服务**

    `ChatVoice[web]` 安装后可以通过 `chatvoice serve app` 启动当前 Speakr FastAPI + browser 服务。

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
| ASR API provider | 已实现 | `CHATVOICE_ASR_CHANNEL=api-server` + the ASR API URL setting。 |
| 本地合同 smoke | 已实现 | `CHATVOICE_ASR_CHANNEL=stub-local` 可无 GPU/云凭据启动全链路。 |
| 本地 FunASR 兼容通道 | 保留 | `funasr-gpu` / `funasr-cpu` 仍可用，但生产建议改成外部 ASR API server。 |
| SQLite WAL 存储 | 已实现 | 单服务进程、轻并发默认。 |
| Postgres/MySQL 存储 | 未实现 | 已在 plan/doctor 中检测外部 URL，但 v0.0.2 packaged legacy storage 仍只支持 SQLite。 |

## 不在当前范围

- 不把 GPU 模型下载、CUDA/PyTorch 安装和 Web 服务打成一个默认进程。
- 不在 v0.0.2 里宣称 MySQL/Postgres 已经完成；高并发数据库迁移需要单独版本。
- 不输出 token、cookie、Authorization header、原始录音或完整 transcript。
- 不用 `kill` / `kill -9` 管理服务；重启类命令要先有 supervisor/graceful 方案。
