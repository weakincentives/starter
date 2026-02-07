"""Tests for trivia agent loop."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from trivia_agent.agent_loop import (
    TriviaAgentLoop,
    TriviaRuntime,
    create_workspace_section,
    enumerate_workspace_mounts,
    main,
)
from trivia_agent.config import RedisSettings
from trivia_agent.mailboxes import TriviaMailboxes, create_mailboxes
from trivia_agent.models import TriviaRequest, TriviaResponse
from trivia_agent.sections import QuestionParams, build_question_section

if TYPE_CHECKING:
    from weakincentives.adapters import ProviderAdapter


class FakeAdapter:
    """Fake adapter for testing that returns canned responses."""

    def __init__(self, response: TriviaResponse) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []


@pytest.fixture
def fake_adapter() -> FakeAdapter:
    """Create a fake adapter returning a canned response."""
    return FakeAdapter(TriviaResponse(answer="42"))


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


class TestEnumerateWorkspaceMounts:
    """Tests for enumerate_workspace_mounts function."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test that non-existent directory returns empty tuple."""
        result = enumerate_workspace_mounts(tmp_path / "nonexistent")
        assert result == ()

    def test_returns_empty_for_file(self, tmp_path: Path) -> None:
        """Test that file path returns empty tuple."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        result = enumerate_workspace_mounts(file_path)
        assert result == ()

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        """Test that empty directory returns empty tuple."""
        result = enumerate_workspace_mounts(tmp_path)
        assert result == ()

    def test_returns_mounts_for_files(self, tmp_path: Path) -> None:
        """Test that files are returned as mounts."""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.md").write_text("content2")
        result = enumerate_workspace_mounts(tmp_path)
        assert len(result) == 2
        assert result[0].mount_path == "file1.txt"
        assert result[1].mount_path == "file2.md"

    def test_ignores_directories(self, tmp_path: Path) -> None:
        """Test that subdirectories are ignored."""
        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "subdir").mkdir()
        result = enumerate_workspace_mounts(tmp_path)
        assert len(result) == 1
        assert result[0].mount_path == "file.txt"

    def test_mounts_sorted_by_name(self, tmp_path: Path) -> None:
        """Test that mounts are sorted alphabetically."""
        (tmp_path / "zebra.txt").write_text("z")
        (tmp_path / "alpha.txt").write_text("a")
        result = enumerate_workspace_mounts(tmp_path)
        assert [m.mount_path for m in result] == ["alpha.txt", "zebra.txt"]


class TestCreateWorkspaceSection:
    """Tests for create_workspace_section function."""

    def test_creates_workspace_section(self, tmp_path: Path) -> None:
        """Test that workspace section is created."""
        from weakincentives.adapters.claude_agent_sdk import ClaudeAgentWorkspaceSection
        from weakincentives.runtime import Session

        (tmp_path / "CLAUDE.md").write_text("# Test")
        session = Session()
        result = create_workspace_section(session=session, workspace_dir=tmp_path)
        assert isinstance(result, ClaudeAgentWorkspaceSection)

    def test_mounts_files_from_workspace(self, tmp_path: Path) -> None:
        """Test that files from workspace are mounted."""
        from weakincentives.runtime import Session

        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        session = Session()
        result = create_workspace_section(session=session, workspace_dir=tmp_path)
        assert len(result._mounts) == 2


class TestBuildQuestionSection:
    """Tests for build_question_section."""

    def test_section_has_correct_key(self) -> None:
        """Test that section has the correct key."""
        section = build_question_section()
        assert section.key == "question"

    def test_section_has_correct_title(self) -> None:
        """Test that section has the correct title."""
        section = build_question_section()
        assert section.title == "Question"


class TestQuestionParams:
    """Tests for QuestionParams."""

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        params = QuestionParams(question="What is Python?")
        assert params.question == "What is Python?"


class TestTriviaAgentLoop:
    """Tests for TriviaAgentLoop."""

    def test_prepare_creates_prompt_with_question(
        self,
        fake_mailboxes: TriviaMailboxes,
    ) -> None:
        """Test that prepare() creates a prompt with the question."""
        # Create a mock adapter
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        loop = TriviaAgentLoop(
            adapter=mock_adapter,
            requests=fake_mailboxes.requests,
        )

        request = TriviaRequest(question="What is 2+2?")
        prompt, session = loop.prepare(request)

        # Render the prompt to check content
        rendered = str(prompt.render())
        assert "What is 2+2?" in rendered
        assert "Question" in rendered

    def test_prepare_returns_session(
        self,
        fake_mailboxes: TriviaMailboxes,
    ) -> None:
        """Test that prepare() returns a valid session."""
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        loop = TriviaAgentLoop(
            adapter=mock_adapter,
            requests=fake_mailboxes.requests,
        )

        request = TriviaRequest(question="Test question")
        prompt, session = loop.prepare(request)

        assert session is not None

    def test_prepare_with_experiment(
        self,
        fake_mailboxes: TriviaMailboxes,
    ) -> None:
        """Test that prepare() handles experiment parameter."""
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        loop = TriviaAgentLoop(
            adapter=mock_adapter,
            requests=fake_mailboxes.requests,
        )

        request = TriviaRequest(question="Test question")

        # Create a mock experiment
        mock_experiment = MagicMock()
        mock_experiment.overrides_tag = "test-tag"

        prompt, session = loop.prepare(request, experiment=mock_experiment)

        # Should not raise
        assert prompt is not None
        assert session is not None

    def test_prepare_seeds_overrides_store(
        self,
        fake_mailboxes: TriviaMailboxes,
    ) -> None:
        """Test that prepare() seeds the overrides store when provided."""
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()
        mock_overrides_store = MagicMock()

        loop = TriviaAgentLoop(
            adapter=mock_adapter,
            requests=fake_mailboxes.requests,
            overrides_store=mock_overrides_store,
        )

        request = TriviaRequest(question="Test question")
        prompt, session = loop.prepare(request)

        # Verify seed was called with the prompt and default tag
        mock_overrides_store.seed.assert_called_once()
        call_args = mock_overrides_store.seed.call_args
        assert call_args.kwargs.get("tag") == "latest"


class TestTriviaRuntime:
    """Tests for TriviaRuntime dataclass."""

    def test_default_values(self) -> None:
        """Test that TriviaRuntime has sensible defaults."""
        runtime = TriviaRuntime()
        assert runtime.adapter is None
        assert runtime.mailboxes is None
        # out and err should be stdout/stderr by default
        assert runtime.out is not None
        assert runtime.err is not None

    def test_custom_streams(self) -> None:
        """Test that custom streams can be provided."""
        out = io.StringIO()
        err = io.StringIO()
        runtime = TriviaRuntime(out=out, err=err)
        assert runtime.out is out
        assert runtime.err is err


class TestMain:
    """Tests for main() function."""

    def test_missing_redis_url(self) -> None:
        """Test that main() fails with missing REDIS_URL."""
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict("os.environ", {}, clear=True):
            result = main(runtime=TriviaRuntime(out=out, err=err))

        assert result == 1
        assert "REDIS_URL" in err.getvalue()

    def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that main() fails with missing ANTHROPIC_API_KEY."""
        out = io.StringIO()
        err = io.StringIO()

        # Set REDIS_URL but not ANTHROPIC_API_KEY
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = main(runtime=TriviaRuntime(out=out, err=err))

        assert result == 1
        error_output = err.getvalue()
        assert "ANTHROPIC_API_KEY" in error_output
        assert "export ANTHROPIC_API_KEY=" in error_output

    def test_api_key_not_required_when_adapter_injected(
        self,
        fake_mailboxes: TriviaMailboxes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that API key is not required when adapter is injected."""
        out = io.StringIO()
        err = io.StringIO()
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        runtime = TriviaRuntime(
            adapter=mock_adapter,
            mailboxes=fake_mailboxes,
            out=out,
            err=err,
        )

        # Set REDIS_URL but not ANTHROPIC_API_KEY
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("trivia_agent.agent_loop.LoopGroup") as mock_loop_group:
            mock_instance = MagicMock()
            mock_loop_group.return_value = mock_instance
            result = main(runtime=runtime)

        # Should succeed because adapter is injected
        assert result == 0

    def test_successful_startup(
        self,
        fake_mailboxes: TriviaMailboxes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successful startup with injected dependencies."""
        out = io.StringIO()
        err = io.StringIO()
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        runtime = TriviaRuntime(
            adapter=mock_adapter,
            mailboxes=fake_mailboxes,
            out=out,
            err=err,
        )

        # Patch LoopGroup.run to avoid actually running
        with patch("trivia_agent.agent_loop.LoopGroup") as mock_loop_group:
            mock_instance = MagicMock()
            mock_loop_group.return_value = mock_instance

            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
            result = main(runtime=runtime)

        assert result == 0
        assert "Starting trivia agent worker" in out.getvalue()
        mock_instance.run.assert_called_once()

    def test_creates_real_dependencies_when_not_injected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that main() creates real dependencies when not injected."""
        out = io.StringIO()
        err = io.StringIO()

        fake_redis = fakeredis.FakeRedis()
        monkeypatch.setattr(
            "trivia_agent.mailboxes.Redis.from_url",
            lambda url: fake_redis,
        )

        runtime = TriviaRuntime(out=out, err=err)

        with patch("trivia_agent.agent_loop.LoopGroup") as mock_loop_group:
            mock_instance = MagicMock()
            mock_loop_group.return_value = mock_instance

            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = main(runtime=runtime)

        assert result == 0

    def test_debug_bundle_config_when_dir_set(
        self,
        fake_mailboxes: TriviaMailboxes,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that debug bundle config is set when directory is specified."""
        out = io.StringIO()
        err = io.StringIO()
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        runtime = TriviaRuntime(
            adapter=mock_adapter,
            mailboxes=fake_mailboxes,
            out=out,
            err=err,
        )

        bundles_dir = tmp_path / "debug_bundles"

        with patch("trivia_agent.agent_loop.LoopGroup") as mock_loop_group:
            with patch("trivia_agent.agent_loop.TriviaAgentLoop") as mock_qa_loop:
                mock_instance = MagicMock()
                mock_loop_group.return_value = mock_instance
                mock_qa_loop.return_value = MagicMock()

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                monkeypatch.setenv("TRIVIA_DEBUG_BUNDLES_DIR", str(bundles_dir))
                result = main(runtime=runtime)

        assert result == 0
        # Check that TriviaAgentLoop was called with config containing debug_bundle
        call_kwargs = mock_qa_loop.call_args.kwargs
        assert call_kwargs.get("config") is not None
        assert call_kwargs["config"].debug_bundle is not None
        assert call_kwargs["config"].debug_bundle.target == bundles_dir
        assert bundles_dir.exists()  # Directory should be created

    def test_no_debug_bundle_config_when_dir_not_set(
        self,
        fake_mailboxes: TriviaMailboxes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that debug bundle is None when directory is not set."""
        out = io.StringIO()
        err = io.StringIO()
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        runtime = TriviaRuntime(
            adapter=mock_adapter,
            mailboxes=fake_mailboxes,
            out=out,
            err=err,
        )

        with patch("trivia_agent.agent_loop.LoopGroup") as mock_loop_group:
            with patch("trivia_agent.agent_loop.TriviaAgentLoop") as mock_qa_loop:
                mock_instance = MagicMock()
                mock_loop_group.return_value = mock_instance
                mock_qa_loop.return_value = MagicMock()

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                # Don't set TRIVIA_DEBUG_BUNDLES_DIR
                result = main(runtime=runtime)

        assert result == 0
        call_kwargs = mock_qa_loop.call_args.kwargs
        assert call_kwargs.get("config") is not None
        assert call_kwargs["config"].debug_bundle is None
        assert call_kwargs["config"].deadline is None

    def test_prompt_overrides_store_when_dir_set(
        self,
        fake_mailboxes: TriviaMailboxes,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that prompt overrides store is set when directory is specified."""
        out = io.StringIO()
        err = io.StringIO()
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        runtime = TriviaRuntime(
            adapter=mock_adapter,
            mailboxes=fake_mailboxes,
            out=out,
            err=err,
        )

        overrides_dir = tmp_path / "prompt_overrides"

        with patch("trivia_agent.agent_loop.LoopGroup") as mock_loop_group:
            with patch("trivia_agent.agent_loop.TriviaAgentLoop") as mock_qa_loop:
                mock_instance = MagicMock()
                mock_loop_group.return_value = mock_instance
                mock_qa_loop.return_value = MagicMock()

                monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
                monkeypatch.setenv("TRIVIA_PROMPT_OVERRIDES_DIR", str(overrides_dir))
                result = main(runtime=runtime)

        assert result == 0
        call_kwargs = mock_qa_loop.call_args.kwargs
        assert call_kwargs.get("overrides_store") is not None
        assert overrides_dir.exists()  # Directory should be created

    def test_adapter_creation_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that main() handles adapter creation failure gracefully."""
        out = io.StringIO()
        err = io.StringIO()

        runtime = TriviaRuntime(out=out, err=err)

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("trivia_agent.agent_loop.create_adapter") as mock_create_adapter:
            mock_create_adapter.side_effect = RuntimeError("SDK initialization failed")
            result = main(runtime=runtime)

        assert result == 1
        assert "Failed to create adapter" in err.getvalue()
        assert "SDK initialization failed" in err.getvalue()

    def test_mailbox_creation_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that main() handles mailbox/Redis connection failure gracefully."""
        out = io.StringIO()
        err = io.StringIO()
        mock_adapter: ProviderAdapter[TriviaResponse] = MagicMock()

        runtime = TriviaRuntime(adapter=mock_adapter, out=out, err=err)

        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        with patch("trivia_agent.agent_loop.create_mailboxes") as mock_create_mailboxes:
            mock_create_mailboxes.side_effect = ConnectionError("Connection refused")
            result = main(runtime=runtime)

        assert result == 1
        assert "Failed to connect to Redis" in err.getvalue()
        assert "Connection refused" in err.getvalue()
