import re
from pathlib import Path


STATIC_INDEX = Path(__file__).resolve().parents[1] / "src" / "chatvoice" / "web" / "static" / "index.html"


def _script_source() -> str:
    return STATIC_INDEX.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(f"function {name} body not found")


def test_one_time_api_token_value_is_cleared_on_unauthenticated_render_and_mode_switch():
    source = _script_source()
    assert "function clearApiTokenOutput" in source

    clear_body = _function_body(source, "clearApiTokenOutput")
    assert "api-token-output" in clear_body
    assert ".textContent = ''" in clear_body
    assert "api-token-result').hidden = true" in clear_body

    render_body = _function_body(source, "renderApiTokens")
    unauthenticated_branch = render_body.split("return;", 1)[0]
    assert "clearApiTokenOutput()" in unauthenticated_branch

    activate_body = _function_body(source, "activateStorageMode")
    assert "clearApiTokenOutput()" in activate_body


def test_one_time_api_token_value_is_cleared_when_settings_panel_closes_or_logout_starts():
    source = _script_source()

    assert re.search(r"settings-dialog'\)\.addEventListener\('close',\s*\(\) => closeTokenCreatePopover\(\)", source)
    assert re.search(r"settings-dialog'\)\.addEventListener\('cancel',\s*\([^)]*\) => \{[^}]*closeTokenCreatePopover\(\)", source, re.S)

    logout_body = _function_body(source, "handleAccountAction")
    assert "clearApiTokenOutput()" in logout_body


def test_settings_panel_surfaces_server_side_api_key_status_without_browser_secret_inputs():
    source = _script_source()
    settings_markup = source[source.index('<dialog id="settings-dialog">'):source.index('<dialog id="entry-dialog"')]

    assert "api-key-config-title" in settings_markup
    assert "服务端 API Key" in settings_markup
    assert "CHATVOICE_ASR_API_KEY" in settings_markup
    assert "DASHSCOPE_API_KEY" in settings_markup
    assert "api-key-status-list" in settings_markup
    assert "type=\"password\"" not in settings_markup

    assert "function renderServerKeyStatus" in source
    status_body = _function_body(source, "renderServerKeyStatus")
    assert "api_keys" in status_body
    assert "asr_api_key_configured" in status_body
    assert "model_api_key_configured" in status_body
    assert "voice_cloning_key_configured" in status_body

    refresh_body = _function_body(source, "refreshStatus")
    assert "renderServerKeyStatus" in refresh_body


def test_settings_panel_and_recorder_surface_asr_heartbeat_state():
    source = _script_source()
    settings_markup = source[source.index('<dialog id="settings-dialog">'):source.index('<dialog id="entry-dialog"')]

    assert "识别服务心跳" in settings_markup
    assert "asr-health-status-list" in settings_markup
    assert "asr-health-message" in settings_markup
    assert "function renderAsrHealthStatus" in source
    assert "function refreshHeartbeat" in source
    assert "'/api/heartbeat'" in source

    refresh_body = _function_body(source, "refreshStatus")
    assert "refreshHeartbeat" in refresh_body
    assert "renderAsrHealthStatus" in refresh_body

    handler_body = _function_body(source, "handleAsrEvent")
    assert "asr.stream.processing" in handler_body
    assert "asr.stream.heartbeat" in handler_body
    assert "首次加载模型中" in handler_body
    assert "识别处理中" in handler_body


def test_pause_commits_current_asr_window_before_resume():
    source = _script_source()

    request_body = _function_body(source, "requestAsrWindowCommit")
    assert "allowPaused" in request_body
    assert "reason === 'pause'" in request_body
    assert "asr.stream.commit" in request_body

    pause_body = _function_body(source, "pauseRecording")
    assert "requestAsrWindowCommit({ reason: 'pause', allowPaused: true })" in pause_body
    assert "正在整理刚才的转写" in pause_body

    handler_body = _function_body(source, "handleAsrEvent")
    assert "pauseCommitPending" in handler_body
    assert "暂停前文字已确认" in handler_body
    assert "beginTranscriptPass()" in handler_body


def test_title_refresh_quick_new_and_reset_confirmation_are_exposed():
    source = _script_source()
    header_markup = source[source.index('<header class="meeting-header">'):source.index('<nav class="content-tabs"')]

    assert "id=\"refresh-title\"" in header_markup
    assert "刷新标题" in header_markup
    assert "id=\"quick-new-meeting\"" in header_markup
    assert "新建" in header_markup

    assert "function refreshMeetingTitle" in source
    refresh_title_body = _function_body(source, "refreshMeetingTitle")
    assert "summaryContent" in refresh_title_body
    assert "generateMeetingTitle(context, { force: true, explicit: true })" in refresh_title_body

    assert "function requestResetSession" in source
    reset_body = _function_body(source, "requestResetSession")
    assert "confirm(" in reset_body
    assert "确定清空这一次录音/会议内容吗" in reset_body
    assert "resetSession()" in reset_body

    assert "refresh-title').addEventListener('click', refreshMeetingTitle" in source
    assert "quick-new-meeting').addEventListener('click', () => createNewMeeting()" in source
    assert "reset-recording').addEventListener('click', requestResetSession" in source


