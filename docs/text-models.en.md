# Independent notes and title models

Meeting notes and titles have independent OpenAI-compatible Chat Completions settings. Markdown Todo reuses the meeting-notes model without additional configuration.

Each purpose uses its own Base, sensitive Key and Model in ChatEnv's canonical `ChatVoice` provider:

```dotenv
CHATVOICE_MEETING_NOTES_API_BASE=https://ark.cn-beijing.volces.com/api/plan/v3
CHATVOICE_MEETING_NOTES_API_KEY=<your-Agent-Plan-key>
CHATVOICE_MEETING_NOTES_MODEL=doubao-seed-2.0-lite
CHATVOICE_MEETING_TITLE_API_BASE=https://ark.cn-beijing.volces.com/api/plan/v3
CHATVOICE_MEETING_TITLE_API_KEY=<your-Agent-Plan-key>
CHATVOICE_MEETING_TITLE_MODEL=doubao-seed-2.0-mini
```

Replace placeholders using secure stdin, never secret CLI arguments. Once either Base or Key is nonempty, all three fields for that purpose are required. Missing fields return HTTP 503 without borrowing voice, CRS, global OpenAI, or the other purpose's credentials. Empty Base and Key retain legacy behavior. Explicit independent settings take precedence over the legacy notes provider selector. The same key may be deliberately copied to both fields; there is no implicit sharing. Verify endpoint and model availability against your subscription; do not substitute a usage-billed endpoint.

## Validate before deployment

Keep validation secrets under managed ChatArch home, outside source trees:

```bash
chatenv --home "$CHATARCH_HOME/chatvoice/validation" paste --stdin -t chatvoice
chatenv --home "$CHATARCH_HOME/chatvoice/validation" test -t chatvoice -I
```

The test hook validates both boundaries before any request, then performs one synthetic request per configured purpose. Legacy-only profiles explicitly receive a schema-only result without network access. The hook does not import the web app, database or GPU models. `max_tokens` is an output parameter, not a hard reasoning-token or monetary budget.

Back up the old wheel, active ChatEnv profile and SQLite file. Install only the verified wheel without upgrading GPU dependencies, activate the complete configuration, and gracefully restart ChatVoice through its existing supervisor. Do not restart unrelated gateways. Roll back the wheel and config if acceptance fails; do not overwrite an unchanged database unnecessarily.

## Acceptance

`/api/status` exposes separate `meeting_notes` and `meeting_title` summaries containing provider, model, base_host, key_configured and configured, without keys or complete base URLs. The legacy `meeting_title_model` field remains.

Exercise real `POST /api/meeting-notes/polish`, `POST /api/meeting-title`, and `POST /api/meeting-notes/revise/stream` requests. The revision stream emits meta/delta/done events and the canvas protocol uses `[[[CANVAS]]]` and `[[[REPLY]]]`. HTTP errors, error objects inside HTTP 200, empty content, in-stream errors and incomplete streams must not become success. Error messages do not echo upstream bodies or credentials.

Click summary, title-refresh and revision controls on the public guest UI with a synthetic transcript; never replace model responses. Guest records remain in browser storage.

This hotfix does not repair an unavailable voice subscription or change Token Plan validation, ASR, TTS, realtime voice, or voice-cloning settings.
