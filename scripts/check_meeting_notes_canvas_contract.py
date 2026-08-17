#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import main  # noqa: E402


class FakeUpstreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        chunks = (
            "[[[CANVAS]]]\n# 项目会议\n",
            "## 行动项\n- 王同学：周五前完成测试。\n",
            "[[[REPLY]]]\n已把行动项移到前面，并保留原有事实。",
        )
        for chunk in chunks:
            payload = {"choices": [{"delta": {"content": chunk}}]}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
        yield b"data: [DONE]\n\n"


captured: dict[str, object] = {}


def fake_urlopen(request, timeout=0):
    captured["timeout"] = timeout
    captured["payload"] = json.loads(request.data.decode("utf-8"))
    captured["authorization_present"] = bool(request.headers.get("Authorization"))
    return FakeUpstreamResponse()


main._token_plan_key = lambda: "contract-key"
main._token_plan_base = lambda: "https://example.invalid/v1"
main.urllib.request.urlopen = fake_urlopen

client = TestClient(main.app)
response = client.post(
    "/api/meeting-notes/revise/stream",
    json={
        "transcript": "王同学负责在周五前完成测试。",
        "current_summary": "# 项目会议\n王同学负责完成测试。",
        "instruction": "把行动项移到最前面。",
        "messages": [{"role": "user", "text": "请保持简洁。"}],
    },
)

payload = captured.get("payload", {})
messages = payload.get("messages", []) if isinstance(payload, dict) else []
checks = {
    "endpoint_streams_sse": response.status_code == 200 and response.headers.get("content-type", "").startswith("text/event-stream"),
    "canvas_and_reply_markers_are_forwarded": "[[[CANVAS]]]" in response.text and "[[[REPLY]]]" in response.text,
    "stream_has_lifecycle_events": all(f"event: {event}" in response.text for event in ("meta", "delta", "done")),
    "upstream_streaming_is_enabled": isinstance(payload, dict) and payload.get("stream") is True,
    "thinking_is_disabled": isinstance(payload, dict) and payload.get("enable_thinking") is False,
    "context_contains_transcript_summary_and_instruction": bool(messages)
    and all(
        marker in messages[-1].get("content", "")
        for marker in ("会议转写", "当前纪要画布", "本轮要求", "王同学负责在周五前完成测试", "把行动项移到最前面")
    ),
    "credential_stays_server_side": captured.get("authorization_present") is True,
}
checks["ok"] = all(checks.values())
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
