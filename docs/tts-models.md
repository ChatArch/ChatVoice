# 语音合成后端

系统 TTS 与“我的复刻声音”共用声音工作室的文字输入，但使用不同后端。TTS 音色由服务端配置，网页动态展示，不要求用户手填音色 ID。

| 协议 | `CHATVOICE_TTS_API_TYPE` | 额外要求 |
| --- | --- | --- |
| OpenAI 兼容语音 | `openai` | 支持 `/audio/speech` 的服务 |
| 火山引擎单向流 | `volcengine` | 资源 ID 与后端支持的音色 |
| Qwen WebSocket | `qwen-ws` | 兼容后端、模型权限与对应 Plan 凭据 |

## OpenAI 兼容示例

```dotenv
CHATVOICE_TTS_API_TYPE=openai
CHATVOICE_TTS_API_BASE=https://speech.example.com/v1
CHATVOICE_TTS_API_KEY=[REDACTED]
CHATVOICE_TTS_MODEL=your-tts-model
CHATVOICE_TTS_VOICES='[{"id":"voice-id","label":"默认音色"}]'
```

替换全部占位值。音色目录是 JSON 数组，首项为默认；标签用于页面，`id` 发送给提供者。

## 其他协议

火山引擎需要 `CHATVOICE_TTS_RESOURCE_ID`。`API_BASE` 可为包含 `/api/v3/tts/unidirectional` 的完整地址，也可由适配器补齐该路径。`MODEL` 与资源 ID 是不同字段。

Qwen WebSocket 使用其对应模型接口和凭据策略；不能把其他协议的普通密钥按该供应商的规则校验，也不能仅因模型列表可见就断言有调用权限。

任一独立 TTS 字段非空即启用显式配置，缺项报错。只有全部独立字段为空才选择遗留兼容路径；不会借用文本模型密钥。

## 页面使用与验收

1. 进入声音工作室，选择配置中的系统音色。
2. 输入文字，选择页面提供的输出格式并生成。
3. 确认结果可播放，再下载文件。
4. 切换音色/格式后分别验证，不把一个成功样例当作全部协议可用。

API 的提供者、模型、音色响应头应与选择一致；还需检查实际容器、采样率和可播放音频，不能只看文件扩展名。`chatenv test -t chatvoice -I` 的合成探测会消耗额度。

[完整配置](configuration.md) · [声音复刻](voice-cloning.md) · [故障排查](troubleshooting.md)
