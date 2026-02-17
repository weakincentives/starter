"""Tests for trivia agent adapters."""

from unittest.mock import MagicMock

import pytest
from weakincentives.adapters import ProviderAdapter
from weakincentives.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter
from weakincentives.adapters.codex_app_server import CodexAppServerAdapter
from weakincentives.adapters.opencode_acp import OpenCodeACPAdapter
from weakincentives.prompt import TaskCompletionResult

from trivia_agent.adapters import (
    ADAPTER_ENV,
    SimpleTaskCompletionChecker,
    create_adapter,
    resolve_adapter_choice,
)


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


class TestResolveAdapterChoice:
    """Tests for resolve_adapter_choice function."""

    def test_defaults_to_claude(self) -> None:
        """Test that missing env var defaults to 'claude'."""
        assert resolve_adapter_choice({}) == "claude"

    def test_empty_string_defaults_to_claude(self) -> None:
        """Test that empty string defaults to 'claude'."""
        assert resolve_adapter_choice({ADAPTER_ENV: ""}) == "claude"

    def test_whitespace_defaults_to_claude(self) -> None:
        """Test that whitespace-only string defaults to 'claude'."""
        assert resolve_adapter_choice({ADAPTER_ENV: "  "}) == "claude"

    def test_reads_claude(self) -> None:
        """Test reading 'claude' from env."""
        assert resolve_adapter_choice({ADAPTER_ENV: "claude"}) == "claude"

    def test_reads_codex(self) -> None:
        """Test reading 'codex' from env."""
        assert resolve_adapter_choice({ADAPTER_ENV: "codex"}) == "codex"

    def test_reads_opencode(self) -> None:
        """Test reading 'opencode' from env."""
        assert resolve_adapter_choice({ADAPTER_ENV: "opencode"}) == "opencode"

    def test_rejects_invalid_value(self) -> None:
        """Test that invalid adapter values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid TRIVIA_ADAPTER='bogus'"):
            resolve_adapter_choice({ADAPTER_ENV: "bogus"})


class TestCreateAdapter:
    """Tests for create_adapter function."""

    def test_returns_claude_adapter_by_default(self) -> None:
        """Test that create_adapter returns a Claude adapter by default."""
        adapter = create_adapter()
        assert isinstance(adapter, ClaudeAgentSDKAdapter)

    def test_returns_claude_adapter_explicitly(self) -> None:
        """Test that create_adapter('claude') returns a Claude adapter."""
        adapter = create_adapter("claude")
        assert isinstance(adapter, ClaudeAgentSDKAdapter)

    def test_returns_codex_adapter(self) -> None:
        """Test that create_adapter('codex') returns a Codex adapter."""
        adapter = create_adapter("codex")
        assert isinstance(adapter, CodexAppServerAdapter)

    def test_returns_opencode_adapter(self) -> None:
        """Test that create_adapter('opencode') returns an OpenCode adapter."""
        adapter = create_adapter("opencode")
        assert isinstance(adapter, OpenCodeACPAdapter)

    def test_all_adapters_are_provider_adapters(self) -> None:
        """Test that all adapter types satisfy the ProviderAdapter protocol."""
        for choice in ("claude", "codex", "opencode"):
            adapter = create_adapter(choice)  # type: ignore[arg-type]
            assert isinstance(adapter, ProviderAdapter)

    def test_claude_adapter_has_client_config(self) -> None:
        """Test that claude adapter is configured with client config."""
        adapter = create_adapter("claude")
        assert adapter._client_config is not None  # type: ignore[union-attr]

    def test_claude_adapter_no_task_completion_on_client_config(self) -> None:
        """Test that task completion checker is not on client config (moved to prompt)."""
        adapter = create_adapter("claude")
        assert not hasattr(adapter._client_config, "task_completion_checker")  # type: ignore[union-attr]
