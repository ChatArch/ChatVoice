"""Server-side managed account helpers for ChatVoice.

These functions are intentionally local-runtime helpers. They create/list invited
accounts in the same SQLite storage used by the packaged web service, without
exposing password material in return values.
"""

from __future__ import annotations

from contextlib import closing
from typing import Any


class AccountRuntimeError(RuntimeError):
    """Raised when the packaged web runtime is unavailable."""


def _legacy_app():
    try:
        from chatvoice.web import legacy_app
    except Exception as exc:  # pragma: no cover - depends on optional web extra
        raise AccountRuntimeError('Account management requires the "ChatVoice[web]" extra.') from exc
    return legacy_app


def create_account(account: str, password: str, display_name: str | None = None) -> dict[str, str]:
    """Create one invited account in the local ChatVoice service database."""

    app = _legacy_app()
    return app.provision_managed_account(account, password, display_name)


def list_accounts() -> list[dict[str, Any]]:
    """List invited account metadata without password hashes or salts."""

    app = _legacy_app()
    with app._MEETING_DB_LOCK, closing(app._meeting_db()) as connection:
        rows = connection.execute(
            "SELECT id, account, display_name, created_at FROM accounts ORDER BY created_at"
        ).fetchall()
    return [dict(row) for row in rows]
