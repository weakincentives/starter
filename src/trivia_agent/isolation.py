"""Isolation configuration for the Secret Trivia agent.

This module provides functions to configure the agent's isolation environment,
including skill discovery/mounting and sandbox settings. Use these functions
to build an IsolationConfig that controls what skills the agent has access to
and whether it runs in a sandboxed environment.

Environment Variables:
    TRIVIA_SKILLS_DIR: Override the default skills directory path.
    TRIVIA_DISABLE_SANDBOX: Set to any non-empty value to disable sandboxing.
    ANTHROPIC_API_KEY: API key for hermetic authentication within the sandbox.

Example:
    >>> from trivia_agent.isolation import resolve_isolation_config
    >>> import os
    >>> config = resolve_isolation_config(os.environ)
    >>> # Use config with your agent's AgentLoop or EvalLoop
"""

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

    Scans the specified directory for subdirectories containing a SKILL.md file,
    which marks them as valid skill directories. Each discovered skill is wrapped
    in a SkillMount for use with WINK's skill system.

    A valid skill directory structure looks like:
        skills/
            my-skill/
                SKILL.md    # Required - contains skill instructions
                ...         # Optional additional files

    Args:
        skills_dir: Path to the parent directory containing skill subdirectories.
            If the path does not exist or is not a directory, returns an empty tuple.

    Returns:
        A tuple of SkillMount objects for all discovered skills, sorted alphabetically
        by directory name. Returns an empty tuple if no valid skills are found or if
        skills_dir is invalid.

    Example:
        >>> from pathlib import Path
        >>> skills = discover_skills(Path("skills"))
        >>> for skill in skills:
        ...     print(skill.source.name)
        secret-trivia
    """
    if not skills_dir.exists() or not skills_dir.is_dir():
        return ()
    return tuple(
        SkillMount(source=skill_dir)
        for skill_dir in sorted(skills_dir.iterdir())
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()
    )


def resolve_skills_config(env: Mapping[str, str]) -> SkillConfig | None:
    """Resolve skills configuration from environment variables or defaults.

    Determines the skills directory from the TRIVIA_SKILLS_DIR environment variable,
    falling back to the default skills directory (project_root/skills) if not set.
    Then discovers and mounts all valid skills found in that directory.

    The resolved SkillConfig has validation enabled, meaning skill mounts will be
    validated when the agent starts to ensure SKILL.md files are properly formatted.

    Args:
        env: A mapping of environment variable names to values (typically os.environ).
            Checks for TRIVIA_SKILLS_DIR to override the default skills directory.

    Returns:
        A SkillConfig with all discovered skills and validation enabled, or None if
        no valid skills were found in the skills directory.

    Example:
        >>> import os
        >>> config = resolve_skills_config(os.environ)
        >>> if config:
        ...     print(f"Found {len(config.skills)} skill(s)")
        ... else:
        ...     print("No skills found")
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
    """Build a complete isolation configuration from environment variables.

    Creates an IsolationConfig that controls the agent's runtime environment,
    including skill access, sandbox isolation, and API authentication. This is
    the main entry point for configuring agent isolation.

    Configuration behavior:
        - Skills: Discovered from TRIVIA_SKILLS_DIR or default skills directory
        - Sandbox: Enabled by default for security; set TRIVIA_DISABLE_SANDBOX
          to any non-empty value to disable (useful for local development)
        - API Key: Read from ANTHROPIC_API_KEY for hermetic authentication,
          ensuring the sandboxed agent uses its own credentials
        - Network: Permissive by default (no network_policy), allowing the
          agent full internet access within the sandbox

    Args:
        env: A mapping of environment variable names to values (typically os.environ).
            Relevant variables:
            - ANTHROPIC_API_KEY: Required for API authentication
            - TRIVIA_SKILLS_DIR: Optional override for skills directory
            - TRIVIA_DISABLE_SANDBOX: Set to disable sandbox (e.g., "1" or "true")

    Returns:
        An IsolationConfig ready to pass to AgentLoop or EvalLoop. Contains:
        - sandbox: SandboxConfig with enabled/disabled state
        - skills: SkillConfig with discovered skills, or None
        - api_key: The Anthropic API key for authenticated requests

    Example:
        >>> import os
        >>> from trivia_agent.agent_loop import AgentLoop
        >>> config = resolve_isolation_config(os.environ)
        >>> loop = AgentLoop(isolation=config, ...)
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
