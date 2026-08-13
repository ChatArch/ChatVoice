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
checks["exact_tab_labels"] = labels == ["语音合成", "实时对话", "语音转写"]

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
checks["asr_only_has_live_text"] = "asr-live-text" in panels.get("asr", "") and "asr-live-text" not in panels.get("tts", "") + panels.get("realtime", "")
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

checks["tts_voice_cloning_copy"] = "声音克隆" in panels.get("tts", "") and "VoiceEnrollmentService" not in panels.get("tts", "")
asr_panel = panels.get("asr", "")
checks["asr_meeting_notes_copy"] = "会议纪要" in asr_panel and "智能润色" in asr_panel and "实时摘要" in asr_panel
checks["asr_stream_route_copy"] = "/ws/asr/stream" in text

# Realtime ASR product contract from user correction:
# one button starts/stops live transcription; speech appears automatically as text;
# no upload/record/manual segmentation controls are user-facing in the ASR tab.
checks["asr_has_one_button_realtime_surface"] = "asr-live-card" in asr_panel and "asr-live-toggle" in asr_panel and "开始实时转写" in asr_panel and "asr-live-text" in asr_panel
checks["asr_has_next_step_text_sink"] = "meeting-transcript" in asr_panel and "实时转写完成后会自动留下" in asr_panel
checks["asr_no_manual_segmentation_ui"] = all(x not in asr_panel for x in ("asr-stream-commit", "提交当前", "手动分段", "分片麦克风", "连接分片", "断开分片", "分片实时转写"))
checks["asr_no_upload_recording_ui"] = all(x not in asr_panel for x in ("asr-upload", "asr-record", "asr-send-recording", "上传音频", "开始录音", "识别上一次录音"))
checks["asr_live_updates_meeting_text"] = "renderAsrLiveText" in text and "asrLiveSegments" in text and "syncLiveTextToMeetingNotes" in text
checks["browser_no_manual_asr_commit"] = "asr.stream.commit" not in text

checks["ok"] = all(bool(v) for k, v in checks.items() if k != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
