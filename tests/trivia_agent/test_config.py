"""Tests for trivia agent configuration."""

import dataclasses
from pathlib import Path

import pytest

from trivia_agent.config import RedisSettings, load_redis_settings


class TestRedisSettings:
    """Tests for RedisSettings dataclass."""

    def test_instantiation(self) -> None:
        """Test basic instantiation with all fields."""
        settings = RedisSettings(
            url="redis://localhost:6379",
            requests_queue="trivia:requests",
            eval_requests_queue="trivia:eval:requests",
            debug_bundles_dir=Path("./debug_bundles"),
            prompt_overrides_dir=Path("./prompt_overrides"),
        )
        assert settings.url == "redis://localhost:6379"
        assert settings.requests_queue == "trivia:requests"
        assert settings.eval_requests_queue == "trivia:eval:requests"
        assert settings.debug_bundles_dir == Path("./debug_bundles")
        assert settings.prompt_overrides_dir == Path("./prompt_overrides")

    def test_instantiation_no_debug_dir(self) -> None:
        """Test instantiation with None debug_bundles_dir."""
        settings = RedisSettings(
            url="redis://localhost:6379",
            requests_queue="trivia:requests",
            eval_requests_queue="trivia:eval:requests",
            debug_bundles_dir=None,
            prompt_overrides_dir=None,
        )
        assert settings.debug_bundles_dir is None
        assert settings.prompt_overrides_dir is None

    def test_frozen(self) -> None:
        """Test that the dataclass is immutable."""
        settings = RedisSettings(
            url="redis://localhost:6379",
            requests_queue="trivia:requests",
            eval_requests_queue="trivia:eval:requests",
            debug_bundles_dir=None,
            prompt_overrides_dir=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.url = "changed"  # type: ignore[misc]

    def test_is_dataclass(self) -> None:
        """Test that RedisSettings is a dataclass."""
        assert dataclasses.is_dataclass(RedisSettings)


class TestLoadRedisSettings:
    """Tests for load_redis_settings function."""

    def test_missing_redis_url(self) -> None:
        """Test error when REDIS_URL is missing."""
        settings, error = load_redis_settings({})
        assert settings is None
        assert error == "REDIS_URL environment variable is required"

    def test_empty_redis_url(self) -> None:
        """Test error when REDIS_URL is empty string."""
        settings, error = load_redis_settings({"REDIS_URL": ""})
        assert settings is None
        assert error == "REDIS_URL environment variable is required"

    def test_default_queue_names(self) -> None:
        """Test default queue names when not specified."""
        settings, error = load_redis_settings({"REDIS_URL": "redis://localhost:6379"})
        assert error is None
        assert settings is not None
        assert settings.requests_queue == "trivia:requests"
        assert settings.eval_requests_queue == "trivia:eval:requests"

    def test_custom_queue_names(self) -> None:
        """Test custom queue names from environment."""
        env = {
            "REDIS_URL": "redis://localhost:6379",
            "TRIVIA_REQUESTS_QUEUE": "custom:requests",
            "TRIVIA_EVAL_REQUESTS_QUEUE": "custom:eval:requests",
        }
        settings, error = load_redis_settings(env)
        assert error is None
        assert settings is not None
        assert settings.requests_queue == "custom:requests"
        assert settings.eval_requests_queue == "custom:eval:requests"

    def test_no_debug_bundles_dir(self) -> None:
        """Test that debug_bundles_dir is None when not specified."""
        settings, error = load_redis_settings({"REDIS_URL": "redis://localhost:6379"})
        assert error is None
        assert settings is not None
        assert settings.debug_bundles_dir is None
        assert settings.prompt_overrides_dir is None

    def test_with_debug_bundles_dir(self, tmp_path: Path) -> None:
        """Test debug_bundles_dir is set when specified."""
        bundles_dir = tmp_path / "debug_bundles"
        env = {
            "REDIS_URL": "redis://localhost:6379",
            "TRIVIA_DEBUG_BUNDLES_DIR": str(bundles_dir),
        }
        settings, error = load_redis_settings(env)
        assert error is None
        assert settings is not None
        assert settings.debug_bundles_dir == bundles_dir
        assert bundles_dir.exists()  # Directory should be created

    def test_with_prompt_overrides_dir(self, tmp_path: Path) -> None:
        """Test prompt_overrides_dir is set when specified."""
        overrides_dir = tmp_path / "prompt_overrides"
        env = {
            "REDIS_URL": "redis://localhost:6379",
            "TRIVIA_PROMPT_OVERRIDES_DIR": str(overrides_dir),
        }
        settings, error = load_redis_settings(env)
        assert error is None
        assert settings is not None
        assert settings.prompt_overrides_dir == overrides_dir
        assert overrides_dir.exists()  # Directory should be created

    def test_full_configuration(self, tmp_path: Path) -> None:
        """Test loading with all environment variables set."""
        bundles_dir = tmp_path / "bundles"
        overrides_dir = tmp_path / "overrides"
        env = {
            "REDIS_URL": "redis://custom-host:6380",
            "TRIVIA_REQUESTS_QUEUE": "prod:requests",
            "TRIVIA_EVAL_REQUESTS_QUEUE": "prod:eval:requests",
            "TRIVIA_DEBUG_BUNDLES_DIR": str(bundles_dir),
            "TRIVIA_PROMPT_OVERRIDES_DIR": str(overrides_dir),
        }
        settings, error = load_redis_settings(env)
        assert error is None
        assert settings is not None
        assert settings.url == "redis://custom-host:6380"
        assert settings.requests_queue == "prod:requests"
        assert settings.eval_requests_queue == "prod:eval:requests"
        assert settings.debug_bundles_dir == bundles_dir
        assert settings.prompt_overrides_dir == overrides_dir
        assert bundles_dir.exists()  # Directory should be created
        assert overrides_dir.exists()  # Directory should be created
