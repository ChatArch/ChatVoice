# 千问 Token Plan TTS / Realtime Demo 探索

## 目标

创建一个轻量网页 Demo，探索现有千问 Token Plan API Key 中两个音频模型的真实接入方式：

1. `qwen-audio-3.0-tts-plus`：确认 TTS API 形态、请求/响应格式、音频返回方式，并做最小网页 Demo。
2. `qwen-audio-3.0-realtime-plus`：确认 realtime 语音对话 API 形态、是否为 OpenAI-compatible Realtime、WebSocket / session 创建方式和浏览器接入边界。
3. 官方实践：优先查找千问官方文档、SDK、示例、Gradio/Streamlit/网页 starter；若官方有可用 Demo，记录复用方式；若没有，再自建最小 Demo。
4. 密钥加载：API Key 只在服务端环境变量或本地 env 文件中读取，密钥不进前端、不进报告、不输出到日志。

## Observable outcome

用户最终能看到：

- 一份探索报告说明 TTS 与 Realtime 怎么接、官方是否有 Demo、当前 Key 能不能实际调用。
- 一个轻量本地 Demo 网页代码：后端从服务端环境变量或本地 env 文件读取 Key，前端只调用本地后端；至少 TTS 路径可通过最小 smoke 验证，Realtime 若协议确认则提供最小连接/诊断页面。

## 服务器资源边界

- 默认按轻量本地 Demo 运行，长期部署需另行配置进程管理和反向代理。
- 允许：写轻量 Python/HTML Demo、短时绑定 `127.0.0.1` 做本地 smoke。
- 不建议：直接提交密钥、让浏览器直连上游模型、无鉴权公网暴露后端。
- 默认启动在 `127.0.0.1`，按需通过 SSH tunnel 或受控反向代理访问。

## 密钥与安全

- 使用服务端环境变量或本地 env 文件：`OPENAI_API_KEY` / `DASHSCOPE_API_KEY` / `OPENAI_API_BASE`。
- 不打印、不写入真实 `OPENAI_API_KEY` / `DASHSCOPE_API_KEY`。
- 只记录字段是否存在、Base URL host/path、模型名等安全元数据；不输出 key 值或 key fingerprint。
- 前端不得直接接触 Key；Demo 后端读取服务端密钥并代理上游调用。

## 探索顺序

1. 配置服务端环境变量或本地 env 文件，确认 Token Plan Key 可被后端读取。
2. 官方资料优先：千问 Token Plan、TTS、Realtime、OpenAI-compatible / Realtime 文档，查找官方 Demo/SDK/Gradio/Streamlit。
3. 最小 API 探针：只做 `/models` 与极小 TTS / Realtime session 级别测试；若接口不匹配，保存真实错误。
4. 构建 Demo：轻量 Python 标准库或已有环境，页面包括 TTS 表单、Realtime 诊断/连接区。
5. 本地 smoke：只验证 `127.0.0.1` 端点，不做公网发布。
6. 汇总报告与下一步建议。

## ASR 多渠道补充范围（2026-08-13）

用户希望后续不要只围绕千问 Realtime：如果纯 ASR 的使用形式可以做到相似，就做成多渠道体验。当前新增范围：

1. 增加统一 ASR 通道层，首选 `funasr-cpu`，后续可扩展 Whisper / 云 ASR / Qwen 专用 ASR。
2. 体验形态统一为一键实时文字：用户点击“开始实时转写”后直接说话，页面自动持续显示文字；不得把上传录音、录音回放、手动提交、手动分段作为 ASR 标签页主流程。
3. ASR 实时文字自动保留到“下一步内容”，用于后续会议纪要、智能润色和实时摘要。
4. 主展示只显示 corrected/final；raw/interim 只可作为低层级调试旁注，不能和 corrected 同级重复。
5. 默认走 GPU 路线：`funasr-gpu`（CUDA PyTorch + FunASR/SenseVoiceSmall worker）。`funasr-cpu` 和 `stub-local` 仅作为显式 fallback / smoke 通道。

## 完成标准

- `reports/qwen-audio-tts-realtime-exploration.md` 完成，包含来源、官方 Demo 情况、API 结论、实测结果、风险和下一步。
- `app/` 下有可读 Demo 源码和启动说明。
- 页面包含 `语音合成`、`实时对话`、`语音转写` 三块能力；ASR 标签页必须是一键实时转文字体验，文字自动出现并留下给下一步内容。
- 后端提供 `/api/asr/channels`、`/api/asr` 和 `/ws/asr/stream`；浏览器 ASR 主流程使用 `/ws/asr/stream` 持续发送麦克风音频，默认走 `funasr-gpu`。
- `progress.md` 记录每个实质动作。
- 若 TTS、Realtime 或 ASR 调用失败，报告真实 HTTP/WebSocket/依赖错误和可能原因，不伪造成功。
