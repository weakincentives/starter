"""Environment configuration for the trivia agent.

This module provides configuration loading for Redis-based message queuing
and debug bundle storage. Configuration is loaded from environment variables,
with sensible defaults for queue names.

Example:
    Load settings from the current environment::

        import os
        from trivia_agent.config import load_redis_settings

        settings, error = load_redis_settings(os.environ)
        if error:
            raise RuntimeError(error)
        print(f"Connected to Redis at {settings.url}")

Environment Variables:
    REDIS_URL: Required. Redis connection URL (e.g., "redis://localhost:6379").
    TRIVIA_REQUESTS_QUEUE: Optional. Queue name for trivia requests.
        Defaults to "trivia:requests".
    TRIVIA_EVAL_REQUESTS_QUEUE: Optional. Queue name for evaluation requests.
        Defaults to "trivia:eval:requests".
    TRIVIA_DEBUG_BUNDLES_DIR: Optional. Directory path for storing debug bundles.
        Created if it does not exist.
    TRIVIA_PROMPT_OVERRIDES_DIR: Optional. Directory path for prompt override files.
        Created if it does not exist.
"""

from collections.abc import Mapping
from pathlib import Path

from weakincentives import FrozenDataclass


@FrozenDataclass()
class RedisSettings:
    """Redis connection and queue configuration.

    An immutable dataclass holding all Redis-related settings for the trivia
    agent worker. Instances are created via :func:`load_redis_settings` rather
    than direct instantiation.

    Attributes:
        url: Redis connection URL (e.g., "redis://localhost:6379" or
            "redis://user:pass@host:port/db"). Used to establish the
            Redis client connection.
        requests_queue: Name of the Redis queue for incoming trivia requests.
            The worker polls this queue for new questions to process.
        eval_requests_queue: Name of the Redis queue for evaluation requests.
            Used by the evaluation loop to receive test cases with expected
            answers.
        debug_bundles_dir: Optional directory path where debug bundles (*.zip)
            are saved after each agent run. Set to None to disable debug
            bundle storage. The directory is created automatically if it
            does not exist.
        prompt_overrides_dir: Optional directory path containing prompt override
            files. Allows customizing agent prompts without code changes.
            Set to None to use default prompts. The directory is created
            automatically if it does not exist.

    Example:
        Access settings after loading from environment::

            settings, error = load_redis_settings(os.environ)
            if settings:
                redis_client = redis.from_url(settings.url)
                print(f"Listening on queue: {settings.requests_queue}")
    """

    url: str
    requests_queue: str
    eval_requests_queue: str
    debug_bundles_dir: Path | None
    prompt_overrides_dir: Path | None


def load_redis_settings(
    env: Mapping[str, str],
) -> tuple[RedisSettings | None, str | None]:
    """Load Redis settings from environment variables.

    Parses environment variables to construct a :class:`RedisSettings` instance.
    This function uses a result tuple pattern instead of exceptions, making it
    easy to handle configuration errors gracefully at startup.

    The following environment variables are read:

    - ``REDIS_URL`` (required): Redis connection URL
    - ``TRIVIA_REQUESTS_QUEUE`` (optional): Queue name, defaults to "trivia:requests"
    - ``TRIVIA_EVAL_REQUESTS_QUEUE`` (optional): Eval queue, defaults to "trivia:eval:requests"
    - ``TRIVIA_DEBUG_BUNDLES_DIR`` (optional): Debug bundle output directory
    - ``TRIVIA_PROMPT_OVERRIDES_DIR`` (optional): Prompt overrides directory

    If directory paths are provided, they are resolved to absolute paths and
    created (including parent directories) if they do not exist.

    Args:
        env: A mapping of environment variable names to values. Typically
            ``os.environ``, but any ``Mapping[str, str]`` works, which is
            useful for testing with custom configurations.

    Returns:
        A 2-tuple of ``(settings, error)``:

        - On success: ``(RedisSettings(...), None)``
        - On failure: ``(None, "error message describing the problem")``

        Always check the error value before using settings.

    Example:
        Typical usage at application startup::

            import os
            from trivia_agent.config import load_redis_settings

            settings, error = load_redis_settings(os.environ)
            if error:
                print(f"Configuration error: {error}")
                sys.exit(1)

            # Safe to use settings here
            worker = Worker(redis_url=settings.url)

        Testing with custom environment::

            test_env = {
                "REDIS_URL": "redis://localhost:6379",
                "TRIVIA_REQUESTS_QUEUE": "test:requests",
            }
            settings, error = load_redis_settings(test_env)
            assert error is None
            assert settings.requests_queue == "test:requests"
    """
    url = env.get("REDIS_URL")
    if not url:
        return None, "REDIS_URL environment variable is required"

    requests_queue = env.get("TRIVIA_REQUESTS_QUEUE", "trivia:requests")
    eval_requests_queue = env.get("TRIVIA_EVAL_REQUESTS_QUEUE", "trivia:eval:requests")

    debug_bundles_str = env.get("TRIVIA_DEBUG_BUNDLES_DIR")
    debug_bundles_dir: Path | None = None
    if debug_bundles_str:
        debug_bundles_dir = Path(debug_bundles_str).resolve()
        debug_bundles_dir.mkdir(parents=True, exist_ok=True)

    prompt_overrides_str = env.get("TRIVIA_PROMPT_OVERRIDES_DIR")
    prompt_overrides_dir: Path | None = None
    if prompt_overrides_str:
        prompt_overrides_dir = Path(prompt_overrides_str).resolve()
        prompt_overrides_dir.mkdir(parents=True, exist_ok=True)

    return (
        RedisSettings(
            url=url,
            requests_queue=requests_queue,
            eval_requests_queue=eval_requests_queue,
            debug_bundles_dir=debug_bundles_dir,
            prompt_overrides_dir=prompt_overrides_dir,
        ),
        None,
    )
