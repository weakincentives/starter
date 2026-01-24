"""Feedback providers for the trivia agent.

Feedback providers deliver ongoing progress guidance during agent execution.
While tool policies (see tools.py) gate calls based on preconditions, feedback
providers observe trajectory and inject soft guidance for course-correction.

This module demonstrates:
- Built-in DeadlineFeedback for time awareness
- Custom feedback provider for domain-specific guidance
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from weakincentives.prompt import (
    DeadlineFeedback,
    Feedback,
    FeedbackProviderConfig,
    FeedbackTrigger,
)

if TYPE_CHECKING:
    from weakincentives.prompt import FeedbackContext


@dataclass(frozen=True, slots=True)
class TriviaHostReminder:
    """Remind the agent to stay in character as trivia host.

    This custom feedback provider demonstrates how to write domain-specific
    guidance. It monitors tool call count and injects reminders if the agent
    seems to be overthinking instead of just giving the secret answer.

    Attributes:
        max_calls_before_reminder: Trigger reminder after this many calls.
    """

    max_calls_before_reminder: int = 5

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return "TriviaHostReminder"

    def should_run(self, *, context: FeedbackContext) -> bool:
        """Check if reminder should be delivered.

        Only runs if we haven't already delivered feedback recently.
        """
        # Don't spam - check if we already gave feedback
        if context.last_feedback is not None:
            calls_since = context.tool_calls_since_last_feedback()
            return calls_since >= self.max_calls_before_reminder
        return context.tool_call_count >= self.max_calls_before_reminder

    def provide(self, *, context: FeedbackContext) -> Feedback:
        """Generate the feedback message."""
        call_count = context.tool_call_count
        summary = (
            f"You have made {call_count} tool calls. "
            "Remember: you already know the secret answers from your skills. "
            "Just give the answer directly - no need to search or verify!"
        )
        return Feedback(
            provider_name=self.name,
            summary=summary,
            severity="caution" if call_count > 10 else "info",
        )


def build_feedback_providers() -> tuple[FeedbackProviderConfig, ...]:
    """Build the feedback provider configuration for the trivia agent.

    Returns:
        Tuple of configured feedback providers:
        - DeadlineFeedback: Reports remaining time every 15 seconds
        - TriviaHostReminder: Encourages direct answers after 5 tool calls
    """
    return (
        # Built-in deadline feedback - warns when time is running low
        FeedbackProviderConfig(
            provider=DeadlineFeedback(warning_threshold_seconds=30),
            trigger=FeedbackTrigger(every_n_seconds=15),
        ),
        # Custom trivia host reminder
        FeedbackProviderConfig(
            provider=TriviaHostReminder(max_calls_before_reminder=5),
            trigger=FeedbackTrigger(every_n_calls=3),
        ),
    )
