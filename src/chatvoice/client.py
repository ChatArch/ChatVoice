"""HTTP client helpers for ChatVoice services.

The CLI intentionally calls these importable functions instead of embedding HTTP
logic in command handlers, so downstream ChatArch tools can reuse the same API.
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


class ChatVoiceApiError(RuntimeError):
    """Raised when a ChatVoice service returns an error response."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _decode_json_response(response) -> dict[str, Any]:
    body = response.read(5_000_000)
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _read_error_payload(exc: urllib.error.HTTPError) -> Any:
    try:
        body = exc.read(1_000_000)
        return json.loads(body.decode("utf-8")) if body else None
    except Exception:
        return None


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail, ensure_ascii=False)
    return fallback


@dataclass
class ChatVoiceClient:
    """Small urllib-based client for a running ChatVoice service."""

    base_url: str = "http://127.0.0.1:18087"
    timeout: float = 10.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._csrf_token: str | None = None

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        bearer_token: str | None = None,
        csrf: bool = False,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json", "User-Agent": "chatvoice-cli/0.1"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if csrf:
            if not self._csrf_token:
                raise ChatVoiceApiError("login required before CSRF-protected request")
            headers["X-CSRF-Token"] = self._csrf_token
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return _decode_json_response(response)
        except urllib.error.HTTPError as exc:
            payload = _read_error_payload(exc)
            raise ChatVoiceApiError(_error_message(payload, exc.reason), status_code=exc.code, payload=payload) from exc
        except Exception as exc:
            raise ChatVoiceApiError(str(exc)) from exc

    def login(self, account: str, password: str) -> dict[str, Any]:
        payload = self._request("/api/auth/login", method="POST", payload={"account": account, "password": password})
        csrf_token = payload.get("csrf_token")
        if not isinstance(csrf_token, str) or not csrf_token:
            raise ChatVoiceApiError("login response did not include a CSRF token")
        self._csrf_token = csrf_token
        return payload

    def list_tokens(self) -> dict[str, Any]:
        return self._request("/api/tokens")

    def create_token(
        self,
        *,
        name: str = "cli",
        expires_days: int | None = None,
        scopes: Iterable[str] = (),
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if expires_days is not None:
            payload["expires_days"] = expires_days
        scope_list = [scope for scope in scopes if scope]
        if scope_list:
            payload["scopes"] = scope_list
        return self._request("/api/tokens", method="POST", payload=payload, csrf=True)

    def revoke_token(self, token_id: str) -> dict[str, Any]:
        return self._request(f"/api/tokens/{urllib.parse.quote(token_id, safe='')}", method="DELETE", csrf=True)

    def list_meetings(self, token: str) -> dict[str, Any]:
        return self._request("/api/data/meetings", bearer_token=token)

    def get_meeting(self, token: str, meeting_id: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(meeting_id, safe="")
        return self._request(f"/api/data/meetings/{quoted}", bearer_token=token)

    def list_conversations(self, token: str) -> dict[str, Any]:
        return self._request("/api/data/conversations", bearer_token=token)

    def get_conversation(self, token: str, conversation_id: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(conversation_id, safe="")
        return self._request(f"/api/data/conversations/{quoted}", bearer_token=token)


def create_remote_token(
    base_url: str,
    account: str,
    password: str,
    name: str,
    expires_days: int | None,
    scopes: Iterable[str] = (),
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    client = ChatVoiceClient(base_url, timeout=timeout)
    client.login(account, password)
    return client.create_token(name=name, expires_days=expires_days, scopes=scopes)


def list_remote_tokens(base_url: str, account: str, password: str, *, timeout: float = 10.0) -> dict[str, Any]:
    client = ChatVoiceClient(base_url, timeout=timeout)
    client.login(account, password)
    return client.list_tokens()


def revoke_remote_token(base_url: str, account: str, password: str, token_id: str, *, timeout: float = 10.0) -> dict[str, Any]:
    client = ChatVoiceClient(base_url, timeout=timeout)
    client.login(account, password)
    return client.revoke_token(token_id)


def list_remote_meetings(base_url: str, token: str, *, timeout: float = 10.0) -> dict[str, Any]:
    return ChatVoiceClient(base_url, timeout=timeout).list_meetings(token)


def get_remote_meeting(base_url: str, token: str, meeting_id: str, *, timeout: float = 10.0) -> dict[str, Any]:
    return ChatVoiceClient(base_url, timeout=timeout).get_meeting(token, meeting_id)


def list_remote_conversations(base_url: str, token: str, *, timeout: float = 10.0) -> dict[str, Any]:
    return ChatVoiceClient(base_url, timeout=timeout).list_conversations(token)


def get_remote_conversation(base_url: str, token: str, conversation_id: str, *, timeout: float = 10.0) -> dict[str, Any]:
    return ChatVoiceClient(base_url, timeout=timeout).get_conversation(token, conversation_id)


__all__ = [
    "ChatVoiceApiError",
    "ChatVoiceClient",
    "create_remote_token",
    "get_remote_conversation",
    "get_remote_meeting",
    "list_remote_conversations",
    "list_remote_meetings",
    "list_remote_tokens",
    "revoke_remote_token",
]
