"""Isolation configuration for the Secret Trivia agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from weakincentives.adapters.claude_agent_sdk.isolation import (
    IsolationConfig,
    SandboxConfig,
)
from weakincentives.skills import SkillConfig, SkillMount

if TYPE_CHECKING:
    from collections.abc import Mapping

SKILLS_DIR_ENV = "TRIVIA_SKILLS_DIR"
DISABLE_SANDBOX_ENV = "TRIVIA_DISABLE_SANDBOX"
API_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def discover_skills(skills_dir: Path) -> tuple[SkillMount, ...]:
    """Discover all valid skill directories under the given path.

    A valid skill directory contains a SKILL.md file.

    Args:
        skills_dir: Directory to scan for skills.

    Returns:
        Tuple of SkillMount objects for discovered skills.
    """
    if not skills_dir.exists() or not skills_dir.is_dir():
        return ()
    return tuple(
        SkillMount(source=skill_dir)
        for skill_dir in sorted(skills_dir.iterdir())
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()
    )


def resolve_skills_config(env: Mapping[str, str]) -> SkillConfig | None:
    """Resolve skills configuration from environment or defaults.

    Args:
        env: Environment variables mapping.

    Returns:
        SkillConfig if skills are found, None otherwise.
    """
    skills_dir_str = env.get(SKILLS_DIR_ENV, "").strip()
    skills_dir = Path(skills_dir_str) if skills_dir_str else DEFAULT_SKILLS_DIR
    skill_mounts = discover_skills(skills_dir)
    if not skill_mounts:
        return None
    return SkillConfig(skills=skill_mounts, validate_on_mount=True)


def resolve_isolation_config(
    env: Mapping[str, str],
) -> IsolationConfig:
    """Resolve isolation config from environment, including skills and sandbox.

    Uses the ANTHROPIC_API_KEY for hermetic authentication (isolated from host).
    Sandbox is enabled by default with permissive internet access (no network policy).

    Args:
        env: Environment variables mapping.

    Returns:
        Configured IsolationConfig with API key auth and sandbox enabled.
    """
    skills_config = resolve_skills_config(env)
    api_key = env.get(API_KEY_ENV)

    # Sandbox enabled by default; can be disabled via env var
    sandbox_disabled = env.get(DISABLE_SANDBOX_ENV, "").strip()
    sandbox = SandboxConfig(enabled=not sandbox_disabled)

    # No network_policy means permissive internet access
    return IsolationConfig(
        sandbox=sandbox,
        skills=skills_config,
        api_key=api_key,
        # network_policy=None means no restrictions (permissive)
    )
