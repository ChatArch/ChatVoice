# 离线操作回归

## 常规入口

在独立开发环境安装项目的 `dev`、`web`、`docs` extras，并让 **Node.js 22 或更新版本**位于 `PATH`：

```sh
node --version
python -m pytest tests
```

不需要 Playwright、Chromium、浏览器、真实麦克风、模型服务或供应商凭据。Node 缺失或版本过旧会让控制器测试明确失败，而不是跳过。CI 为各 Python 测试任务配置 Node 22。

`tests/conftest.py` 在测试收集、应用导入之前，将 `HOME`、`CHATARCH_HOME`、`CHATVOICE_HOME` 指向专用临时目录，结束后恢复环境。临时目录遵循标准 `TMPDIR`；不要在生产运行环境安装测试依赖或运行验收。路由测试另外为每个用例分配 SQLite 文件。

快速执行操作矩阵：

```sh
python -m pytest tests/test_nonbrowser_flows.py tests/test_nonbrowser_routes.py -q
```

## 流程与测试映射

下列控制器名称对应 `test_nonbrowser_controller_flow` 的参数 ID；路由函数位于 `tests/test_nonbrowser_routes.py`。

| 操作 | 执行测试及断言 |
| --- | --- |
| 登录、退出、访客、会话失效、CSRF | `access-*` 执行登录表单和退出事件；`test_account_record_token_session_lifecycle` 通过真实 ASGI 验证登录失败、cookie、CSRF、退出、过期会话删除和两账户记录隔离。 |
| API Token 创建、使用、撤销、一次性明文 | `token` 执行创建、剪贴板和关闭设置事件；上述路由生命周期覆盖只返回一次的明文、Bearer 数据读取、撤销后 401。`test_api_tokens.py` 补充 scope 和过期边界。 |
| 开始、暂停、继续、结束录音 | `recording-{connecting,recording,paused,finishing}-{reset,new,delete}` 执行已注册事件，检查 socket、麦克风轨道、音频图、动画及计时器关闭和旧 ASR 回调失效；`asrFinish` 验证真实 ASR revision 合并、commit 确认、finish 后存储和摘要。 |
| 会议创建、保存、重开、标题、标签、搜索、复制、清空、删除 | `meeting`、`title-*`、`recording-*-reset` 执行真实控制器及持久化函数；隔离 IndexedDB 边界保存真实记录快照。账户存储由上述 ASGI 生命周期覆盖。 |
| 摘要、标题、SSE 修改、四个预设、撤销、画布编辑/复制 | `summary-*`、`title-*`、`revision-*`、`lateRevision` 验证内容、保存结果、busy/readOnly 恢复；HTTP 200 的 SSE error、缺少 done、空摘要和迟到结果不能覆盖原内容。`test_text_routes_finish_and_failure` 穿过真实路由及文本适配器，检查成功/错误/截断和响应关闭。 |
| 系统 TTS | `tts-*` 覆盖动态音色选择、MP3/WAV、短/长/空文本、音频 URL、下载扩展名、错误/超时/空音频释放 busy，以及配置缺失时的禁用说明。`test_tts_api.py`、`test_tts_qwen.py` 覆盖默认音色、协议、非法音频、截断及资源关闭；`test_tts_web.py` 覆盖 HTTP 分发和响应头。 |
| 一次性声音复刻 | `clone-*` 执行参考文件 change、录音 start/stop、登录/参考音频/授权前提、生成、定时轮询、下载、失败；覆盖提交/状态/音频请求迟到以及参考 URL 和轮询清理，刷新状态保留复刻选择；不创建音色历史。`test_clone_routes_lifecycle` 覆盖未登录、CSRF、空/过大/上游拒绝的音频、失败任务、下载及删除临时任务。 |
| 实时对话 | `realtime-*` 覆盖连接、输入 PCM、文本请求、转写合并、输出 PCM 排队、静音/恢复、结束、Markdown 导出、历史保存/重开/删除、连接和设备失败清理。`test_realtime_asgi_protocol_and_cleanup` 执行真实 WebSocket 路由，检查双向帧、文本/音频转换、`session.created` 转发、不支持的模型和上游连接失败。 |
| 导航、产品切换、设置、标签页、帮助链接 | `navigation` 执行真实切换和设置事件，检查面板 hidden、活动产品、录音期间切换限制、当前标签页、dialog 和外部链接目标属性；不以像素位置作断言。 |

## 测试边界

