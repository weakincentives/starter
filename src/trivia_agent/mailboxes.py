"""Redis mailbox setup for the trivia agent.

This module provides Redis-backed mailboxes for asynchronous communication
between the trivia agent worker and clients. It defines two main communication
channels:

1. **Requests mailbox**: For regular trivia questions (TriviaRequest -> TriviaResponse)
2. **Eval requests mailbox**: For evaluation runs (EvalRequest -> EvalResult)

The mailboxes use Redis lists as queues, enabling reliable message passing
between the dispatch scripts and the background agent worker.

Example:
    Creating and using mailboxes in a worker::

        from trivia_agent.config import RedisSettings
        from trivia_agent.mailboxes import create_mailboxes

        settings = RedisSettings()
        mailboxes = create_mailboxes(settings)

        # Worker polls for requests
        for request in mailboxes.requests:
            # Process request...
            pass
"""

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
    """Build a unique reply queue name for a request.

    Constructs a Redis queue name by combining a prefix with the request's
    unique identifier. This ensures each request gets its own dedicated
    reply channel, preventing response mix-ups in concurrent scenarios.

    Args:
        prefix: The base name for reply queues (e.g., "trivia-replies").
            Must be non-empty.
        request_id: The UUID of the request being processed. Typically
            obtained from MainLoopRequest.id or EvalRequest.sample.id.

    Returns:
        A queue name in the format "{prefix}-{request_id}".

    Raises:
        ValueError: If prefix is empty.

    Example:
        >>> from uuid import uuid4
        >>> request_id = uuid4()
        >>> queue_name = build_reply_queue_name("trivia-replies", request_id)
        >>> queue_name  # "trivia-replies-550e8400-e29b-41d4-a716-446655440000"
    """
    if not prefix:
        raise ValueError("Reply queue prefix must be non-empty.")
    return f"{prefix}-{request_id}"


@FrozenDataclass()
class TriviaMailboxes:
    """Container for trivia agent mailboxes.

    An immutable dataclass that groups together the mailboxes needed by the
    trivia agent worker. This container is returned by `create_mailboxes()`
    and passed to the worker's main loop.

    Attributes:
        requests: Mailbox for regular trivia questions. Receives
            MainLoopRequest[TriviaRequest] messages and allows sending
            MainLoopResult[TriviaResponse] replies.
        eval_requests: Mailbox for evaluation runs. Receives
            EvalRequest[TriviaRequest, str] messages (where str is the
            expected answer) and allows sending EvalResult replies.

    Example:
        Creating and iterating over mailboxes::

            settings = RedisSettings()
            mailboxes = create_mailboxes(settings)

            # In your worker loop:
            for request in mailboxes.requests:
                response = process_trivia(request)
                # Send response to reply queue...

            # Or for evals:
            for eval_req in mailboxes.eval_requests:
                result = run_eval(eval_req)
                # Send result to reply queue...
    """

    requests: RequestsMailbox
    eval_requests: EvalRequestsMailbox


def create_mailboxes(settings: RedisSettings) -> TriviaMailboxes:
    """Create Redis mailboxes for the trivia agent.

    Factory function that initializes the Redis connection and creates
    both the requests and eval_requests mailboxes. Call this once at
    worker startup and pass the result to your main loop.

    The function creates a single Redis client that is shared between
    both mailboxes for efficient connection pooling.

    Args:
        settings: Redis configuration containing:
            - url: Redis connection URL (e.g., "redis://localhost:6379")
            - requests_queue: Name of the requests queue
            - eval_requests_queue: Name of the eval requests queue

    Returns:
        A TriviaMailboxes instance containing both request and eval mailboxes,
        ready for use in the worker loop.

    Example:
        Typical usage in worker.py::

            from trivia_agent.config import RedisSettings
            from trivia_agent.mailboxes import create_mailboxes

            settings = RedisSettings()  # Loads from environment
            mailboxes = create_mailboxes(settings)

            # Pass to MainLoop
            main_loop = MainLoop(
                mailboxes=[mailboxes.requests, mailboxes.eval_requests],
                ...
            )
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
    """Create a responses mailbox for receiving replies from the worker.

    Used by dispatch scripts to create a dedicated mailbox for receiving
    the response to a specific request. The queue_name should be built
    using `build_reply_queue_name()` to ensure uniqueness.

    This mailbox is read-only from the client's perspective (None reply type),
    as clients only receive responses, they don't reply to them.

    Args:
        client: An existing Redis client instance. Should use the same
            Redis server as the worker's mailboxes.
        queue_name: Name of the reply queue, typically generated by
            `build_reply_queue_name(prefix, request_id)`.

    Returns:
        A mailbox that yields MainLoopResult[TriviaResponse] messages.
        Iterate over it or call methods like `.get()` to receive responses.

    Example:
        Waiting for a response in a dispatch script::

            from redis import Redis
            from trivia_agent.mailboxes import (
                build_reply_queue_name,
                create_responses_mailbox,
            )

            client = Redis.from_url("redis://localhost:6379")
            queue_name = build_reply_queue_name("replies", request.id)
            responses = create_responses_mailbox(client, queue_name)

            # Block until response arrives
            result = next(iter(responses))
            print(result.body.answer)
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
    """Create an eval results mailbox for receiving evaluation results.

    Used by eval dispatch scripts to create a dedicated mailbox for receiving
    the evaluation result for a specific sample. Similar to
    `create_responses_mailbox()` but typed for EvalResult instead of
    MainLoopResult.

    The EvalResult contains the evaluation score and any evaluator-specific
    metadata from the trivia_evaluator.

    Args:
        client: An existing Redis client instance. Should use the same
            Redis server as the worker's mailboxes.
        queue_name: Name of the reply queue, typically generated by
            `build_reply_queue_name(prefix, sample_id)`.

    Returns:
        A mailbox that yields EvalResult messages containing scores and
        evaluation metadata.

    Example:
        Running an evaluation and getting results::

            from redis import Redis
            from trivia_agent.mailboxes import (
                build_reply_queue_name,
                create_eval_results_mailbox,
            )

            client = Redis.from_url("redis://localhost:6379")
            queue_name = build_reply_queue_name("eval-replies", sample.id)
            results = create_eval_results_mailbox(client, queue_name)

            # Block until eval completes
            eval_result = next(iter(results))
            print(f"Score: {eval_result.score}")
    """
    return cast(
        "Mailbox[EvalResult, None]",
        RedisMailbox(
            name=queue_name,
            client=client,
            body_type=EvalResult,
        ),
    )
