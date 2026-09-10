# 运行目录与数据结构

源码、持久数据和临时处理文件分开管理。

| 内容 | 位置或载体 |
| --- | --- |
| 安装代码 | 当前 Python 环境的 `site-packages/chatvoice` |
| 配置 | ChatEnv 的 `envs/ChatVoice/` |
| 账号记录 | 一个 SQLite 文件 |
| 访客记录 | 当前浏览器 IndexedDB |
| ASR 中间文件 | 运行根目录的 `temp/asr` |
| 模型缓存 | 运行根目录的 `model-cache` 或显式指定的模型缓存 |

## 默认布局

```text
~/.chatarch/chatvoice/
├── data/
│   └── meetings.sqlite3
├── logs/
├── run/
├── temp/
│   └── asr/
└── model-cache/
```

```bash
chatvoice paths --json
chatvoice doctor --json
```

路径解析顺序为：Python 显式 `chatvoice_home` → 进程变量 `CHATVOICE_RUNTIME_ROOT`（兼容）→ `CHATVOICE_HOME` → `CHATARCH_HOME/chatvoice` → `~/.chatarch/chatvoice`。数据库可由进程变量 `MEETING_DB_PATH`（兼容）或 `CHATVOICE_SQLITE_PATH` 覆盖。

ChatEnv 中登记了路径字段，但并不会替任意 CLI 进程自动导出变量。覆盖路径时，让账号命令、备份命令和服务启动环境使用同一值。

## SQLite 数据 {#schema}

| 表 | 内容 |
| --- | --- |
| `accounts` | 账号元数据与密码验证材料 |
| `auth_sessions` | 会话摘要、CSRF 与过期时间 |
| `api_tokens` | Token 摘要、scope、有效期、撤销状态 |
| `meeting_records` | 转写、标签、摘要、纪要对话、Markdown Todo 与 Todo 对话 |
| `conversation_records` | 实时对话文字与模型/音色元数据 |

转写片段、标签与对话消息用 JSON 文本列保存；摘要与 `todo_markdown` 是正文文本。原始录音不是数据库字段。Todo 为空的旧记录仍可读取，旧客户端省略 Todo 字段不会清空它们。

当前存储是单节点 SQLite WAL。Postgres/MySQL 没有可用切换配置；不要把增加进程数当作数据库迁移。

## 一致性备份与恢复 {#backup}

```bash
chatvoice data dump --output "$HOME/.chatarch/chatvoice/backup.sqlite3" --json
```

备份使用 SQLite 一致性快照。不要在写入时仅复制主 `.sqlite3` 文件而忽略 WAL 状态。

恢复会替换当前数据库。先正常停止服务，再确认目标和备份：

```bash
systemctl --user stop chatvoice.service
chatvoice data import "$HOME/.chatarch/chatvoice/backup.sqlite3" --yes --json
systemctl --user start chatvoice.service
```

默认先备份当前数据库；`--no-backup-current` 会关闭这项保护。恢复不是代码升级的默认步骤，不能用旧快照覆盖新记录。

## 临时文件与日志

ASR 可能为解码/识别短暂落盘，正常处理后清理；异常退出时应检查任务自有的残留。TTS/复刻的临时生成结果和会议原始录音是不同的数据类型，见[保留边界](recording-storage.md)。

`logs/` 是可用的运行目录，不表示程序自动把所有请求写到固定日志文件。使用 systemd 部署时，优先查看该 unit 的 journal；日志位置由启动方式决定。
