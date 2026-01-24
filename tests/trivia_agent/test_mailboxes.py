"""Tests for trivia agent mailboxes."""

import dataclasses
from pathlib import Path
from uuid import UUID

import fakeredis
import pytest

from trivia_agent.config import RedisSettings
from trivia_agent.mailboxes import (
    TriviaMailboxes,
    _parse_eval_request,
    build_reply_queue_name,
    create_eval_results_mailbox,
    create_mailboxes,
    create_responses_mailbox,
)


@pytest.fixture
def redis_settings() -> RedisSettings:
    """Create test Redis settings."""
    return RedisSettings(
        url="redis://localhost:6379",
        requests_queue="test:requests",
        eval_requests_queue="test:eval:requests",
        debug_bundles_dir=None,
        prompt_overrides_dir=None,
    )


class TestTriviaMailboxes:
    """Tests for TriviaMailboxes dataclass."""

    def test_is_dataclass(self) -> None:
        """Test that TriviaMailboxes is a dataclass."""
        assert dataclasses.is_dataclass(TriviaMailboxes)


class TestCreateMailboxes:
    """Tests for create_mailboxes function."""

    def test_creates_mailboxes_with_correct_queue_names(
        self,
        redis_settings: RedisSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that mailboxes are created with correct queue names."""
        # Patch Redis.from_url to use fakeredis
        fake_redis = fakeredis.FakeRedis()
        monkeypatch.setattr(
            "trivia_agent.mailboxes.Redis.from_url",
            lambda url: fake_redis,
        )

        mailboxes = create_mailboxes(redis_settings)

        assert mailboxes.requests.name == "test:requests"
        assert mailboxes.eval_requests.name == "test:eval:requests"

    def test_creates_mailboxes_with_custom_queue_names(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that custom queue names are used."""
        fake_redis = fakeredis.FakeRedis()
        monkeypatch.setattr(
            "trivia_agent.mailboxes.Redis.from_url",
            lambda url: fake_redis,
        )

        settings = RedisSettings(
            url="redis://custom:6380",
            requests_queue="custom:queue",
            eval_requests_queue="custom:eval",
            debug_bundles_dir=Path("./bundles"),
            prompt_overrides_dir=None,
        )

        mailboxes = create_mailboxes(settings)

        assert mailboxes.requests.name == "custom:queue"
        assert mailboxes.eval_requests.name == "custom:eval"

    def test_returns_qa_mailboxes_instance(
        self,
        redis_settings: RedisSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that create_mailboxes returns a TriviaMailboxes instance."""
        fake_redis = fakeredis.FakeRedis()
        monkeypatch.setattr(
            "trivia_agent.mailboxes.Redis.from_url",
            lambda url: fake_redis,
        )

        mailboxes = create_mailboxes(redis_settings)

        assert isinstance(mailboxes, TriviaMailboxes)


class TestBuildReplyQueueName:
    """Tests for build_reply_queue_name function."""

    def test_builds_queue_name_with_prefix_and_id(self) -> None:
        """Test building reply queue name with prefix and request ID."""
        request_id = UUID("12345678-1234-5678-1234-567812345678")
        name = build_reply_queue_name("qa:replies", request_id)
        assert name == "qa:replies-12345678-1234-5678-1234-567812345678"

    def test_empty_prefix_raises_error(self) -> None:
        """Test that empty prefix raises ValueError."""
        request_id = UUID("12345678-1234-5678-1234-567812345678")
        with pytest.raises(ValueError, match="must be non-empty"):
            build_reply_queue_name("", request_id)


class TestCreateResponsesMailbox:
    """Tests for create_responses_mailbox function."""

    def test_creates_mailbox_with_correct_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that responses mailbox is created with correct name."""
        fake_redis = fakeredis.FakeRedis()

        mailbox = create_responses_mailbox(fake_redis, "test:replies")  # type: ignore[arg-type]

        assert mailbox.name == "test:replies"


class TestCreateEvalResultsMailbox:
    """Tests for create_eval_results_mailbox function."""

    def test_creates_mailbox_with_correct_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that eval results mailbox is created with correct name."""
        fake_redis = fakeredis.FakeRedis()

        mailbox = create_eval_results_mailbox(fake_redis, "test:eval:replies")  # type: ignore[arg-type]

        assert mailbox.name == "test:eval:replies"


class TestParseEvalRequest:
    """Tests for _parse_eval_request wrapper."""

    def test_parses_eval_request_with_nested_fields(self) -> None:
        """Test that EvalRequest is parsed with properly-typed nested fields."""
        data = {
            "sample": {
                "id": "sample-1",
                "input": {"question": "What is the secret?"},
                "expected": "42",
            },
            "experiment": {
                "name": "test-exp",
                "overrides_tag": "latest",
                "flags": {},
                "owner": "test-owner",
                "description": "Test description",
            },
        }
        result = _parse_eval_request(data)
        assert result.sample.id == "sample-1"
        assert result.sample.input.question == "What is the secret?"
        assert result.sample.expected == "42"
        assert result.experiment.name == "test-exp"
        assert result.experiment.overrides_tag == "latest"
        assert result.experiment.owner == "test-owner"
        assert result.experiment.description == "Test description"
