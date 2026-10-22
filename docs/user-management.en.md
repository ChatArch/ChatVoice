# User Management

```bash
python -m pip install "ChatVoice[web]==0.5.1"
```

ChatVoice 0.5.x depends on the published `ChatLogin>=0.2.0,<0.3.0` range, so user management needs no Git installation. For offline deployment, pin wheels inside that public release range.

User management reuses the original Speakr invited-account login. After signing in with the same account password, the original `meeting_session` cookie reaches the meeting workspace, `/user-management/profile`, and role-gated `/user-management/users`. There is no public signup, no second user database, and no migration of meetings, conversations, ASR state, voice jobs, API tokens, or guest IndexedDB data.

## Entrypoints

| Role | Pages | Capabilities |
| --- | --- | --- |
| OWNER | `/user-management/users`, `/user-management/profile` | Manage the account directory, create/disable/delete users, manage admins, atomically transfer owner, maintain own profile |
| ADMIN | `/user-management/users`, `/user-management/profile` | Manage ordinary users and own profile; cannot grant admin or take over owner |
| USER | `/user-management/profile` | View/update own profile and password |

The top-right `...` settings menu shows "Admin page" for OWNER/ADMIN and opens `/user-management/users`; the account card also shows "User management". Every signed-in member sees "Profile". Meetings, recordings and realtime conversations keep their business authorization checks; Copilot remains an internal beta without a web entry.

## Preservation and Permissions

- Original `accounts.id` remains the stable user ID; business-table `owner_id` values are not rewritten.
- Original account names, display names, password salt/hash bytes are preserved; old passwords are not rehashed.
- Schema initialization is explicit, idempotent, and additive; old accounts default to enabled `USER`, and the single owner is selected through trusted Python adoption.
- Role, status, deletion, password change, and owner transfer increment revision and invalidate affected sessions.
- API tokens for disabled/deleted accounts are denied without deleting preserved rows.
- OWNER means account-directory owner, not omniscient access to all meetings, recordings, or tokens; host business ACLs still check record ownership.

## Configuration

`CHATVOICE_PUBLIC_ORIGIN=https://voice.example.invalid` is the trusted fixed origin read through server-side typed `ChatVoiceConfig`. It represents only the browser-visible scheme/host/port, with no credentials, path, query, or fragment, and is never derived from request `Host`, proxy headers, or caller host.

Invited accounts still use the existing `chatvoice accounts add/list` flow or equivalent trusted tooling. Single-owner adoption is performed by host Python setup with ChatLogin provider's `adopt_owner(...)`; do not invent or document a public owner CLI command.
