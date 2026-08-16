# Progress

## 2026-08-17 会议录音前端改造

- 默认首页从模型能力实验台改为移动端优先的会议录音产品页
- 复用现有 `/ws/asr/stream`，浏览器麦克风音频实时发送到统一 ASR 通道
- 增加 MediaRecorder 本地归档、暂停/继续、结束和下载
- 增加“文字记录 / 实时摘要”，摘要调用现有 `/api/meeting-notes/polish`
- 保留 TTS、声音克隆、Realtime 与 ASR 后端路由，暂不在主页面暴露
- 更新前端合同检查，覆盖产品主界面、录音状态、WebSocket、摘要与密钥边界

## 下一步

- 已在本地启动 FastAPI，完成静态页、前端合同、转写提取和 ASR 合同检查
- 已推送 GitHub `main`（提交 `0df1bf0`），同步 Recall 并重启现有服务
- 已通过公网 HTTPS/WSS 验证：新版首页、识别设置、摘要页及 `funasr-gpu` 静音流完整返回
- 公网体验地址：`https://qwen-audio-demo.public.wzhecnu.cn/?v=0df1bf0`

## 当前发布级别

- 可作为内部/邀请制 Beta 使用：HTTPS、WSS、GPU ASR、服务端密钥与摘要接口均可用
- 尚不按正式生产服务承诺：当前进程由 tmux 守护，未配置登录、限流、监控告警与历史数据存储
- 现有流式 ASR 连接仍有 60 秒演示限制；长会议、本地恢复与完整录音二次校对尚待实现
- 下一步优先完成手机真机麦克风测试、连接续期/重连、IndexedDB 分片保存和 systemd/容器化守护
