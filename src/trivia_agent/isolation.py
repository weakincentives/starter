"""Isolation configuration for the Secret Trivia agent.

This module provides functions to configure the agent's isolation environment,
including skill discovery and sandbox settings. Use these functions
to build an IsolationConfig that controls sandbox and authentication settings,
and to discover skills for section-level mounting.

Environment Variables:
    TRIVIA_SKILLS_DIR: Override the default skills directory path.
    TRIVIA_DISABLE_SANDBOX: Set to any non-empty value to disable sandboxing.
    ANTHROPIC_API_KEY: API key for hermetic authentication within the sandbox.

Example:
    >>> from trivia_agent.isolation import resolve_isolation_config, discover_skills
    >>> import os
    >>> config = resolve_isolation_config(os.environ)
    >>> skills = discover_skills(Path("skills"))
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from weakincentives.adapters.claude_agent_sdk.isolation import (
    IsolationConfig,
    SandboxConfig,
)
from weakincentives.skills import SkillMount

if TYPE_CHECKING:
    from collections.abc import Mapping

SKILLS_DIR_ENV = "TRIVIA_SKILLS_DIR"
DISABLE_SANDBOX_ENV = "TRIVIA_DISABLE_SANDBOX"
API_KEY_ENV = "ANTHROPIC_API_KEY"
BEDROCK_ENV = "CLAUDE_CODE_USE_BEDROCK"
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


def resolve_skills(env: Mapping[str, str]) -> tuple[SkillMount, ...]:
    """Resolve skills from environment variables or defaults.

    Determines the skills directory from the TRIVIA_SKILLS_DIR environment variable,
    falling back to the default skills directory (project_root/skills) if not set.
    Then discovers all valid skills found in that directory.

    Skills are returned as SkillMount tuples for attachment to prompt sections.

    Args:
        env: A mapping of environment variable names to values (typically os.environ).
            Checks for TRIVIA_SKILLS_DIR to override the default skills directory.

    Returns:
        A tuple of SkillMount objects for all discovered skills. Returns an empty
        tuple if no valid skills were found.

    Example:
        >>> import os
        >>> skills = resolve_skills(os.environ)
        >>> print(f"Found {len(skills)} skill(s)")
    """
    skills_dir_str = env.get(SKILLS_DIR_ENV, "").strip()
    skills_dir = Path(skills_dir_str) if skills_dir_str else DEFAULT_SKILLS_DIR
    return discover_skills(skills_dir)


# Env var prefixes and names to forward for Bedrock authentication
_BEDROCK_ENV_PREFIXES = ("AWS_",)
_BEDROCK_ENV_NAMES = frozenset({"CLAUDE_CODE_USE_BEDROCK", "HOME"})
# Env vars that must NOT be forwarded (prevent nested Claude Code detection)
_BEDROCK_ENV_EXCLUDE = frozenset({"CLAUDECODE"})


def _collect_bedrock_env(env: Mapping[str, str]) -> dict[str, str]:
    """Collect environment variables needed for Bedrock authentication.

    Forwards AWS_* variables and CLAUDE_CODE_USE_BEDROCK while excluding
    CLAUDECODE to prevent nested session detection.
    """
    result: dict[str, str] = {}
    for key, value in env.items():
        if key in _BEDROCK_ENV_EXCLUDE:
            continue
        if key in _BEDROCK_ENV_NAMES or any(key.startswith(p) for p in _BEDROCK_ENV_PREFIXES):
            result[key] = value
    return result


def has_auth(env: Mapping[str, str]) -> bool:
    """Check whether the environment has valid authentication configured.

    Returns True if either ANTHROPIC_API_KEY or CLAUDE_CODE_USE_BEDROCK is set,
    indicating the agent can authenticate with the model provider.
    """
    return bool(env.get(API_KEY_ENV) or env.get(BEDROCK_ENV))


def resolve_isolation_config(
    env: Mapping[str, str],
) -> IsolationConfig:
    """Build a complete isolation configuration from environment variables.

    Creates an IsolationConfig that controls the agent's runtime environment,
    including sandbox isolation and API authentication. This is the main entry
    point for configuring agent isolation.

    Note: Skills are no longer part of IsolationConfig. Use resolve_skills()
    to discover skills and attach them to prompt sections instead.

    Configuration behavior:
        - Sandbox: Enabled by default for security; set TRIVIA_DISABLE_SANDBOX
          to any non-empty value to disable (useful for local development)
        - Authentication: Uses ANTHROPIC_API_KEY for direct API access, or
          inherits host environment when CLAUDE_CODE_USE_BEDROCK is set
        - Network: Permissive by default (no network_policy), allowing the
          agent full internet access within the sandbox

    Args:
        env: A mapping of environment variable names to values (typically os.environ).
            Relevant variables:
            - ANTHROPIC_API_KEY: API key for direct Anthropic API authentication
            - CLAUDE_CODE_USE_BEDROCK: Set to use AWS Bedrock (inherits host env)
            - TRIVIA_DISABLE_SANDBOX: Set to disable sandbox (e.g., "1" or "true")

    Returns:
        An IsolationConfig ready to pass to the adapter. Contains:
        - sandbox: SandboxConfig with enabled/disabled state
        - api_key or include_host_env for authentication

    Example:
        >>> import os
        >>> config = resolve_isolation_config(os.environ)
    """
    api_key = env.get(API_KEY_ENV)
    use_bedrock = bool(env.get(BEDROCK_ENV, "").strip())

    # Sandbox enabled by default; can be disabled via env var
    sandbox_disabled = env.get(DISABLE_SANDBOX_ENV, "").strip()
    sandbox = SandboxConfig(enabled=not sandbox_disabled)

    # When using Bedrock, pass through the relevant AWS and Bedrock env vars.
    # We use explicit env instead of include_host_env to avoid inheriting
    # CLAUDECODE (which prevents Claude Code from launching inside itself).
    if use_bedrock:
        bedrock_env = _collect_bedrock_env(env)
        return IsolationConfig(
            sandbox=sandbox,
            env=bedrock_env if bedrock_env else None,
        )

    # No network_policy means permissive internet access
    return IsolationConfig(
        sandbox=sandbox,
        api_key=api_key,
        # network_policy=None means no restrictions (permissive)
    )
