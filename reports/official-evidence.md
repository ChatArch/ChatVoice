# 千问 TTS / Realtime 官方证据整理

> Snapshot: 2026-08-12  
> Scope: 千问 Token Plan Key 暴露的 `qwen-audio-3.0-tts-plus` 与 `qwen-audio-3.0-realtime-plus` 接入方式、官方 Demo / 最佳实践线索。  
> Secret policy: 本报告不保存 API Key；所有请求只记录 status、request_id、事件类型、字节数、错误码等脱敏信息。

## 1. 已验证来源

- 千问文档索引：`https://platform.qianwenai.com/docs/llms.txt`
- 千问完整文档文本：`https://platform.qianwenai.com/docs/llms-full.txt`
- 非实时语音合成 HTTP API：`https://platform.qianwenai.com/docs/api-reference/speech-synthesis/cosyvoice-nrt/http-api.md`
- Qwen-Audio-TTS 音色列表：`https://platform.qianwenai.com/docs/api-reference/speech-synthesis/qwen-audio-tts/voice-list.md`
- 实时语音对话指南：`https://platform.qianwenai.com/docs/developer-guides/speech/qwen-audio-realtime.md`
- Realtime API 概述：`https://platform.qianwenai.com/docs/developer-guides/realtime-api/overview.md`
- Realtime WebRTC 最佳实践：`https://platform.qianwenai.com/docs/developer-guides/realtime-api/webrtc-omni-realtime.md`
- Qwen-TTS-Realtime WebSocket API：`https://platform.qianwenai.com/docs/api-reference/speech-synthesis/qwen-tts-realtime/websocket-api.md`
- Qwen-TTS-Realtime client events：`https://platform.qianwenai.com/docs/api-reference/speech-synthesis/qwen-tts-realtime/client-events.md`

项目内已保存：

- 本报告仅保留官方 URL 与关键结论；大体量文档快照不进入公开仓库。

## 2. 模型能力结论

### `qwen-audio-3.0-tts-plus`

官方 HTTP API 页面明确支持非实时语音合成：

- Endpoint: `POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer`
- Header: `Authorization: Bearer $DASHSCOPE_API_KEY`
- Request body:
  - `model`: `qwen-audio-3.0-tts-plus` 或同系列模型。
  - `input.text`: 待合成文本。
  - `input.voice`: 必选音色。
  - `input.format`: 默认 `mp3`；可选 `mp3`、`pcm`、`wav`、`opus`。
  - `input.sample_rate`: 默认 `22050`；可选 8000/16000/22050/24000/44100/48000。
- Non-stream response: `output.audio.url`，URL 有效期 24 小时。
- SSE streaming response: `output.audio.data` 为 Base64 音频片段，最后仍可能给出 `output.audio.url`。

`qwen-audio-3.0-tts-plus` 官方系统音色当前包括：

- `longanlingxin`：女声，中文普通话/英文。
- `longanlufeng`：男声，中文普通话/英文。

因此最小 Demo 默认使用：`model=qwen-audio-3.0-tts-plus`、`voice=longanlingxin`、`format=mp3`。

### `qwen-audio-3.0-realtime-plus`

官方实时语音对话指南明确：

- 模型是端到端实时语音交互模型，支持低延迟语音对话。
- 支持流式音频输入，以及流式语音 + 文本输出。
- 支持 WebSocket、AOQ、WebRTC 三种接入协议。
- WebSocket URL: `wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen-audio-3.0-realtime-plus`
- Header: `Authorization: Bearer $DASHSCOPE_API_KEY`
- 输入音频：PCM 16kHz、16bit、mono。
- 输出音频：PCM 24kHz、16bit、mono。
- 常见客户端事件：`session.update`、`input_audio_buffer.append`。
- 常见服务端事件：`session.created`、`response.audio.delta`、`conversation.item.input_audio_transcription.completed`、`response.audio_transcript.done`、`response.done`、`error`。
- 支持 turn detection：`server_vad`、`smart_turn`、手动 push-to-talk。

Realtime API 概述页面显示：

- 实时语音对话 `qwen-audio-3.0-realtime-plus` / `qwen-audio-3.0-realtime-flash`：AOQ/WebRTC/WebSocket 均支持。
- 实时语音合成 `qwen-audio-3.0-tts-plus` / `qwen-audio-3.0-tts-flash`：AOQ/WebSocket 支持，WebRTC 不支持。
- 实时语音识别：是另一类模型，如 `Qwen-Audio-3.0-ASR-Flash-Streaming`、`Fun-ASR-Realtime` 系列；这解释了为什么 Token Plan `/models` 只看到 realtime dialogue 而未看到纯 ASR 模型。

## 3. 官方 Demo / 最佳实践现状

已找到官方“最佳实践”页面：

- WebRTC + `qwen3.5-omni-plus-realtime` 实时通话示例。
- AOQ + `qwen3.5-omni-plus-realtime` 实时通话示例。
- `qwen-audio-3.0-realtime-plus` 文档内提供 Python WebSocket quickstart。

但截至本次检索：

- 未发现官方明确提供 Gradio / Streamlit 形式的 `qwen-audio-3.0-tts-plus` 或 `qwen-audio-3.0-realtime-plus` Demo。
- GitHub 搜索 `QwenTtsRealtime`、`OmniRealtimeConversation`、`qwen-audio-3.0-tts-plus`、`qwen-audio-3.0-realtime-plus` 未返回可直接采用的官方 Demo 仓库。

因此 Demo 路线采用“官方 API/事件协议 + 自建轻量 Web Demo”：

1. 后端持有 API Key，前端永不接触 Key。
2. TTS 使用 HTTP `SpeechSynthesizer` 端点生成音频。
3. Realtime 优先实现 WebSocket 代理模式；如果要浏览器原生实时通话，后续可扩展 WebRTC AppServer SDP 代理。

## 4. Demo 设计约束

- 不在浏览器暴露 `DASHSCOPE_API_KEY`。
- 不保存真实 Key 到项目仓库；只提供 `.env.example`。
- 服务默认绑定 `127.0.0.1`，临时验证后关闭；如需公网入口再按 local/public service pattern 单独做。
- 探针输出只允许包含：HTTP status、模型名、request_id、usage、音频字节数、事件类型、脱敏错误信息。

## 5. 待实测项

- Token Plan Key 是否允许实际调用 `qwen-audio-3.0-tts-plus`。成功标准：HTTP 200，返回音频 URL，下载音频字节 > 0。
- Token Plan Key 是否允许 WebSocket 握手 `qwen-audio-3.0-realtime-plus`。成功标准：握手成功并收到 `session.created`，发送 `session.update` 后收到 `session.updated` 或可解释错误。
- 若 Realtime 需要真实麦克风音频才能响应，Demo 后端仍可完成连接/事件面板/音频转发结构，完整口语交互由浏览器端麦克风测试验收。
