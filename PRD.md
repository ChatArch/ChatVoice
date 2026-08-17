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
- 只记录字段是否存在、Base URL host/path、模型名等安全元数据；不输出 key 值或任何密钥派生标识。
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
2. 体验形态参考 Open WebUI Chat 输入框：输入框右下角只有一个麦克风按钮；用户点一下进入“录音中”，说话内容像打字一样实时渲染到同一个文本框。
3. 输入框中的语音文字自动保留到“下一步内容”，用于后续会议纪要、智能润色和实时摘要。
4. 主展示只显示 corrected/final；raw/interim 只可作为低层级调试旁注，不能和 corrected 同级重复。
5. 默认走 GPU 路线：`funasr-gpu`（CUDA PyTorch + FunASR/SenseVoiceSmall worker）。`funasr-cpu` 和 `stub-local` 仅作为显式 fallback / smoke 通道。

## 完成标准

- `reports/qwen-audio-tts-realtime-exploration.md` 完成，包含来源、官方 Demo 情况、API 结论、实测结果、风险和下一步。
- `app/` 下有可读 Demo 源码和启动说明。
- 页面包含 `语音合成`、`实时对话`、`语音转写` 三块能力；ASR 标签页必须是 Open WebUI 风格的输入框麦克风体验，按钮进入录音态，文字实时进入输入框并留下给下一步内容。
- 后端提供 `/api/asr/channels`、`/api/asr` 和 `/ws/asr/stream`；浏览器 ASR 主流程使用 `/ws/asr/stream` 持续发送麦克风音频，默认走 `funasr-gpu`。
- `progress.md` 记录每个实质动作。
- 若 TTS、Realtime 或 ASR 调用失败，报告真实 HTTP/WebSocket/依赖错误和可能原因，不伪造成功。

## 会议录音前端升级（2026-08-17）

### 目标

把默认首页从开发者音频能力面板升级为移动端优先的会议录音产品页，视觉和交互参考豆包会议录音：

- 页面主体实时展示带时间位置的转写文本
- “文字记录 / 实时摘要”两个主标签
- 底部固定真实波形、时长、暂停/继续和结束
- 录音按钮直接连接现有 `/ws/asr/stream`
- 摘要按钮调用现有 `/api/meeting-notes/polish`

### 约束

- 不修改或删除已有 TTS、声音克隆、Realtime、ASR 与会议纪要后端路由
- 浏览器继续只连接本项目后端，不接触上游密钥
- 识别通道从 `/api/asr/channels` 获取，界面默认使用服务端指定通道
- 前端正确呈现等待权限、连接中、录音中、暂停、收尾、已结束和失败状态
- 保留注入辅助函数，支持无需麦克风的前端合同验证
- 访客模式在入口和录音控制区明确展示“每个录音段 10 分钟”；登录模式明确展示“每个录音段 2 小时”
- 暂停不计入录音段时长；结束后或打开历史会议后允许继续追加新录音段
- 长录音必须滚动上下文窗口，不能对数小时音频持续做全量重识别
- 两小时录音期间，原始 MediaRecorder 分片必须持续写入浏览器 IndexedDB；只在用户下载时组装完整 Blob，避免录音过程占用线性增长的 JS 内存

## 双模式会话管理（2026-08-17）

### 目标

- 首页先让用户选择“访客使用”或“登录账号”
- 左侧提供新会议、搜索、按日期分组、切换和删除会议记录
- 访客模式的标题、转写和摘要只保存在浏览器 IndexedDB，声笺服务端不持久化会议正文
- 登录模式的标题、转写和摘要绑定账号保存在服务端 SQLite，可在同一账号下跨设备读取
- 两种模式都可调用实时 ASR 与摘要接口；音频和文字会在请求期间经过服务端处理
- 原始录音默认不上传保存，仍只存在于当前页面并可下载

### 账号与安全约束

- 首版账号使用用户名/邮箱与密码；密码只保存 PBKDF2-SHA256 加盐哈希
- 登录态使用 HttpOnly、SameSite Cookie；服务器会议写操作同时校验 CSRF token
- 匿名请求不得读取或写入服务器会议数据库
- 账号之间的会议记录必须严格隔离
- 清空当前会议时同时清除转写和摘要，并取消仍在进行的摘要请求，防止旧响应回写
