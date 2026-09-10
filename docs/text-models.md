# 独立文本模型

纪要、标题与语音是不同能力。文本模型使用 OpenAI 兼容 Chat Completions 接口，不要求与 ASR 或 TTS 来自同一提供者。

| 用途 | 配置前缀 | 作用 |
| --- | --- | --- |
| 纪要 | `CHATVOICE_MEETING_NOTES_` | 摘要、纪要对话、Todo 转换与改写 |
| 标题 | `CHATVOICE_MEETING_TITLE_` | 会议标题 |
| 语音 | 另见 TTS 配置 | 不向文本用途借用密钥 |

## 配置完整三项

在 ChatEnv 的 `ChatVoice` 类型中设置：

```dotenv
CHATVOICE_MEETING_NOTES_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_NOTES_API_KEY=[REDACTED]
CHATVOICE_MEETING_NOTES_MODEL=your-notes-model
CHATVOICE_MEETING_TITLE_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_TITLE_API_KEY=[REDACTED]
CHATVOICE_MEETING_TITLE_MODEL=your-title-model
```

这些是示例占位值。两组配置可以指向同一后端，但每组都需完整声明。独立 base/key 任一非空即启用该用途的独立路径；缺字段会明确失败，不从语音、另一文本用途或全局 OpenAI 配置借值。

具体导入和激活命令见[配置参考](configuration.md)。

## 验证顺序

```bash
chatenv test -t chatvoice -I
```

1. 用短合成文字生成摘要，确认返回正文而非仅推理文本。
2. 单独请求标题；摘要成功不代表标题配置正确。
3. 在网页继续对话完善纪要，再转换为 Todo 并改写。
4. 验证原摘要保留、保存与刷新恢复。

连通性测试会调用已配置的模型并消耗其额度。生产探测不要使用真实会议内容。

## 错误与边界

| 状态 | 含义与处理 |
| --- | --- |
| 配置错误 / 503 | 检查该用途的完整三项，不更换无关语音配置 |
| 上游或输出错误 / 502 | 检查服务日志、网络和提供者状态；保留原文后重试 |
| 空、截断或仅推理输出 | 不视为成功正文 |
| 额度或权限不足 | 停止请求；不要自动切到按量付费入口 |

非流式完成要求非空正文和明确完成状态；纪要流式修改也需要真正的结束标记。页面展示的是脱敏状态，不返回模型密钥。

[Markdown Todo](markdown-todo.md) · [HTTP 接口](api-access.md) · [故障排查](troubleshooting.md)
