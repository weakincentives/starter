"""Tests for prompt sections."""

from trivia_agent.sections import (
    EmptyParams,
    GameRulesSection,
    HintsSection,
    LuckyDiceSection,
    QuestionParams,
    QuestionSection,
)


class TestQuestionParams:
    """Tests for QuestionParams dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        params = QuestionParams(question="What is the secret number?")
        assert params.question == "What is the secret number?"


class TestEmptyParams:
    """Tests for EmptyParams dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        params = EmptyParams()
        assert params is not None


class TestQuestionSection:
    """Tests for QuestionSection."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = QuestionSection()
        assert section.key == "question"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = QuestionSection()
        assert section.title == "Question"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = QuestionSection()
        assert isinstance(section, MarkdownSection)


class TestGameRulesSection:
    """Tests for GameRulesSection with progressive disclosure."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = GameRulesSection()
        assert section.key == "rules"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = GameRulesSection()
        assert section.title == "Game Rules"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = GameRulesSection()
        assert isinstance(section, MarkdownSection)


class TestHintsSection:
    """Tests for HintsSection with attached tool."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = HintsSection()
        assert section.key == "hints"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = HintsSection()
        assert section.title == "Hints"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = HintsSection()
        assert isinstance(section, MarkdownSection)


class TestLuckyDiceSection:
    """Tests for LuckyDiceSection with tool policy."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = LuckyDiceSection()
        assert section.key == "dice"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = LuckyDiceSection()
        assert section.title == "Lucky Dice"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = LuckyDiceSection()
        assert isinstance(section, MarkdownSection)
