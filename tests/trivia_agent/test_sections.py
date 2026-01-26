"""Tests for prompt sections."""

from trivia_agent.sections import (
    EmptyParams,
    QuestionParams,
    build_game_rules_section,
    build_hints_section,
    build_lucky_dice_section,
    build_question_section,
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


class TestBuildQuestionSection:
    """Tests for build_question_section."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = build_question_section()
        assert section.key == "question"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = build_question_section()
        assert section.title == "Question"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = build_question_section()
        assert isinstance(section, MarkdownSection)


class TestBuildGameRulesSection:
    """Tests for build_game_rules_section with progressive disclosure."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = build_game_rules_section()
        assert section.key == "rules"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = build_game_rules_section()
        assert section.title == "Game Rules"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = build_game_rules_section()
        assert isinstance(section, MarkdownSection)


class TestBuildHintsSection:
    """Tests for build_hints_section with attached tool."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = build_hints_section()
        assert section.key == "hints"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = build_hints_section()
        assert section.title == "Hints"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = build_hints_section()
        assert isinstance(section, MarkdownSection)


class TestBuildLuckyDiceSection:
    """Tests for build_lucky_dice_section with tool policy."""

    def test_has_correct_key(self) -> None:
        """Test section has correct key."""
        section = build_lucky_dice_section()
        assert section.key == "dice"

    def test_has_correct_title(self) -> None:
        """Test section has correct title."""
        section = build_lucky_dice_section()
        assert section.title == "Lucky Dice"

    def test_section_type(self) -> None:
        """Test section is a MarkdownSection."""
        from weakincentives import MarkdownSection

        section = build_lucky_dice_section()
        assert isinstance(section, MarkdownSection)
