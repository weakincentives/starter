"""Runtime adapter configuration for the trivia agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from weakincentives.adapters.claude_agent_sdk import (
    ClaudeAgentSDKAdapter,
    TaskCompletionContext,
    TaskCompletionResult,
)
from weakincentives.adapters.claude_agent_sdk.config import ClaudeAgentSDKClientConfig

from trivia_agent.models import TriviaResponse

if TYPE_CHECKING:
    from weakincentives.adapters.claude_agent_sdk.isolation import IsolationConfig

# Use Claude Sonnet (alias)
DEFAULT_MODEL = "sonnet"


class SimpleTaskCompletionChecker:
    """A simple task completion checker that always succeeds.

    For the trivia agent, once structured output is produced, the task is complete.
    No additional verification is needed.
    """

    def check(self, context: TaskCompletionContext) -> TaskCompletionResult:
        """Always returns ok() since trivia tasks complete with structured output.

        Args:
            context: Task completion context (unused).

        Returns:
            TaskCompletionResult.ok() indicating the task is complete.
        """
        return TaskCompletionResult.ok()


def create_adapter(
    *,
    isolation: IsolationConfig | None = None,
    cwd: str | None = None,
) -> ClaudeAgentSDKAdapter[TriviaResponse]:
    """Create a Claude Agent SDK adapter for the trivia agent.

    Args:
        isolation: Optional isolation configuration with skills and sandbox.
        cwd: Optional working directory for the agent.

    Returns:
        A configured ClaudeAgentSDKAdapter instance.
    """
    checker = SimpleTaskCompletionChecker()
    client_config = ClaudeAgentSDKClientConfig(
        task_completion_checker=checker,
        isolation=isolation,
        cwd=cwd,
    )
    return ClaudeAgentSDKAdapter[TriviaResponse](
        model=DEFAULT_MODEL,
        client_config=client_config,
    )
