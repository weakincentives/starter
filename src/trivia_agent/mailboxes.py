"""Redis mailbox setup for the trivia agent."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from redis import Redis
from weakincentives import FrozenDataclass
from weakincentives.contrib.mailbox import RedisMailbox
from weakincentives.evals import EvalRequest, EvalResult, Experiment, Sample
from weakincentives.runtime import MainLoopRequest, MainLoopResult
from weakincentives.serde import parse

from trivia_agent.config import RedisSettings
from trivia_agent.models import TriviaRequest, TriviaResponse

# =============================================================================
# Parse wrapper for EvalRequest
# =============================================================================
# EvalRequest[TriviaRequest, str] doesn't properly parse its nested Experiment
# field. This wrapper manually constructs the EvalRequest with properly-typed
# nested objects.


def _parse_eval_request(data: Mapping[str, Any]) -> EvalRequest[TriviaRequest, str]:
    """Parse EvalRequest with properly-typed nested fields."""
    sample_data = data.get("sample", {})
    sample = Sample[TriviaRequest, str](
        id=str(sample_data.get("id", "")),
        input=parse(TriviaRequest, sample_data.get("input", {})),
        expected=str(sample_data.get("expected", "")),
    )
    experiment_data = data.get("experiment", {})
    experiment = parse(Experiment, experiment_data)
    return EvalRequest(sample=sample, experiment=experiment)


if TYPE_CHECKING:
    from uuid import UUID

    from weakincentives.runtime import Mailbox

# Type aliases for the mailboxes
RequestsMailbox = RedisMailbox[
    MainLoopRequest[TriviaRequest],
    MainLoopResult[TriviaResponse],
]
EvalRequestsMailbox = RedisMailbox[
    EvalRequest[TriviaRequest, str],
    EvalResult,
]
ResponsesMailbox = RedisMailbox[MainLoopResult[TriviaResponse], None]
EvalResultsMailbox = RedisMailbox[EvalResult, None]


def build_reply_queue_name(prefix: str, request_id: "UUID") -> str:
    """Build a unique reply queue name for a request."""
    if not prefix:
        raise ValueError("Reply queue prefix must be non-empty.")
    return f"{prefix}-{request_id}"


@FrozenDataclass()
class TriviaMailboxes:
    """Container for trivia agent mailboxes."""

    requests: RequestsMailbox
    eval_requests: EvalRequestsMailbox


def create_mailboxes(settings: RedisSettings) -> TriviaMailboxes:
    """Create Redis mailboxes for the trivia agent.

    Args:
        settings: Redis configuration settings.

    Returns:
        A TriviaMailboxes instance containing both request and eval mailboxes.
    """
    client = Redis.from_url(settings.url)  # type: ignore[reportUnknownMemberType]

    requests: RequestsMailbox = RedisMailbox(
        name=settings.requests_queue,
        client=client,
        body_type=MainLoopRequest[TriviaRequest],
    )

    eval_requests: EvalRequestsMailbox = RedisMailbox(
        name=settings.eval_requests_queue,
        client=client,
        body_type=cast(type[EvalRequest[TriviaRequest, str]], _parse_eval_request),
    )

    return TriviaMailboxes(
        requests=requests,
        eval_requests=eval_requests,
    )


def create_responses_mailbox(
    client: Redis,  # type: ignore[type-arg]
    queue_name: str,
) -> "Mailbox[MainLoopResult[TriviaResponse], None]":
    """Create a responses mailbox for receiving replies.

    Args:
        client: Redis client instance.
        queue_name: Name of the reply queue.

    Returns:
        A mailbox for receiving MainLoopResult responses.
    """
    return cast(
        "Mailbox[MainLoopResult[TriviaResponse], None]",
        RedisMailbox(
            name=queue_name,
            client=client,
            body_type=MainLoopResult[TriviaResponse],
        ),
    )


def create_eval_results_mailbox(
    client: Redis,  # type: ignore[type-arg]
    queue_name: str,
) -> "Mailbox[EvalResult, None]":
    """Create an eval results mailbox for receiving eval replies.

    Args:
        client: Redis client instance.
        queue_name: Name of the reply queue.

    Returns:
        A mailbox for receiving EvalResult responses.
    """
    return cast(
        "Mailbox[EvalResult, None]",
        RedisMailbox(
            name=queue_name,
            client=client,
            body_type=EvalResult,
        ),
    )
