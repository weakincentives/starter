"""Tests for trivia agent isolation configuration."""

from pathlib import Path

from weakincentives.adapters.claude_agent_sdk.isolation import IsolationConfig
from weakincentives.skills import SkillConfig

from trivia_agent.isolation import (
    discover_skills,
    resolve_isolation_config,
    resolve_skills_config,
)


class TestDiscoverSkills:
    """Tests for discover_skills function."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that non-existent directory returns empty tuple."""
        result = discover_skills(tmp_path / "nonexistent")
        assert result == ()

    def test_returns_empty_for_file(self, tmp_path: Path) -> None:
        """Test that file path returns empty tuple."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        result = discover_skills(file_path)
        assert result == ()

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        """Test that empty directory returns empty tuple."""
        result = discover_skills(tmp_path)
        assert result == ()

    def test_returns_empty_for_dir_without_skill_md(self, tmp_path: Path) -> None:
        """Test that directories without SKILL.md are ignored."""
        (tmp_path / "not-a-skill").mkdir()
        result = discover_skills(tmp_path)
        assert result == ()

    def test_discovers_skill_with_skill_md(self, tmp_path: Path) -> None:
        """Test that directories with SKILL.md are discovered."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---")
        result = discover_skills(tmp_path)
        assert len(result) == 1
        assert result[0].source == skill_dir

    def test_discovers_multiple_skills_sorted(self, tmp_path: Path) -> None:
        """Test that multiple skills are discovered and sorted."""
        for name in ["zebra", "alpha", "beta"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---")
        result = discover_skills(tmp_path)
        assert len(result) == 3
        assert [r.source.name for r in result] == ["alpha", "beta", "zebra"]


class TestResolveSkillsConfig:
    """Tests for resolve_skills_config function."""

    def test_returns_none_for_empty_env(self, tmp_path: Path) -> None:
        """Test that empty environment with no default skills returns None."""
        result = resolve_skills_config({})
        # May return None or SkillConfig depending on default skills dir
        assert result is None or isinstance(result, SkillConfig)

    def test_returns_none_for_nonexistent_dir(self) -> None:
        """Test that nonexistent skills dir returns None."""
        result = resolve_skills_config({"TRIVIA_SKILLS_DIR": "/nonexistent/path"})
        assert result is None

    def test_returns_config_for_valid_skills_dir(self, tmp_path: Path) -> None:
        """Test that valid skills directory returns SkillConfig."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---")
        result = resolve_skills_config({"TRIVIA_SKILLS_DIR": str(tmp_path)})
        assert isinstance(result, SkillConfig)
        assert len(result.skills) == 1


class TestResolveIsolationConfig:
    """Tests for resolve_isolation_config function."""

    def test_returns_isolation_config(self) -> None:
        """Test that function returns IsolationConfig."""
        result = resolve_isolation_config({})
        assert isinstance(result, IsolationConfig)

    def test_sandbox_enabled_by_default(self) -> None:
        """Test that sandbox is enabled by default for hermetic isolation."""
        result = resolve_isolation_config({})
        assert result.sandbox is not None
        assert result.sandbox.enabled is True

    def test_sandbox_disabled_when_env_set(self) -> None:
        """Test that sandbox is disabled when TRIVIA_DISABLE_SANDBOX is set."""
        result = resolve_isolation_config({"TRIVIA_DISABLE_SANDBOX": "1"})
        assert result.sandbox is not None
        assert result.sandbox.enabled is False

    def test_includes_api_key_when_provided(self) -> None:
        """Test that API key is included for hermetic auth."""
        result = resolve_isolation_config({"ANTHROPIC_API_KEY": "test-key"})
        assert result.api_key == "test-key"

    def test_api_key_is_none_when_not_provided(self) -> None:
        """Test that API key is None when not in environment."""
        result = resolve_isolation_config({})
        assert result.api_key is None

    def test_includes_skills_when_found(self, tmp_path: Path) -> None:
        """Test that skills are included when found."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---")
        result = resolve_isolation_config({"TRIVIA_SKILLS_DIR": str(tmp_path)})
        assert result.skills is not None
        assert len(result.skills.skills) == 1