def test_homepage_toolbar_uses_left_history_menu_and_right_settings_menu_only():
    source = _script_source()
    site_bar = source[source.index('<header class="site-bar">'):source.index('<section class="recorder-shell')]
    transcript_panel = source[source.index('<section class="tab-panel active" id="transcript-panel"'):source.index('<section class="tab-panel" id="summary-panel"')]
    toolbar_css = source[source.index(".toolbar-menu {"):source.index(".settings-icon {")]

    assert "brand-cluster" in site_bar
    assert "id=\"toggle-sidebar\"" in site_bar
    assert site_bar.index('id="toggle-sidebar"') < site_bar.index('class="brand"')
    assert "product-tabs" in site_bar
    assert "product-tab active" in site_bar
    assert "id=\"meeting-product-tab\"" in site_bar
    assert "id=\"studio-product-tab\"" in site_bar
    assert "id=\"conversation-product-tab\"" in site_bar
    assert "workspace-label" not in site_bar
    assert "language-button" not in site_bar
    assert "id=\"toggle-settings-menu\"" in site_bar
    assert ">•••</button>" in site_bar
    assert "id=\"settings-menu\"" in site_bar
    assert "toolbar-menu-list" in site_bar
    assert "打开设置，包含识别状态、模型和 API Token" in site_bar
    assert "<b>设置</b>" in site_bar
    assert "product-menu-action" not in site_bar
    assert "open-model-status" not in site_bar
    assert "open-token-settings" not in site_bar
    assert site_bar.count("data-settings-focus=") == 1
    assert "https://arch.gh.wzhecnu.cn/ChatVoice/" in site_bar
    assert "https://github.com/ChatArch/ChatVoice" in site_bar
    assert "id=\"copy-transcript\"" not in site_bar
    assert "复制文字记录" not in site_bar
    assert "id=\"copy-transcript\"" in transcript_panel
    assert "复制文字" in transcript_panel

    assert "function toggleSettingsMenu" in source
    assert "function openSettingsDialog" in source
    assert ".site-bar {" in source and "z-index: 80" in source
    assert ".toolbar-menu" in source and "z-index: 120" in source
    assert "width: max-content" in toolbar_css
    assert "min-width: 128px" in toolbar_css
    assert "width: 156px" not in toolbar_css
    assert "width: 228px" not in toolbar_css
    assert "width: min(246px" not in source
    assert ".toolbar-menu-list { display: grid; grid-template-columns: 1fr" in toolbar_css
    assert "grid-template-columns: 26px max-content" in toolbar_css
    assert "grid-template-columns: repeat(3" not in toolbar_css
    assert "querySelectorAll('.product-menu-action').forEach" not in source
    assert "querySelectorAll('.product-tab').forEach" in source
    assert "addEventListener('click', () => switchProductView" in source
    switch_body = _function_body(source, "switchProductView")
    assert "workspace-title" not in switch_body
    assert "product-menu-action" not in switch_body
    assert "aria-selected" in switch_body
    assert "aria-checked" not in switch_body
    assert "toggle-settings-menu').addEventListener('pointerdown'" in source
    assert "toggle-settings-menu').addEventListener('click'" in source
    assert "settings-menu').addEventListener('click'" in source
    assert "copy-transcript').addEventListener('click', copyTranscriptText" in source


def test_title_action_buttons_are_icon_only_to_keep_title_row_compact():
    source = _script_source()
    title_actions = source[source.index('<div class="meeting-title-actions"'):source.index('</div>', source.index('<div class="meeting-title-actions"'))]

    assert "id=\"refresh-title\"" in title_actions
    assert "icon-only" in title_actions
    assert "aria-label=\"刷新标题\"" in title_actions
    assert "title=\"刷新标题\"" in title_actions
    assert "<strong>刷新标题</strong>" not in title_actions
    assert "<span aria-hidden=\"true\">↻</span>" in title_actions
    assert "id=\"quick-new-meeting\"" in title_actions
    assert "class=\"title-action-button icon-only primary\"" in title_actions
    assert "aria-label=\"新建会议\"" in title_actions
    assert "title=\"新建会议\"" in title_actions
    assert "<strong>新建</strong>" not in title_actions
    assert "<span aria-hidden=\"true\">＋</span>" in title_actions

    title_mode_body = _function_body(source, "setMeetingTitleMode")
    assert "refreshButton.setAttribute('aria-label'" in title_mode_body
    assert "refreshButton.title" in title_mode_body
    assert "refresh-title').textContent" not in source
    assert "refreshButton.textContent" not in title_mode_body
    assert "textContent = mode === 'generating'" not in title_mode_body

    css_block = source[source.index(".title-action-button.icon-only") : source.index(".title-action-button.primary")]
    assert "max-width: 34px" in css_block
    assert "position: relative" in css_block
    assert ".title-action-button.icon-only strong { display: none; }" in css_block
    assert ".title-action-button.icon-only::after" in css_block
    assert "content: attr(aria-label)" in css_block
    assert ".title-action-button.icon-only:hover::after" in css_block
    assert ".title-action-button.icon-only:focus::after" in css_block
    assert ".title-action-button.icon-only:focus-visible::after" in css_block
    assert "@media (hover: none)" in css_block


