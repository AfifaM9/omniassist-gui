import unittest

from mcp_tools.registry import MCPToolRegistry


class TestMCPTools(unittest.TestCase):
    def setUp(self):
        self.registry = MCPToolRegistry()

    def test_registry_loading(self):
        self.assertGreater(len(self.registry.tools), 0)

    def test_only_functions_are_registered(self):
        """Classes imported by a tool module must not leak into the registry."""
        import inspect

        for name, tool in self.registry.tools.items():
            self.assertTrue(inspect.isfunction(tool), f"{name} is not a function")

    def test_missing_dependency_does_not_break_discovery(self):
        """A failing module is reported but the other tools still load."""
        self.assertNotIn("registry", self.registry.load_errors)
        for name in ("run_shell", "write_file", "basic_calculate"):
            self.assertIn(name, self.registry.tools)

    def test_describe_exposes_parameters(self):
        described = {t["name"]: t for t in self.registry.describe()}
        self.assertIn("run_shell", described)
        self.assertIn("command", described["run_shell"]["parameters"])
        self.assertTrue(described["run_shell"]["parameters"]["command"]["required"])

    def test_execute_tool_runs_the_function(self):
        result = self.registry.execute_tool("basic_calculate", expression="2 + 2")
        self.assertEqual(result, "4")

    def test_execute_unknown_tool_returns_error(self):
        self.assertIn("not found", self.registry.execute_tool("nope"))


if __name__ == "__main__":
    unittest.main()
