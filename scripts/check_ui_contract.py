#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML = PROJECT_ROOT / "app" / "static" / "index.html"
text = HTML.read_text(encoding="utf-8")

checks: dict[str, object] = {}

labels = re.findall(r'<button[^>]+class="tab-button[^>]*"[^>]*>(.*?)</button>', text, flags=re.S)
labels = [re.sub(r"<[^>]+>", "", x).strip() for x in labels]
checks["exact_tab_labels"] = labels == ["TTS", "realtime communication", "ASR transcription"]

panel_ids = re.findall(r'<section class="tab-panel(?: active)?" id="panel-([a-z]+)"', text)
checks["exact_three_panels"] = panel_ids == ["tts", "realtime", "asr"]

parts = re.split(r'<section class="tab-panel(?: active)?" id="panel-([a-z]+)"[^>]*>', text)
panels: dict[str, str] = {}
for i in range(1, len(parts), 2):
    name = parts[i]
    body = parts[i + 1].split('</section>', 1)[0]
    panels[name] = body
checks["panel_keys"] = set(panels) == {"tts", "realtime", "asr"}

# Tab content isolation: each function's controls/boards live only in its own panel.
checks["tts_only_has_voice_cloning"] = "voice-cloning-card" in panels.get("tts", "") and "voice-cloning-card" not in panels.get("realtime", "") + panels.get("asr", "")
checks["realtime_only_has_realtime_board"] = "realtime-board" in panels.get("realtime", "") and "realtime-board" not in panels.get("tts", "") + panels.get("asr", "")
checks["asr_only_has_asr_board"] = "asr-board" in panels.get("asr", "") and "asr-board" not in panels.get("tts", "") + panels.get("realtime", "")
checks["asr_only_has_meeting_notes"] = "meeting-notes-card" in panels.get("asr", "") and "meeting-notes-card" not in panels.get("tts", "") + panels.get("realtime", "")
checks["debug_log_inside_realtime_panel"] = 'id="log"' in panels.get("realtime", "") and 'id="log"' not in panels.get("tts", "") + panels.get("asr", "")

# Realtime UI contract: corrected/final is the only primary utterance. Raw text may be aside only.
checks["has_raw_aside_style"] = ".raw-aside" in text
checks["raw_aside_not_primary_text"] = "bubble.appendChild(raw)" in text and "原始识别" in text
checks["duplicate_regression_helper_present"] = "__demoInjectDuplicateScenario" in text
checks["duplicate_regression_uses_mismatched_ids"] = "item_dup_raw" in text and "item_dup_corrected" in text
checks["dedupe_merges_raw_corrected"] = "findSimilarRawTranscript" in text and "collapseFillerForCompare" in text

checks["debug_details_collapsed"] = '<details class="card span2 debug-details" open' not in text
checks["debug_developer_label"] = "开发者调试事件日志（默认折叠）" in text

checks["tts_voice_cloning_copy"] = "voice cloning" in panels.get("tts", "") and "VoiceEnrollmentService" not in panels.get("tts", "")
checks["asr_meeting_notes_copy"] = "AI polish" in panels.get("asr", "") and "realtime summary" in panels.get("asr", "")
checks["asr_stream_route_copy"] = "/ws/asr/stream" in panels.get("asr", "")

checks["ok"] = all(bool(v) for k, v in checks.items() if k != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
