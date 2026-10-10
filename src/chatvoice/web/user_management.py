"""ChatVoice installation of ChatLogin managed-account routes."""
from __future__ import annotations

from urllib.parse import urlsplit

from chatlogin.fastapi import CookieSettings
from chatlogin.managed import ManagedUsers
from chatlogin.managed_web import ManagedAuth
from chatlogin.user_ui import UserAdminUI, UserProfileUI
from fastapi import FastAPI

from chatvoice.web.auth_adapter import ManagedDirectoryStore


def validate_public_origin(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if any(ord(character) < 33 or ord(character) > 126 for character in raw):
        raise RuntimeError("CHATVOICE_PUBLIC_ORIGIN must be a printable ASCII origin")
    parsed = urlsplit(raw)
    try:
        parsed.port
    except ValueError as exc:
        raise RuntimeError("CHATVOICE_PUBLIC_ORIGIN has an invalid port") from exc
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise RuntimeError("CHATVOICE_PUBLIC_ORIGIN must be a concrete http(s) origin")
    return raw


def install_user_management(app: FastAPI, *, connect, lock, clock, login_ui, cookie_name: str, ttl: int, origin: str) -> ManagedAuth:
    store = ManagedDirectoryStore(connect, lock, clock)
    users = ManagedUsers(store, session_namespace="chatvoice", ttl=ttl, clock=clock)
    origin = validate_public_origin(origin)
    auth = ManagedAuth(
        users,
        origin=origin,
        prefix="/user-management",
        ui=login_ui,
        admin_ui=UserAdminUI(login_ui=login_ui, title="Speakr 用户管理", subtitle=""),
        profile_ui=UserProfileUI(login_ui=login_ui, title="Speakr 个人账号", subtitle=""),
        cookie=CookieSettings(name=cookie_name, path="/", max_age=ttl, secure=origin.startswith("https://")),
        allow_native=False,
        allow_insecure_loopback=origin.startswith("http://"),
    )
    app.include_router(auth.router)
    return auth


__all__ = ["install_user_management", "validate_public_origin"]
