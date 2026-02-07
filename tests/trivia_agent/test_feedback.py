"""Tests for feedback providers."""

from unittest.mock import MagicMock

from trivia_agent.feedback import TriviaHostReminder, build_feedback_providers


class TestTriviaHostReminder:
    """Tests for TriviaHostReminder feedback provider."""

    def test_name_property(self) -> None:
        """Test that name returns correct identifier."""
        reminder = TriviaHostReminder()
        assert reminder.name == "TriviaHostReminder"

    def test_should_run_first_time_below_threshold(self) -> None:
        """Test should_run returns False when below threshold on first run."""
        reminder = TriviaHostReminder(max_calls_before_reminder=5)
        context = MagicMock()
        context.last_feedback_for_provider.return_value = None
        context.tool_call_count = 3
        assert reminder.should_run(context=context) is False
        context.last_feedback_for_provider.assert_called_with("TriviaHostReminder")

    def test_should_run_first_time_at_threshold(self) -> None:
        """Test should_run returns True when at threshold on first run."""
        reminder = TriviaHostReminder(max_calls_before_reminder=5)
        context = MagicMock()
        context.last_feedback_for_provider.return_value = None
        context.tool_call_count = 5
        assert reminder.should_run(context=context) is True

    def test_should_run_after_feedback_below_threshold(self) -> None:
        """Test should_run returns False after feedback if below threshold."""
        reminder = TriviaHostReminder(max_calls_before_reminder=5)
        context = MagicMock()
        context.last_feedback_for_provider.return_value = MagicMock()  # Not None
        context.tool_calls_since_last_feedback_for_provider.return_value = 3
        assert reminder.should_run(context=context) is False
        context.tool_calls_since_last_feedback_for_provider.assert_called_with("TriviaHostReminder")

    def test_should_run_after_feedback_at_threshold(self) -> None:
        """Test should_run returns True after feedback when at threshold."""
        reminder = TriviaHostReminder(max_calls_before_reminder=5)
        context = MagicMock()
        context.last_feedback_for_provider.return_value = MagicMock()  # Not None
        context.tool_calls_since_last_feedback_for_provider.return_value = 5
        assert reminder.should_run(context=context) is True

    def test_provide_returns_feedback(self) -> None:
        """Test provide returns properly structured feedback."""
        reminder = TriviaHostReminder()
        context = MagicMock()
        context.tool_call_count = 7

        feedback = reminder.provide(context=context)

        assert feedback.provider_name == "TriviaHostReminder"
        assert "7 tool calls" in feedback.summary
        assert feedback.severity == "info"

    def test_provide_returns_caution_severity_for_many_calls(self) -> None:
        """Test provide returns caution severity when calls exceed 10."""
        reminder = TriviaHostReminder()
        context = MagicMock()
        context.tool_call_count = 15

        feedback = reminder.provide(context=context)

        assert feedback.severity == "caution"


class TestBuildFeedbackProviders:
    """Tests for build_feedback_providers function."""

    def test_returns_tuple(self) -> None:
        """Test that build_feedback_providers returns a tuple."""
        result = build_feedback_providers()
        assert isinstance(result, tuple)

    def test_returns_two_providers(self) -> None:
        """Test that two providers are configured."""
        result = build_feedback_providers()
        assert len(result) == 2

    def test_providers_have_triggers(self) -> None:
        """Test that all providers have triggers configured."""
        result = build_feedback_providers()
        for config in result:
            assert config.trigger is not None
