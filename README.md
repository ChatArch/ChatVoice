# ChatVoice

[文档](https://arch.gh.wzhecnu.cn/ChatVoice/) · [英文版](README.en.md) · [PyPI](https://pypi.org/project/ChatVoice/) · [源码](https://github.com/ChatArch/ChatVoice) · [运行与备份](https://arch.gh.wzhecnu.cn/ChatVoice/runtime-layout/)

ChatVoice 是 ChatArch 的录音转写与会议工作区 Python 包，包含 Speakr 网页界面：从语音获得文字，整理摘要，再把值得推进的想法转成可编辑的 Markdown Todo。

## 按场景开始

| 你要做什么 | 阅读入口 |
| --- | --- |
| 安装并打开网页 | [快速上手](https://arch.gh.wzhecnu.cn/ChatVoice/quickstart/) |
| 录音、整理摘要和继续完善纪要 | [网页使用](https://arch.gh.wzhecnu.cn/ChatVoice/web-guide/) |
| 将摘要转为待办，继续对话修改并导出 | [Markdown Todo](https://arch.gh.wzhecnu.cn/ChatVoice/markdown-todo/) |
| 配置 ASR、文本模型、语音合成或声音复刻 | [配置参考](https://arch.gh.wzhecnu.cn/ChatVoice/configuration/) |
| 部署服务、邀请账号、备份数据 | [部署与启动](https://arch.gh.wzhecnu.cn/ChatVoice/deployment/) |
| 查看命令或接入自己的程序 | [CLI 树](https://arch.gh.wzhecnu.cn/ChatVoice/cli-tree/) · [HTTP 接口](https://arch.gh.wzhecnu.cn/ChatVoice/api-access/) · [Python 接口树](https://arch.gh.wzhecnu.cn/ChatVoice/interface-tree/) |

## 安装与检查

要求 Python 3.10 或更高版本，建议安装到独立虚拟环境。

```bash
python -m pip install "ChatVoice[web]==0.2.0"
chatvoice --version
chatvoice --tree
chatvoice serve app --dry-run --json
```

安装包本身不会自动启动服务，也不会自动下载 GPU 模型。[快速上手](https://arch.gh.wzhecnu.cn/ChatVoice/quickstart/)区分无模型界面体验与真实转写部署。

## 当前能力

- **会议记录**：实时转写、暂停与继续、会议标题、标签、历史记录和复制文字。
- **摘要与纪要**：生成摘要，手动编辑纪要，或通过对话修改并撤销。
- **Markdown Todo**：由用户点击“转为 Todo”，在独立页面继续编辑、对话完善、复制或下载 `.md`；不会自动转换或执行任务。
- **声音工作室**：配置系统音色与输出格式；通过独立声音复刻服务，以授权参考音频生成临时试听结果。
- **实时对话**：对接当前支持的 Qwen 实时语音模型，需服务端配置和有效使用权限。
- **程序化访问**：命令行、Python 客户端、受限 API Token，以及单文件数据库备份与恢复。

模型配置保留在服务端。摘要和标题使用独立文本设置；Todo 复用摘要模型，不增加一套密钥。ASR HTTP 服务使用 `CHATVOICE_ASR_API_URL`，本地 FunASR 则需要另行准备模型依赖。

## 数据与安全边界

账号记录保存到 `~/.chatarch/chatvoice` 下的 SQLite；访客记录仅存于当前浏览器。录音会为识别而短暂经过浏览器和服务端，但不作为会议音频档案保存。密钥不进入浏览器。

自助注册关闭，由部署者创建受邀账号。ChatVoice 直接依赖 ChatLogin 0.1.2 的内建 `ChatVoiceAuth`，复用既有账号、会话和 CSRF；`/login` 使用可定制的共享 `LoginUI`。会议所有权和 Token 权限仍由 ChatVoice 控制，访客草稿等待 IndexedDB 事务提交后才跳转登录。详见[数据保留边界](https://arch.gh.wzhecnu.cn/ChatVoice/recording-storage/)。

## 开发

```bash
python -m pip install -e ".[web,dev,docs]"
python -m pytest tests -q
mkdocs build --strict
```

前端控制器回归要求 Node.js 22 或更高版本。普通测试不代表真实模型已经可用；真实服务验收单独执行，见[开发与验证](https://arch.gh.wzhecnu.cn/ChatVoice/testing/)。
