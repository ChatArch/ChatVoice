#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from chatvoice.web import legacy_app as main  # noqa: E402

checks: dict[str, object] = {}
checks["title_model_follows_openai_api_model"] = main._meeting_title_model() == main._read_profile().get("OPENAI_API_MODEL")
checks["title_route_exists"] = any(getattr(route, "path", None) == "/api/meeting-title" for route in main.app.routes)
checks["title_prefix_is_removed"] = main._normalize_meeting_title("会议标题：《实时转写产品方案讨论》。") == "实时转写产品方案讨论"
checks["title_is_bounded"] = len(main._normalize_meeting_title("标题：" + "测试" * 30)) <= 28
checks["request_is_bounded"] = main.MeetingTitleRequest.model_fields["transcript"].metadata[1].max_length == 4000
checks["title_generation_disables_reasoning"] = '"enable_thinking": False' in Path(main.__file__).read_text(encoding="utf-8")
checks["ok"] = all(bool(value) for key, value in checks.items() if key != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
