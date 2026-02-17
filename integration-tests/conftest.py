"""Pytest configuration for integration tests."""

from __future__ import annotations

import os
import shutil

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register integration test marker."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires Docker and API key)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip integration tests based on adapter prerequisites."""
    adapter = os.environ.get("TRIVIA_ADAPTER", "claude")

    skip_reason: str | None = None

    if adapter == "claude":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            skip_reason = "ANTHROPIC_API_KEY not set - skipping integration tests"
    elif adapter == "codex":
        if shutil.which("codex") is None:
            skip_reason = "codex binary not found on PATH - skipping integration tests"
    elif adapter == "opencode":
        if shutil.which("opencode") is None:
            skip_reason = "opencode binary not found on PATH - skipping integration tests"

    if skip_reason:
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            item.add_marker(skip_marker)
