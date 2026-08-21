# 声音复刻使用指南

本页描述当前 Speakr / ChatVoice 声音工作室里的 **本地复刻 · 一次性生成** 流程。它对应 hitk 上的 VoiceClone sidecar + IndexTTS-2.5：上传或录制一段参考音频，再输入一段新文本，页面生成一段临时复刻试听音频。

## 当前定位

- 这是一次性 voice cloning：参考音频 + 新文本 -> 本次生成音频。
- 需要登录账号；访客模式不能生成复刻音频。
- 不保存 voice profile，不创建可复用 voice id。
- 不保存生成历史；结果只作为临时任务文件，用于当前页面试听/下载。
- 会议记录页仍不保存原始会议录音；声音复刻的参考音频和输出音频是独立的临时任务文件。

## 适用场景

你可以用它完成一个完整的 Voice Cloning 验收：

1. 录一段自己的声音或上传一段授权参考音频；
2. 输入希望这个声音重新说出的新文本；
3. 点击生成复刻试听；
4. 等待进度条显示生成状态；
5. 在试听结果里播放生成音频，并和参考音频做听感对比；
6. 如需带走当前结果，点击下载生成音频。

## 网页端使用步骤

1. 打开 Speakr 公网页面。

   <https://speakr.public.wzhecnu.cn/>

2. 选择 **登录账号** 并登录受邀账号。

   声音复刻会上传参考音频到本地 VoiceClone sidecar 生成临时任务，因此必须使用账号会话。访客模式下点击生成会提示先登录。

3. 进入顶部 **声音工作室**。

4. 在 **文字与声音** 文本框里输入要生成的新文本。

   这里不是参考音频的转写内容，而是希望复刻声音重新说出的目标文本。建议先用 1–3 句中文短文本验收，再尝试更长文案。

5. 在 **本地复刻 · 一次性生成** 卡片里准备参考音频。

   - 点击 **参考音频** 上传 WAV/MP3/WebM 等浏览器可选音频文件；或
   - 点击 **录参考音**，授权麦克风后录制 10–20 秒。

   推荐参考音频：单人、干净、无背景音乐、无混响，10–20 秒即可。

6. 选择语言和语速。

   当前常用验收路径为：语言 **中文**，语速 **正常**。

7. 勾选授权确认。

   必须确认已获得声音本人授权，仅用于本次调试生成。未勾选时点击生成会提示授权缺失。

8. 点击 **生成复刻试听**。

   页面会显示进度条：

   - `提交中`：ChatVoice 正在把文本和参考音频发给本地 sidecar；
   - `generating · 预计 ...s`：IndexTTS-2.5 正在生成；
   - `生成完成`：音频已返回页面。

9. 在 **试听结果** 区域播放或下载。

   生成成功后，结果区会显示：

   - 音频播放器；
   - `VoiceClone · indextts`；
   - 文件大小；
   - **下载生成音频** 按钮。

## 验收标准

一次完整验收应同时满足：

- 登录账号后可以进入 **声音工作室**；
- `/api/voice-clone/status` 返回 `configured=true`、`status=ready`、`engine=indextts`；
- 参考音频上传后卡片显示文件名；
- 未满足登录/参考音频/授权/文本任一前置条件时，点击生成有明确提示，不是无响应；
- 点击生成后出现进度条，能看到 `生成中…` 或 `generating` 状态；
- 生成完成后 **试听结果** 出现播放器；
- 播放器可以播放，下载按钮存在；
- 浏览器 console 没有 JS error。

## 已完成的 hitk 公网验收

2026-08-22 在公网页面完成过一次端到端验收：

- 页面：<https://speakr.public.wzhecnu.cn/?preview=voiceclone-acceptance-guide>
- 登录：临时验收账号，验收后删除。
- 参考音频：`voice_01-reference.wav`，约 467 KB。
- 目标文本：一段中文新文本，用于让参考声音重新说出。
- 进度状态：页面显示 `generating · 预计 45s`，进度条约 45%。
- 生成结果：`VoiceClone · indextts`，约 1.5 MB，约 35.5 秒。
- 播放验证：点击播放器后 `paused=false`、`readyState=4`。
- Console：无 JS error。

截图留档：

- 上传参考音频后：`browser_screenshot_ede123acad43401baa28f83821754fce.png`
- 生成中进度条：`browser_screenshot_d0c0c00a1cf0463d81a73f11733b8e52.png`
- 生成完成并播放：`browser_screenshot_af2a981d4c0e464a9d7cd4cbabbd8456.png`

## 常见问题

### 点击生成没有反应怎么办？

当前版本已经修复旧版无响应问题。按钮会在 sidecar ready 时保持可点击，并按缺失条件提示：

- `请先登录账号`
- `请先上传或录制参考音频`
- `请先确认已获得声音本人授权`
- `请先输入要生成的文字`
- `本地复刻服务尚未就绪`

如果仍然无响应，打开浏览器 console；不应出现 `clone-audio-url`、`clone-prefix` 或 `voice-cloning/create` 相关错误。

### 为什么不是创建 voice id？

当前 MVP 是 one-shot voice cloning，不是 enrollment。系统不会保存 voice profile，也不会让用户管理 voice id。每次生成都需要参考音频和目标文本。

### 普通“生成声音”和“生成复刻试听”有什么区别？

- **生成声音**：使用系统音色或已有自定义 voice id 做普通 TTS。
- **生成复刻试听**：使用本次上传/录制的参考音频做本地 one-shot 复刻。

如果只是验证 Voice Cloning，请使用 **本地复刻 · 一次性生成** 卡片里的 **生成复刻试听**。

## 运维检查

```bash
curl -sS https://speakr.public.wzhecnu.cn/api/voice-clone/status | jq
```

期望关键字段：

```json
{
  "configured": true,
  "status": "ready",
  "engine": "indextts",
  "model_version": "2.5",
  "device": "cuda:0",
  "model_loaded": true
}
```

hitk 当前服务：

```text
chatvoice-production-18087
voiceclone-sidecar-18187
```
