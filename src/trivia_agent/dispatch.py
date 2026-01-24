"""Submit questions to the trivia agent."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import field
from typing import TextIO
from uuid import uuid4

from redis import Redis
from weakincentives import FrozenDataclass
from weakincentives.evals import EvalRequest, EvalResult, Experiment, Sample
from weakincentives.runtime import MainLoopRequest, MainLoopResult
from weakincentives.runtime.mailbox import Mailbox, ReceiptHandleExpiredError

from trivia_agent.config import load_redis_settings
from trivia_agent.mailboxes import (
    TriviaMailboxes,
    build_reply_queue_name,
    create_eval_results_mailbox,
    create_mailboxes,
    create_responses_mailbox,
)
from trivia_agent.models import TriviaRequest, TriviaResponse

# Reply queue prefix for eval results
EVAL_REPLY_QUEUE_PREFIX = "qa:eval:replies"

# Default timeout in seconds
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_WAIT_TIME_SECONDS = 5
REPLY_QUEUE_PREFIX = "qa:replies"


@FrozenDataclass()
class DispatchRuntime:
    """Runtime dependencies for the dispatcher.

    Used for dependency injection in tests.
    """

    mailboxes: TriviaMailboxes | None = None
    responses: Mailbox[MainLoopResult[TriviaResponse], None] | None = None
    eval_results: Mailbox[EvalResult, None] | None = None
    out: TextIO = field(default_factory=lambda: sys.stdout)
    err: TextIO = field(default_factory=lambda: sys.stderr)
    now: Callable[[], float] = field(default_factory=lambda: time.monotonic)


def _wait_for_eval_result(
    eval_results: Mailbox[EvalResult, None],
    sample_id: str,
    timeout_seconds: float,
    wait_time_seconds: int,
    now: Callable[[], float],
) -> EvalResult | None:
    """Wait for an eval result matching the sample ID.

    Args:
        eval_results: Mailbox to receive eval results from.
        sample_id: ID of the sample to match.
        timeout_seconds: Maximum time to wait.
        wait_time_seconds: Time to wait between polls.
        now: Function returning current time.

    Returns:
        The matching eval result, or None if timeout.
    """
    deadline = now() + timeout_seconds

    while True:
        remaining = deadline - now()
        if remaining <= 0:
            return None

        wait_time = min(wait_time_seconds, max(0, int(remaining)))
        messages = eval_results.receive(max_messages=1, wait_time_seconds=wait_time)
        if not messages:
            continue

        msg = messages[0]
        result = msg.body

        # Check if this is the result we're waiting for
        if result.sample_id != sample_id:
            # Not our result, put it back
            with contextlib.suppress(ReceiptHandleExpiredError):
                msg.nack(visibility_timeout=0)
            continue

        # Acknowledge and return
        with contextlib.suppress(ReceiptHandleExpiredError):
            msg.acknowledge()
        return result


def _wait_for_response(
    responses: Mailbox[MainLoopResult[TriviaResponse], None],
    request_id: str,
    timeout_seconds: float,
    wait_time_seconds: int,
    now: Callable[[], float],
) -> MainLoopResult[TriviaResponse] | None:
    """Wait for a response matching the request ID.

    Args:
        responses: Mailbox to receive responses from.
        request_id: ID of the request to match.
        timeout_seconds: Maximum time to wait.
        wait_time_seconds: Time to wait between polls.
        now: Function returning current time.

    Returns:
        The matching response, or None if timeout.
    """
    deadline = now() + timeout_seconds

    while True:
        remaining = deadline - now()
        if remaining <= 0:
            return None

        wait_time = min(wait_time_seconds, max(0, int(remaining)))
        messages = responses.receive(max_messages=1, wait_time_seconds=wait_time)
        if not messages:
            continue

        msg = messages[0]
        result = msg.body

        # Check if this is the response we're waiting for
        if str(result.request_id) != request_id:
            # Not our response, put it back
            with contextlib.suppress(ReceiptHandleExpiredError):
                msg.nack(visibility_timeout=0)
            continue

        # Acknowledge and return
        with contextlib.suppress(ReceiptHandleExpiredError):
            msg.acknowledge()
        return result


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime: DispatchRuntime | None = None,
) -> int:
    """Main entry point for the trivia dispatcher.

    Args:
        argv: Command line arguments.
        runtime: Optional runtime dependencies for testing.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    rt = runtime or DispatchRuntime()
    out = rt.out
    err = rt.err

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Submit questions to the trivia agent.",
    )
    parser.add_argument(
        "--question",
        required=True,
        help="The question to ask the agent.",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Submit as an evaluation case.",
    )
    parser.add_argument(
        "--expected",
        help="Expected answer substring (required with --eval).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Seconds to wait for response (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for response, just submit and exit.",
    )
    parser.add_argument(
        "--experiment",
        default="cli-eval",
        help="Experiment name for grouping eval runs (default: cli-eval).",
    )
    parser.add_argument(
        "--owner",
        help="Owner of the experiment (e.g., email or username).",
    )
    parser.add_argument(
        "--description",
        dest="exp_description",
        help="Description of what this eval run is testing.",
    )

    args = parser.parse_args(argv)

    # Validate eval arguments
    if args.eval and not args.expected:
        err.write("Error: --expected is required when using --eval\n")
        return 1

    # Load configuration
    settings, error = load_redis_settings(os.environ)
    if error:
        err.write(f"Configuration error: {error}\n")
        return 1

    assert settings is not None  # for type checker

    # Use injected or create real dependencies
    mailboxes = rt.mailboxes or create_mailboxes(settings)

    # Create the request
    request = TriviaRequest(question=args.question)

    if args.eval:
        # Submit as eval request with reply_to for results
        sample_id = str(uuid4())
        sample = Sample(
            id=sample_id,
            input=request,
            expected=args.expected,
        )
        experiment = Experiment(
            name=args.experiment,
            owner=args.owner,
            description=args.exp_description,
        )
        eval_request = EvalRequest(sample=sample, experiment=experiment)

        if args.no_wait:
            # Just submit and exit
            mailboxes.eval_requests.send(eval_request)
            out.write(f"Submitted eval case: {args.question}\n")
            out.write(f"Expected: {args.expected}\n")
            out.write(f"Experiment: {experiment.name}\n")
            return 0

        # Create reply mailbox for eval results
        reply_queue = build_reply_queue_name(EVAL_REPLY_QUEUE_PREFIX, eval_request.request_id)
        client = Redis.from_url(settings.url)  # type: ignore[reportUnknownMemberType]
        eval_results = rt.eval_results or create_eval_results_mailbox(client, reply_queue)

        try:
            mailboxes.eval_requests.send(eval_request, reply_to=eval_results)
            out.write(f"Submitted eval case: {args.question}\n")
            out.write(f"Expected: {args.expected}\n")
            out.write(f"Experiment: {experiment.name}\n")
            if experiment.owner:
                out.write(f"Owner: {experiment.owner}\n")
            if experiment.description:
                out.write(f"Description: {experiment.description}\n")
            out.write("Waiting for eval result...\n")

            result = _wait_for_eval_result(
                eval_results=eval_results,
                sample_id=sample_id,
                timeout_seconds=args.timeout,
                wait_time_seconds=DEFAULT_WAIT_TIME_SECONDS,
                now=rt.now,
            )

            if result is None:
                err.write(f"Timeout: No eval result within {args.timeout} seconds.\n")
                return 1

            if result.error:
                err.write(f"Error: {result.error}\n")
                return 1

            # Display eval results
            out.write("\n=== Eval Result ===\n")
            status = "PASSED" if result.score.passed else "FAILED"
            out.write(f"Status: {status}\n")
            out.write(f"Score: {result.score.value:.2f}\n")
            out.write(f"Reason: {result.score.reason}\n")
            out.write(f"Latency: {result.latency_ms}ms\n")
            if result.bundle_path:
                out.write(f"Bundle: {result.bundle_path}\n")

            return 0 if result.score.passed else 1

        finally:
            eval_results.close()
            client.close()

    # Submit as regular request
    main_request = MainLoopRequest(request=request)

    if args.no_wait:
        # Just submit and exit
        mailboxes.requests.send(main_request)
        out.write(f"Submitted question: {args.question}\n")
        return 0

    # Create reply mailbox and submit with reply_to
    reply_queue = build_reply_queue_name(REPLY_QUEUE_PREFIX, main_request.request_id)
    client = Redis.from_url(settings.url)  # type: ignore[reportUnknownMemberType]
    responses = rt.responses or create_responses_mailbox(client, reply_queue)

    try:
        mailboxes.requests.send(main_request, reply_to=responses)
        out.write(f"Submitted question: {args.question}\n")
        out.write("Waiting for response...\n")

        result = _wait_for_response(
            responses=responses,
            request_id=str(main_request.request_id),
            timeout_seconds=args.timeout,
            wait_time_seconds=DEFAULT_WAIT_TIME_SECONDS,
            now=rt.now,
        )

        if result is None:
            err.write(f"Timeout: No response received within {args.timeout} seconds.\n")
            return 1

        if result.error:
            err.write(f"Error: {result.error}\n")
            return 1

        if result.output:
            out.write(f"\nAnswer: {result.output.answer}\n")
        else:
            err.write("Error: No output in response.\n")
            return 1

    finally:
        responses.close()
        client.close()

    return 0
