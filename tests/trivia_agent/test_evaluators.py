"""Tests for custom evaluators."""

from unittest.mock import MagicMock

from trivia_agent.evaluators import trivia_evaluator
from trivia_agent.models import TriviaResponse


class TestTriviaEvaluator:
    """Tests for trivia_evaluator function."""

    def test_passes_when_secret_in_answer(self) -> None:
        """Test evaluator passes when secret is in answer."""
        output = TriviaResponse(answer="The secret number is 42")
        session = MagicMock()

        score = trivia_evaluator(output, "42", session)

        assert score.passed is True
        assert score.value > 0.5

    def test_fails_when_secret_not_in_answer(self) -> None:
        """Test evaluator fails when secret is not in answer."""
        output = TriviaResponse(answer="I don't know the secret")
        session = MagicMock()

        score = trivia_evaluator(output, "42", session)

        assert score.passed is False
        assert "wrong" in score.reason.lower()

    def test_case_insensitive_matching(self) -> None:
        """Test that matching is case insensitive."""
        output = TriviaResponse(answer="The secret word is BANANA")
        session = MagicMock()

        score = trivia_evaluator(output, "banana", session)

        assert score.passed is True

    def test_brief_answer_gets_high_score(self) -> None:
        """Test that brief answers get high brevity score."""
        output = TriviaResponse(answer="42")
        session = MagicMock()

        score = trivia_evaluator(output, "42", session)

        assert score.value >= 0.9  # Both correctness and brevity high

    def test_medium_answer_gets_lower_score(self) -> None:
        """Test that medium-length answers get penalized."""
        # Create a medium answer (>20 but <=50 words)
        medium_answer = "The secret is 42. " + "word " * 30
        output = TriviaResponse(answer=medium_answer)
        session = MagicMock()

        score = trivia_evaluator(output, "42", session)

        # Should still pass (has correct answer) but lower overall score
        assert score.passed is True
        assert score.value < 1.0  # Penalized for length

    def test_verbose_answer_gets_lowest_score(self) -> None:
        """Test that verbose answers get lowest brevity score."""
        # Create a verbose answer (>50 words)
        verbose_answer = "42 " + "word " * 60
        output = TriviaResponse(answer=verbose_answer)
        session = MagicMock()

        score = trivia_evaluator(output, "42", session)

        assert score.passed is True  # Correct answer
        assert score.value < 0.8  # Significantly penalized

    def test_includes_reasons_in_score(self) -> None:
        """Test that score includes explanatory reasons."""
        output = TriviaResponse(answer="42")
        session = MagicMock()

        score = trivia_evaluator(output, "42", session)

        assert score.reason is not None
        assert len(score.reason) > 0

    def test_works_without_session(self) -> None:
        """Test evaluator works when session is None."""
        output = TriviaResponse(answer="42")

        score = trivia_evaluator(output, "42", session=None)

        assert score.passed is True
        assert score.value == 1.0
