"""EvalLoop setup for the trivia agent.

This module provides evaluation capabilities for the trivia agent,
allowing you to test agent responses against expected secret answers.

It demonstrates:
- Session-aware evaluators for behavioral assertions
- Integration with MainLoop for consistent execution
- Collocated evals (same prompts, tools, and config as production)
- Debug bundles with eval metadata for tracing
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
    """Create an EvalLoop for the trivia agent.

    The trivia_evaluator checks:
    - Whether the secret answer is correct
    - Response brevity (trivia answers should be short)

    The EvalLoop wraps the same MainLoop used in production, ensuring
    evals run against your exact setup. No drift, no separate harness.

    Args:
        loop: The main TriviaAgentLoop to wrap.
        requests: The eval requests mailbox.
        debug_bundle_dir: Optional directory for debug bundles.

    Returns:
        An EvalLoop configured with the trivia_evaluator.
    """
    config = EvalLoopConfig(debug_bundle_dir=debug_bundle_dir)
    return EvalLoop(
        loop=loop,
        evaluator=cast(SessionEvaluator, trivia_evaluator),  # Session-aware evaluator
        requests=requests,
        config=config,
    )
