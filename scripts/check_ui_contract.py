#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML = PROJECT_ROOT / "src" / "chatvoice" / "web" / "static" / "index.html"
text = HTML.read_text(encoding="utf-8")

checks: dict[str, object] = {}

checks["meeting_recorder_is_primary_surface"] = all(
    marker in text
    for marker in (
        'id="recorder-shell"',
        'id="meeting-title"',
        'id="recording-console"',
    )
)
checks["exact_product_tabs"] = (
    text.count('<button class="content-tab') == 3
    and 'id="transcript-tab"' in text
    and 'id="summary-tab"' in text
    and 'id="summary-chat-tab"' in text
    and "文字记录" in text
    and "实时摘要" in text
    and "完善纪要" in text
)
checks["top_level_workspaces_exist"] = (
    text.count('<button class="product-tab') == 3
    and 'id="meeting-product-tab"' in text
    and 'id="studio-product-tab"' in text
    and 'id="conversation-product-tab"' in text
    and 'data-product-view="meeting"' in text
    and 'data-product-view="studio"' in text
    and 'data-product-view="conversation"' in text
)
checks["voice_studio_tts_is_wired"] = all(
    marker in text
    for marker in ('id="tts-text"', 'id="voice-options"', 'id="synthesize-voice"', "fetch('/api/tts'", 'id="tts-audio"', 'id="download-voice"')
)
checks["voice_clone_is_configuration_aware"] = all(
    marker in text
    for marker in ('id="clone-capability"', 'id="clone-voice-card"', "voiceCloningConfigured", "fetch('/api/voice-clone/jobs'", "CHATVOICE_VOICECLONE_URL")
)
checks["token_plan_key_status_is_openai_compatible"] = all(
    marker in text
    for marker in ("OPENAI_API_KEY", "sk-sp", "model_api_key_is_token_plan")
) and "DASHSCOPE_API_KEY" not in text
checks["studio_switch_guards_active_recording"] = (
    "请先结束当前录音，再切换功能" in text
    and "['connecting', 'recording', 'paused', 'finishing'].includes(recorderState)" in text
)
checks["realtime_conversation_page_exists"] = all(
    marker in text
    for marker in ('id="realtime-chat"', 'id="conversation-messages"', 'id="conversation-main"', 'id="conversation-mute"', 'id="conversation-end"')
)
checks["realtime_conversation_audio_is_wired"] = all(
    marker in text
    for marker in ("/ws/realtime", "input_audio_buffer.append", "payload.demo_event === 'audio.delta'", "createBuffer(1, sampleCount, sampleRate)")
)
checks["realtime_conversation_supports_barge_in"] = all(
    marker in text
    for marker in ("input_audio_buffer.speech_started", "stopRealtimePlayback(false)", "type: 'response.cancel'")
)
checks["realtime_conversation_has_privacy_boundary"] = "声笺不保存对话音频" in text
checks["realtime_model_selector_is_server_driven"] = all(
    marker in text for marker in ('id="conversation-model"', "fetch('/api/realtime/models'", "model=${encodeURIComponent(realtimeModel)}")
)
checks["realtime_conversation_history_is_wired"] = all(
    marker in text
    for marker in ("GUEST_CONVERSATION_STORE", "fetch('/api/conversations')", "function createNewConversation", "function openConversation", "function deleteConversationRecord")
)
checks["realtime_conversation_can_export"] = all(
    marker in text for marker in ('id="conversation-export"', "function exportCurrentConversation", "text/markdown;charset=utf-8")
)
checks["user_turn_is_reserved_before_response"] = (
    "function ensureUserRealtimeDraft" in text
    and text.index("ensureUserRealtimeDraft();", text.index("input_audio_buffer.speech_started")) < text.index("response.created", text.index("input_audio_buffer.speech_started"))
)
checks["transcript_and_summary_panels_exist"] = all(
    marker in text
    for marker in ('id="transcript-panel"', 'id="summary-panel"', 'id="transcript-list"', 'id="summary-output"')
)
checks["recording_controls_exist"] = all(
    marker in text
    for marker in ('id="record-toggle"', 'id="finish-recording"', 'id="reset-recording"', 'id="recording-waveform"', 'id="elapsed"')
)
checks["idle_waveform_is_flat"] = "waveform-placeholder::before" in text and "getByteTimeDomainData" in text and "const silent = rms" in text
checks["new_recording_can_be_cleared"] = "function resetSession" in text and "内容已清空，可以开始新录音" in text
checks["finish_waits_for_gpu_result"] = "}, 90000);" in text and "}, 5000);" not in text
checks["transcript_revision_is_supported"] = all(marker in text for marker in ("function applyTranscriptRevision", "revision_scope", "已回写第", "回写中"))
checks["waveform_is_damped"] = "height * .38" in text and "previous * .76 + target * .24" in text
checks["real_asr_websocket_is_used"] = "/ws/asr/stream" in text and "asr.stream.start" in text and "asr.stream.append" in text and "asr.stream.finish" in text
checks["browser_microphone_capture_exists"] = "navigator.mediaDevices.getUserMedia" in text and "createScriptProcessor" in text and "pcm" in text
checks["recording_audio_is_not_persisted"] = "服务器不保存录音" in text and 'id="download-recording"' not in text and "recordingUrl" not in text
checks["recording_states_are_explicit"] = all(state in text for state in ("connecting", "recording", "paused", "finishing", "ended", "error"))
checks["asr_channel_is_server_driven"] = "/api/asr/channels" in text and 'id="asr-channel"' in text
checks["summary_endpoint_is_used"] = "/api/meeting-notes/polish" in text and 'id="generate-summary"' in text
checks["summary_canvas_chat_is_wired"] = all(
    marker in text
    for marker in (
        'id="summary-canvas"',
        'id="summary-chat-messages"',
        'id="summary-chat-form"',
        "/api/meeting-notes/revise/stream",
        "function parseSummaryRevisionOutput",
        "summary_chat_messages",
        "summary_customized",
    )
)
checks["customized_summary_is_not_auto_overwritten"] = all(
    marker in text
    for marker in (
        "if (summaryCustomized && !explicit) return;",
        "if (transcriptText() && (!summaryCustomized || !hasGeneratedSummary)) generateSummary();",
        "继续录音不会自动覆盖",
    )
)
checks["meeting_title_is_auto_generated"] = all(
    marker in text
    for marker in ('id="title-state"', "fetch('/api/meeting-title'", "function maybeGenerateMeetingTitle", "AI 已命名")
)
checks["manual_title_has_priority"] = all(
    marker in text
    for marker in ("function markMeetingTitleManual", "meetingTitleMode === 'manual'", "titleAbortController.abort()")
)
checks["no_raw_api_key_in_browser"] = all(marker not in text for marker in ("Authorization: Bearer", "sk-sp-", "OPENAI_API_KEY=", "OPENAI_API_KEY ="))
checks["legacy_model_labs_are_not_primary_tabs"] = "语音转写</button>" not in text
checks["contract_helpers_exist"] = all(name in text for name in ("__demoInjectAsrScenario", "__demoInjectSummary", "__demoGetState"))
checks["permission_error_is_handled"] = "NotAllowedError" in text and "未获得麦克风权限" in text
checks["navigation_guard_exists"] = "beforeunload" in text
checks["meeting_sidebar_exists"] = all(marker in text for marker in ('id="meeting-sidebar"', 'id="new-meeting"', 'id="meeting-search"', 'id="meeting-groups"'))
checks["guest_storage_is_browser_only"] = "indexedDB.open" in text and "GUEST_STORE" in text and "X-Client-Id" not in text
checks["account_mode_is_available"] = all(marker in text for marker in ('id="entry-dialog"', "fetch('/api/auth/login'", "/api/auth/session", "/api/auth/logout"))
checks["self_registration_is_not_offered"] = all(
    marker in text for marker in ("仅限受邀账号使用", "不开放自行注册", "fetch('/api/auth/login'")
) and all(marker not in text for marker in ('data-auth-mode="register"', "创建账号并同步", "/api/auth/${authMode}"))
checks["summary_reset_cancels_stale_request"] = all(marker in text for marker in ("summaryAbortController.abort()", "requestEpoch !== contentEpoch", "persist = true"))
checks["transcript_has_three_stable_zones"] = all(
    marker in text
    for marker in ('id="history-label"', 'id="rewrite-region"', 'id="rewrite-list"', 'id="live-region"', "visibleTranscriptSegments")
)
checks["confirmed_transcript_is_monotonic"] = all(
    marker in text for marker in ("window.TranscriptState.planRevision", "transcriptSegments.push", "识别回退，已保留上一版")
)
pause_block = text.split("function pauseRecording()", 1)[1].split("function resumeRecording()", 1)[0]
checks["pause_preserves_transcript"] = all(marker in pause_block for marker in ("updateRecorderUi('paused'", "requestAsrWindowCommit({ reason: 'pause', allowPaused: true })", "scheduleMeetingSave(0)")) and all(
    marker not in pause_block for marker in ("resetSession(", "transcriptSegments = []")
)
checks["ended_recording_can_continue_same_meeting"] = all(
    marker in text for marker in ("const continuingMeeting", "beginTranscriptPass();", "正在继续当前会议", "'继续录音'")
)
checks["finishing_preserves_live_text"] = "['recording', 'connecting', 'paused', 'finishing'].includes(recorderState)" in text and "settlePendingTranscript()" in text
checks["recording_limits_are_explicit"] = all(
    marker in text for marker in ('id="record-limit-status"', 'id="record-limit-remaining"', "访客试用 · 每段最长 10 分钟", "payload.max_connection_seconds", "channelsData.stream_policy")
)
checks["pause_does_not_consume_pass_time"] = "if (recorderState !== 'recording') return;\n        elapsedSeconds += 1;\n        recordingPassSeconds += 1;" in text
checks["long_meeting_rollover_is_wired"] = all(
    marker in text for marker in ("function requestAsrWindowCommit", "asr.stream.commit", "recordingPassSeconds - lastAsrWindowCommitAt >= 42", "长会议窗口已无感衔接")
)
checks["server_policy_controls_frontend_limit"] = all(
    marker in text for marker in ("payload.max_connection_seconds", "channelsData.stream_policy", "recordingPassSeconds >= asrPassLimitSeconds")
)
checks["long_recording_uses_stream_windows_not_audio_archive"] = all(
    marker in text for marker in ("function requestAsrWindowCommit", "recordingPassSeconds - lastAsrWindowCommitAt >= 42", "长会议窗口已无感衔接")
) and "downloadCurrentArchive" not in text
checks["audio_archive_is_not_persisted"] = all(marker in text for marker in ("服务器不保存录音", "音频只用于实时识别"))

checks["ok"] = all(bool(value) for key, value in checks.items() if key != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
