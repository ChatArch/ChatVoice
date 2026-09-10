# 部署与启动

先确定服务形态，再安装和配置。ChatVoice 自带网页服务，不自带系统服务安装器或通用反向代理管理器。

| 形态 | 适用场景 | 关键条件 |
| --- | --- | --- |
| 前台单进程 | 开发、受控体验 | 退出终端会停止服务 |
| 用户级 systemd | Linux 长期运行 | 持久虚拟环境、明确数据目录、正常停止策略 |
| 自托管 ASR HTTP 服务 | GPU 与网页服务分离 | `CHATVOICE_ASR_API_URL` 指向实际转写接口 |
| 同进程 FunASR | 已准备好本地模型环境 | 匹配 CUDA/PyTorch，启动预热，避免每请求重载 |

## 安装和预检

```bash
python -m pip install "ChatVoice[web]==0.1.17"
chatvoice paths --json
chatvoice doctor --json
chatvoice service plan --ensure-dirs --json
chatvoice serve app --dry-run --json
```

代码安装在 Python 的 `site-packages`；运行数据默认写入 `~/.chatarch/chatvoice`。模型与密钥按[配置参考](configuration.md)设置在服务端。摘要模型与标题模型使用各自的独立配置，Todo 复用纪要模型。

如果覆盖路径，为账号管理命令和服务设置相同的进程环境：

```bash
export CHATARCH_HOME="$HOME/.chatarch"
export CHATVOICE_HOME="$CHATARCH_HOME/chatvoice"
export CHATVOICE_SQLITE_PATH="$CHATVOICE_HOME/data/meetings.sqlite3"
```

## 创建账号

先安全提供 `CHATVOICE_ACCOUNT_LOGIN`，再执行：

```bash
chatvoice accounts add member@example.com --display-name 成员 --password-env CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts list --json
```

自助注册关闭。已有账号、密码材料和会话由 ChatLogin 宿主适配层复用，不需要重新建用户库或重置密码。

## 前台启动

```bash
chatvoice serve app --host 127.0.0.1 --port 18087 --workers 1
```

本机验证可用回环地址；远程用户使用实际部署的 HTTPS 入口。反向代理应转发 WebSocket，并避免缓冲纪要 SSE；不要把原始模型密钥发到网页。

## 用户级 systemd 示例

先确认虚拟环境与数据目录存在。将以下薄入口保存为 `~/.config/systemd/user/chatvoice.service`；它不是由 `chatvoice service plan` 自动安装的。

```ini
[Unit]
Description=ChatVoice Speakr
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/.chatarch/chatvoice
Environment=CHATVOICE_HOME=%h/.chatarch/chatvoice
ExecStart=%h/.chatarch/chatvoice/.venv/bin/chatvoice serve app --host 127.0.0.1 --port 18087 --workers 1
Restart=on-failure
KillSignal=SIGINT
SendSIGKILL=no
TimeoutStopSec=120

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now chatvoice.service
systemctl --user status chatvoice.service
journalctl --user -u chatvoice.service -n 100 --no-pager
```

按主机政策确认退出登录后的用户服务生命周期。代理、`ffmpeg` 和模型依赖也必须在服务的实际运行环境可用；交互式终端可用不代表 systemd 自动继承它们。

## 上线验证与升级

1. 读取 `/api/heartbeat` 的版本、`database.ok` 和 ASR 状态。
2. 用短合成内容分别验证真实 ASR、摘要、标题、Todo、TTS；未启用的可选能力应明确记录。
3. 验证网页账号/访客、保存、刷新和实际入口，不仅测试回环端口。
4. 升级前保存旧安装包、配置副本与一致性数据库备份；固定目标版本，避免无关 GPU 依赖升级。
5. 使用监督器正常停启，再核对新进程、安装版本、依赖差异和真实功能。

不要用旧数据库备份覆盖升级期间产生的新记录来“回滚代码”。[备份与恢复](runtime-layout.md#backup) · [故障排查](troubleshooting.md)。
