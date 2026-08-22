#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from chatvoice.web.legacy_app import extract_realtime_transcript_events

CASES = [
    (
        {"type": "conversation.item.input_audio_transcription.completed", "transcript": "我想测试实时转写。", "item_id": "item_user"},
        {"role": "user", "phase": "final", "text": "我想测试实时转写。"},
    ),
    (
        {"type": "response.audio_transcript.delta", "delta": "你好，"},
        {"role": "assistant", "phase": "delta", "text": "你好，"},
    ),
    (
        {"type": "response.audio_transcript.done", "transcript": "你好，我收到了。"},
        {"role": "assistant", "phase": "final", "text": "你好，我收到了。"},
    ),
    (
        {"type": "conversation.item.ambient_audio_transcription.delta", "text": "嗯"},
        {"role": "ambient", "phase": "delta", "text": "嗯"},
    ),
    (
        {"type": "conversation.item.created", "item": {"id": "item_x", "role": "assistant", "content": [{"type": "audio", "transcript": "补充文本"}]}},
        {"role": "assistant", "phase": "final", "text": "补充文本"},
    ),
]

result = []
for event, expected in CASES:
    out = extract_realtime_transcript_events(event)
    assert out, event
    got = out[0]
    for key, value in expected.items():
        assert got.get(key) == value, {"event": event, "expected": expected, "got": got}
    result.append({"source": event["type"], "normalized": {k: got[k] for k in ("role", "phase", "text", "source_type")}})

assert extract_realtime_transcript_events({"type": "session.updated", "session": {}}) == []
main_source = (PROJECT_ROOT / "src" / "chatvoice" / "web" / "legacy_app.py").read_text(encoding="utf-8")
assert '"demo_event": "audio.delta"' in main_source
assert '"sample_rate": 24000' in main_source
assert "MAX_ASR_STREAM_JSON_FRAME_BYTES" in main_source
print(json.dumps({"ok": True, "cases": result, "audio_delta_proxy": True, "frame_limits": True}, ensure_ascii=False, indent=2))
