# 用户管理

!!! warning "未发布预览"
    本页描述匹配 ChatLogin/ChatVoice 候选 wheel 对中的能力。公开 ChatVoice 0.4.1 与公开 ChatLogin 0.1.6 不一定包含这些页面和 API；稳定安装在匹配发布后再按正式版本约束采用。

用户管理复用原 Speakr 受邀账号登录。用户用同一个账号密码登录后，原 `meeting_session` Cookie 同时访问会议工作区、`/user-management/profile` 和按角色可见的 `/user-management/users`。不新增公开注册，不复制第二套用户库，也不迁移会议、对话、ASR、声音任务、API token 或访客 IndexedDB 数据。

## 入口

| 角色 | 页面 | 能做什么 |
| --- | --- | --- |
| OWNER | `/user-management/users`、`/user-management/profile` | 管理账号目录、创建/停用/删除用户、管理 admin、原子交接 owner、维护本人资料 |
| ADMIN | `/user-management/users`、`/user-management/profile` | 管理普通用户和本人资料；不能授予 admin 或接管 owner |
| USER | `/user-management/profile` | 查看/修改本人资料与密码 |

网页右上角 `•••` 设置菜单在 OWNER/ADMIN 登录后显示“管理员页面”，进入 `/user-management/users`；账号卡也显示“用户管理”。所有登录成员显示“个人账号”。原会议、录音、实时对话和会中助手导航保持业务权限检查。

## 数据保留与权限

- 原 `accounts.id` 继续作为稳定用户 ID，业务表 `owner_id` 不重写。
- 原账号名、显示名、密码 salt/hash 字节保留；旧密码不会被重新哈希。
- schema 初始化是显式、幂等、additive 的；旧账号默认 enabled `USER`，唯一 owner 由受信任 Python adoption 指定。
- 角色、状态、删除、改密和 owner 交接会递增 revision，使受影响会话失效。
- API token 遇到 disabled/deleted 账号会拒绝访问，但不会删除保留行。
- OWNER 是账号目录 owner，不是所有会议、录音或 token 的全读角色；宿主业务 ACL 仍必须检查记录归属。

## 配置

`CHATVOICE_PUBLIC_ORIGIN=https://voice.example.invalid` 是服务端 typed `ChatVoiceConfig` 读取的受信任固定 origin。它只表示浏览器实际访问的 scheme/host/port，不包含用户名密码、path、query 或 fragment，也不从请求 `Host`、代理头或 caller host 推导。

受邀账号仍通过现有 `chatvoice accounts add/list` 或等价受信任工具维护。唯一 owner 采用通过宿主 Python setup 调用匹配 ChatLogin provider 的 `adopt_owner(...)` 完成；不要发明或记录公开 owner CLI 命令。
