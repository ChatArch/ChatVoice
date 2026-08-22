# Voice Cloning Guide

This page documents the current **Generate Voice** unified panel in Speakr / ChatVoice Voice Studio: system voices and **My Cloned Voice** are selectable in one voice-card list, share the same text box, and generate a temporary preview audio.

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
4. In **选择音色**, check one voice card:
   - **龙安灵心** / **龙安鲁风** for built-in system TTS voices;
   - **我的复刻声音** for local cloning from your own reference audio (the card shows the current reference status).
   All cards live in the same list and share the same text box. If the server has no model key, the page shows **系统音色未配置模型 Key…暂不可用** and disables system-voice generation; this does not affect **我的复刻声音**.
5. For **我的复刻声音**, upload a clean 10-20 second single-speaker reference audio file, or record one from the browser.
6. Choose language and speed.
7. Check the authorization confirmation.
8. Enter the new text the cloned voice should speak in the shared text box.
9. Click **用复刻声音生成**.
10. Watch the progress bar, then play or download the generated audio in **试听结果**.
11. Optional: keep the source on **我的复刻声音**, change the text, and generate again without re-uploading the reference audio.

## Acceptance Criteria

A complete acceptance pass checks that:

- The unified **选择音色** list contains system voices (龙安灵心 / 龙安鲁风) and **我的复刻声音** as selectable cards in one place, sharing one text box.
- `/api/voice-clone/status` reports `configured=true`, `status=ready`, and `engine=indextts`.
- The selected reference filename is visible on the cloned-voice card and marked as reusable for this session.
- Without a model key, system voices show a clear disabled state and `/api/tts` returns 503 (not 500).
- Missing login/reference/consent/text states produce clear toasts instead of silent no-ops.
- Clicking generate shows progress such as `generating`.
- Completion shows a browser audio player, `VoiceClone · indextts` metadata, file size, and a download button.
- Switching to a system voice and back to **我的复刻声音** keeps the reference; changing the text and generating again works without re-uploading (the cloned voice is reusable in-session).
- The generated audio can be played.
- The browser console has no JavaScript errors.

## Verified hitk Public Acceptance

On 2026-08-22 the public page was accepted end-to-end (unified panel):

- Page: <https://speakr.public.wzhecnu.cn/?preview=voiceclone-merged-selector>
- Reference audio: `merged-reference.wav`, about 467 KB.
- Voice list: 龙安灵心 / 龙安鲁风 / **我的复刻声音** selectable in one list.
- System voice state: no model key -> disabled with **系统音色未配置模型 Key…可改用“我的复刻声音”**; `/api/tts` returned 503.
- Cloned voice flow: check **我的复刻声音** -> upload reference -> consent -> generate -> completed; switched to 龙安灵心 and back without losing the reference, changed text and generated again (about 389 KB).
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
