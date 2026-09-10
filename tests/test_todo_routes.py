"""Real Todo route wiring, mocked model boundary only."""
import asyncio
import json

import httpx
import pytest

from test_todo_storage import todo_app

@pytest.mark.parametrize("route,body,output", [
    ("/api/meeting-notes/todo", {"summary":"整理报告"}, "# Todo\n- [ ] 整理报告"),
    ("/api/meeting-notes/todo/revise", {"summary":"整理报告", "current_todo":"- [x] 核对范围\n- [ ] 整理报告", "instruction":"拆细"}, json.dumps({"content":"- [x] 核对范围\n- [ ] 整理报告\n  - [ ] 汇总用例", "reply":"已拆细。"},ensure_ascii=False)),
    ("/api/meeting-notes/todo/revise", {"summary":"", "current_todo":"- [ ] 整理报告", "instruction":"细分"}, json.dumps({"content":"- [ ] 整理报告\n  - [ ] 汇总用例", "reply":"已拆细。"},ensure_ascii=False)),
])
def test_todo_http_routes(todo_app,monkeypatch,route,body,output):
    calls=[]
    def model(req):
        calls.append(req)
        return {"content":output,"model":"offline"}
    monkeypatch.setattr(todo_app,"_meeting_notes_blocking",model)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=todo_app.app),base_url="http://app.example.test") as client:
            response=await client.post(route,json=body)
            assert response.status_code==200,response.text
            assert response.json()["model"]=="offline"
            assert "- [ ]" in response.json()["content"]
            assert json.loads(calls[0].transcript)["summary"]==body["summary"]
    asyncio.run(asyncio.wait_for(flow(),15))


@pytest.mark.parametrize("body", [{"summary":""},{"summary":"  "},{"summary":"x"*20001},{}])
def test_todo_generation_rejects_invalid_input(todo_app,monkeypatch,body):
    monkeypatch.setattr(todo_app,"_meeting_notes_blocking",lambda req: pytest.fail("Must not call model"))
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=todo_app.app),base_url="http://app.example.test") as client:
            assert (await client.post("/api/meeting-notes/todo",json=body)).status_code==422
    asyncio.run(asyncio.wait_for(flow(),15))


@pytest.mark.parametrize("kind,expected",[("config",503),("upstream",502),("invalid",502)])
def test_todo_errors_are_safe(todo_app,monkeypatch,kind,expected):
    def model(req):
        if kind=="config": raise todo_app.HTTPException(503,"SENSITIVE-CREDENTIAL")
        if kind=="upstream": raise TimeoutError("SENSITIVE-CREDENTIAL")
        return {"content":"SENSITIVE-CREDENTIAL","model":"offline"}
    monkeypatch.setattr(todo_app,"_meeting_notes_blocking",model)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=todo_app.app),base_url="http://app.example.test") as client:
            response=await client.post("/api/meeting-notes/todo",json={"summary":"整理报告"})
            assert response.status_code==expected,response.text
            assert "SENSITIVE-CREDENTIAL" not in response.text
    asyncio.run(asyncio.wait_for(flow(),15))
