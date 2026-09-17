"""Tests for the agent loop: tool execution and tool-result feedback."""

import unittest
from unittest.mock import patch

from core.agent import OmniAssist
from core.events import AgentEvent


class _Call:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class _Response:
    def __init__(self, text=None, function_calls=None):
        self.text = text
        self.function_calls = function_calls


class _ScriptedModels:
    """Returns queued responses, recording the contents it was given."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.seen = []

    def generate_content(self, model, contents, config):
        self.seen.append(contents)
        return self._responses.pop(0)


class _ScriptedClient:
    def __init__(self, responses):
        self.models = _ScriptedModels(responses)


def _make_agent(responses):
    agent = object.__new__(OmniAssist)
    agent.model_id = "test-model"
    agent.fallback_models = []
    agent.max_iterations = 10
    agent.temperature = 0.2
    agent.offline = False
    agent.client = _ScriptedClient(responses)
    from core.reasoning import CognitiveEngine
    from core.router import TaskRouter
    from core.state import ConversationState
    from mcp_tools.registry import MCPToolRegistry

    agent.state = ConversationState()
    agent.reasoning = CognitiveEngine()
    agent.tool_registry = MCPToolRegistry()
    agent.router = TaskRouter(agent.tool_registry)
    return agent


class TestAgentLoop(unittest.TestCase):
    def test_plain_response_needs_one_iteration(self):
        agent = _make_agent([_Response(text="hello there")])
        events = list(agent.run_stream("hi"))
        self.assertEqual([e.type for e in events], ["plan", "final"])
        self.assertEqual(events[-1].content, "hello there")

    def test_tool_call_is_actually_executed(self):
        agent = _make_agent([
            _Response(function_calls=[_Call("basic_calculate", {"expression": "6 * 7"})]),
            _Response(text="The answer is 42."),
        ])
        events = list(agent.run_stream("what is 6*7"))

        types = [e.type for e in events]
        self.assertEqual(types, ["plan", "tool_call", "tool_result", "final"])

        tool_result = next(e for e in events if e.type == "tool_result")
        # The real tool ran: basic_calculate returns the computed value.
        self.assertEqual(tool_result.content, "42")
        self.assertEqual(tool_result.tool, "basic_calculate")

    def test_tool_result_is_fed_back_to_the_model(self):
        agent = _make_agent([
            _Response(function_calls=[_Call("basic_calculate", {"expression": "1 + 1"})]),
            _Response(text="done"),
        ])
        list(agent.run_stream("add one and one"))

        # Second model call must carry the observation from the first tool run.
        self.assertEqual(len(agent.client.models.seen), 2)
        followup = agent.client.models.seen[1]
        self.assertEqual(followup[1].parts[0].function_call.name, "basic_calculate")
        self.assertEqual(followup[2].parts[0].function_response.response["result"], "2")

    def test_loop_stops_at_max_iterations(self):
        agent = _make_agent([
            _Response(function_calls=[_Call("basic_calculate", {"expression": "1"})]),
            _Response(function_calls=[_Call("basic_calculate", {"expression": "2"})]),
        ])
        agent.max_iterations = 2
        events = list(agent.run_stream("loop forever"))
        self.assertEqual(events[-1].type, "final")
        self.assertIn("maximum number of iterations", events[-1].content)

    def test_final_iteration_forces_a_text_answer(self):
        """The last turn must instruct the model to stop calling tools."""
        agent = _make_agent([
            _Response(function_calls=[_Call("basic_calculate", {"expression": "1"})]),
            _Response(text="stopped and summarized"),
        ])
        agent.max_iterations = 2
        events = list(agent.run_stream("do work"))
        self.assertEqual(events[-1].type, "final")
        self.assertEqual(events[-1].content, "stopped and summarized")

        final_turn = agent.client.models.seen[-1]
        joined = str(final_turn)
        self.assertIn("Do not call any more tools", joined)
        # Earlier turns must not carry that instruction.
        self.assertNotIn("Do not call any more tools", str(agent.client.models.seen[0]))

    def test_tool_turn_uses_structured_function_response(self):
        """Tool output is sent as function_response parts, not flattened prose."""
        agent = _make_agent([_Response(text="ok")])
        contents = agent._initial_contents("hello")
        call = _Call("run_shell", {"command": "ls"})
        updated = agent._append_tool_turn(contents, [call], [(call, "file-a\nfile-b")])

        self.assertEqual(len(updated), 3)
        self.assertEqual(updated[1].role, "model")
        self.assertEqual(updated[1].parts[0].function_call.name, "run_shell")
        self.assertEqual(updated[2].role, "user")
        response_part = updated[2].parts[0].function_response
        self.assertEqual(response_part.name, "run_shell")
        self.assertEqual(response_part.response["result"], "file-a\nfile-b")

    def test_model_failure_is_reported_not_raised(self):
        agent = _make_agent([])
        events = list(agent.run_stream("hi"))
        self.assertEqual(events[-1].type, "error")
        self.assertIn("Agent Runtime Exception Handled", events[-1].content)

    def test_offline_agent_runs_end_to_end(self):
        with patch.dict("os.environ", {}, clear=True):
            agent = OmniAssist()
        self.assertTrue(agent.offline)
        events = list(agent.run_stream("hello"))
        self.assertEqual(events[-1].type, "final")
        self.assertIn("Offline mode", events[-1].content)


class TestAgentEvents(unittest.TestCase):
    def test_serialization(self):
        event = AgentEvent("tool_call", "run_shell({'command': 'ls'})", tool="run_shell", args={"command": "ls"})
        payload = event.to_dict()
        self.assertEqual(payload["type"], "tool_call")
        self.assertEqual(payload["tool"], "run_shell")
        self.assertEqual(payload["args"], {"command": "ls"})


if __name__ == "__main__":
    unittest.main()
