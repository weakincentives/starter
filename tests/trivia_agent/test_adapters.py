"""Tests for trivia agent adapters."""

from unittest.mock import MagicMock

from weakincentives.adapters.claude_agent_sdk import (
    ClaudeAgentSDKAdapter,
    TaskCompletionResult,
)

from trivia_agent.adapters import SimpleTaskCompletionChecker, create_adapter


class TestSimpleTaskCompletionChecker:
    """Tests for SimpleTaskCompletionChecker class."""

    def test_check_returns_ok(self) -> None:
        """Test that check always returns TaskCompletionResult.ok()."""
        checker = SimpleTaskCompletionChecker()
        mock_context = MagicMock()
        result = checker.check(mock_context)
        assert result == TaskCompletionResult.ok()

    def test_check_ignores_context(self) -> None:
        """Test that check doesn't use any context fields."""
        checker = SimpleTaskCompletionChecker()
        # Pass a completely empty mock
        result = checker.check(MagicMock())
        assert result.complete is True
        assert result.feedback is None


class TestCreateAdapter:
    """Tests for create_adapter function."""

    def test_returns_claude_agent_sdk_adapter(self) -> None:
        """Test that create_adapter returns a ClaudeAgentSDKAdapter."""
        adapter = create_adapter()
        assert isinstance(adapter, ClaudeAgentSDKAdapter)

    def test_adapter_uses_default_model(self) -> None:
        """Test that adapter uses default model configuration."""
        adapter = create_adapter()
        # The adapter should be created without errors
        assert adapter is not None

    def test_adapter_has_client_config(self) -> None:
        """Test that adapter is configured with task completion checker."""
        adapter = create_adapter()
        # Verify adapter was created with client config
        assert adapter._client_config is not None
        assert adapter._client_config.task_completion_checker is not None

    def test_adapter_task_completion_checker_is_simple_checker(self) -> None:
        """Test that the task completion checker is SimpleTaskCompletionChecker."""
        adapter = create_adapter()
        checker = adapter._client_config.task_completion_checker
        assert isinstance(checker, SimpleTaskCompletionChecker)
