"""OmniAssist primary agent: lifecycle, reasoning loop, and tool execution.

The agent drives a real multi-step loop. Each iteration asks the model for the
next action; if the model requests tool calls they are executed and their
results are appended to the conversation so the model can observe them and
decide what to do next. The loop ends when the model replies with plain text or
when ``max_iterations`` is reached.
"""

import os

import yaml

from core.reasoning import CognitiveEngine
from core.router import TaskRouter
from core.selfmodify import SelfModifier
from core.state import ConversationState
from mcp_tools.registry import MCPToolRegistry

try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    pass

DEFAULT_MODEL = "gemini-3.5-flash-lite"


class OfflineClient:
    """Deterministic stand-in for the GenAI client used when no API key is set.

    It lets the CLI, the web UI, and the test suite run end-to-end without
    credentials. It is never used when a real API key is configured.
    """

    class _Models:
        def generate_content(self, model, contents, config):
            return OfflineResponse(contents)

    def __init__(self):
        self.models = self._Models()


class OfflineResponse:
    def __init__(self, contents):
        self.function_calls = None
        prompt = contents if isinstance(contents, str) else str(contents)
        self.text = (
            "Offline mode: no GEMINI_API_KEY is configured, so no model was called.\n\n"
            f"Received prompt: {prompt[:400]}"
        )


