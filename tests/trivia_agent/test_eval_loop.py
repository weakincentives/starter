"""Tests for eval loop setup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import fakeredis
import pytest
from weakincentives.evals import EvalLoop

from trivia_agent.config import RedisSettings
from trivia_agent.eval_loop import create_eval_loop
from trivia_agent.mailboxes import TriviaMailboxes, create_mailboxes
from trivia_agent.models import TriviaResponse
from trivia_agent.worker import TriviaAgentLoop

if TYPE_CHECKING:
    from weakincentives.adapters import ProviderAdapter


@pytest.fixture
def fake_mailboxes(monkeypatch: pytest.MonkeyPatch) -> TriviaMailboxes:
    """Create mailboxes using fakeredis."""
    fake_redis = fakeredis.FakeRedis()
    monkeypatch.setattr(
        "trivia_agent.mailboxes.Redis.from_url",
        lambda url: fake_redis,
    )
    settings = RedisSettings(
        url="redis://localhost:6379",
        requests_queue="test:requests",
        eval_requests_queue="test:eval:requests",
        debug_bundles_dir=None,
        prompt_overrides_dir=None,
    )
    return create_mailboxes(settings)


class TestCreateEvalLoop:
    """Tests for create_eval_loop function."""

    def test_returns_eval_loop(
        self,
        fake_mailboxes: TriviaMailboxes,
    ) -> None:
        """Test that create_eval_loop returns an EvalLoop."""
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        loop = TriviaAgentLoop(
            adapter=mock_adapter,
            requests=fake_mailboxes.requests,
        )

        eval_loop = create_eval_loop(loop, fake_mailboxes.eval_requests)

        assert isinstance(eval_loop, EvalLoop)
