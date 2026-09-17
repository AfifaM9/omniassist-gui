import os
import unittest
from unittest.mock import patch

from core.agent import OmniAssist


class TestOmniAssistCore(unittest.TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False)
    def test_agent_initialization(self):
        agent = OmniAssist(api_key="test-key")
        self.assertIsNotNone(agent.state)
        self.assertIsNotNone(agent.tool_registry)
        self.assertFalse(agent.offline)

    def test_agent_initialization_without_key_uses_offline_mode(self):
        with patch.dict(os.environ, {}, clear=True):
            agent = OmniAssist()
        self.assertTrue(agent.offline)
        self.assertIsNotNone(agent.client)

    def test_config_is_loaded(self):
        agent = OmniAssist(api_key="test-key")
        self.assertEqual(agent.model_id, "gemini-3.5-flash-lite")
        self.assertIn("gemini-3.1-flash-lite", agent.fallback_models)
        self.assertEqual(agent.max_iterations, 10)


if __name__ == "__main__":
    unittest.main()
