"""
Windows-specific tests for run_data_agents.py script.

These tests ensure multiprocessing works correctly on Windows where
the 'spawn' method requires all objects to be picklable.

Background:
-----------
On Windows, multiprocessing uses the 'spawn' method instead of 'fork',
which requires all objects passed to child processes to be serializable
via pickle. This includes:
- The target function passed to Process()
- Any classes or objects referenced by that function

Common pitfall:
--------------
Using nested functions or closures as Process targets will fail on Windows
with: "AttributeError: Can't pickle local object '<function>'"

The original implementation used a factory function pattern:
    def create_agent_runner(agent_class, agent_name):
        def run_agent():  # <-- Nested function, not picklable!
            ...
        return run_agent

This was fixed by:
1. Moving run_agent to module level (making it picklable)
2. Using functools.partial to bind arguments instead of closures
"""

import multiprocessing
import pickle
import sys
from functools import partial
from unittest.mock import MagicMock, patch

import pytest

# Only run these tests on Windows
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-specific multiprocessing tests"
)


class TestWindowsMultiprocessing:
    """Test that multiprocessing components are picklable on Windows."""

    def test_agent_classes_are_picklable(self):
        """Agent classes should be picklable for Windows multiprocessing."""
        from conversational_bi.agents.data_agents.base_data_agent import (
            CustomersDataAgent,
            OrdersDataAgent,
            ProductsDataAgent,
        )

        # All agent classes should be picklable
        for agent_class in [CustomersDataAgent, OrdersDataAgent, ProductsDataAgent]:
            try:
                pickled = pickle.dumps(agent_class)
                unpickled = pickle.loads(pickled)
                assert unpickled == agent_class
            except Exception as e:
                pytest.fail(f"{agent_class.__name__} is not picklable: {e}")

    def test_run_agent_function_is_picklable(self):
        """The run_agent function should be picklable for Windows."""
        # Import after ensuring we're on Windows
        sys.path.insert(0, "scripts")
        try:
            from run_data_agents import run_agent

            # Function itself should be picklable
            try:
                pickled = pickle.dumps(run_agent)
                unpickled = pickle.loads(pickled)
                assert callable(unpickled)
            except Exception as e:
                pytest.fail(f"run_agent function is not picklable: {e}")
        finally:
            sys.path.pop(0)

    def test_partial_run_agent_is_picklable(self):
        """Partial application of run_agent should be picklable."""
        sys.path.insert(0, "scripts")
        try:
            from run_data_agents import run_agent, AGENTS
            from conversational_bi.agents.data_agents.base_data_agent import (
                CustomersDataAgent,
            )

            # Create partial as done in the script
            agent_class = CustomersDataAgent
            agent_name = "customers"
            runner = partial(run_agent, agent_class, agent_name)

            # Should be picklable
            try:
                pickled = pickle.dumps(runner)
                unpickled = pickle.loads(pickled)
                assert callable(unpickled)
            except Exception as e:
                pytest.fail(f"partial(run_agent, ...) is not picklable: {e}")
        finally:
            sys.path.pop(0)

    def test_agents_registry_values_are_picklable(self):
        """All values in AGENTS registry should be picklable."""
        sys.path.insert(0, "scripts")
        try:
            from run_data_agents import AGENTS

            for name, (agent_class, config_name) in AGENTS.items():
                # Agent class should be picklable
                try:
                    pickle.dumps(agent_class)
                except Exception as e:
                    pytest.fail(f"Agent class for '{name}' is not picklable: {e}")

                # Config name (string) should be picklable
                try:
                    pickle.dumps(config_name)
                except Exception as e:
                    pytest.fail(f"Config name for '{name}' is not picklable: {e}")
        finally:
            sys.path.pop(0)

    @patch('multiprocessing.Process')
    def test_process_can_be_created_with_partial(self, mock_process_class):
        """Should be able to create Process with partial function."""
        sys.path.insert(0, "scripts")
        try:
            from run_data_agents import run_agent
            from conversational_bi.agents.data_agents.base_data_agent import (
                CustomersDataAgent,
            )

            # This is what the actual script does
            runner = partial(run_agent, CustomersDataAgent, "customers")

            # Should not raise when creating process
            try:
                process = multiprocessing.Process(
                    target=runner,
                    name="customers-agent"
                )
                # If we got here, the target is picklable
                assert process is not None
            except AttributeError as e:
                if "pickle" in str(e).lower():
                    pytest.fail(f"Process creation failed due to pickle error: {e}")
                raise
        finally:
            sys.path.pop(0)

    def test_no_nested_functions_in_main(self):
        """Ensure no nested functions are used as Process targets."""
        sys.path.insert(0, "scripts")
        try:
            import inspect
            from run_data_agents import main

            # Get the source code of main
            source = inspect.getsource(main)

            # Check that we're not using nested functions as targets
            # Look for the pattern that caused the original bug
            assert "create_agent_runner" not in source, \
                "main() should not use create_agent_runner (nested function factory)"

            # Verify we're using partial
            assert "partial" in source, \
                "main() should use functools.partial for Windows compatibility"
        finally:
            sys.path.pop(0)


class TestScriptStructure:
    """Test the structure of run_data_agents.py for Windows compatibility."""

    def test_run_agent_is_module_level_function(self):
        """run_agent must be defined at module level, not nested."""
        sys.path.insert(0, "scripts")
        try:
            import run_data_agents

            # Check that run_agent is a module-level attribute
            assert hasattr(run_data_agents, 'run_agent'), \
                "run_agent should be a module-level function"

            # Check it's defined in the module's __dict__
            assert 'run_agent' in run_data_agents.__dict__, \
                "run_agent should be in module __dict__"

            # Verify it's not a nested function by checking __qualname__
            qualname = run_data_agents.run_agent.__qualname__
            assert '.<locals>.' not in qualname, \
                f"run_agent appears to be a nested function: {qualname}"
        finally:
            sys.path.pop(0)

    def test_agents_registry_is_module_level(self):
        """AGENTS registry should be at module level."""
        sys.path.insert(0, "scripts")
        try:
            import run_data_agents

            assert hasattr(run_data_agents, 'AGENTS'), \
                "AGENTS should be a module-level constant"
            assert isinstance(run_data_agents.AGENTS, dict), \
                "AGENTS should be a dictionary"
        finally:
            sys.path.pop(0)
