"""Pytest configuration for integration tests."""

from __future__ import annotations

import os

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
    """Skip integration tests if ANTHROPIC_API_KEY is not set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        skip_marker = pytest.mark.skip(
            reason="ANTHROPIC_API_KEY not set - skipping integration tests"
        )
        for item in items:
            item.add_marker(skip_marker)
