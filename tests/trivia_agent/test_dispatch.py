"""Tests for trivia agent dispatch."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from weakincentives.evals import EvalResult, Score
from weakincentives.runtime import MainLoopResult

from trivia_agent.dispatch import (
    DispatchRuntime,
    _wait_for_eval_result,
    _wait_for_response,
    main,
)
from trivia_agent.mailboxes import TriviaMailboxes
from trivia_agent.models import TriviaResponse


class TestDispatchRuntime:
    """Tests for DispatchRuntime dataclass."""

    def test_default_values(self) -> None:
        """Test that DispatchRuntime has sensible defaults."""
        runtime = DispatchRuntime()
        assert runtime.mailboxes is None
        assert runtime.responses is None
        assert runtime.out is not None
        assert runtime.err is not None

    def test_custom_streams(self) -> None:
        """Test that custom streams can be provided."""
        out = io.StringIO()
        err = io.StringIO()
        runtime = DispatchRuntime(out=out, err=err)
        assert runtime.out is out
        assert runtime.err is err


class TestMain:
    """Tests for main() function."""

    def test_missing_question_argument(self) -> None:
        """Test that main() fails without --question."""
        out = io.StringIO()
        err = io.StringIO()

        with pytest.raises(SystemExit) as exc_info:
            main(argv=[], runtime=DispatchRuntime(out=out, err=err))

        assert exc_info.value.code == 2  # argparse error code

    def test_missing_redis_url(self) -> None:
        """Test that main() fails with missing REDIS_URL."""
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict("os.environ", {}, clear=True):
            result = main(
                argv=["--question", "Test?", "--no-wait"],
                runtime=DispatchRuntime(out=out, err=err),
            )

        assert result == 1
        assert "REDIS_URL" in err.getvalue()

    def test_submit_regular_question_no_wait(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test submitting a regular question with --no-wait."""
        out = io.StringIO()
        err = io.StringIO()

        # Create mock mailboxes
        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            out=out,
            err=err,
        )

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        result = main(
            argv=["--question", "What is Python?", "--no-wait"],
            runtime=runtime,
        )

        assert result == 0
        assert "Submitted question: What is Python?" in out.getvalue()
        mock_requests.send.assert_called_once()

        # Check the request content
        sent_request = mock_requests.send.call_args[0][0]
        assert sent_request.request.question == "What is Python?"

    def test_eval_requires_expected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that --eval requires --expected."""
        out = io.StringIO()
        err = io.StringIO()

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        result = main(
            argv=["--question", "What is 2+2?", "--eval"],
            runtime=DispatchRuntime(out=out, err=err),
        )

        assert result == 1
        assert "--expected is required" in err.getvalue()

    def test_submit_eval_case(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test submitting an evaluation case."""
        out = io.StringIO()
        err = io.StringIO()

        # Create mock mailboxes
        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            out=out,
            err=err,
        )

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        result = main(
            argv=[
                "--question",
                "What is 2+2?",
                "--eval",
                "--expected",
                "4",
                "--no-wait",  # Don't wait for results in test
            ],
            runtime=runtime,
        )

        assert result == 0
        assert "Submitted eval case: What is 2+2?" in out.getvalue()
        assert "Expected: 4" in out.getvalue()
        mock_eval_requests.send.assert_called_once()

        # Check the eval request content
        sent_request = mock_eval_requests.send.call_args[0][0]
        assert sent_request.sample.input.question == "What is 2+2?"
        assert sent_request.sample.expected == "4"
        assert sent_request.experiment.name == "cli-eval"

    def test_creates_real_mailboxes_when_not_injected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that main() creates real mailboxes when not injected."""
        out = io.StringIO()
        err = io.StringIO()

        # Patch create_mailboxes to avoid actual Redis connection
        with patch("trivia_agent.dispatch.create_mailboxes") as mock_create:
            mock_mailboxes = MagicMock()
            mock_create.return_value = mock_mailboxes

            runtime = DispatchRuntime(out=out, err=err)

            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
            result = main(
                argv=["--question", "Test?", "--no-wait"],
                runtime=runtime,
            )

        assert result == 0
        mock_create.assert_called_once()


class TestWaitForResponse:
    """Tests for _wait_for_response function."""

    def test_returns_matching_response(self) -> None:
        """Test that matching response is returned."""
        request_id = "12345678-1234-5678-1234-567812345678"
        response = MainLoopResult(
            request_id=UUID(request_id),
            output=TriviaResponse(answer="42"),
            error=None,
        )

        mock_msg = MagicMock()
        mock_msg.body = response
        mock_responses = MagicMock()
        mock_responses.receive.return_value = [mock_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1  # Increments by 0.1 each call

        result = _wait_for_response(
            responses=mock_responses,
            request_id=request_id,
            timeout_seconds=10.0,
            wait_time_seconds=1,
            now=now,
        )

        assert result is not None
        assert result.output is not None
        assert result.output.answer == "42"
        mock_msg.acknowledge.assert_called_once()

    def test_returns_none_on_timeout(self) -> None:
        """Test that None is returned on timeout."""
        mock_responses = MagicMock()
        mock_responses.receive.return_value = []

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 5.0  # Fast forward time

        result = _wait_for_response(
            responses=mock_responses,
            request_id="12345678-1234-5678-1234-567812345678",
            timeout_seconds=10.0,
            wait_time_seconds=1,
            now=now,
        )

        assert result is None

    def test_nacks_non_matching_response(self) -> None:
        """Test that non-matching responses are nacked."""
        request_id = "12345678-1234-5678-1234-567812345678"
        wrong_id = "87654321-4321-8765-4321-876543218765"

        wrong_response = MainLoopResult(
            request_id=UUID(wrong_id),
            output=TriviaResponse(answer="wrong"),
            error=None,
        )
        correct_response = MainLoopResult(
            request_id=UUID(request_id),
            output=TriviaResponse(answer="correct"),
            error=None,
        )

        wrong_msg = MagicMock()
        wrong_msg.body = wrong_response
        correct_msg = MagicMock()
        correct_msg.body = correct_response

        mock_responses = MagicMock()
        mock_responses.receive.side_effect = [[wrong_msg], [correct_msg]]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        result = _wait_for_response(
            responses=mock_responses,
            request_id=request_id,
            timeout_seconds=10.0,
            wait_time_seconds=1,
            now=now,
        )

        assert result is not None
        assert result.output is not None
        assert result.output.answer == "correct"
        wrong_msg.nack.assert_called_once()
        correct_msg.acknowledge.assert_called_once()


class TestMainWithWait:
    """Tests for main() function with waiting for response."""

    def test_wait_for_response_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test waiting for response successfully."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_response_msg = MagicMock()
        mock_response_msg.body = MainLoopResult(
            request_id=UUID("12345678-1234-5678-1234-567812345678"),
            output=TriviaResponse(answer="4"),
            error=None,
        )

        mock_responses = MagicMock()
        mock_responses.receive.return_value = [mock_response_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            responses=mock_responses,
            out=out,
            err=err,
            now=now,
        )

        # Patch Redis and MainLoopRequest to control request_id
        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.MainLoopRequest") as mock_request_cls:
                mock_request = MagicMock()
                mock_request.request_id = UUID("12345678-1234-5678-1234-567812345678")
                mock_request.request = MagicMock()
                mock_request_cls.return_value = mock_request

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 2+2?"],
                    runtime=runtime,
                )

        assert result == 0
        assert "Answer: 4" in out.getvalue()

    def test_wait_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test timeout when waiting for response."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_responses = MagicMock()
        mock_responses.receive.return_value = []  # No messages

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 100.0  # Fast forward past timeout

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            responses=mock_responses,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
            result = main(
                argv=["--question", "What is 2+2?", "--timeout", "1"],
                runtime=runtime,
            )

        assert result == 1
        assert "Timeout" in err.getvalue()

    def test_response_with_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test handling response with error."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_response_msg = MagicMock()
        mock_response_msg.body = MainLoopResult(
            request_id=UUID("12345678-1234-5678-1234-567812345678"),
            output=None,
            error="Agent failed",
        )

        mock_responses = MagicMock()
        mock_responses.receive.return_value = [mock_response_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            responses=mock_responses,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.MainLoopRequest") as mock_request_cls:
                mock_request = MagicMock()
                mock_request.request_id = UUID("12345678-1234-5678-1234-567812345678")
                mock_request.request = MagicMock()
                mock_request_cls.return_value = mock_request

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 2+2?"],
                    runtime=runtime,
                )

        assert result == 1
        assert "Agent failed" in err.getvalue()

    def test_response_with_no_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test handling response with no output."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_response_msg = MagicMock()
        mock_response_msg.body = MainLoopResult(
            request_id=UUID("12345678-1234-5678-1234-567812345678"),
            output=None,
            error=None,
        )

        mock_responses = MagicMock()
        mock_responses.receive.return_value = [mock_response_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            responses=mock_responses,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.MainLoopRequest") as mock_request_cls:
                mock_request = MagicMock()
                mock_request.request_id = UUID("12345678-1234-5678-1234-567812345678")
                mock_request.request = MagicMock()
                mock_request_cls.return_value = mock_request

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 2+2?"],
                    runtime=runtime,
                )

        assert result == 1
        assert "No output" in err.getvalue()


class TestWaitForEvalResult:
    """Tests for _wait_for_eval_result function."""

    def test_returns_matching_result(self) -> None:
        """Test that matching eval result is returned."""
        sample_id = "sample-123"
        eval_result = EvalResult(
            sample_id=sample_id,
            experiment_name="test",
            score=Score(value=1.0, passed=True, reason="Correct"),
            latency_ms=100,
        )

        mock_msg = MagicMock()
        mock_msg.body = eval_result
        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = [mock_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        result = _wait_for_eval_result(
            eval_results=mock_eval_results,
            sample_id=sample_id,
            timeout_seconds=10.0,
            wait_time_seconds=1,
            now=now,
        )

        assert result is not None
        assert result.score.passed is True
        mock_msg.acknowledge.assert_called_once()

    def test_returns_none_on_timeout(self) -> None:
        """Test that None is returned on timeout."""
        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = []

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 5.0

        result = _wait_for_eval_result(
            eval_results=mock_eval_results,
            sample_id="sample-123",
            timeout_seconds=10.0,
            wait_time_seconds=1,
            now=now,
        )

        assert result is None

    def test_nacks_non_matching_result(self) -> None:
        """Test that non-matching results are nacked."""
        sample_id = "sample-123"
        wrong_id = "sample-456"

        wrong_result = EvalResult(
            sample_id=wrong_id,
            experiment_name="test",
            score=Score(value=0.0, passed=False, reason="Wrong"),
            latency_ms=100,
        )
        correct_result = EvalResult(
            sample_id=sample_id,
            experiment_name="test",
            score=Score(value=1.0, passed=True, reason="Correct"),
            latency_ms=100,
        )

        wrong_msg = MagicMock()
        wrong_msg.body = wrong_result
        correct_msg = MagicMock()
        correct_msg.body = correct_result

        mock_eval_results = MagicMock()
        mock_eval_results.receive.side_effect = [[wrong_msg], [correct_msg]]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        result = _wait_for_eval_result(
            eval_results=mock_eval_results,
            sample_id=sample_id,
            timeout_seconds=10.0,
            wait_time_seconds=1,
            now=now,
        )

        assert result is not None
        assert result.score.passed is True
        wrong_msg.nack.assert_called_once()
        correct_msg.acknowledge.assert_called_once()


class TestEvalWithWait:
    """Tests for eval dispatch with waiting for results."""

    def test_eval_wait_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test waiting for eval result successfully."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_eval_msg = MagicMock()
        mock_eval_msg.body = EvalResult(
            sample_id="test-sample",
            experiment_name="cli-eval",
            score=Score(value=0.85, passed=True, reason="Correct; Concise"),
            latency_ms=150,
        )

        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = [mock_eval_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            eval_results=mock_eval_results,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.uuid4") as mock_uuid4:
                mock_uuid4.return_value = MagicMock(__str__=lambda _: "test-sample")

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 42?", "--eval", "--expected", "42"],
                    runtime=runtime,
                )

        assert result == 0
        output = out.getvalue()
        assert "=== Eval Result ===" in output
        assert "PASSED" in output
        assert "0.85" in output

    def test_eval_wait_with_experiment_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test eval with experiment metadata (owner and description)."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_eval_msg = MagicMock()
        mock_eval_msg.body = EvalResult(
            sample_id="test-sample",
            experiment_name="my-experiment",
            score=Score(value=1.0, passed=True, reason="Correct"),
            latency_ms=100,
        )

        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = [mock_eval_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            eval_results=mock_eval_results,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.uuid4") as mock_uuid4:
                mock_uuid4.return_value = MagicMock(__str__=lambda _: "test-sample")

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=[
                        "--question",
                        "What is the secret?",
                        "--eval",
                        "--expected",
                        "42",
                        "--experiment",
                        "my-experiment",
                        "--owner",
                        "test-owner",
                        "--description",
                        "Testing experiment metadata",
                    ],
                    runtime=runtime,
                )

        assert result == 0
        output = out.getvalue()
        assert "Experiment: my-experiment" in output
        assert "Owner: test-owner" in output
        assert "Description: Testing experiment metadata" in output
        assert "=== Eval Result ===" in output
        assert "PASSED" in output

    def test_eval_wait_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test eval that fails."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_eval_msg = MagicMock()
        mock_eval_msg.body = EvalResult(
            sample_id="test-sample",
            experiment_name="cli-eval",
            score=Score(value=0.0, passed=False, reason="Wrong answer"),
            latency_ms=150,
        )

        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = [mock_eval_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            eval_results=mock_eval_results,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.uuid4") as mock_uuid4:
                mock_uuid4.return_value = MagicMock(__str__=lambda _: "test-sample")

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 42?", "--eval", "--expected", "banana"],
                    runtime=runtime,
                )

        assert result == 1
        output = out.getvalue()
        assert "FAILED" in output

    def test_eval_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test timeout when waiting for eval result."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = []

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 100.0

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            eval_results=mock_eval_results,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
            result = main(
                argv=[
                    "--question",
                    "What is 42?",
                    "--eval",
                    "--expected",
                    "42",
                    "--timeout",
                    "1",
                ],
                runtime=runtime,
            )

        assert result == 1
        assert "Timeout" in err.getvalue()

    def test_eval_with_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test eval result with error."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_eval_msg = MagicMock()
        mock_eval_msg.body = EvalResult(
            sample_id="test-sample",
            experiment_name="cli-eval",
            score=Score(value=0.0, passed=False, reason=""),
            latency_ms=0,
            error="Agent crashed",
        )

        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = [mock_eval_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            eval_results=mock_eval_results,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.uuid4") as mock_uuid4:
                mock_uuid4.return_value = MagicMock(__str__=lambda _: "test-sample")

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 42?", "--eval", "--expected", "42"],
                    runtime=runtime,
                )

        assert result == 1
        assert "Agent crashed" in err.getvalue()

    def test_eval_with_bundle_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test eval result includes bundle path in output."""
        out = io.StringIO()
        err = io.StringIO()

        mock_requests = MagicMock()
        mock_eval_requests = MagicMock()
        mock_mailboxes = TriviaMailboxes(
            requests=mock_requests,
            eval_requests=mock_eval_requests,
        )

        mock_eval_msg = MagicMock()
        mock_eval_msg.body = EvalResult(
            sample_id="test-sample",
            experiment_name="cli-eval",
            score=Score(value=1.0, passed=True, reason="Correct"),
            latency_ms=150,
            bundle_path=Path("/tmp/debug_bundles/abc123.zip"),
        )

        mock_eval_results = MagicMock()
        mock_eval_results.receive.return_value = [mock_eval_msg]

        call_count = 0

        def now() -> float:
            nonlocal call_count
            call_count += 1
            return call_count * 0.1

        runtime = DispatchRuntime(
            mailboxes=mock_mailboxes,
            eval_results=mock_eval_results,
            out=out,
            err=err,
            now=now,
        )

        with patch("trivia_agent.dispatch.Redis"):
            with patch("trivia_agent.dispatch.uuid4") as mock_uuid4:
                mock_uuid4.return_value = MagicMock(__str__=lambda _: "test-sample")

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                result = main(
                    argv=["--question", "What is 42?", "--eval", "--expected", "42"],
                    runtime=runtime,
                )

        assert result == 0
        output = out.getvalue()
        assert "Bundle: /tmp/debug_bundles/abc123.zip" in output
