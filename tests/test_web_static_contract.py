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
    assert ".value = ''" in clear_body
    assert ".hidden = true" in clear_body

    render_body = _function_body(source, "renderApiTokens")
    unauthenticated_branch = render_body.split("return;", 1)[0]
    assert "clearApiTokenOutput()" in unauthenticated_branch

    activate_body = _function_body(source, "activateStorageMode")
    assert "clearApiTokenOutput()" in activate_body


def test_one_time_api_token_value_is_cleared_when_settings_panel_closes_or_logout_starts():
    source = _script_source()

    assert re.search(r"settings-dialog'\)\.addEventListener\('close',\s*\(\) => clearApiTokenOutput\(\)", source)
    assert re.search(r"settings-dialog'\)\.addEventListener\('cancel',\s*\([^)]*\) => \{[^}]*clearApiTokenOutput\(\)", source, re.S)

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


def test_homepage_toolbar_uses_clear_left_menu_and_labeled_actions():
    source = _script_source()
    site_bar = source[source.index('<header class="site-bar">'):source.index('<section class="recorder-shell')]

    assert "brand-cluster" in site_bar
    assert "id=\"toggle-sidebar\"" in site_bar
    assert site_bar.index('id="toggle-sidebar"') < site_bar.index('class="brand"')
    assert "language-button" not in site_bar
    assert "设置/状态" in site_bar
    assert "复制" in site_bar
    assert '复制文字记录">•••' not in site_bar
    assert "aria-label=\"打开识别设置与服务状态\"" in site_bar
    assert "aria-label=\"复制文字记录\"" in site_bar


def test_raw_audio_archive_is_explicit_opt_in_and_local_only():
    source = _script_source()
    footer_markup = source[source.index('<footer class="recording-console'):source.index('</footer>', source.index('<footer class="recording-console'))]
    entry_markup = source[source.index('<dialog id="entry-dialog"'):source.index('<div class="toast"')]

    assert "默认不保存原始录音" in footer_markup
    assert "保存音频" in footer_markup
    assert "仅在本浏览器暂存" in footer_markup
    assert "原始录音默认不保存" in entry_markup
    assert "原始录音仍默认不上传服务器，也不自动留存在浏览器" in entry_markup
    assert "服务器默认不保存原始录音" in entry_markup

    assert "let archiveOptIn = false" in source
    capture_body = _function_body(source, "startMicrophoneCapture")
    assert "if (archiveOptIn) startArchiveRecording(microphoneStream)" in capture_body
    assert "startArchiveRecording(microphoneStream);" not in capture_body.replace("if (archiveOptIn) startArchiveRecording(microphoneStream);", "")

    assert "function handleArchiveButton" in source
    assert "download-recording').addEventListener('click', handleArchiveButton" in source
    archive_body = _function_body(source, "updateArchiveButton")
    assert "未保存音频" in archive_body
    assert "下载录音" in archive_body
    assert "服务器不保存原始录音" in archive_body