class OmniAssist:
    """Main OmniAssist primary agent class coordinating lifecycle, reasoning, and tools."""

    def __init__(self, api_key: str | None = None, model_id: str | None = None):
        self.state = ConversationState()
        self.reasoning = CognitiveEngine()
        self.self_modifier = SelfModifier()
        self.tool_registry = MCPToolRegistry()
        self.router = TaskRouter(self.tool_registry)

        self.max_iterations = 10
        self.temperature = 0.2
        self.model_id = model_id or DEFAULT_MODEL
        self.fallback_models = []
        self._load_config(model_id)

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.offline = not self.api_key
        if self.offline:
            self.client = OfflineClient()
        else:
            from google import genai

            os.environ.setdefault("GEMINI_API_KEY", self.api_key)
            os.environ.setdefault("GOOGLE_API_KEY", self.api_key)
            self.client = genai.Client(api_key=self.api_key)

    def _load_config(self, model_id: str | None):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "config.yml"
        )
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception:  # noqa: BLE001 - a broken config must not block startup
            return
        models = config_data.get("models", {}) or {}
        if not model_id:
            self.model_id = models.get("primary", self.model_id)
        self.fallback_models = [m for m in (models.get("fallbacks") or []) if m]
        agent_cfg = config_data.get("agent", {}) or {}
        self.max_iterations = int(agent_cfg.get("max_iterations", self.max_iterations))
        self.temperature = float(agent_cfg.get("temperature", self.temperature))

    def _build_system_prompt(self, plan: str) -> str:
        """Generates an explicit system prompt directing multi-step autonomous behavior."""
        return f"""You are OmniAssist, an autonomous, highly capable AI operational agent.

### CORE INSTRUCTIONS & AUTONOMY:
1. **Multi-Step Execution**: You are equipped with direct tool access. When given a complex goal, break it down into sequential, logical sub-steps. Do not ask the user for permission to execute sub-steps—take initiative using available tools.
2. **Tool Feedback Loops**: Execute tools sequentially. Inspect the results of each tool execution, evaluate if your sub-goal was achieved, adapt if errors occur, and trigger the next step until the overall task is fully resolved.
3. **Problem-Solving**: If a tool returns an error or incomplete data, retry with modified parameters or try an alternative tool before giving up.
4. **Final Response**: Once all tool calls and multi-step actions are complete, synthesize a clean, concise, and structured final summary for the user.

### CURRENT CONTEXT & STRATEGIC PLAN:
{plan}
"""

    def _model_chain(self) -> list[str]:
        return [self.model_id] + [m for m in self.fallback_models if m and m != self.model_id]

    def _build_config(self, plan: str):
        """Builds the SDK config object, including tool declarations."""
        if self.offline:
            return None
        from google.genai import types

        kwargs = {
            "system_instruction": self._build_system_prompt(plan),
            "temperature": self.temperature,
        }
        declarations = self.router.tool_declarations()
        if declarations:
            kwargs["tools"] = declarations
        return types.GenerateContentConfig(**kwargs)

    def _generate(self, contents, config) -> tuple:
        """Try each model in the priority chain until one succeeds."""
        errors = []
        for model in self._model_chain():
            try:
                response = self.client.models.generate_content(
                    model=model, contents=contents, config=config
                )
                return model, response
            except Exception as e:  # noqa: BLE001 - fall through the chain
                errors.append(f"{model}: {e}")
        raise RuntimeError("; ".join(errors))

    def _plan(self, prompt: str) -> str:
        return self.reasoning.evaluate_plan(prompt)

    def _initial_contents(self, prompt: str):
        """Builds the opening user turn in the shape the SDK expects."""
        if self.offline:
            return prompt
        from google.genai import types

        return [types.Content(role="user", parts=[types.Part(text=prompt)])]

    def _append_tool_turn(self, contents, calls, observations):
        """Appends the model's tool calls and the tool responses to the transcript.

        Gemini expects tool output as ``function_response`` parts on a ``user``
        turn, not as flattened prose. Sending it as prose makes the model
        re-issue the same call until the iteration cap is hit.
        """
        if self.offline:
            return contents
        from google.genai import types

        model_parts = [
            types.Part(
                function_call=types.FunctionCall(name=call.name, args=dict(call.args or {}))
            )
            for call in calls
        ]
        response_parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    name=call.name,
                    response={"result": result},
                )
            )
            for call, result in observations
        ]
        return [
            *contents,
            types.Content(role="model", parts=model_parts),
            types.Content(role="user", parts=response_parts),
        ]

    def run(self, prompt: str) -> str:
        """Runs the full agent loop and returns the final assistant text."""
        text = ""
        for event in self.run_stream(prompt):
            if event.type in ("final", "error"):
                text = event.content
        return text

    def run_stream(self, prompt: str):
        """Generator yielding agent events.

        Event types: ``plan``, ``tool_call``, ``tool_result``, ``final``, ``error``.
        Consuming this generator is what actually advances the agent loop.
        """
        from core.events import AgentEvent

        self.state.add_message("user", prompt)
        plan = self._plan(prompt)
        yield AgentEvent("plan", plan)

        try:
            config = self._build_config(plan)
        except Exception as e:  # noqa: BLE001
            yield AgentEvent("error", f"Agent Runtime Exception Handled: {e}")
            return

        contents = self._initial_contents(prompt)
        max_iterations = max(1, self.max_iterations)
        for iteration in range(max_iterations):
            turn = contents
            if iteration == max_iterations - 1 and not self.offline:
                # Final iteration: ask for prose so the run always terminates.
                from google.genai import types

                turn = [
                    *contents,
                    types.Content(
                        role="user",
                        parts=[types.Part(text=(
                            "This is your final step. Do not call any more tools. "
                            "Summarize what you found and answer the user now."
                        ))],
                    ),
                ]
            try:
                _model_used, response = self._generate(turn, config)
            except Exception as e:  # noqa: BLE001 - surface, never crash the UI
                yield AgentEvent("error", f"Agent Runtime Exception Handled: {e}")
                return

            calls = getattr(response, "function_calls", None) or []
            if not calls:
                text = getattr(response, "text", None) or "Execution completed."
                self.state.add_message("assistant", text)
                yield AgentEvent("final", text)
                return

            observations = []
            for call in calls:
                args = dict(call.args or {})
                yield AgentEvent("tool_call", f"{call.name}({args})", tool=call.name, args=args)
                result = self.router.execute(call.name, args)
                yield AgentEvent("tool_result", result, tool=call.name)
                observations.append((call, result))

            contents = self._append_tool_turn(contents, calls, observations)

        message = "Reached the maximum number of iterations before completing the task."
        self.state.add_message("assistant", message)
        yield AgentEvent("final", message)
