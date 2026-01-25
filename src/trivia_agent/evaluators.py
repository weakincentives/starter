"""Custom evaluators for the trivia agent.

This module provides evaluation functions for scoring trivia agent responses.
Evaluators are used by WINK's eval system to automatically grade agent outputs
against expected answers.

Key capabilities:
    - Multi-criteria scoring (correctness + brevity)
    - Session-aware evaluation for behavioral checks
    - Configurable pass/fail thresholds

Usage:
    Evaluators are registered in the EvalLoop and called automatically during
    evaluation runs. They receive the agent's structured output and expected
    answer, returning a Score object.

    To run an evaluation::

        make dispatch-eval QUESTION="What is the secret number?" EXPECTED="42"

For session-aware behavioral checks (e.g., inspecting tool usage), WINK's
slice architecture provides typed access via ``session[SliceClass].latest()``.
See the SESSIONS spec for details on dispatching events and querying state.

See Also:
    - ``weakincentives.evals.Score``: The score dataclass returned by evaluators
    - ``trivia_agent.eval_loop``: EvalLoop configuration using this evaluator
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
    """Evaluate a trivia agent response for correctness and quality.

    Scores the agent's answer against the expected secret using two criteria:

    1. **Correctness** (50% of score): The expected secret must appear in the
       agent's answer (case-insensitive substring match). This is a hard
       requirement - incorrect answers always fail regardless of other scores.

    2. **Brevity** (50% of score): Trivia answers should be concise.
       - 20 words or fewer: 1.0 (perfect)
       - 21-50 words: 0.7 (acceptable)
       - 51+ words: 0.3 (too verbose)

    The final score is the average of both criteria. A response passes if:
    - The total score is >= 0.6, AND
    - The correctness check passed (secret was found)

    Args:
        output: The agent's structured response containing the answer text.
            Must have an ``answer`` attribute (str) with the trivia answer.
        expected: The expected secret answer to check for (e.g., "42", "banana").
            Matching is case-insensitive and uses substring containment.
        session: Optional read-only session view for behavioral checks.
            Use ``session[SliceClass].latest()`` to inspect tool usage,
            state changes, or other session data. Defaults to None.

    Returns:
        A ``Score`` object with:
            - ``value`` (float): Combined score from 0.0 to 1.0
            - ``passed`` (bool): True if answer is correct and score >= 0.6
            - ``reason`` (str): Semicolon-separated explanations for each criterion

    Example:
        Direct usage (typically called by WINK's eval system)::

            from trivia_agent.evaluators import trivia_evaluator
            from trivia_agent.models import TriviaResponse

            response = TriviaResponse(answer="The secret number is 42!")
            score = trivia_evaluator(response, expected="42")

            print(score.passed)  # True
            print(score.value)   # 1.0 (correct and brief)
            print(score.reason)  # "Correct! Secret '42' found; Perfect brevity (6 words)"

    Note:
        This evaluator is registered in ``eval_loop.py`` and runs automatically
        during ``make dispatch-eval`` commands. You typically don't call it
        directly unless writing custom evaluation scripts.
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
