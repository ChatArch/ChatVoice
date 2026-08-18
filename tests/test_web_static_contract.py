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
