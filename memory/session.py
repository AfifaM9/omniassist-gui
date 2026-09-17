"""Filesystem-backed session persistence used by the CLI and the web API."""

import json
import os
import re
import time

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SessionPersistence:
    """Session state saving and loading across agent reboots."""

    def __init__(self, session_dir: str = "./data/sessions"):
        self.session_dir = session_dir

    def _path_for(self, session_id: str) -> str:
        if not _SAFE_ID.match(session_id or ""):
            raise ValueError(f"Invalid session id: {session_id!r}")
        return os.path.join(self.session_dir, f"{session_id}.json")

    def save_session(self, session_id: str, state_data: dict):
        """Saves current session context to disk."""
        try:
            os.makedirs(self.session_dir, exist_ok=True)
            payload = dict(state_data)
            payload.setdefault("session_id", session_id)
            payload["updated_at"] = time.time()
            with open(self._path_for(session_id), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return "Session saved successfully."
        except Exception as e:
            return f"Session Save Error: {e}"

    def load_session(self, session_id: str) -> dict:
        """Loads previous session context from disk."""
        try:
            path = self._path_for(session_id)
        except ValueError as e:
            return {"error": str(e)}
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}

    def list_sessions(self) -> list[dict]:
        """Returns lightweight summaries of every stored session, newest first."""
        if not os.path.isdir(self.session_dir):
            return []
        sessions = []
        for fname in os.listdir(self.session_dir):
            if not fname.endswith(".json"):
                continue
            sid = fname[: -len(".json")]
            data = self.load_session(sid)
            if "error" in data:
                continue
            messages = data.get("messages", [])
            sessions.append(
                {
                    "session_id": sid,
                    "title": data.get("title") or self._derive_title(messages),
                    "message_count": len(messages),
                    "updated_at": data.get("updated_at", 0),
                }
            )
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

    def delete_session(self, session_id: str) -> bool:
        try:
            path = self._path_for(session_id)
        except ValueError:
            return False
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @staticmethod
    def _derive_title(messages: list) -> str:
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                return str(msg["content"])[:60]
        return "New conversation"
