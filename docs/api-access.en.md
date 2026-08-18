# API Access

ChatVoice 0.1.0 adds an end-to-end data access path for the packaged service: sign in with an invited account, create an API token, then read meetings and conversations through `/api/data/...` or `chatvoice data ...`.

## Access model

| Entry | Credential | Purpose |
| --- | --- | --- |
| Browser login | HttpOnly session cookie + CSRF token | Save meetings/conversations and create/revoke API tokens in the web UI |
| API token | Bearer token | Automation reads for meeting transcripts, summaries, and realtime conversation text |
| Guest mode | Browser IndexedDB | Local trial only; does not write the backend database and cannot create API tokens |

Token values are shown only once when created. The backend SQLite database stores only the hash, prefix, scopes, creation time, expiry time, revocation time, and last-used time.

## Fresh-start local flow

Install and start the service:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.0"
chatvoice service plan --ensure-dirs --json
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

In another shell using the same runtime, create an invited account:

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

Open `http://127.0.0.1:18087/`, log in, create or open a meeting, and generate a summary.

## Create a token in the web UI

1. Open **Settings**.
2. In **API Token**, enter a name and optional expiry.
3. Click **Create Token**.
4. Copy the returned value immediately; after closing, only metadata remains visible.
5. Revoke a token from the token row when it should stop working.

## Create / list / revoke tokens from CLI

The CLI creates tokens through the browser login endpoint, so it needs the account password. Passwords are read from environment variables only:

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
chatvoice tokens list --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice tokens revoke <token-id> --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
```

## Read meetings and conversations

Put the one-time token value into the environment variable selected by `--token-env`:

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data meeting <meeting-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversation <conversation-id> --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

HTTP endpoints:

```text
GET /api/data/meetings
GET /api/data/meetings/{meeting_id}
GET /api/data/conversations
GET /api/data/conversations/{conversation_id}
```

Requests need:

```text
Authorization: Bearer <api-token>
```

## Scopes and boundaries

Supported scopes:

```text
read:meetings
read:conversations
```

Boundaries:

- API tokens read data only; they cannot write meetings, edit summaries, or manage accounts.
- Revoked or expired tokens fail immediately.
- Data-read endpoints return transcript and summary text; do not paste output into public logs or PRs.
- Raw recording files still do not enter the backend database and are not returned by these data APIs.
