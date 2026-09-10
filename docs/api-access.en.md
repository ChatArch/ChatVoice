# API Access

Sign in to ChatVoice with an invited account, create an API token, then read your meetings and conversations through data endpoints or `chatvoice data`.

## Login Backend and Frontend Boundary

ChatVoice directly uses the built-in `ChatVoiceAuth` backend from `ChatLogin>=0.1.2,<0.2.0`, retaining the existing account/session schema, IDs and password material. `/login` renders shared LoginUI templates and assets with host CSS branding; business pages and guest IndexedDB remain unchanged.

Existing `/api/auth/*` routes, JSON fields and cookie contracts remain compatible. Existing accounts map to ordinary users, not a new Web Admin. ChatVoice retains resource ownership and API-token scopes; guest IndexedDB records are not automatically uploaded. A package release is not a production restart or data migration.

## Customize the shared login page

The default `/login` uses host-owned monochrome branding. Supply a `LoginUI` from your Python entrypoint to select another theme or trusted host template without editing site-packages:

```python
from chatlogin.ui import LoginUI
from chatvoice.web import create_app

app = create_app(login_ui=LoginUI(
    title="My voice workspace", palette="forest", layout="split",
    appearance="system", guest_url="/?mode=guest",
))
```

Guest drafts are saved before entering login; active recordings and realtime conversations prevent navigation. The shared form submits `username`, while existing `account` clients remain supported. Returned `next` values are constrained to safe local paths. Passwords, sessions and CSRF values are not saved in browser persistent storage.

## Access model

System speech supports [independent TTS protocols](tts-models.en.md). `POST /api/tts` still accepts text, optional voice and mp3/wav; the first configured voice is default, with `X-TTS-Provider/Model/Voice` response headers. `GET /api/status` adds a safe `tts` object. Invalid configuration returns 503; upstream failures return fixed sanitized 502 errors. Data access, authentication and clone APIs are unchanged.

| Entry | Credential | Purpose |
| --- | --- | --- |
| Browser login | HttpOnly session cookie + CSRF | Save meetings/conversations and manage API tokens |
| Browser voice cloning | HttpOnly session cookie + CSRF | Authorized reference audio and one-shot VoiceClone jobs |
| Data API token | Bearer authentication scheme | Scoped automation reads of the owner's text/tags/summaries |
| Guest mode | Browser IndexedDB | Local trial; no backend account records or API-token creation |

A token value is returned only once at creation. SQLite stores its digest, prefix, scopes, timestamps, expiry and revocation metadata, not its raw value.

## Fresh-start local flow

```bash
python -m pip install "ChatVoice[web]==0.2.0"
chatvoice service plan --ensure-dirs --json
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

From another shell using the same runtime, provision an invited account:

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

The test entry is `http://127.0.0.1:18087/`. `stub-local` supports model-free contract testing. Real transcription and summaries need separately configured server-side providers. This loopback address is not a deployed public URL.

## Create a token in the web UI

Create a token in Settings, choosing a name and expiry. Copy its one-time value; later views show only metadata. Clear the one-time token display on logout or storage-mode changes.

## Create / list / revoke tokens from CLI

```bash
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
chatvoice tokens list --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice tokens revoke <token-id> --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
```

Pass passwords through environment variables, not command-line argument values. Creation output includes a one-time token; do not paste it into public logs or PRs.

## Read meetings and conversations

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data meeting <meeting-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversation <conversation-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

HTTP clients use the `Bearer` authentication scheme in the `Authorization` header with the previously created data token.

```text
GET /api/data/meetings
GET /api/data/meetings/{meeting_id}
GET /api/data/conversations
GET /api/data/conversations/{conversation_id}
```

Meeting lists return metadata/previews and `tags`; details add transcripts and summaries. Conversation details return realtime messages. Do not log full bodies during routine polling.

## Voice clone job API

This is not a data bearer-token interface. The browser uses its login cookie and CSRF with multipart form data:

```text
GET    /api/voice-clone/status
POST   /api/voice-clone/jobs
GET    /api/voice-clone/jobs/{job_id}
GET    /api/voice-clone/jobs/{job_id}/audio
DELETE /api/voice-clone/jobs/{job_id}
```

Creation fields are `text`, `lang`, `duration_factor`, and `reference_audio`. The endpoint proxies a local sidecar without exposing provider secrets. Generated audio is a temporary job artifact, not a voice profile or meeting-history item. See [Voice Cloning Guide](voice-cloning.md).

## Scopes and boundaries

- Supported scopes are `read:meetings` and `read:conversations`.
- Tokens are read-only: no meeting writes, summary edits or account management. Omitted scopes use both read scopes; an explicit empty array is rejected.
- Expired/revoked tokens stop working immediately, and reads retain owner isolation.
- Meeting tags are deduplicated strings; old records without tags return `[]`.
- Raw recording audio is neither stored in the backend database nor returned by these data APIs.
