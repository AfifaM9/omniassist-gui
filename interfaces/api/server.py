"""FastAPI backend for the OmniAssist web UI.

Endpoints:
  GET  /api/auth              auth mode + whether a credential is required
  POST /api/auth/token        exchange the GUI Omni token for a session
  POST /api/auth/totp         exchange a 6-digit TOTP code for a session
  GET  /api/health            runtime status and model chain
  GET  /api/tools             registered tools and their parameters
  GET  /api/sessions          stored conversations
  GET  /api/sessions/{id}     one stored conversation
  DEL  /api/sessions/{id}     delete a stored conversation
  POST /api/run               run the agent, return the final answer
  WS   /ws/run                run the agent, stream every step as JSON
  GET  /                      the single-page web UI
"""

import asyncio
import logging
import os
import uuid

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.agent import OmniAssist
from core.auth import build_manager_from_env
from memory.session import SessionPersistence

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
VERSION = 'v2026.6 "Dirt Cake"'

# The agent can run shell commands and write files, so the API is not safe to
# expose unauthenticated. The active mode is chosen by the launch flag
# (--token / --totp) and carried in OMNIASSIST_AUTH_MODE:
#   open  (:8000) no credential
#   token (:8002) the GUI Omni bearer token
#   totp  (:8001) a 6-digit TOTP from OMNIASSIST_TOTP_SECRET (locked if unset)
API_TOKEN = os.environ.get("OMNIASSIST_API_TOKEN")  # kept for backward compatibility
auth = build_manager_from_env()

app = FastAPI(title="OmniAssist API", version=VERSION)
sessions = SessionPersistence()
_agents: dict[str, OmniAssist] = {}


def get_agent(session_id: str) -> OmniAssist:
    """Returns a per-session agent so conversations stay isolated."""
    if session_id not in _agents:
        _agents[session_id] = OmniAssist()
    return _agents[session_id]


def _presented_credential(request: Request) -> str | None:
    """Extracts a credential from the Authorization header or ?token= query."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    return request.query_params.get("token")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _authorized(credential: str | None) -> bool:
    """True if the presented credential satisfies the active mode.

    A previously issued session token is accepted in every credential mode, so
    the UI only asks for the secret once per session.
    """
    if not auth.requires_credential:
        return True
    if auth.is_valid_session(credential):
        return True
    if auth.mode.value == "token":
        return auth.check_token(credential)
    if auth.mode.value == "totp":
        return auth.check_totp(credential)
    return True


async def require_token(request: Request):
    """Dependency guarding every state-changing or tool-running endpoint."""
    if not auth.requires_credential:
        return
    if auth.is_locked_out(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many attempts; try again later")
    if not _authorized(_presented_credential(request)):
        raise HTTPException(status_code=401, detail="Missing or invalid credential")


class CredentialRequest(BaseModel):
    credential: str = Field(min_length=1)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1)
    session_id: str | None = None


def _record(session_id: str, prompt: str, answer: str, events: list[dict]) -> None:
    stored = sessions.load_session(session_id)
    messages = stored.get("messages", []) if "error" not in stored else []
    messages.append({"role": "user", "content": prompt})
    messages.append({"role": "assistant", "content": answer, "events": events})
    sessions.save_session(session_id, {"messages": messages})


@app.get("/api/auth")
def auth_info():
    """Public: tells the UI which gate to show. Never leaks the secret."""
    return auth.describe()


def _issue_or_401(request: Request, ok: bool) -> dict:
    ip = _client_ip(request)
    if auth.is_locked_out(ip):
        raise HTTPException(status_code=429, detail="Too many attempts; try again later")
    if not ok:
        auth._record_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid credential")
    auth._clear_failures(ip)
    return {"session": auth.issue_session()}


@app.post("/api/auth/token")
def auth_with_token(req: CredentialRequest, request: Request):
    """Exchanges the GUI Omni token for a session token."""
    return _issue_or_401(request, auth.check_token(req.credential))


@app.post("/api/auth/totp")
def auth_with_totp(req: CredentialRequest, request: Request):
    """Exchanges a 6-digit TOTP code for a session token."""
    return _issue_or_401(request, auth.check_totp(req.credential))


@app.get("/api/health")
def health():
    agent = get_agent("__health__")
    return {
        "status": "ok",
        "version": VERSION,
        "offline": agent.offline,
        "model": agent.model_id,
        "fallbacks": agent.fallback_models,
        "max_iterations": agent.max_iterations,
        "tools": len(agent.tool_registry.tools),
        "tool_load_errors": agent.tool_registry.load_errors,
    }


@app.get("/api/tools")
def list_tools():
    return {"tools": get_agent("__health__").tool_registry.describe()}


@app.get("/api/sessions", dependencies=[Depends(require_token)])
def list_sessions():
    return {"sessions": sessions.list_sessions()}


@app.get("/api/sessions/{session_id}", dependencies=[Depends(require_token)])
def get_session(session_id: str):
    data = sessions.load_session(session_id)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@app.delete("/api/sessions/{session_id}", dependencies=[Depends(require_token)])
def delete_session(session_id: str):
    if not sessions.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    _agents.pop(session_id, None)
    return {"deleted": session_id}


@app.post("/api/run", dependencies=[Depends(require_token)])
def run_agent_endpoint(req: PromptRequest):
    session_id = req.session_id or str(uuid.uuid4())
    agent = get_agent(session_id)
    events = []
    answer = ""
    for event in agent.run_stream(req.prompt):
        payload = event.to_dict()
        events.append(payload)
        if event.type in ("final", "error"):
            answer = event.content
    _record(session_id, req.prompt, answer, events)
    return {"session_id": session_id, "response": answer, "events": events}


@app.websocket("/ws/run")
async def ws_run(websocket: WebSocket):
    """Streams agent events over a WebSocket.

    Client sends ``{"prompt": "...", "session_id": "..."}`` and receives one JSON
    frame per event, followed by a ``done`` frame.
    """
    ws_ip = websocket.client.host if websocket.client else "unknown"
    if auth.requires_credential and (
        auth.is_locked_out(ws_ip)
        or not _authorized(websocket.query_params.get("token"))
    ):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            prompt = (payload.get("prompt") or "").strip()
            if not prompt:
                await websocket.send_json({"type": "error", "content": "Empty prompt."})
                continue

            session_id = payload.get("session_id") or str(uuid.uuid4())
            await websocket.send_json({"type": "session", "content": session_id})

            agent = get_agent(session_id)
            events = []
            answer = ""
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()

            def produce(agent=agent, loop=loop, queue=queue, prompt=prompt):
                # The agent loop is synchronous; drain it on a worker thread and
                # hand events to the event loop so the socket keeps streaming.
                try:
                    for event in agent.run_stream(prompt):
                        loop.call_soon_threadsafe(queue.put_nowait, event.to_dict())
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            loop.run_in_executor(None, produce)

            while True:
                item = await queue.get()
                if item is None:
                    break
                events.append(item)
                if item["type"] in ("final", "error"):
                    answer = item["content"]
                await websocket.send_json(item)

            _record(session_id, prompt, answer, events)
            await websocket.send_json({"type": "done", "session_id": session_id})
    except WebSocketDisconnect:
        return
    except Exception as e:  # noqa: BLE001 - keep the socket usable
        try:
            await websocket.send_json({"type": "error", "content": f"Server error: {e}"})
        except Exception:
            logging.getLogger(__name__).warning("Could not report error to websocket", exc_info=True)


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
