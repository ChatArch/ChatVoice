# 故障排查

先区分入口、业务处理和外部模型，不要反复重启所有组件。

| 现象 | 先检查 | 下一步 |
| --- | --- | --- |
| 页面或麦克风不可用 | 实际网址、HTTPS、浏览器权限 | [网页使用](web-guide.md) |
| 摘要/Todo 失败 | 对应文本配置、502/503、额度 | [文本模型](text-models.md) |
| TTS 没有可用音色或生成失败 | 独立 TTS 配置与返回格式 | [语音后端](tts-models.md) |
| 复刻服务离线 | 当前配置地址、sidecar 监听与监督器 | [复刻排查](#voiceclone) |
| 刷新后记录不见 | 账号/访客模式、浏览器来源与保存状态 | [保留边界](recording-storage.md) |
| 只读 API 拒绝 | Token scope、过期、撤销、对象所有权 | [HTTP 接口](api-access.md) |

## 先看当前状态

```bash
chatvoice doctor --json
chatvoice health status --url https://speakr.example.com --json
```

`/api/heartbeat` 中的数据库状态是 `database.ok`，ASR 预热是 `asr.funasr_model_warm`。不要用不存在的同名顶层字段判断故障。

`/api/status` 和模型列表不是完整生成验收；模型可见不代表有额度或权限。记录实际请求时间、路由、HTTP 状态与安全错误信息，不收集原始密钥。

## 摘要与 Todo

- `503`：优先核对当前用途的独立配置，不修改无关 TTS/ASR。
- `502`：区分上游拒绝、网络失败、空/截断输出；保留原文。
- 浏览器显示请求失败，但相同 HTTP 请求成功：检查浏览器网络错误、代理和超时，不直接认定密钥失效。
- 对话未结束、SSE 缺少结束标记或输出不完整时，不把局部文本作为成功覆盖原文。

使用监督器的实际日志。例如 systemd 部署：

```bash
journalctl --user -u chatvoice.service -n 100 --no-pager
```

日志位置由启动方式决定；存在 `logs/` 目录不表示已经记录全部上游错误正文。

## 声音复刻离线 {#voiceclone}

1. 读取 `CHATVOICE_VOICECLONE_URL`，确认主服务实际访问哪台机器、哪个端口。
2. 从主服务主机检查该地址的 `/health`，不要只在 sidecar 自己的回环地址验证。
3. 检查 sidecar 的监听进程、运行环境、完整模型目录和已有监督器。
4. 如果原临时会话已消失，复用原环境建立持久监督器，正常启动；不要重装全部 GPU 依赖或顺手重启主网页服务。
5. 服务可达后执行授权测试任务，确认 `model_loaded=true`、生成音频可解码并清理任务。
6. 最后读回 ChatVoice 的 `/api/voice-clone/status`，应为 `configured=true`、`status=ready`。

`model_loaded=false` 可能只是冷启动，不等于离线。先确认状态，再决定是否需要重启。

## 保存与身份

访客数据属于当前浏览器，不会自动上传到账号。刷新后如出现入口选择框，重新选择对应模式；账号模式同时确认登录的账号和会议。只读 Token 无权代替网页 Cookie/CSRF 保存记录。

[部署与升级](deployment.md) · [测试方法](testing.md)
