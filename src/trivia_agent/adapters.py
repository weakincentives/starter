"""Runtime adapter configuration for the trivia agent.

This module provides the adapter layer between the trivia agent and the WINK
runtime. The adapter configures how the agent interacts with the Claude model,
handles task completion, and manages execution isolation.

Key components:
    - ``SimpleTaskCompletionChecker``: Pass-through completion checker (used by prompt)
    - ``create_adapter``: Factory function to build configured adapters
    - ``AdapterChoice``: Literal type for selecting the adapter backend
    - ``resolve_adapter_choice``: Reads TRIVIA_ADAPTER env var

The default adapter is ``claude`` (Claude Agent SDK), accessed via the "sonnet" alias.

Usage:
    >>> from trivia_agent.adapters import create_adapter, resolve_adapter_choice
    >>> adapter_choice = resolve_adapter_choice(os.environ)
    >>> adapter = create_adapter(adapter_choice, isolation=isolation, cwd=cwd)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from weakincentives.adapters import ProviderAdapter
from weakincentives.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter
from weakincentives.adapters.claude_agent_sdk.config import ClaudeAgentSDKClientConfig
from weakincentives.prompt import TaskCompletionContext, TaskCompletionResult

from trivia_agent.models import TriviaResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from weakincentives.adapters.claude_agent_sdk.isolation import IsolationConfig

# Use Claude Sonnet (alias)
DEFAULT_MODEL = "sonnet"

# Adapter selection
AdapterChoice = Literal["claude", "codex", "opencode"]
ADAPTER_ENV = "TRIVIA_ADAPTER"
_VALID_ADAPTERS: set[str] = {"claude", "codex", "opencode"}


class SimpleTaskCompletionChecker:
    """Task completion checker that unconditionally marks tasks as complete.

    This checker implements a pass-through completion strategy where any task
    that produces structured output is considered complete. It is designed for
    scenarios where the structured output itself (e.g., TriviaResponse) serves
    as sufficient proof of task completion.

    Use this checker when:
        - Task success is determined solely by producing valid structured output
        - No additional validation logic is required after response generation
        - You want the simplest possible completion behavior

    For more complex scenarios requiring validation (e.g., checking answer
    correctness, verifying external state), implement a custom checker with
    conditional logic in the ``check`` method.

    Example:
        >>> checker = SimpleTaskCompletionChecker()
        >>> result = checker.check(context)
        >>> assert result.is_ok()
    """

    def check(self, context: TaskCompletionContext) -> TaskCompletionResult:
        """Evaluate task completion and return success unconditionally.

        This method is called by the WINK runtime after the agent produces
        structured output. It always returns ``TaskCompletionResult.ok()``,
        signaling that no further agent iterations are needed.

        Args:
            context: The task completion context provided by the runtime.
                Contains information about the current task state, but is
                unused in this implementation since completion is unconditional.

        Returns:
            TaskCompletionResult: Always returns ``TaskCompletionResult.ok()``
                indicating successful task completion. The agent will stop
                processing and return its response to the caller.
        """
        return TaskCompletionResult.ok()


def resolve_adapter_choice(env: Mapping[str, str]) -> AdapterChoice:
    """Read the adapter choice from the environment.

    Reads the ``TRIVIA_ADAPTER`` environment variable and validates it against
    the supported adapter values (``claude``, ``codex``, ``opencode``).
    Defaults to ``claude`` if the variable is not set or is empty.

    Args:
        env: A mapping of environment variable names to values (typically os.environ).

    Returns:
        The validated adapter choice.

    Raises:
        ValueError: If the env var value is not one of the supported adapters.
    """
    raw = env.get(ADAPTER_ENV, "").strip()
    if not raw:
        return "claude"
    if raw not in _VALID_ADAPTERS:
        msg = f"Invalid {ADAPTER_ENV}={raw!r}. Must be one of: claude, codex, opencode"
        raise ValueError(msg)
    return cast("AdapterChoice", raw)


def _create_claude_adapter(
    *,
    isolation: IsolationConfig | None,
    cwd: str | None,
) -> ProviderAdapter[TriviaResponse]:
    """Create a Claude Agent SDK adapter."""
    client_config = ClaudeAgentSDKClientConfig(
        isolation=isolation,
        cwd=cwd,
    )
    return cast(
        "ProviderAdapter[TriviaResponse]",
        ClaudeAgentSDKAdapter[TriviaResponse](
            model=DEFAULT_MODEL,
            client_config=client_config,
        ),
    )


def _create_codex_adapter(
    *,
    cwd: str | None,
) -> ProviderAdapter[TriviaResponse]:
    """Create a Codex App Server adapter."""
    from weakincentives.adapters.codex_app_server import (
        CodexAppServerAdapter,
        CodexAppServerClientConfig,
    )

    client_config = CodexAppServerClientConfig(
        cwd=cwd,
        approval_policy="never",
    )
    return cast(
        "ProviderAdapter[TriviaResponse]",
        CodexAppServerAdapter[TriviaResponse](client_config=client_config),
    )


def _create_opencode_adapter(
    *,
    cwd: str | None,
) -> ProviderAdapter[TriviaResponse]:
    """Create an OpenCode ACP adapter."""
    from weakincentives.adapters.opencode_acp import (
        OpenCodeACPAdapter,
        OpenCodeACPClientConfig,
    )

    client_config = OpenCodeACPClientConfig(cwd=cwd)
    return cast(
        "ProviderAdapter[TriviaResponse]",
        OpenCodeACPAdapter[TriviaResponse](client_config=client_config),
    )


def create_adapter(
    adapter: AdapterChoice = "claude",
    *,
    isolation: IsolationConfig | None = None,
    cwd: str | None = None,
) -> ProviderAdapter[TriviaResponse]:
    """Create and configure a provider adapter for the trivia agent.

    Factory function that assembles all components needed to run the trivia
    agent with the selected backend. The returned adapter is ready to be
    passed to a WINK AgentLoop or EvalLoop.

    Supported adapters:
        - ``claude``: Claude Agent SDK (default) - uses Claude Sonnet model
        - ``codex``: Codex App Server - uses OpenAI Codex
        - ``opencode``: OpenCode ACP - uses ACP protocol

    Args:
        adapter: Which adapter backend to use. Defaults to ``"claude"``.
        isolation: Optional isolation configuration for the Claude adapter.
            Only used when ``adapter="claude"``. Ignored for other adapters.
        cwd: Optional working directory path for the agent.

    Returns:
        ProviderAdapter[TriviaResponse]: A fully configured adapter instance.
    """
    if adapter == "claude":
        return _create_claude_adapter(isolation=isolation, cwd=cwd)
    if adapter == "codex":
        return _create_codex_adapter(cwd=cwd)
    # opencode
    return _create_opencode_adapter(cwd=cwd)
