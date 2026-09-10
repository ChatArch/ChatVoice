# 独立 TTS 配置

系统语音合成支持独立配置；ASR、实时对话、纪要/标题、VoiceClone、账号和数据库保持不变。配置仍使用 ChatEnv 的同一个 `ChatVoice` provider，不新增浏览器设置页。

## 配置字段

| 字段 | 规则 |
| --- | --- |
| `CHATVOICE_TTS_API_TYPE` | `volcengine`、`openai` 或 `qwen`，显式协议而非模型名称分派 |
| `CHATVOICE_TTS_API_BASE` | Volcengine/OpenAI 使用 HTTP(S) 根 API base；Qwen 使用完整 ws/wss WebSocket 地址，不追加路径 |
| `CHATVOICE_TTS_API_KEY` | 独立敏感凭据，绝不借用纪要、标题、实时语音或全局 key |
| `CHATVOICE_TTS_MODEL` | 任意配置的模型标识；OpenAI 请求携带 model，Volcengine 使用独立 resource 路由 |
| `CHATVOICE_TTS_RESOURCE_ID` | Volcengine 必填；资源标识与展示/model 标识不同，OpenAI/Qwen 可留空 |
| `CHATVOICE_TTS_VOICES` | 非空 JSON 数组 `[{"id":"configured-voice","label":"音色名称"}]`，第一项为默认音色 |

音色最多 64 项，id/label 各最多 80 字符且分别唯一；id 为可打印 ASCII，label 不含控制字符或尖括号，`clone` 保留给现有复刻卡。模型标识最多 256 个可打印 ASCII 字符。不要在标识或标签中填写凭据。

任意一个非空独立字段即启用此配置；缺失字段、未知协议、不安全 URL、无效音色列表均使 TTS 返回 503，绝不静默回退。只有六个字段全部为空才保留旧 Qwen `sk-sp` gate/call。根地址禁止 userinfo、查询、fragment、控制字符；不跟随重定向。生产应使用 HTTPS，仅在可信网络内使用 HTTP。

公共 base 示例：Volcengine `https://openspeech.bytedance.com/api/v3/plan`；OpenAI-compatible `https://api.openai.com/v1`。模型、资源和音色必须由操作者按服务能力配置，示例不提供隐式默认值。

### 显式 Qwen WebSocket 协议

设置 `CHATVOICE_TTS_API_TYPE=qwen`，使用相同的独立 BASE/KEY/MODEL/VOICES 字段。BASE 是**完整** ws/wss 地址，保留路径和末尾斜杠，例如公开 Token Plan 地址 `wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`，不追加操作路径。独立 KEY 必须满足原有 `sk-sp` Token Plan 保护，拒绝普通按量 key。RESOURCE_ID 可为空且此协议不使用。模型与音色只来自独立配置，不读取或借用 `CHATVOICE_OPENAI_*`、SDK 或环境默认凭据。

每次调用独立创建同步 `websocket-client` 连接，显式发送 Authorization。按顺序发送 `run-task`，等待对应的 `task-started`，发送携带文本的 `continue-task` 和 `finish-task`；成功要求对应的 `task-finished` 与非空、结构有效的 MP3/WAV 音频。使用本地生成的 task ID 关联事件，不暴露上游错误正文。MP3/WAV 均直接请求 24kHz。无重试、重定向、SDK 全局 key 修改或失败回退；独立 TTS 字段全部为空时，旧 Qwen 路径保持不变。

仅允许无 userinfo、query、fragment、控制字符的 ws/wss URL。远程使用 WSS，WS 仅用于可信本地端点。沿用 60 秒总期限、10 秒 socket 超时；接收线上数据最多 24 MiB，单帧/文本消息最多 2 MiB，音频最多 16 MiB。超长帧在分配正文前拒绝，分片消息也受限；所有结果都会关闭连接。如果 websocket-client 开启 trace 日志，拒绝建立连接，避免凭据进入日志且不修改全局日志开关。直接声明依赖 `websocket-client`，不导入 DashScope synthesizer。此协议通过离线测试，真实 Qwen 验收由操作者另行负责。

## API 与验证

`POST /api/tts` 保持 `{text, voice?, format: "mp3" | "wav"}`，text 最多 800 字；省略 voice 使用配置列表第一项。不属于配置目录的音色被拒绝。返回音频及 `X-TTS-Provider`、`X-TTS-Model`、`X-TTS-Voice`、耗时/字节数/摘要，文件名 `tts.mp3` 或 `tts.wav`。旧 Qwen 路径额外保留兼容头。

Volcengine 请求追加 `/tts/unidirectional`，使用 `X-Api-Key` 和 `X-Api-Resource-Id`，发送 `req_params{text,speaker,audio_params{format,sample_rate:24000}}`。NDJSON 必须有有效非空音频和 `20000000` 终结成功；支持跳过文档规定的 `data:null` / sentence 对象，不把文本元数据当成音频。HTTP 200 内嵌错误、截断、非法 JSON/base64/类型都返回脱敏 502。HTTP Chunked 文档建议使用 PCM，避免流式 WAV 重复 header；WAV 因此通过请求 `pcm` 并使用标准库封装 24kHz 单声道 int16。原始 PCM 没有魔数前缀；验证依赖协议成功、非空、大小上限及 int16 对齐，不通过前缀判断格式。

OpenAI 请求追加 `/audio/speech`，独立 Bearer key，发送 model/input/voice/response_format。音频进行最小 MP3 帧/WAV 结构验证，不能用 HTML/JSON 错误正文替代成功。PCM 仅检查非空及 int16 对齐，真实可解码性由发布验收使用解码器验证。响应最多 24 MiB，NDJSON 行最多 2 MiB，音频最多 16 MiB；连接/读取超时 10 秒，总读取期限 60 秒。

`GET /api/status` 新增 `tts`：provider、base_host、model、key_configured、configured、voices、default_voice 和固定安全错误；不返回 key、resource 或上游原始正文。顶层 tts_model 为有效 TTS 模型。UI 只根据 `tts.configured` 判断系统 TTS，动态文本节点渲染音色，刷新时保留复刻选择；实时音色下拉框不变。

显式配置后，`chatenv --home <isolated-home> test -t chatvoice -I` 沿用已经解析的 EnvStore，调用短合成文本并丢弃音频，不导入 Web/GPU。失败返回非零，纪要/标题 probe 保持原逻辑。此命令会调用配置的真实端点：仅在确认费用与授权后由操作者执行；自动测试必须 mock 网络并隔离 HOME/CHATARCH_HOME/TMPDIR。

## 发布与回滚边界

先审查本地 wheel、mock 测试、CLI 树与严格文档构建，再由部署负责人执行真实合成/解码/页面生成播放验收和备份回滚。此 hotfix 本身不部署、不修改账号或后付费设置。完整保留旧配置备份；回滚到旧 TTS 需清空全部六个独立字段并确保旧 Token Plan key 合规，不保留半套配置。不要修改 ASR、实时、文本、VoiceClone 或数据库配置。
