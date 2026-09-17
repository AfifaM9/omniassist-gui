"""Task routing between the primary agent loop and registered MCP tools."""

import inspect

try:  # pragma: no cover - import guard keeps the router usable without the SDK
    from google.genai import types
except Exception:  # noqa: BLE001
    types = None


class TaskRouter:
    """Routes tasks between internal sub-agents and registered MCP tools."""

    def __init__(self, tool_registry):
        self.registry = tool_registry

    def route(self, task: str) -> str:
        return f"[TaskRouter] Analyzing task routing parameters for: '{task}'"

    def tool_declarations(self) -> list:
        """Builds SDK tool declarations from the registry's callables."""
        if types is None:
            return []
        functions = []
        for name, func in sorted(self.registry.tools.items()):
            doc = inspect.getdoc(func) or ""
            parameters = {"type": "OBJECT", "properties": {}, "required": []}
            for pname, param in inspect.signature(func).parameters.items():
                if pname == "self":
                    continue
                annotation = param.annotation
                if annotation is bool:
                    json_type = "BOOLEAN"
                elif annotation in (int, float):
                    json_type = "INTEGER" if annotation is int else "NUMBER"
                else:
                    json_type = "STRING"
                parameters["properties"][pname] = {
                    "type": json_type,
                    "description": f"Parameter '{pname}'",
                }
                if param.default is inspect.Parameter.empty:
                    parameters["required"].append(pname)
            functions.append(
                types.FunctionDeclaration(
                    name=name,
                    description=doc.split("\n\n")[0].strip() or name,
                    parameters=parameters,
                )
            )
        return [types.Tool(function_declarations=functions)] if functions else []

    def execute(self, tool_name: str, args: dict | None = None) -> str:
        """Invokes a registered tool by name and returns its result as text."""
        return str(self.registry.execute_tool(tool_name, **(args or {})))