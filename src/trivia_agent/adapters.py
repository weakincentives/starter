"""Runtime adapter configuration for the trivia agent.

This module provides the adapter layer between the trivia agent and the WINK
runtime. The adapter configures how the agent interacts with the Claude model,
handles task completion, and manages execution isolation.

Key components:
    - ``SimpleTaskCompletionChecker``: Pass-through completion checker (used by prompt)
    - ``create_adapter``: Factory function to build configured adapters

The default model is Claude Sonnet, accessed via the "sonnet" alias.

Usage:
    >>> from trivia_agent.adapters import create_adapter
    >>> adapter = create_adapter()
    >>> # Pass adapter to AgentLoop.create() or EvalLoop.create()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from weakincentives.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter
from weakincentives.adapters.claude_agent_sdk.config import ClaudeAgentSDKClientConfig
from weakincentives.prompt import TaskCompletionContext, TaskCompletionResult

from trivia_agent.models import TriviaResponse

if TYPE_CHECKING:
    from weakincentives.adapters.claude_agent_sdk.isolation import IsolationConfig

# Use Claude Sonnet (alias)
DEFAULT_MODEL = "sonnet"


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


def create_adapter(
    *,
    isolation: IsolationConfig | None = None,
    cwd: str | None = None,
) -> ClaudeAgentSDKAdapter[TriviaResponse]:
    """Create and configure a Claude Agent SDK adapter for the trivia agent.

    Factory function that assembles all components needed to run the trivia
    agent: model selection, isolation configuration, and working directory
    setup. The returned adapter is ready to be passed to a WINK AgentLoop
    or EvalLoop.

    The adapter is configured with:
        - Model: Claude Sonnet (via the "sonnet" alias)
        - Response type: TriviaResponse (structured output schema)

    Note: Task completion checking is declared on the PromptTemplate (see
    agent_loop.py), not on the adapter config.

    Args:
        isolation: Optional isolation configuration that controls the agent's
            execution environment. When provided, specifies:
            - Skills to load (e.g., secret-trivia skill with answers)
            - Sandbox settings restricting file/network access
            If None, the agent runs without isolation constraints.
        cwd: Optional working directory path for the agent. The agent will
            execute with this directory as its current working directory.
            If None, uses the default working directory.

    Returns:
        ClaudeAgentSDKAdapter[TriviaResponse]: A fully configured adapter
            instance typed to produce TriviaResponse structured output.
            Pass this adapter to ``AgentLoop.create()`` or ``EvalLoop.create()``
            to run the trivia agent.

    Example:
        >>> from trivia_agent.isolation import create_isolation_config
        >>> isolation = create_isolation_config()
        >>> adapter = create_adapter(isolation=isolation, cwd="/path/to/workspace")
        >>> # Use adapter with AgentLoop
        >>> loop = AgentLoop.create(adapter=adapter, sections=[...])
    """
    client_config = ClaudeAgentSDKClientConfig(
        isolation=isolation,
        cwd=cwd,
    )
    return ClaudeAgentSDKAdapter[TriviaResponse](
        model=DEFAULT_MODEL,
        client_config=client_config,
    )
