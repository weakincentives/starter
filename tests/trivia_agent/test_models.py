"""Tests for trivia agent models."""

import dataclasses

import pytest

from trivia_agent.models import TriviaRequest, TriviaResponse


class TestTriviaRequest:
    """Tests for TriviaRequest dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation with required field."""
        request = TriviaRequest(question="What is Python?")
        assert request.question == "What is Python?"

    def test_frozen(self) -> None:
        """Test that the dataclass is immutable."""
        request = TriviaRequest(question="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            request.question = "changed"  # type: ignore[misc]

    def test_is_dataclass(self) -> None:
        """Test that TriviaRequest is a dataclass."""
        assert dataclasses.is_dataclass(TriviaRequest)
        assert dataclasses.is_dataclass(TriviaRequest(question="test"))

    def test_equality(self) -> None:
        """Test equality comparison."""
        r1 = TriviaRequest(question="test")
        r2 = TriviaRequest(question="test")
        r3 = TriviaRequest(question="different")
        assert r1 == r2
        assert r1 != r3


class TestTriviaResponse:
    """Tests for TriviaResponse dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation with required field."""
        response = TriviaResponse(answer="Python is a programming language.")
        assert response.answer == "Python is a programming language."

    def test_frozen(self) -> None:
        """Test that the dataclass is immutable."""
        response = TriviaResponse(answer="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            response.answer = "changed"  # type: ignore[misc]

    def test_is_dataclass(self) -> None:
        """Test that TriviaResponse is a dataclass."""
        assert dataclasses.is_dataclass(TriviaResponse)
        assert dataclasses.is_dataclass(TriviaResponse(answer="test"))

    def test_equality(self) -> None:
        """Test equality comparison."""
        r1 = TriviaResponse(answer="test")
        r2 = TriviaResponse(answer="test")
        r3 = TriviaResponse(answer="different")
        assert r1 == r2
        assert r1 != r3
