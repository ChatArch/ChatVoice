# Voice Cloning Guide

This page documents the current **Local Clone · One-Shot Generation** workflow in Speakr / ChatVoice Voice Studio. It is backed by the VoiceClone sidecar on hitk and IndexTTS-2.5: upload or record a reference audio sample, enter new text, then generate a temporary cloned preview audio.

## Current Scope

- One-shot voice cloning: reference audio + new text -> generated audio.
- Signed-in accounts only; guest mode cannot run cloning jobs.
- No reusable voice profile or voice id is saved.
- No generated-audio history is saved; generated files are temporary job artifacts for the current preview/download.
- Meeting recording still does not save raw meeting audio. Voice cloning reference/output files are separate temporary task files.

## Browser Workflow

1. Open Speakr: <https://speakr.public.wzhecnu.cn/>.
2. Log in with an invited account.
3. Open the top **声音工作室 / Voice Studio** tab.
4. Enter the new text the cloned voice should speak in the main text box.
5. In **本地复刻 · 一次性生成**, upload a clean 10-20 second single-speaker reference audio file, or record one from the browser.
6. Choose language and speed.
7. Check the authorization confirmation.
8. Click **生成复刻试听**.
9. Watch the progress bar, then play or download the generated audio in **试听结果**.

## Acceptance Criteria

A complete acceptance pass checks that:

- `/api/voice-clone/status` reports `configured=true`, `status=ready`, and `engine=indextts`.
- The selected reference filename is visible in the clone card.
- Missing login/reference/consent/text states produce clear toasts instead of silent no-ops.
- Clicking generate shows progress such as `generating`.
- Completion shows a browser audio player, `VoiceClone · indextts` metadata, file size, and a download button.
- The generated audio can be played.
- The browser console has no JavaScript errors.

## Verified hitk Public Acceptance

On 2026-08-22 the public page was accepted end-to-end:

- Page: <https://speakr.public.wzhecnu.cn/?preview=voiceclone-acceptance-guide>
- Reference audio: `voice_01-reference.wav`, about 467 KB.
- Progress: `generating · 预计 45s`, around 45%.
- Result: `VoiceClone · indextts`, about 1.5 MB, about 35.5 seconds.
- Playback: `paused=false`, `readyState=4` after clicking play.
- Browser console: no JavaScript errors.

## Operations Check

```bash
curl -sS https://speakr.public.wzhecnu.cn/api/voice-clone/status | jq
```

Expected fields:

```json
{
  "configured": true,
  "status": "ready",
  "engine": "indextts",
  "model_version": "2.5",
  "device": "cuda:0",
  "model_loaded": true
}
```
