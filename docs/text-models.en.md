# Independent Text Models

Notes, titles and speech are separate capabilities. Text uses an OpenAI-compatible Chat Completions interface and need not share a provider with ASR or TTS.

| Purpose | Configuration prefix | Use |
| --- | --- | --- |
| Notes | `CHATVOICE_MEETING_NOTES_` | Summaries, note refinement, Todo conversion/refinement |
| Titles | `CHATVOICE_MEETING_TITLE_` | Meeting titles |
| Speech | Separate TTS settings | Never supplies fallback text credentials |

## Configure complete triples

Set these in the ChatEnv `ChatVoice` namespace:

```dotenv
CHATVOICE_MEETING_NOTES_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_NOTES_API_KEY=[REDACTED]
CHATVOICE_MEETING_NOTES_MODEL=your-notes-model
CHATVOICE_MEETING_TITLE_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_TITLE_API_KEY=[REDACTED]
CHATVOICE_MEETING_TITLE_MODEL=your-title-model
```

Replace the placeholders. Both purposes may use the same provider, but each triple is explicit. A nonempty independent base or key enables that purpose's independent path. Incomplete settings fail instead of borrowing speech, other-purpose or global OpenAI credentials.

See [configuration](configuration.md) for profile import and activation.

## Verification order

```bash
chatenv test -t chatvoice -I
```

1. Summarize short synthetic text and verify final content, not reasoning alone.
2. Test the title independently; working notes do not establish title readiness.
3. Refine notes in the web app, then convert and refine a Todo.
4. Confirm source preservation, saving and restoration after refresh.

Connectivity tests call configured providers and consume their quota. Do not use private meeting content for production probes.

## Errors and boundaries

| State | Action |
| --- | --- |
| Configuration error / 503 | Check the complete purpose-specific triple |
| Upstream/output error / 502 | Inspect service logs, network and provider state; preserve content |
| Empty, truncated or reasoning-only output | Not a successful final document |
| Quota/permission failure | Stop; do not silently switch to pay-as-you-go endpoints |

Non-streaming text needs nonempty final content and explicit completion. Revision streams need a real terminal marker. Browser diagnostics expose sanitized state, never provider credentials.

[Markdown Todo](markdown-todo.md) · [HTTP API](api-access.md) · [Troubleshooting](troubleshooting.md)
