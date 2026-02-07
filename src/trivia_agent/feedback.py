"""Feedback providers for the trivia agent.

Feedback providers deliver ongoing guidance during agent execution, observing
the agent's trajectory and injecting soft course-correction when needed.
Unlike tool policies (see tools.py) which gate calls based on preconditions,
feedback providers offer advisory messages that the agent can incorporate
into its reasoning.

This module provides:

- **TriviaHostReminder**: A custom feedback provider that monitors tool call
  count and reminds the agent to give direct answers from its loaded skills
  instead of over-researching.

- **build_feedback_providers()**: Factory function that assembles the complete
  feedback configuration including both built-in and custom providers.

Usage:
    Import and call `build_feedback_providers()` during agent setup to get
    a tuple of configured providers ready for the WINK AgentLoop::

        from trivia_agent.feedback import build_feedback_providers

        providers = build_feedback_providers()
        # Pass to AgentLoop or session configuration

See Also:
    - weakincentives.prompt.DeadlineFeedback: Built-in time awareness provider
    - weakincentives.prompt.FeedbackProviderConfig: Wrapper for provider + trigger
    - weakincentives.prompt.FeedbackTrigger: Controls when feedback is checked
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
    """Custom feedback provider that reminds the agent to give direct answers.

    This provider monitors the agent's tool call count and injects guidance
    when the agent appears to be overthinking instead of providing the secret
    answer directly. Since the trivia agent already knows the answers from
    loaded skills, excessive tool usage indicates the agent needs redirection.

    Implements the WINK FeedbackProvider protocol with `name`, `should_run`,
    and `provide` methods. Use with `FeedbackProviderConfig` to control
    when feedback is delivered.

    Attributes:
        max_calls_before_reminder: Number of tool calls before triggering a
            reminder. Defaults to 5. Lower values provide earlier intervention;
            higher values allow more exploration before nudging.

    Example:
        >>> from weakincentives.prompt import FeedbackProviderConfig, FeedbackTrigger
        >>> reminder = TriviaHostReminder(max_calls_before_reminder=3)
        >>> config = FeedbackProviderConfig(
        ...     provider=reminder,
        ...     trigger=FeedbackTrigger(every_n_calls=2),
        ... )
    """

    max_calls_before_reminder: int = 5

    @property
    def name(self) -> str:
        """Return the unique identifier for this feedback provider.

        The name is used by WINK to track which provider generated feedback
        and to prevent duplicate feedback from the same source.

        Returns:
            str: The string "TriviaHostReminder", identifying this provider
            in logs and feedback history.
        """
        return "TriviaHostReminder"

    def should_run(self, *, context: FeedbackContext) -> bool:
        """Determine whether this provider should deliver feedback now.

        Evaluates the current execution context to decide if a reminder is
        warranted. Returns True when tool calls exceed the threshold, but
        avoids spamming by checking calls since last feedback delivery.

        Args:
            context: The current feedback context containing execution state,
                including total tool call count, last feedback delivered, and
                methods to query calls since last feedback.

        Returns:
            bool: True if the agent has made at least `max_calls_before_reminder`
            tool calls (either total or since last feedback), False otherwise.
        """
        # Don't spam - check if we already gave feedback
        if context.last_feedback_for_provider(self.name) is not None:
            calls_since = context.tool_calls_since_last_feedback_for_provider(self.name)
            return calls_since >= self.max_calls_before_reminder
        return context.tool_call_count >= self.max_calls_before_reminder

    def provide(self, *, context: FeedbackContext) -> Feedback:
        """Generate a feedback message encouraging direct answers.

        Creates a Feedback object that reminds the agent it already knows
        the secret answers from loaded skills and should respond directly
        instead of searching or verifying. Severity escalates from "info"
        to "caution" after 10 tool calls.

        Args:
            context: The current feedback context containing execution state.
                Used to retrieve the total tool call count for the message
                and to determine appropriate severity level.

        Returns:
            Feedback: A feedback object with provider name, summary message
            including the current call count, and severity ("info" for 10
            or fewer calls, "caution" for more than 10 calls).
        """
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
    """Build the complete feedback provider configuration for the trivia agent.

    Assembles both built-in and custom feedback providers with appropriate
    triggers. This function is called during agent initialization to set up
    ongoing guidance that helps the agent stay on track.

    The configuration includes:

    1. **DeadlineFeedback** (built-in): Time-based awareness that warns when
       execution time is running low. Configured with a 30-second warning
       threshold and triggers every 15 seconds.

    2. **TriviaHostReminder** (custom): Domain-specific guidance that nudges
       the agent to give direct answers instead of over-researching.
       Triggers every 3 tool calls, activates after 5 total calls.

    Returns:
        tuple[FeedbackProviderConfig, ...]: A tuple of two configured feedback
        providers ready to be passed to the WINK AgentLoop or session builder.

    Example:
        >>> from trivia_agent.feedback import build_feedback_providers
        >>> providers = build_feedback_providers()
        >>> len(providers)
        2
        >>> providers[0].provider.__class__.__name__
        'DeadlineFeedback'
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
