"""Short-term conversational message buffer."""


class ConversationMemory:
    """Short-term conversational message buffer."""

    def __init__(self, max_history: int = 30):
        self.max_history = max_history
        self.history = []

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        while len(self.history) > self.max_history:
            self.history.pop(0)

    def get_context(self) -> list:
        return list(self.history)

    def clear(self):
        self.history.clear()
