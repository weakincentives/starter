"""Tests for custom tools."""

from unittest.mock import MagicMock

from trivia_agent.tools import (
    HintLookupParams,
    HintLookupResult,
    PickUpDiceParams,
    PickUpDiceResult,
    ThrowDiceParams,
    ThrowDiceResult,
    _handle_hint_lookup,
    _handle_pick_up_dice,
    _handle_throw_dice,
    hint_lookup_tool,
    pick_up_dice_tool,
    throw_dice_tool,
)


def _make_mock_context() -> MagicMock:
    """Create a mock context."""
    return MagicMock()


class TestHintLookupParams:
    """Tests for HintLookupParams dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        params = HintLookupParams(category="number")
        assert params.category == "number"


class TestHintLookupResult:
    """Tests for HintLookupResult dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        result = HintLookupResult(found=True, hint="test hint")
        assert result.found is True
        assert result.hint == "test hint"

    def test_render_when_found(self) -> None:
        """Test render returns formatted hint when found."""
        result = HintLookupResult(found=True, hint="test hint")
        assert result.render() == "Hint: test hint"

    def test_render_when_not_found(self) -> None:
        """Test render returns not found message."""
        result = HintLookupResult(found=False, hint="")
        assert result.render() == "No hint available for this category."


class TestHandleHintLookup:
    """Tests for _handle_hint_lookup function."""

    def test_finds_number_hint(self) -> None:
        """Test finding hint for number category."""
        params = HintLookupParams(category="number")
        context = _make_mock_context()

        result = _handle_hint_lookup(params, context=context)

        assert result.value is not None
        assert result.value.found is True
        assert "life" in result.value.hint.lower()

    def test_finds_word_hint(self) -> None:
        """Test finding hint for word category."""
        params = HintLookupParams(category="word")
        context = _make_mock_context()

        result = _handle_hint_lookup(params, context=context)

        assert result.value is not None
        assert result.value.found is True
        assert "fruit" in result.value.hint.lower()

    def test_finds_color_hint(self) -> None:
        """Test finding hint for color category."""
        params = HintLookupParams(category="color")
        context = _make_mock_context()

        result = _handle_hint_lookup(params, context=context)

        assert result.value is not None
        assert result.value.found is True
        assert "red" in result.value.hint.lower() or "blue" in result.value.hint.lower()

    def test_finds_phrase_hint(self) -> None:
        """Test finding hint for phrase category."""
        params = HintLookupParams(category="phrase")
        context = _make_mock_context()

        result = _handle_hint_lookup(params, context=context)

        assert result.value is not None
        assert result.value.found is True
        assert "ali baba" in result.value.hint.lower()

    def test_case_insensitive_search(self) -> None:
        """Test that search is case insensitive."""
        params = HintLookupParams(category="NUMBER")
        context = _make_mock_context()

        result = _handle_hint_lookup(params, context=context)

        assert result.value is not None
        assert result.value.found is True

    def test_returns_not_found_for_unknown_category(self) -> None:
        """Test that unknown categories return not found."""
        params = HintLookupParams(category="quantum physics")
        context = _make_mock_context()

        result = _handle_hint_lookup(params, context=context)

        assert result.value is not None
        assert result.value.found is False
        assert result.value.hint == ""


class TestHintLookupTool:
    """Tests for the hint_lookup_tool instance."""

    def test_tool_has_correct_name(self) -> None:
        """Test that tool has expected name."""
        assert hint_lookup_tool.name == "hint_lookup"

    def test_tool_has_description(self) -> None:
        """Test that tool has a description."""
        assert hint_lookup_tool.description is not None
        assert len(hint_lookup_tool.description) > 0

    def test_tool_has_handler(self) -> None:
        """Test that tool has a handler."""
        assert hint_lookup_tool.handler is not None


# =============================================================================
# Lucky Dice Tool Tests
# =============================================================================


class TestPickUpDiceParams:
    """Tests for PickUpDiceParams dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        params = PickUpDiceParams()
        assert params is not None


class TestPickUpDiceResult:
    """Tests for PickUpDiceResult dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        result = PickUpDiceResult(message="test")
        assert result.message == "test"

    def test_render(self) -> None:
        """Test render returns the message."""
        result = PickUpDiceResult(message="You got it!")
        assert result.render() == "You got it!"


class TestHandlePickUpDice:
    """Tests for _handle_pick_up_dice function."""

    def test_returns_confirmation_message(self) -> None:
        """Test that picking up dice returns confirmation."""
        params = PickUpDiceParams()
        context = _make_mock_context()

        result = _handle_pick_up_dice(params, context=context)

        assert result.value is not None
        assert "picked up" in result.value.message.lower()


class TestThrowDiceParams:
    """Tests for ThrowDiceParams dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        params = ThrowDiceParams()
        assert params is not None


class TestThrowDiceResult:
    """Tests for ThrowDiceResult dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        result = ThrowDiceResult(value=4)
        assert result.value == 4

    def test_render_normal_roll(self) -> None:
        """Test render returns dice value for normal roll."""
        result = ThrowDiceResult(value=3)
        assert "3" in result.render()
        assert "🎲" in result.render()

    def test_render_lucky_roll(self) -> None:
        """Test render returns special message for lucky roll (6)."""
        result = ThrowDiceResult(value=6)
        rendered = result.render()
        assert "6" in rendered
        assert "lucky" in rendered.lower() or "bonus" in rendered.lower()


class TestHandleThrowDice:
    """Tests for _handle_throw_dice function."""

    def test_returns_value_between_1_and_6(self) -> None:
        """Test that dice roll returns valid value."""
        params = ThrowDiceParams()
        context = _make_mock_context()

        # Run multiple times to check range
        for _ in range(100):
            result = _handle_throw_dice(params, context=context)
            assert result.value is not None
            assert 1 <= result.value.value <= 6


class TestPickUpDiceTool:
    """Tests for pick_up_dice_tool instance."""

    def test_tool_has_correct_name(self) -> None:
        """Test that tool has expected name."""
        assert pick_up_dice_tool.name == "pick_up_dice"

    def test_tool_has_description(self) -> None:
        """Test that tool has a description."""
        assert pick_up_dice_tool.description is not None

    def test_tool_has_handler(self) -> None:
        """Test that tool has a handler."""
        assert pick_up_dice_tool.handler is not None


class TestThrowDiceTool:
    """Tests for throw_dice_tool instance."""

    def test_tool_has_correct_name(self) -> None:
        """Test that tool has expected name."""
        assert throw_dice_tool.name == "throw_dice"

    def test_tool_has_description(self) -> None:
        """Test that tool has a description."""
        assert throw_dice_tool.description is not None

    def test_tool_has_handler(self) -> None:
        """Test that tool has a handler."""
        assert throw_dice_tool.handler is not None