- Node VM 加载发布目录的完整内联控制器和 `transcript-state.js`，保留真实事件注册；仅省略页面末尾自动启动请求，并由用例显式调用入口。没有复制业务实现或替换 render、状态更新、保存函数。
- 小型 DOM、IndexedDB、fetch、WebSocket、MediaRecorder、AudioContext、剪贴板、对象 URL 和定时器是离线边界替身。断言包括真实内存状态、渲染结果、保存记录和下载描述，而不只是 mock 调用次数。异步结果使用有界条件屏障；定时轮询由测试显式推进。
- ASGI 测试保留路由匹配、请求校验、鉴权、序列化、SQL 和文本适配器，只替换设备/上游。为避免受限环境的线程通知阻塞，线程执行器及同步流迭代器在该 fixture 内顺序执行原函数/生成器；这不验证线程调度或并发性能。WebSocket 使用内存 ASGI 消息队列，不监听端口。
- `mutations` 在内存里分别删除 SSE error 分支、破坏下载扩展名选择，要求相同业务断言拒绝变异；不修改工作区。原有静态字符串合同测试仍保留，但不能算作操作流程覆盖。
- 不覆盖像素/布局、真实 DOM 引擎差异、浏览器 IndexedDB 事务调度、物理麦克风/权限、扬声器可听性、真实音频解码、真实供应商网络、账单或部署健康。参考录音只用合成 Blob；系统音频正确性由适配器边界测试补充。

## 显式真实验收门槛

仓库提供独立的非浏览器真实验收入口（需要开发环境中的 httpx、websockets 以及系统 ffmpeg/ffprobe）：

```sh
python scripts/verify_service.py --live \
  --url https://voice.example.com \
  --out <project>/playground/live-check \
  --asr-audio <synthetic-mono-pcm16-16khz.wav> \
  --realtime
```

默认验证实际部署的首页参数、标题、纪要、四个修改指令、全部音色×两格式、默认 TTS 文本与空文本拒绝。纪要修改要求 canvas/reply 标记各出现一次、顺序正确且两段均非空。TTS 要求 provider/model/voice 响应头与状态及请求一致、MIME 匹配请求格式，ffmpeg 解码成功，ffprobe 容器与编码符合 MP3 或 PCM16 WAV；回执记录实际身份和音频格式。此入口不启动浏览器，也不创建会议记录。

`--asr-audio` 从 `/api/asr/channels` 读取默认通道及 engine，在发送音频前拒绝 stub/mock。合成输入必须为非空、**最多三秒**的单声道 PCM16 16 kHz WAV，文件不超过 256,000 字节；更长输入明确不属于本次两段提交验收范围。ready/started 的 context 必须大于输入时长，避免自动窗口轮转。ready、started、result 的 channel 和 result.meta.engine 必须匹配配置。暂停和继续后的两段均须有独立、非空的 final 结果，窗口为 1、2，chunk/revision 递增，commit/finish 的 rollover 和 done 窗口正确；回执保留每段实际元数据，不再无条件宣称真实供应商调用。

`--realtime` 校验确认后的 model、voice、modalities、音频格式、指令、历史上限与 turn detection，仅允许一个已请求的活动 response，关联 created/done ID 和转发的上游 response 事件；必须明确返回 `completed` 且有非空文本与音频。缺少 ID 的派生事件只能在该单一活动 response 内接收，转发的上游事件仍须检查 ID。连接成功不算会话成功，这些传输证据也不是对上游供应商的独立认证。

可附加 `--clone-reference <synthetic.wav>` 验证真实复刻：先由管理员准备独立 `qa-verify-` 前缀的测试账号，将凭据注入 `CHATVOICE_VERIFY_ACCOUNT`、`CHATVOICE_VERIFY_PASSWORD`（或使用 `--account-env` / `--password-env` 指定变量名）。只删除本次创建且已结束的任务，并回读 404；退出后回读会话撤销。运行中任务超时会保留精确 job ID 供安全跟进，不扫删其他任务。管理员最终负责清理自己创建的测试账号。

`receipt.json` 逐项保存结果，任何失败、缺失或 BLOCKED 均非零退出；仅明确启用的可选流程列在 `selected_optional_flows`，不把未选择的项目当通过。不会自动重试供应商生成，不会改套餐/模型或启用按量后备。`--live` 会消耗现有配置对应的真实套餐资源；账单授权应在执行前明确。Token Plan 的 `AccessDenied.Unpurchased` 等错误是套餐/权限阻塞，不是网络就绪成功。

`test_live_acceptance_contract.py` 验证完整 SSE、空结果、目标 URL、清理 job ID 与退出码规则；`test_live_exchanges.py` 使用 HTTP/WebSocket 和 ffmpeg/ffprobe 进程边界替身执行真实 verifier，覆盖错误或缺失的身份、ASR 继续段结果归属、实时确认与 response 关联、标记错误和 Plan 拒绝。业务验证函数不替换，禁止真实 socket；进程替身不证明实际音频解码。`test_realtime_provider_errors.py` 执行平面供应商错误与 socket 关闭后提示保留的回归。

离线通过不证明真实服务可连通、账户套餐有效或音频可听。真实 HTTP/SSE/WebSocket 验收必须另行明确授权，使用受控环境与合成数据，不访问用户记录，并分别记录 `PASS`、`FAIL`、`BLOCKED`、`NOT_RUN`。不得把常规 pytest 自动升级为真实供应商探测，也不能以浏览器点击替代这套业务回归。

若沙箱中的旧 `TestClient` 用例阻塞，应保存具体用例、超时退出码和堆栈，报告全量验证受阻，再在获准环境重跑；不能将超时写为全量通过。
