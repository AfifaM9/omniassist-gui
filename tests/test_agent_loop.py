"""Tests for the agent loop: tool execution and tool-result feedback."""

import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.agent import OmniAssist
from core.events import AgentEvent
from memory.vector_store import HashingEmbedder, VectorStore


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


def _make_agent(responses, memory_dir=None):
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

    # Long-term memory must exist before run_stream calls recall()/_finish_turn().
    agent.memory_enabled = True
    agent.memory_dir = memory_dir or "/tmp"
    agent.memory = VectorStore(
        storage_path=os.path.join(agent.memory_dir, "vector_index.json"),
        embedder=HashingEmbedder(),
    )
    agent.last_tool_log = []
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
        # Point memory at a temp dir so the suite never writes into ./data.
        with TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"OMNIASSIST_MEMORY_DIR": tmp}, clear=True):
                agent = OmniAssist()
            self.assertTrue(agent.offline)
            events = list(agent.run_stream("hello"))
            self.assertEqual(events[-1].type, "final")
            self.assertIn("Offline mode", events[-1].content)
            self.assertTrue(os.path.exists(os.path.join(tmp, "vector_index.json")))


class TestMemoryIntegration(unittest.TestCase):
    """Long-term memory must be written by the loop and recalled into the prompt."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_completed_turn_is_persisted(self):
        agent = _make_agent([_Response(text="the answer is 42")], memory_dir=self.tmp)
        list(agent.run_stream("what is the answer?"))
        self.assertEqual(len(agent.memory), 1)
        note = agent.memory.get_document("turn-0")["text"]
        self.assertIn("what is the answer?", note)
        self.assertIn("the answer is 42", note)

    def test_turn_index_starts_at_zero(self):
        agent = _make_agent([_Response(text="one"), _Response(text="two")], memory_dir=self.tmp)
        list(agent.run_stream("first"))
        list(agent.run_stream("second"))
        self.assertIsNotNone(agent.memory.get_document("turn-0"))
        self.assertIsNotNone(agent.memory.get_document("turn-1"))

    def test_memory_is_persisted_to_disk(self):
        agent = _make_agent([_Response(text="stored")], memory_dir=self.tmp)
        list(agent.run_stream("remember this"))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "vector_index.json")))

    def test_prior_memory_is_recalled_into_the_system_prompt(self):
        agent = _make_agent([_Response(text="ok")], memory_dir=self.tmp)
        agent.remember("note-1", "the deployment password rotates every friday")
        self.assertEqual(agent.recall("deployment password rotation", top_k=1)[0]["doc_id"], "note-1")

        captured = {}

        def capture(plan, memories=None):
            captured["memories"] = memories
            return "system"

        agent._build_config = capture
        list(agent.run_stream("when does the password rotate?"))
        self.assertTrue(captured["memories"])
        self.assertEqual(captured["memories"][0]["doc_id"], "note-1")

    def test_no_recall_when_memory_disabled(self):
        agent = _make_agent([_Response(text="ok")], memory_dir=self.tmp)
        agent.memory_enabled = False
        agent.remember("note-1", "should not be stored")
        self.assertEqual(len(agent.memory), 0)
        self.assertEqual(agent.recall("anything"), [])

    def test_tool_usage_is_recorded_in_the_note(self):
        agent = _make_agent([
            _Response(function_calls=[_Call("basic_calculate", {"expression": "6 * 7"})]),
            _Response(text="42"),
        ], memory_dir=self.tmp)
        list(agent.run_stream("what is 6*7"))
        note = agent.memory.get_document("turn-0")["text"]
        self.assertIn("basic_calculate", note)
        self.assertEqual(agent.memory.get_document("turn-0")["metadata"]["tools"], "basic_calculate")

    def test_last_tool_log_is_exposed_after_a_run(self):
        agent = _make_agent([
            _Response(function_calls=[_Call("basic_calculate", {"expression": "6 * 7"})]),
            _Response(text="42"),
        ], memory_dir=self.tmp)
        list(agent.run_stream("what is 6*7"))
        self.assertEqual(agent.last_tool_log[0]["tool"], "basic_calculate")
        self.assertEqual(agent.last_tool_log[0]["result"], "42")

    def test_real_ocr_tool_is_reachable_through_the_loop(self):
        """End-to-end: a function call to ocr_image reaches the real tool."""
        agent = _make_agent([
            _Response(function_calls=[_Call("ocr_image", {"file_path": "/definitely/missing.png"})]),
            _Response(text="handled"),
        ], memory_dir=self.tmp)
        list(agent.run_stream("read that image"))
        result = agent.last_tool_log[0]["result"]
        # Which error surfaces depends on the host: a missing input file, or a
        # missing tesseract binary on CI images. Either proves the call reached
        # the real tool instead of the old no-op stub.
        self.assertTrue(
            "file not found" in result or "OCR unavailable" in result,
            f"unexpected tool result: {result!r}",
        )


class TestAgentEvents(unittest.TestCase):
    def test_serialization(self):
        event = AgentEvent("tool_call", "run_shell({'command': 'ls'})", tool="run_shell", args={"command": "ls"})
        payload = event.to_dict()
        self.assertEqual(payload["type"], "tool_call")
        self.assertEqual(payload["tool"], "run_shell")
        self.assertEqual(payload["args"], {"command": "ls"})


if __name__ == "__main__":
    unittest.main()
