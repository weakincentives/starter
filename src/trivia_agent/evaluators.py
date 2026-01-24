"""Custom evaluators for the trivia agent.

This module demonstrates:
- Custom scoring logic with multiple criteria
- Session-aware evaluator signature (for behavioral checks)

Evaluators score agent outputs against expectations. The trivia_evaluator
checks answer correctness and brevity.

For session-aware behavioral checks (e.g., inspecting tool usage), WINK's
slice architecture provides typed access via `session[SliceClass].latest()`.
See the SESSIONS spec for details on dispatching events and querying state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from weakincentives.evals import Score

if TYPE_CHECKING:
    from trivia_agent.models import TriviaResponse


def trivia_evaluator(
    output: TriviaResponse,
    expected: str,
    session: Any = None,
) -> Score:
    """Evaluator for trivia responses.

    This evaluator checks:
    1. The secret answer is correct (must contain expected value)
    2. Response is concise (trivia answers should be brief)

    The session parameter enables behavioral checks (e.g., inspecting tool
    usage from session state) when WINK's slice architecture is used.

    Args:
        output: The agent's response.
        expected: The expected secret answer.
        session: Read-only view of the session (for behavioral checks).

    Returns:
        Score with value 0.0-1.0, pass/fail, and explanation.
    """
    scores: list[tuple[float, str]] = []

    # Check 1: Correct secret - does answer contain the expected secret?
    if expected.lower() in output.answer.lower():
        scores.append((1.0, f"Correct! Secret '{expected}' found"))
    else:
        scores.append((0.0, f"Wrong! Expected secret '{expected}' not in answer"))

    # Check 2: Conciseness - trivia answers should be brief
    word_count = len(output.answer.split())
    if word_count <= 20:
        scores.append((1.0, f"Perfect brevity ({word_count} words)"))
    elif word_count <= 50:
        scores.append((0.7, f"Acceptable length ({word_count} words)"))
    else:
        scores.append((0.3, f"Too verbose for trivia ({word_count} words)"))

    # Aggregate scores
    total_value = sum(s[0] for s in scores) / len(scores)
    reasons = [s[1] for s in scores]
    passed = total_value >= 0.6 and scores[0][0] > 0  # Must have correct secret

    return Score(
        value=total_value,
        passed=passed,
        reason="; ".join(reasons),
    )
