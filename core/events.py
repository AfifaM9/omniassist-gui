"""Event objects emitted by the agent loop and serialized to the web UI."""


class AgentEvent:
    """A single step in an agent run, streamed to any front-end."""

    __slots__ = ("args", "content", "tool", "type")

    def __init__(self, type: str, content: str, tool: str | None = None, args: dict | None = None):
        self.type = type
        self.content = content
        self.tool = tool
        self.args = args or {}

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content, "tool": self.tool, "args": self.args}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"AgentEvent(type={self.type!r}, tool={self.tool!r})"
