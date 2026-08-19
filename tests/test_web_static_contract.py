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
