"""The installed ChatVoice app must serve the shared login over real TCP."""
import socket
import threading
import time

import httpx
import uvicorn
from test_chatlogin_auth import host, PASSWORD


def test_real_login_server(host):
    app, _ = host
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app.app, host="127.0.0.1", port=sock.getsockname()[1],
                           lifespan="off", ws="none", access_log=False, log_level="warning", timeout_graceful_shutdown=5))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    try:
        with httpx.Client(base_url=origin, trust_env=False, timeout=3) as client:
            deadline = time.monotonic() + 10
            while True:
                try:
                    if client.get("/api/auth/session").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() > deadline:
                    raise AssertionError("Owned login server did not become ready")
                time.sleep(.02)
            page = client.get("/login")
            assert page.status_code == 200 and 'class="chatlogin__form"' in page.text
            for path, kind in [("/assets/chatlogin/login.js", "javascript"), ("/assets/chatlogin/login.css", "text/css"), ("/assets/login-brand.css", "text/css")]:
                response = client.get(path)
                assert response.status_code == 200 and kind in response.headers["content-type"]
            assert client.get("/api/meetings").status_code == 401
            response = client.post("/api/auth/login", json={"username": "alice@example.invalid", "password": PASSWORD, "next": "/"})
            assert response.status_code == 200 and response.json()["next"] == "/"
            token = client.cookies.get("meeting_session")
            session = client.get("/api/auth/session").json()
            assert session["user"]["account"] == "alice@example.invalid"
            assert client.get("/api/meetings").status_code == 200
            assert client.post("/api/auth/logout").status_code == 403
            assert client.post("/api/auth/logout", headers={"X-CSRF-Token": session["csrf_token"]}).status_code == 200
            assert client.get("/api/auth/session").json()["authenticated"] is False
            client.cookies.set("meeting_session", token)
            assert client.get("/api/meetings").status_code == 401
    finally:
        server.should_exit = True
        thread.join(8)
        sock.close()
        assert not thread.is_alive(), "Owned login server did not close gracefully"
