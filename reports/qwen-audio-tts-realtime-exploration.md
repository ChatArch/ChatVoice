# 千问 Token Plan TTS / Realtime 探索报告

> 日期：2026-08-12  
> 执行环境：local/remote Python environment  
> 密钥策略：所有实测均从服务端环境变量或本地 env 文件读取 Key；报告、源码和日志中不保存真实 Key。

## 1. 结论

### 模型列表

`OpenAI/qwen-token-plan` 的 Token Plan Base URL 为：

```text
https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

`GET /models` 实测 HTTP 200，返回 11 个模型：

```text
qwen3.7-max
qwen3.7-plus
qwen3.6-flash
glm-5.2
deepseek-v4-pro
wan2.7-image
wan2.7-image-pro
qwen-audio-3.0-tts-plus
deepseek-v4-flash-0731
qwen3.8-max
qwen-audio-3.0-realtime-plus
```

其中音频相关：

- `qwen-audio-3.0-tts-plus`：语音合成，已实测成功生成 MP3。
- `qwen-audio-3.0-realtime-plus`：实时语音对话，已实测 WebSocket 正确路径可建立 session 并接收 `session.created` / `session.updated`。
- 未在该 Key 的模型列表里看到专门 ASR 模型（如 `qwen-audio-3.0-asr-*`、`paraformer-*`）。因此它不应被当成“纯实时字幕/ASR Key”。Realtime 模型可能有输入音频转写相关 session 字段，但主能力是实时语音对话，不等同于专用 ASR。

### 关键接入边界

Token Plan Key（`sk-sp-...` 类型）和普通千问/DashScope Key（`sk-ws-...` 类型）隔离，必须配套 Token Plan URL 使用。官方快速开始明确：OpenAI 兼容 Base URL 是 `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`，且 Token Plan 和按量 API Key / Base URL 完全隔离。

实测也验证了这一点：

- 直接调用 `https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer`：401 / `InvalidApiKey`。
- Token Plan OpenAI-compatible `/models`：200。
- Token Plan `/audio/speech`、`/chat/completions`、`/responses` 并不是 `qwen-audio-3.0-tts-plus` 的正确 TTS 路径：分别返回 URL error、InternalError、Unsupported model。
- 官方 Token Plan 多模态最佳实践给出的 TTS 路径是：DashScope Python SDK + `dashscope.base_websocket_api_url = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"`。

## 2. 官方资料与 Demo 情况

已保存官方文档快照在：

- Token Plan quickstart
- Token Plan multimodal-generation best practices
- OpenAI-compatible overview
- Qwen Audio TTS voice list
- Qwen Audio Realtime developer guides

官方 Token Plan 文档目前没有找到可直接启动的 Gradio / Streamlit / 网页 Demo。官方给的是“在 Claude Code / Codex / Hermes 等工具里通过 Slash Command / Skill 接入”的最佳实践模板；TTS 示例核心代码是：

```python
import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

dashscope.api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
dashscope.base_websocket_api_url = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"

synthesizer = SpeechSynthesizer(
  model="qwen-audio-3.0-tts-plus",
  voice="<voice>",
  format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
)
audio = synthesizer.call("<text>")
```

因此本项目自建了一个轻量 FastAPI + 静态 HTML Demo。

## 3. 实测结果

### TTS 探针

脚本：`scripts/probe_token_plan_tts_ws.py`

真实输出摘要：

```json
{
  "model": "qwen-audio-3.0-tts-plus",
  "voice": "longanlingxin",
  "audio_bytes": 67800,
  "elapsed_ms": 2219,
  "first_package_delay_ms": 1173.338134765625,
  "request_id": "60a4f2a61796412fb9923033c0f1ddea",
  "audio_file": "playground/probe-output/token-plan-tts-<timestamp>.mp3"
}
```

结论：TTS 实际可用。

### Realtime 探针

正确路径：

```text
wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen-audio-3.0-realtime-plus
```

脚本输出摘要：

```json
{
  "connected": true,
  "events": [
    {"type": "session.created"},
    {"type": "session.updated"}
  ]
}
```

其中 `session.updated` 的 session keys 包含：

```text
id, input_audio_transcription, modalities, model, object, turn_detection, voice
```

结论：Realtime session 和协议事件可用；本轮仅做了连接、`session.update` 与短静音 buffer 级别诊断，没有做长时间麦克风对话和音频播放闭环。

### Demo smoke

脚本：`scripts/smoke_demo.py --port 18087`

真实 smoke 结果：

```json
{
  "ok": true,
  "status": {
    "models_ok": true,
    "models": {"count": 11},
    "tts_websocket_url_shape": "wss://[HOST]/api-ws/v1/inference",
    "realtime_websocket_url_shape": "wss://[HOST]/api-ws/v1/realtime?model=qwen-audio-3.0-realtime-plus"
  },
  "tts": {
    "status": 200,
    "content_type": "audio/mpeg",
    "bytes": 44812,
    "elapsed_ms": "1526"
  },
  "realtime_ws": {
    "events": [
      {"type": "proxy.connected"},
      {"type": "session.created"},
      {"type": "session.updated"},
      {"recv_stop": "timeout"}
    ]
  }
}
```

Smoke 之后已检查 `:18087`，没有遗留监听。

## 4. Demo 文件

- `app/main.py`：FastAPI 后端；读取 ChatEnv profile；提供 `/api/status`、`/api/tts`、`/ws/realtime`。
- `app/static/index.html`：网页 UI；TTS 表单、音频播放器、Realtime 连接诊断与麦克风入口。
- `scripts/probe_token_plan_tts_ws.py`：TTS 官方路径最小探针。
- `scripts/probe_qwen_audio.py`：早期 DashScope/Realtime 边界探针，保留用于对比错误。
- `scripts/smoke_demo.py`：短时启动本地服务并验证 status / TTS / Realtime proxy，结束后关闭。
- `README.md`：运行方式与边界说明。
- `.env.example`：仅占位符，不含真实 Key。

## 5. 运行方式

```bash
cd qwen-audio-tts-realtime-demo
uvicorn app.main:app --host 127.0.0.1 --port 18087
```

本地浏览器访问建议用 SSH tunnel：

```bash
ssh -L 18087:127.0.0.1:18087 <your-server>
```

然后打开：

```text
http://127.0.0.1:18087/
```

## 6. 风险与下一步

1. **Realtime 尚未完成真实人声对话闭环**：目前验证到代理、session 创建/更新和静音 buffer 事件；下一步应在浏览器里授权麦克风，验证是否返回转写/音频 delta，并补浏览器端音频播放。
2. **ASR 不宜承诺**：虽然 Realtime session 有 `input_audio_transcription` 字段，但该 Token Plan 模型列表没有专用 ASR 模型；如果目标是会议字幕/实时转写，应另拿 Qwen-ASR / Paraformer / DashScope ASR 相关权限或 Key。
3. **OpenAI `/audio/speech` 不适配本模型**：Token Plan TTS 不是普通 OpenAI Speech endpoint；Demo 应继续用官方 Token Plan WebSocket SDK 路线。
4. **不要直接公网部署**：当前只做轻量 demo。若要公网部署，应另行配置鉴权、TLS、反向代理和速率限制。
