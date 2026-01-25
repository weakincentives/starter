"""EvalLoop setup for the trivia agent.

This module provides evaluation capabilities for the trivia agent,
allowing you to test agent responses against expected secret answers.

The EvalLoop wraps your production MainLoop, ensuring evaluations run
against your exact agent configuration with no drift or separate test harness.

Key features:
    - Session-aware evaluators for behavioral assertions
    - Integration with MainLoop for consistent execution
    - Collocated evals (same prompts, tools, and config as production)
    - Debug bundles with eval metadata for tracing

Usage:
    To run an evaluation, use the CLI command::

        make dispatch-eval QUESTION="What is the secret number?" EXPECTED="42"

    Or programmatically::

        from trivia_agent.eval_loop import create_eval_loop
        from trivia_agent.worker import TriviaAgentLoop
        from trivia_agent.mailboxes import EvalRequestsMailbox

        loop = TriviaAgentLoop(...)
        mailbox = EvalRequestsMailbox(...)
        eval_loop = create_eval_loop(loop, mailbox)
        # Process eval requests through the mailbox

See Also:
    - :mod:`trivia_agent.evaluators` for the trivia_evaluator implementation
    - :mod:`trivia_agent.worker` for the TriviaAgentLoop being wrapped
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from weakincentives.evals import EvalLoop, EvalLoopConfig, SessionEvaluator

from trivia_agent.evaluators import trivia_evaluator
from trivia_agent.mailboxes import EvalRequestsMailbox
from trivia_agent.models import TriviaRequest, TriviaResponse
from trivia_agent.worker import TriviaAgentLoop


def create_eval_loop(
    loop: TriviaAgentLoop,
    requests: EvalRequestsMailbox,
    debug_bundle_dir: Path | None = None,
) -> EvalLoop[TriviaRequest, TriviaResponse, str]:
    """Create an EvalLoop for evaluating trivia agent responses.

    This factory function creates an EvalLoop that wraps the production
    TriviaAgentLoop, enabling automated testing of agent responses against
    expected secret answers. The EvalLoop uses the same prompts, tools,
    and configuration as production, ensuring evaluation fidelity.

    The configured trivia_evaluator checks:
        - **Correctness**: Whether the agent's response contains the expected
          secret answer (42, banana, purple, or "Open sesame!")
        - **Brevity**: Whether the response is appropriately concise for a
          trivia answer (penalizes overly verbose responses)

    Args:
        loop: The TriviaAgentLoop instance to wrap. This should be a fully
            configured production loop with skills loaded and tools registered.
        requests: The EvalRequestsMailbox that provides evaluation requests.
            Each request contains a question and an expected answer string.
        debug_bundle_dir: Optional directory path where debug bundles will be
            saved. Debug bundles contain execution artifacts useful for
            tracing and debugging eval failures. If None, bundles are not saved.

    Returns:
        An EvalLoop instance parameterized with:
            - TriviaRequest as the input type
            - TriviaResponse as the output type
            - str as the expected answer type

        The returned EvalLoop can process evaluation requests from the mailbox
        and will produce scored results based on the trivia_evaluator logic.

    Example:
        Create an eval loop and use it to evaluate agent responses::

            from pathlib import Path
            from trivia_agent.eval_loop import create_eval_loop
            from trivia_agent.worker import TriviaAgentLoop
            from trivia_agent.mailboxes import EvalRequestsMailbox

            # Set up components
            loop = TriviaAgentLoop(config=my_config)
            mailbox = EvalRequestsMailbox(redis_client=redis)
            bundle_dir = Path("debug_bundles")

            # Create the eval loop
            eval_loop = create_eval_loop(
                loop=loop,
                requests=mailbox,
                debug_bundle_dir=bundle_dir,
            )

            # The eval loop will process requests from the mailbox
            # and save debug bundles for inspection

    Note:
        The evaluator is session-aware, meaning it has access to the full
        session context (tool calls, messages, etc.) when scoring responses.
        This enables richer evaluation logic beyond simple string matching.
    """
    config = EvalLoopConfig(debug_bundle_dir=debug_bundle_dir)
    return EvalLoop(
        loop=loop,
        evaluator=cast(SessionEvaluator, trivia_evaluator),  # Session-aware evaluator
        requests=requests,
        config=config,
    )