def test_raw_audio_archive_is_not_offered_in_meeting_recorder():
    source = _script_source()
    footer_markup = source[source.index('<footer class="recording-console'):source.index('</footer>', source.index('<footer class="recording-console'))]
    entry_markup = source[source.index('<dialog id="entry-dialog"'):source.index('<div class="toast"')]

    assert "默认不保存" not in footer_markup
    assert "默认不保存" not in entry_markup
    assert "服务器不保存录音，只保存文本和摘要" in entry_markup
    assert "服务器只保存文字和摘要" in footer_markup
    assert "服务器不保存录音" in entry_markup
    assert "音频只用于实时识别" in entry_markup

    forbidden = [
        "保存到本机",
        "下载音频",
        "下载本机音频",
        "download-recording",
        "MediaRecorder",
        "AUDIO_DB_NAME",
        "recording-chunks",
        "archiveOptIn",
        "startArchiveRecording",
        "handleArchiveButton",
        "updateArchiveButton",
    ]
    for marker in forbidden:
        assert marker not in source

    capture_body = _function_body(source, "startMicrophoneCapture")
    assert "asr.stream.append" in capture_body
    assert "MediaRecorder" not in capture_body


def test_api_token_management_uses_one_time_key_modal_pattern():
    source = _script_source()
    token_panel = source[source.index('<section class="token-panel"'):source.index('</section>', source.index('<section class="token-panel"'))]

    assert "id=\"open-token-create\"" in token_panel
    assert "新建 Token" in token_panel
    assert "id=\"token-create-popover\"" in token_panel
    assert "配置名称和有效期后生成" in token_panel
    assert "生成后会自动复制" in token_panel
    assert "关闭后不能再复制" in token_panel
    assert "id=\"api-token-expires\"" in token_panel
    assert "<select id=\"api-token-expires\">" in token_panel
    assert "7 天" in token_panel
    assert "15 天" in token_panel
    assert "30 天" in token_panel
    assert "90 天" in token_panel
    assert "永久" in token_panel
    assert "365" not in token_panel
    assert "id=\"api-token-result\"" in token_panel
    assert "<code id=\"api-token-output\"></code>" in token_panel
    assert "textarea" not in token_panel
    assert "生成 Token" in token_panel
    assert "id=\"copy-api-token\"" in token_panel
    assert "masked key" in token_panel

    render_body = _function_body(source, "renderApiTokens")
    assert "filter((token) => !token.revoked_at)" in render_body
    assert "token-mask" in render_body
    assert "maskApiToken(token)" in render_body
    assert ">删除</button>" in render_body
    assert "已撤销" not in render_body
    assert ">撤销</button>" not in render_body

    create_body = _function_body(source, "createApiToken")
    assert "api-token-result').hidden = false" in create_body
    assert "api-token-output').textContent = payload.token" in create_body
    assert "copyApiTokenOutput()" in create_body
    assert "关闭新建弹窗后无法再次查看明文" in create_body

    clear_body = _function_body(source, "clearApiTokenOutput")
    assert "api-token-output').textContent = ''" in clear_body
    assert "api-token-result').hidden = true" in clear_body

    revoke_body = _function_body(source, "revokeApiToken")
    assert "删除这个 API Token" in revoke_body
    assert "Token 已删除" in revoke_body
    assert "撤销" not in revoke_body

    assert "open-token-create').addEventListener('click', openTokenCreatePopover" in source
    assert "copy-api-token').addEventListener('click', copyApiTokenOutput" in source
    assert "close-token-create').addEventListener('click', closeTokenCreatePopover" in source


def test_logged_in_recording_has_no_frontend_duration_cap():
    source = _script_source()

    assert "登录账号 · 单段" not in source
    assert "2 * 60 * 60" not in source
    assert "访客使用 · 单段 10 分钟" in source
    assert "访客试用 · 本段剩余" in source
    assert "policy.hidden = !guestMode" in source

    timer_body = _function_body(source, "startTimer")
    assert "storageMode === 'guest' && recordingPassSeconds >= asrPassLimitSeconds" in timer_body
    assert "访客试用已达到 10 分钟" in timer_body
