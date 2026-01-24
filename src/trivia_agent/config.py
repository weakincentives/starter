"""Environment configuration for the trivia agent."""

from collections.abc import Mapping
from pathlib import Path

from weakincentives import FrozenDataclass


@FrozenDataclass()
class RedisSettings:
    """Redis connection and queue configuration."""

    url: str
    requests_queue: str
    eval_requests_queue: str
    debug_bundles_dir: Path | None
    prompt_overrides_dir: Path | None


def load_redis_settings(
    env: Mapping[str, str],
) -> tuple[RedisSettings | None, str | None]:
    """Load Redis settings from environment variables.

    Args:
        env: Environment variable mapping (typically os.environ).

    Returns:
        A tuple of (settings, error). On success, settings is populated and
        error is None. On failure, settings is None and error describes the
        problem.
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
