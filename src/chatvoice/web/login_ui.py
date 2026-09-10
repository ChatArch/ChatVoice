"""Shared ChatLogin form/assets with trusted, host-owned presentation options."""
from importlib.resources import files
from pathlib import Path

from chatlogin.security import safe_next
from chatlogin.ui import LoginUI
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response


def install_login_ui(app: FastAPI, static_dir: Path) -> None:
    app.state.login_ui = LoginUI(
        title="声笺 VoiceNote", appearance="light",
        subtitle="仅限受邀账号；如需账号请联系管理员。登录后保存文字与摘要，不保存录音。",
        stylesheet_url="/assets/login-brand.css", guest_url="/?mode=guest",
        guest_label="访客使用 · 记录仅保存在此浏览器",
    )

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, next: str = "/") -> HTMLResponse:
        return HTMLResponse(request.app.state.login_ui.render({
            "assets_path": "/assets/chatlogin", "login_url": "/api/auth/login",
            "session_url": "/api/auth/session", "next": safe_next(next),
        }), headers={"Cache-Control": "no-store"})

    @app.get("/assets/chatlogin/{name}")
    def login_asset(name: str) -> Response:
        media = {"login.css": "text/css", "login.js": "text/javascript"}
        if name not in media:
            raise HTTPException(status_code=404)
        return Response((files("chatlogin.web") / "assets" / name).read_bytes(), media_type=media[name])

    @app.get("/assets/login-brand.css")
    def login_brand() -> FileResponse:
        return FileResponse(static_dir / "login-brand.css", media_type="text/css")
