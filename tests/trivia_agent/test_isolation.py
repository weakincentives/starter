"""Tests for trivia agent isolation configuration."""

from pathlib import Path

from weakincentives.adapters.claude_agent_sdk.isolation import IsolationConfig

from trivia_agent.isolation import (
    _collect_bedrock_env,
    discover_skills,
    has_auth,
    resolve_isolation_config,
    resolve_skills,
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


class TestResolveSkills:
    """Tests for resolve_skills function."""

    def test_returns_tuple_for_empty_env(self) -> None:
        """Test that empty environment returns a tuple (possibly empty)."""
        result = resolve_skills({})
        assert isinstance(result, tuple)

    def test_returns_empty_for_nonexistent_dir(self) -> None:
        """Test that nonexistent skills dir returns empty tuple."""
        result = resolve_skills({"TRIVIA_SKILLS_DIR": "/nonexistent/path"})
        assert result == ()

    def test_returns_skills_for_valid_dir(self, tmp_path: Path) -> None:
        """Test that valid skills directory returns SkillMount tuple."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---")
        result = resolve_skills({"TRIVIA_SKILLS_DIR": str(tmp_path)})
        assert len(result) == 1
        assert result[0].source == skill_dir


class TestCollectBedrockEnv:
    """Tests for _collect_bedrock_env function."""

    def test_collects_aws_vars(self) -> None:
        """Test that AWS_* variables are collected."""
        env = {"AWS_PROFILE": "test", "AWS_REGION": "us-west-2", "OTHER": "ignore"}
        result = _collect_bedrock_env(env)
        assert result == {"AWS_PROFILE": "test", "AWS_REGION": "us-west-2"}

    def test_collects_bedrock_var(self) -> None:
        """Test that CLAUDE_CODE_USE_BEDROCK is collected."""
        result = _collect_bedrock_env({"CLAUDE_CODE_USE_BEDROCK": "1"})
        assert result == {"CLAUDE_CODE_USE_BEDROCK": "1"}

    def test_collects_home(self) -> None:
        """Test that HOME is collected."""
        result = _collect_bedrock_env({"HOME": "/home/user"})
        assert result == {"HOME": "/home/user"}

    def test_excludes_claudecode(self) -> None:
        """Test that CLAUDECODE is excluded."""
        result = _collect_bedrock_env({"CLAUDECODE": "1", "AWS_REGION": "us-east-1"})
        assert "CLAUDECODE" not in result
        assert "AWS_REGION" in result

    def test_returns_empty_for_irrelevant_vars(self) -> None:
        """Test that irrelevant vars are not collected."""
        result = _collect_bedrock_env({"PATH": "/usr/bin", "TERM": "xterm"})
        assert result == {}


class TestHasAuth:
    """Tests for has_auth function."""

    def test_returns_false_for_empty_env(self) -> None:
        """Test that empty environment has no auth."""
        assert has_auth({}) is False

    def test_returns_true_for_api_key(self) -> None:
        """Test that ANTHROPIC_API_KEY provides auth."""
        assert has_auth({"ANTHROPIC_API_KEY": "test-key"}) is True

    def test_returns_true_for_bedrock(self) -> None:
        """Test that CLAUDE_CODE_USE_BEDROCK provides auth."""
        assert has_auth({"CLAUDE_CODE_USE_BEDROCK": "1"}) is True

    def test_returns_true_when_both_set(self) -> None:
        """Test that both auth methods together work."""
        assert has_auth({"ANTHROPIC_API_KEY": "key", "CLAUDE_CODE_USE_BEDROCK": "1"}) is True


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

    def test_bedrock_passes_env_not_include_host(self) -> None:
        """Test that Bedrock config passes explicit env vars."""
        result = resolve_isolation_config(
            {
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "AWS_PROFILE": "my-profile",
                "AWS_REGION": "us-west-2",
            }
        )
        assert result.include_host_env is False
        assert result.api_key is None
        assert result.env is not None
        assert result.env["CLAUDE_CODE_USE_BEDROCK"] == "1"
        assert result.env["AWS_PROFILE"] == "my-profile"

    def test_bedrock_excludes_claudecode(self) -> None:
        """Test that Bedrock config excludes CLAUDECODE env var."""
        result = resolve_isolation_config(
            {
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "CLAUDECODE": "1",
                "AWS_REGION": "us-east-1",
            }
        )
        assert result.env is not None
        assert "CLAUDECODE" not in result.env
