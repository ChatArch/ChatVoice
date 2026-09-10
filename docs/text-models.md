# 独立配置纪要与标题模型

会议纪要、标题可以分别配置独立的 OpenAI-compatible Chat Completions 接口，文字任务不借用语音凭据。Markdown Todo 复用会议纪要模型，无需新增配置。

## 配置边界

每个用途各有三个字段，全部写入 ChatEnv 的 `ChatVoice` provider：

| 用途 | Base | Key（敏感字段） | Model |
| --- | --- | --- | --- |
| 纪要、润色、画布修改 | `CHATVOICE_MEETING_NOTES_API_BASE` | `CHATVOICE_MEETING_NOTES_API_KEY` | `CHATVOICE_MEETING_NOTES_MODEL` |
| 自动标题、刷新标题 | `CHATVOICE_MEETING_TITLE_API_BASE` | `CHATVOICE_MEETING_TITLE_API_KEY` | `CHATVOICE_MEETING_TITLE_MODEL` |

一旦某用途的 Base 或 Key 任一非空，该用途必须同时提供 Base、Key、Model；缺项返回 HTTP 503，不会从语音、CRS profile、全局 OpenAI 或另一个用途借用配置。Base 与 Key 都为空时保留旧行为。`CHATVOICE_MEETING_NOTES_PROVIDER` 只控制旧路径，显式独立配置优先。

以下 Agent Plan 示例需替换占位符，仅通过安全 stdin 写入 ChatEnv；不要把真实密钥放进命令参数、仓库、截图或聊天：

```dotenv
CHATVOICE_MEETING_NOTES_API_BASE=https://ark.cn-beijing.volces.com/api/plan/v3
CHATVOICE_MEETING_NOTES_API_KEY=<your-Agent-Plan-key>
CHATVOICE_MEETING_NOTES_MODEL=doubao-seed-2.0-lite
CHATVOICE_MEETING_TITLE_API_BASE=https://ark.cn-beijing.volces.com/api/plan/v3
CHATVOICE_MEETING_TITLE_API_KEY=<your-Agent-Plan-key>
CHATVOICE_MEETING_TITLE_MODEL=doubao-seed-2.0-mini
```

同一 Key 可以被明确写入两个独立字段；系统不会隐式共享。套餐入口和模型可用性应以当前账号为准，不可把此入口替换成按量计费入口。

## 自检与切换

先在隔离 ChatEnv home 中验证，再切生产。隔离 home 也应放在 `$CHATARCH_HOME` 管理目录下，而不是源码仓库：

```bash
chatenv --home "$CHATARCH_HOME/chatvoice/validation" paste --stdin -t chatvoice
chatenv --home "$CHATARCH_HOME/chatvoice/validation" test -t chatvoice -I
```

`test` 会先验证两个用途的完整性，再分别发一个合成文本请求；未配置独立接口时明确报告仅加载 schema，不访问网络。测试不导入 Web、数据库或 GPU 模型。`max_tokens` 是输出参数，不代表供应商推理 token 或费用的硬上限。

生产切换前备份原 wheel、ChatEnv active profile 和 SQLite 文件；只安装已验证 wheel，不升级 GPU 依赖。激活完整配置后，通过现有 supervisor 优雅重启 ChatVoice。不要重启无关 gateway。验证失败时恢复原 wheel 和原配置；数据库没有变化时不应覆盖现有数据库。

## 验收

- `/api/status` 的 `meeting_notes`、`meeting_title` 返回 provider、model、base_host、key_configured、configured；不返回 Key 或完整 Base。旧 `meeting_title_model` 字段保留。
- `POST /api/meeting-notes/polish` 返回非空 `content`。
- `POST /api/meeting-title` 返回中文 `title`。
- `POST /api/meeting-notes/revise/stream` 返回 `meta`、`delta`、`done`；画布协议包含 `[[[CANVAS]]]` 与 `[[[REPLY]]]`。
- 上游 HTTP 错误、200 错误包、空正文、流中错误或未完成流不能当成成功；错误信息不复述上游正文或密钥。
- 从真实公网访客页面点击更新摘要、刷新标题、完善纪要；只注入合成转写输入，不替换模型响应。

此次独立文字配置不会修复失效的语音套餐，也不改变 `CHATVOICE_OPENAI_*` 的 Token Plan 校验、ASR、TTS、实时语音或声音复刻配置。
