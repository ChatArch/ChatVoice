# Voice Cloning Guide

This page documents the current **Generate Voice** unified panel in Speakr / ChatVoice Voice Studio: choose **System Voice** or **My Cloned Voice** (local VoiceClone sidecar + IndexTTS-2.5) in one panel, share the same text box, and generate a temporary preview audio.

## Current Scope

- One-shot voice cloning: reference audio + new text -> generated audio.
- Signed-in accounts only; guest mode cannot run cloning jobs.
- No reusable voice profile or voice id is saved.
- No generated-audio history is saved; generated files are temporary job artifacts for the current preview/download.
- Within one session, the uploaded reference audio is kept so you can change the text and regenerate with the same cloned voice until you leave the page.
- Meeting recording still does not save raw meeting audio. Voice cloning reference/output files are separate temporary task files.

## Browser Workflow

1. Open Speakr: <https://speakr.public.wzhecnu.cn/>.
2. Log in with an invited account.
3. Open the top **声音工作室 / Voice Studio** tab.
4. In **选择声音来源**, choose:
   - **系统音色** for built-in TTS voices (龙安灵心 / 龙安鲁风);
   - **我的复刻声音** for local cloning from your own reference audio.
   Both share the same text box. If the server has no model key, system voices show **未配置模型 Key，暂不可用** and the generate button is disabled; this does not affect the cloned voice.
5. For **我的复刻声音**, upload a clean 10-20 second single-speaker reference audio file, or record one from the browser.
6. Choose language and speed.
7. Check the authorization confirmation.
8. Enter the new text the cloned voice should speak in the shared text box.
9. Click **用复刻声音生成**.
10. Watch the progress bar, then play or download the generated audio in **试听结果**.
11. Optional: keep the source on **我的复刻声音**, change the text, and generate again without re-uploading the reference audio.

## Acceptance Criteria

A complete acceptance pass checks that:

- The unified panel shows **选择声音来源** (system voice / my cloned voice) sharing one text box.
- `/api/voice-clone/status` reports `configured=true`, `status=ready`, and `engine=indextts`.
- The selected reference filename is visible and marked as reusable for this session.
- Without a model key, system voices show a clear disabled state and `/api/tts` returns 503 (not 500).
- Missing login/reference/consent/text states produce clear toasts instead of silent no-ops.
- Clicking generate shows progress such as `generating`.
- Completion shows a browser audio player, `VoiceClone · indextts` metadata, file size, and a download button.
- Changing the text and generating again works without re-uploading the reference (the cloned voice is reusable in-session).
- The generated audio can be played.
- The browser console has no JavaScript errors.

## Verified hitk Public Acceptance

On 2026-08-22 the public page was accepted end-to-end (unified panel):

- Page: <https://speakr.public.wzhecnu.cn/?preview=voiceclone-unified-panel>
- Reference audio: `unified-reference.wav`, about 467 KB.
- System voice state: **未配置模型 Key，暂不可用**, generate disabled, `/api/tts` returned 503.
- Cloned voice flow: upload reference -> consent -> generate -> completed; changed text and generated a second time without re-uploading (about 390 KB).
- Playback: `readyState=4`, playable.
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
