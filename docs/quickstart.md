# 快速上手

真实 HTTP 识别后端使用 `CHATVOICE_ASR_API_URL`；其地址和凭据配置见[配置参考](configuration.md)。

先选择目标。无模型体验只验证界面和流程，不能替代真实识别或模型调用。

<div class="grid cards" markdown>

- **我只使用现有网页**

    ---
    打开部署者提供的 Speakr 地址，选择账号或访客模式。

    [网页使用](web-guide.md)

- **我想先体验界面**

    ---
    使用 `stub-local`，不安装 GPU 模型、不配置云密钥。

    [启动体验](#ui-trial)

- **我要运行真实服务**

    ---
    配置真实 ASR 和文本模型，再按需启用其他语音能力。

    [真实服务](#real-service)

</div>

## 安装 {#install}

要求 Python 3.10+。以下虚拟环境位于 ChatArch 运行目录中；Windows 可使用相同包并按对应虚拟环境激活方式操作。

```bash
python3 -m venv "$HOME/.chatarch/chatvoice/.venv"
. "$HOME/.chatarch/chatvoice/.venv/bin/activate"
python -m pip install "ChatVoice[web]==0.2.0"
chatvoice --version
chatvoice --tree
```

`web` 扩展提供网页服务依赖；不包含 CUDA、PyTorch 或 FunASR 模型安装。

## 启动界面体验 {#ui-trial}

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --dry-run --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

在服务所在机器的浏览器打开 `http://127.0.0.1:18087/`，选择访客模式。退出前台服务使用终端的正常中断操作。

!!! warning "这不是真实转写"
    `stub-local` 不加载模型。摘要、Todo、TTS 和实时对话仍需要各自的后端配置。远程用户不能用自己电脑的 `127.0.0.1` 访问服务器，应使用部署好的 HTTPS 入口。

## 运行真实服务 {#real-service}

| 功能 | 最少需要准备 |
| --- | --- |
| ASR | HTTP ASR 地址，或同服务环境内可用的 FunASR 模型与设备 |
| 摘要、纪要修改、Todo | 会议纪要模型的接口地址、密钥和模型名 |
| 自动标题 | 标题模型的接口地址、密钥和模型名 |
| 系统 TTS | 协议、接口地址、密钥、模型与音色；部分协议还需资源标识 |
| 声音复刻 | 可达的 VoiceClone 服务；网页生成需账号与声音授权 |
| 实时对话 | 当前 Qwen 实时后端凭据、模型权限 |

先按[配置参考](configuration.md)设置需要的能力，然后执行：

```bash
chatenv test -t chatvoice -I
chatvoice serve app --host 127.0.0.1 --port 18087
```

ChatEnv 自检会调用已配置的文本/TTS 服务，可能消耗套餐额度；它不是 ASR、实时语音或声音复刻的全量验收。

## 邀请账号

自助注册关闭。在服务所在环境中，将密码安全放入 `CHATVOICE_ACCOUNT_LOGIN`，再运行：

```bash
chatvoice accounts add member@example.com --display-name 成员 --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

不要将密码直接写入命令参数或公共脚本。随后在网页选择账号登录。长期运行与 HTTPS 入口见[部署指南](deployment.md)。
