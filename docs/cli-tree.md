# CLI 树

命令树由 `chatstyle.add_tree_option()` 从已注册命令生成，提供 `--tree` 和 `--tree-brief`。

下列拓扑来自真实 `chatvoice --tree`。按职责分段阅读；参数名保留原样，注释说明副作用。

## 顶层入口

```text
chatvoice
├── --help  # 查看帮助
├── --version  # 查看版本
├── --tree  # 完整命令树（含参数）
├── --tree-brief  # 简洁命令树
├── accounts  # 在服务所在机器管理受邀账号
├── asr  # 检查识别通道设置
├── data  # 读取服务记录或备份本地数据库
├── doctor [--json]  # 只读本地运行依赖与路径检查
├── health  # 检查运行中服务
├── paths [--json]  # 只读解析后的运行目录
├── serve  # 启动网页服务
├── service  # 查看部署计划
└── tokens  # 管理远端 API Token
```

## `accounts`

```text
chatvoice accounts
├── add <ACCOUNT> [--display-name DISPLAY-NAME] [--password-env PASSWORD-ENV] [--json]  # 创建受邀账号；写入本地数据库
└── list [--json]  # 只读账号元数据
```

账号命令操作当前机器的服务数据库，不是远程账号管理接口。密码通过 `--password-env` 指定的环境变量读取。

## `asr`

```text
chatvoice asr
└── channels [--json]  # 列出通道配置与状态，不执行真实识别
```

这里是配置检查，不会运行模型或证明识别质量。真实识别通过网页或 HTTP/流式接口完成。

## `data`

```text
chatvoice data
├── conversation <CONVERSATION-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # 读取单条对话正文
├── conversations [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # 读取对话列表
├── dump [--output OUTPUT-PATH] [--overwrite] [--json]  # 一致性备份本地 SQLite 单文件
├── import <INPUT-PATH> [--yes] [--no-backup-current] [--json]  # 恢复数据库；需先停止服务
├── meeting <MEETING-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # 读取单条会议和 Todo 正文
└── meetings [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # 读取会议列表
```

`meeting(s)` / `conversation(s)` 使用 `--url` 指向远端服务并通过 `--token-env` 读取 Bearer Token。`dump` / `import` 则操作本地 SQLite；导入前停止服务，默认先备份当前数据库。

## `health`

```text
chatvoice health
└── status [--url URL] [--timeout TIMEOUT] [--json]  # 读取服务的脱敏状态
```

`health status` 读取 `/api/status`。连接成功不等于所有模型、套餐权限或 sidecar 均可用。

## `serve`

```text
chatvoice serve
└── app [--host HOST] [--port PORT] [--reload] [--workers WORKERS] [--dry-run] [--json]  # 启动 Speakr；--dry-run 只展示计划
```

SQLite 部署保持单服务进程。`--reload` 用于开发；`--dry-run` 不启动监听端口。

## `service`

```text
chatvoice service
└── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # 展示计划；--ensure-dirs 会创建目录
```

`service plan` 不安装 systemd、不重启服务；只有显式 `--ensure-dirs` 创建运行目录。

## `tokens`

```text
chatvoice tokens
├── create [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--name NAME] [--expires-days EXPIRES-DAYS] [--scope SCOPES] [--timeout TIMEOUT] [--json]  # 创建 Token；密钥仅展示一次
├── list [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # 只读 Token 元数据
└── revoke <TOKEN-ID> [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # 撤销指定 Token
```

这些命令先以账号登录远端服务。创建结果含一次性密钥，不要写入公共日志；撤销立即使该 Token 失效。

## 常用路径

| 目标 | 命令或入口 |
| --- | --- |
| 解析运行路径 | `chatvoice paths --json` |
| 检查本机环境 | `chatvoice doctor --json` |
| 预览启动计划 | `chatvoice serve app --dry-run --json` |
| 操作 Todo | 网页、HTTP 接口或 Python 模块；当前无 Todo CLI 子命令 |

ChatVoice 以显式参数调用为主。ChatEnv 的 `-i` / `-I` 是配置工具自己的选项，不应附加到未支持它们的 ChatVoice 命令。

[HTTP 接口](api-access.md) · [Python 接口树](interface-tree.md) · [配置参考](configuration.md)
