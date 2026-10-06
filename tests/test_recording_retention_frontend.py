"""Static contracts for the real meeting recording-retention UI."""

from pathlib import Path


INDEX = Path(__file__).resolve().parents[1] / "src" / "chatvoice" / "web" / "static" / "index.html"


def _source() -> str:
    return INDEX.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}")
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(name)


def test_meeting_ui_exposes_default_off_retention_and_truthful_audio_controls():
    source = _source()
    start = source.index('id="meeting-audio-controls"')
    controls = source[start:source.index('<div class="waveform-wrap">', start)]
    assert source.index('id="recording-console"') < start
    assert 'var(--recording-console-space' in source
    assert 'ResizeObserver' in source

    assert 'id="audio-retention-mode"' in controls
    assert '<option value="discard" selected>只做语音识别，不保存录音</option>' in controls
    assert '<option value="retain">保存原始录音</option>' in controls
    assert 'id="audio-retention-hint"' in controls
    assert "不能恢复此前未保存的音频" in controls
    assert 'id="meeting-audio-assets"' in controls
    assert "播放" in controls and "下载" in controls

    assert "audio-retention-mode').addEventListener('change'" in source
    assert "meeting-audio-assets').addEventListener('click'" in source
    save_body = _function_body(source, "saveActiveMeeting")
    assert "audio_retention: audioRetentionMode === 'retain'" in save_body
    open_body = _function_body(source, "openMeeting")
    assert "meeting.audio_retention" in open_body
    assert "renderMeetingAudioAssets(meeting.audio_assets || [])" in open_body


def test_no_save_path_has_no_media_recorder_buffer_and_active_mode_is_locked():
    source = _source()
    start_body = _function_body(source, "startRetainedAudioCapture")
    assert "audioRetentionMode !== 'retain'" in start_body
    assert "retainedRecorderChunks = []" in start_body
    assert start_body.index("audioRetentionMode !== 'retain'") < start_body.index("new MediaRecorder")

    update_body = _function_body(source, "updateAudioRetentionUi")
    assert "['connecting', 'recording', 'paused', 'finishing'].includes(recorderState)" in update_body
    assert "storageMode !== 'account'" in update_body
    assert "audio-retention-mode').disabled" in update_body
    set_body = _function_body(source, "setAudioRetentionMode")
    assert "不能恢复此前未保存的音频" in set_body
    assert "请先登录" in set_body


def test_retained_recorder_flushes_pause_and_tail_once_and_interrupt_discards():
    source = _source()
    pause_body = _function_body(source, "pauseRetainedAudioCapture")
    assert pause_body.index("requestData()") < pause_body.index("pause()")
    assert "retainedRecorder.state === 'recording'" in pause_body

    resume_body = _function_body(source, "resumeRetainedAudioCapture")
    assert "retainedRecorder.state === 'paused'" in resume_body
    assert "retainedRecorder.resume()" in resume_body

    finalize_body = _function_body(source, "finalizeRetainedAudioCapture")
    assert "retainedFinalizePromise" in finalize_body
    assert finalize_body.index("requestData()") < finalize_body.index("stop()")
    assert "ondataavailable" in finalize_body
    assert "onstop" in finalize_body
    assert "uploadRetainedMeetingAudio" in finalize_body

    discard_body = _function_body(source, "discardRetainedAudioCapture")
    assert "retainedRecordingEpoch += 1" in discard_body
    assert "retainedUploadController.abort()" in discard_body
    assert "retainedRecorderChunks = []" in discard_body
    interrupt_body = _function_body(source, "interruptActiveRecording")
    assert "discardRetainedAudioCapture" in interrupt_body
    error_body = _function_body(source, "handleAsrEvent")
    assert "discardRetainedAudioCapture" in error_body

