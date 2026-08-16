#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML = PROJECT_ROOT / "app" / "static" / "index.html"
text = HTML.read_text(encoding="utf-8")

checks: dict[str, object] = {}

checks["meeting_recorder_is_primary_surface"] = all(
    marker in text
    for marker in (
        'class="recorder-shell"',
        'id="meeting-title"',
        'id="recording-console"',
    )
)
checks["exact_product_tabs"] = (
    text.count('<button class="content-tab') == 2
    and 'id="transcript-tab"' in text
    and 'id="summary-tab"' in text
    and "文字记录" in text
    and "实时摘要" in text
)
checks["transcript_and_summary_panels_exist"] = all(
    marker in text
    for marker in ('id="transcript-panel"', 'id="summary-panel"', 'id="transcript-list"', 'id="summary-output"')
)
checks["recording_controls_exist"] = all(
    marker in text
    for marker in ('id="record-toggle"', 'id="finish-recording"', 'id="recording-waveform"', 'id="elapsed"')
)
checks["real_asr_websocket_is_used"] = "/ws/asr/stream" in text and "asr.stream.start" in text and "asr.stream.append" in text and "asr.stream.finish" in text
checks["browser_microphone_capture_exists"] = "navigator.mediaDevices.getUserMedia" in text and "createScriptProcessor" in text and "pcm" in text
checks["local_archive_recording_exists"] = "new MediaRecorder" in text and "download-recording" in text and "recordingUrl" in text
checks["recording_states_are_explicit"] = all(state in text for state in ("connecting", "recording", "paused", "finishing", "ended", "error"))
checks["asr_channel_is_server_driven"] = "/api/asr/channels" in text and 'id="asr-channel"' in text
checks["summary_endpoint_is_used"] = "/api/meeting-notes/polish" in text and 'id="generate-summary"' in text
checks["no_api_key_in_browser"] = all(name not in text for name in ("OPENAI_API_KEY", "DASHSCOPE_API_KEY", "Authorization: Bearer"))
checks["other_model_labs_are_not_primary_tabs"] = all(label not in text for label in ("语音合成</button>", "实时对话</button>", "语音转写</button>"))
checks["contract_helpers_exist"] = all(name in text for name in ("__demoInjectAsrScenario", "__demoInjectSummary", "__demoGetState"))
checks["permission_error_is_handled"] = "NotAllowedError" in text and "未获得麦克风权限" in text
checks["navigation_guard_exists"] = "beforeunload" in text

checks["ok"] = all(bool(value) for key, value in checks.items() if key != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
