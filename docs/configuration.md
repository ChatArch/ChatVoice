# 配置参考

配置按能力选择，不必把所有功能都启用。以下字段以当前发布包的 `ChatVoiceConfig` 为准；密钥只保存在服务端 ChatEnv，页面只显示脱敏状态。

| 要启用的能力 | 主要设置 | 详细说明 |
| --- | --- | --- |
| 录音转写 | ASR 通道、模型运行环境或 HTTP 地址 | [网页使用](web-guide.md#recording) |
| 摘要、纪要改写、Todo | 纪要接口地址、密钥、模型 | [文本模型](text-models.md) |
| 自动标题 | 标题接口地址、密钥、模型 | [文本模型](text-models.md) |
| 系统音色 | TTS 协议、地址、密钥、模型、音色 | [语音合成](tts-models.md) |
| 我的复刻声音 | VoiceClone 地址 | [声音复刻](voice-cloning.md) |
| 实时对话 | 兼容语音配置与有效模型权限 | [网页使用](web-guide.md#realtime) |
| 会中助手预览 | 功能开关、纪要文本模型、ASR | [网页使用](web-guide.md#copilot) |

## 使用 ChatEnv {#chatenv}

先安装 ChatVoice，ChatEnv 才能发现它的配置类型。当前存储域为 `ChatVoice`，命令别名为 `chatvoice`；不要另建大小写不同的存储域。

```bash
chatenv status
chatenv init -t chatvoice -I
chatenv paste --stdin --profile speakr --yes
```

最后一条命令从标准输入接收 `KEY=VALUE` 文本。粘贴配置后结束输入，再激活同名配置：

```bash
chatenv use speakr -t chatvoice -I
chatenv test -t chatvoice -I
```

自检会真实调用已配置的文本/TTS 后端，可能消耗额度。服务需重新加载后才能使用新的启动期配置。ChatEnv 不会自动替其他进程导出环境变量；路径、命令行密码和读取 Token 等进程变量仍需由调用者提供。

## 独立文本模型 {#text}

| 字段 | 含义与要求 |
| --- | --- |
| `CHATVOICE_MEETING_NOTES_API_BASE` | OpenAI-compatible 根地址，程序追加 `/chat/completions` |
| `CHATVOICE_MEETING_NOTES_API_KEY` | 纪要专用密钥，敏感 |
| `CHATVOICE_MEETING_NOTES_MODEL` | 纪要模型标识；同时用于摘要、对话改写和 Todo |
| `CHATVOICE_MEETING_TITLE_API_BASE` | 标题专用根地址 |
| `CHATVOICE_MEETING_TITLE_API_KEY` | 标题专用密钥，敏感 |
| `CHATVOICE_MEETING_TITLE_MODEL` | 标题模型标识 |

填写某用途的独立地址或密钥时，该用途的地址、密钥、模型必须齐全。两用途可以显式填写相同的服务值，但不会互相借用缺失字段。Todo 不需要新增模型配置。会中助手快速回答也复用纪要模型；缺失时返回 503，不借用语音、标题或浏览器提供的任意模型设置。

```dotenv
CHATVOICE_MEETING_NOTES_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_NOTES_API_KEY=[REDACTED]
CHATVOICE_MEETING_NOTES_MODEL=notes-model
CHATVOICE_MEETING_TITLE_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_TITLE_API_KEY=[REDACTED]
CHATVOICE_MEETING_TITLE_MODEL=title-model
```

示例地址、密钥与模型名都是占位值，应替换为已获授权服务的真实设置。

## 会中助手预览 {#copilot}

| 字段 | 默认值 | 用途 |
| --- | --- | --- |
| `CHATVOICE_COPILOT_ENABLED` | `0` | 启用 `/copilot`、页面导航和 `/api/copilot/*` |
| `CHATVOICE_COPILOT_AUTO_PREPARE` | `0` | 允许后台准备草稿；默认关闭，手动 Submit 始终可用 |
| `CHATVOICE_COPILOT_THINKING_MODE` | `provider-default` | 快答思考策略：`provider-default` 不增加厂家字段；`ark-disabled` 仅对本次 Copilot 请求发送火山方舟 `thinking.type=disabled`；其他值拒绝启动请求 |
| `CHATVOICE_ENV_PROFILE` | 空 | 加载指定 ChatEnv ChatVoice profile，不修改全局 active profile；缺失不会回退 active profile |

材料上传支持 TXT、Markdown、PDF、DOCX；不支持 URL 抓取。PDF 没有可提取文字时返回 OCR 不支持。材料文本、会前说明和快速回答状态按登录账号隔离，写操作继续使用既有 Cookie + CSRF 边界。

## ASR {#asr}

| 字段 | 默认值 | 用途 |
| --- | --- | --- |
| `CHATVOICE_ASR_CHANNEL` | 有 HTTP 地址时为 `api-server`，否则为 `stub-local` | 可选 `api-server`、`funasr-gpu`、`funasr-cpu`、`stub-local` |
| `CHATVOICE_ASR_API_URL` | 空 | `api-server` 的完整转写地址 |
| `CHATVOICE_ASR_API_KEY` | 空 | 可选 Bearer 密钥，敏感；按 ASR 服务要求配置 |
| `CHATVOICE_ASR_PREWARM` | `1` | 启动时预热当前本地 FunASR 通道 |
| `CHATVOICE_FUNASR_ALLOW_SUBPROCESS_WORKER` | `0` | 调试兼容开关；允许短命子进程反复加载模型，不建议生产启用 |

本地 FunASR 还读取进程变量 `FUNASR_MODEL`（默认 `iic/SenseVoiceSmall`）和 `FUNASR_GPU_DEVICE`（默认 `cuda:0`）。它们不是当前 ChatEnv 类型中的字段。CPU 通道使用 CPU；GPU 通道需要匹配的 PyTorch/CUDA/FunASR 环境。`stub-local` 不是真实识别。

## 系统语音合成 {#tts}

| 字段 | 用途 |
| --- | --- |
| `CHATVOICE_TTS_API_TYPE` | 当前支持 `openai`、`volcengine`、`qwen` |
| `CHATVOICE_TTS_API_BASE` | HTTP 根地址；Qwen 为完整 `ws/wss` 地址 |
| `CHATVOICE_TTS_API_KEY` | 独立 TTS 密钥，敏感 |
| `CHATVOICE_TTS_MODEL` | 模型标识 |
| `CHATVOICE_TTS_RESOURCE_ID` | Volcengine 所需资源标识；不等同于模型名 |
| `CHATVOICE_TTS_VOICES` | JSON 音色列表，每项为 `id`、`label`；第一项为默认音色 |

任何独立 TTS 字段非空都会启用完整性校验。`openai` / `qwen` 不要求资源标识，其他必要字段不能缺。Qwen 保留 `sk-sp` 密钥限制；这个限制不应用于其他协议。[查看配置示例与协议路径](tts-models.md)。

## 声音复刻与运行目录 {#runtime}

| 字段 | 默认值 | 用途 |
| --- | --- | --- |
| `CHATVOICE_VOICECLONE_URL` | 空 | 独立 VoiceClone 服务根地址 |
| `CHATVOICE_VOICECLONE_TIMEOUT_SECONDS` | `180` | 请求超时秒数，可按模型启动耗时调整 |
| `CHATVOICE_HOME` | `$CHATARCH_HOME/chatvoice` 或 `~/.chatarch/chatvoice` | 运行根目录；为 CLI 和服务启动器设置进程环境覆盖 |
| `CHATVOICE_SQLITE_PATH` | 运行根目录下 `data/meetings.sqlite3` | 显式 SQLite 路径；用进程环境统一账号命令与 Web 服务 |
| `CHATVOICE_REALTIME_MODELS` | 空 | 逗号分隔的实时模型允许列表；仍须符合后端支持范围和使用权限 |

共享的 `CHATARCH_HOME` 由 ChatEnv 提供。路径解析、旧路径别名和备份方法见[运行目录](runtime-layout.md)。

## 遗留部署兼容字段 {#legacy}

这些字段仍在发布包中，但新文本/TTS 部署优先使用上面的独立配置，不必为了 Todo 设置它们。

| 字段 | 兼容用途 |
| --- | --- |
| `CHATVOICE_OPENAI_API_BASE` | 原有语音账户的 HTTP 根地址；默认 Token Plan compatible-mode 地址 |
| `CHATVOICE_OPENAI_API_KEY` | 原有系统 TTS / 实时语音密钥，敏感，要求 `sk-sp` |
| `CHATVOICE_OPENAI_API_MODEL` | 未配置独立文本接口时的旧默认文本模型，默认 `qwen3.7-plus` |
| `CHATVOICE_MEETING_NOTES_PROVIDER` | 旧纪要后端选择，默认 `token-plan-chat-completions` |
| `CHATVOICE_MEETING_NOTES_CRS_PROFILE` | 旧纪要后端的外部配置引用 |
| `CHATVOICE_MEETING_NOTES_CRS_API_BASE` | 旧纪要后端的显式地址覆盖 |
| `CHATVOICE_MEETING_NOTES_CRS_API_KEY` | 旧纪要后端的显式密钥覆盖，敏感 |

显式独立文本配置优先，配置不完整时返回错误，不借用这些兼容字段。套餐额度、接口协议与账户权限是不同概念；不要用更换按量入口来掩盖套餐耗尽。
