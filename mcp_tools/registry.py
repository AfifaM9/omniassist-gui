import importlib
import inspect
import pkgutil

import mcp_tools


class MCPToolRegistry:
    """Discovers callable tools from the ``mcp_tools`` package.

    Discovery is fault-tolerant: a module that fails to import (for example a
    missing optional dependency) is recorded in :attr:`load_errors` and skipped
    instead of aborting the whole registry.
    """

    def __init__(self):
        self.tools = {}
        self.load_errors = {}
        self._discover_tools()

    def _discover_tools(self):
        for _, modname, _ in pkgutil.iter_modules(mcp_tools.__path__):
            if modname == "registry":
                continue
            try:
                module = importlib.import_module(f"mcp_tools.{modname}")
            except Exception as exc:  # noqa: BLE001 - report, never abort discovery
                self.load_errors[modname] = f"{type(exc).__name__}: {exc}"
                continue

            for attr_name, attr in vars(module).items():
                if attr_name.startswith("_") or not inspect.isfunction(attr):
                    continue
                if attr.__module__ != module.__name__:
                    continue
                self.tools[attr_name] = attr

    def describe(self) -> list[dict]:
        """Returns metadata for every registered tool, for UI/API display."""
        described = []
        for name in sorted(self.tools):
            func = self.tools[name]
            doc = inspect.getdoc(func) or ""
            described.append(
                {
                    "name": name,
                    "description": doc.split("\n\n")[0].strip(),
                    "parameters": {
                        pname: {
                            "type": (
                                param.annotation.__name__
                                if param.annotation is not inspect.Parameter.empty
                                and hasattr(param.annotation, "__name__")
                                else "string"
                            ),
                            "required": param.default is inspect.Parameter.empty,
                        }
                        for pname, param in inspect.signature(func).parameters.items()
                    },
                }
            )
        return described

    def execute_tool(self, tool_name: str, *args, **kwargs):
        """Executes a registered tool function by name."""
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found in registry."
        try:
            return self.tools[tool_name](*args, **kwargs)
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"
