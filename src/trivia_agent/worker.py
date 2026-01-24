"""MainLoop + EvalLoop entry point for the trivia agent.

This module demonstrates the full WINK architecture:
- MainLoop for production request processing
- EvalLoop for evaluation with session-aware scoring
- PromptTemplate with multiple sections
- Feedback providers for soft course correction
- Progressive disclosure with SUMMARY visibility
- Custom tools attached to sections
- Workspace seeding via ClaudeAgentWorkspaceSection
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from weakincentives import FrozenDataclass, Prompt
from weakincentives.adapters import ProviderAdapter
from weakincentives.adapters.claude_agent_sdk import ClaudeAgentWorkspaceSection, HostMount
from weakincentives.deadlines import Deadline
from weakincentives.debug.bundle import BundleConfig
from weakincentives.prompt import PromptTemplate
from weakincentives.prompt.overrides import LocalPromptOverridesStore, PromptOverridesStore
from weakincentives.runtime import (
    LoopGroup,
    MainLoop,
    MainLoopConfig,
    MainLoopRequest,
    MainLoopResult,
    Session,
)
from weakincentives.runtime.logging import configure_logging
from weakincentives.runtime.mailbox import Mailbox

from trivia_agent.adapters import create_adapter
from trivia_agent.config import load_redis_settings
from trivia_agent.feedback import build_feedback_providers
from trivia_agent.isolation import API_KEY_ENV, resolve_isolation_config
from trivia_agent.mailboxes import TriviaMailboxes, create_mailboxes
from trivia_agent.models import TriviaRequest, TriviaResponse
from trivia_agent.sections import (
    EmptyParams,
    GameRulesSection,
    HintsSection,
    LuckyDiceSection,
    QuestionParams,
    QuestionSection,
    build_task_examples_section,  # type: ignore[attr-defined]
)

if TYPE_CHECKING:
    from weakincentives.evals import Experiment

# Default deadline duration for agent execution (1 minute)
DEFAULT_DEADLINE_DURATION = timedelta(minutes=1)

# Default workspace seed directory
DEFAULT_WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"


def enumerate_workspace_mounts(workspace_dir: Path) -> tuple[HostMount, ...]:
    """Enumerate files in workspace directory as mounts.

    Each file in the workspace directory is mounted at the workspace root.

    Args:
        workspace_dir: Directory containing files to mount.

    Returns:
        Tuple of HostMount objects for each file.
    """
    if not workspace_dir.exists() or not workspace_dir.is_dir():
        return ()
    return tuple(
        HostMount(host_path=str(f.resolve()), mount_path=f.name)
        for f in sorted(workspace_dir.iterdir())
        if f.is_file()
    )


def create_workspace_section(
    *,
    session: Session,
    workspace_dir: Path,
) -> ClaudeAgentWorkspaceSection:
    """Create a workspace section with seeded content from host.

    Args:
        session: Session for the workspace section.
        workspace_dir: Path to host directory to seed into workspace.

    Returns:
        ClaudeAgentWorkspaceSection configured with seed mounts.
    """
    mounts = enumerate_workspace_mounts(workspace_dir)
    return ClaudeAgentWorkspaceSection(
        session=session,
        mounts=mounts,
        allowed_host_roots=(str(workspace_dir.parent),),
    )


def build_prompt_template() -> PromptTemplate[TriviaResponse]:
    """Build the trivia agent prompt template.

    This template demonstrates WINK's differentiated capabilities:
    - Multiple sections with different purposes
    - Progressive disclosure (GameRulesSection starts summarized)
    - Sections with attached tools (HintsSection)
    - Task examples for multi-step workflow demonstrations
    - Feedback providers for soft guidance

    Note: The workspace section is created per-request in prepare()
    because it needs a session reference.

    Returns:
        PromptTemplate configured with sections and feedback providers.
    """
    return PromptTemplate[TriviaResponse](
        ns="trivia",
        key="main",
        sections=[  # type: ignore[list-item]
            QuestionSection(),
            GameRulesSection(),  # Progressive disclosure - starts summarized
            HintsSection(),  # Has attached hint_lookup tool
            LuckyDiceSection(),  # Lucky Dice mini-game with policy enforcement
            build_task_examples_section(),  # Multi-step workflow examples
        ],
        feedback_providers=build_feedback_providers(),
    )


class TriviaAgentLoop(MainLoop[TriviaRequest, TriviaResponse]):
    """MainLoop implementation for the trivia agent.

    This loop demonstrates:
    - Custom prepare() for request-specific prompt configuration
    - Workspace seeding per request
    - Integration with EvalLoop for evaluation
    """

    _workspace_dir: Path
    _base_template: PromptTemplate[TriviaResponse]

    def __init__(
        self,
        *,
        adapter: ProviderAdapter[TriviaResponse],
        requests: Mailbox[MainLoopRequest[TriviaRequest], MainLoopResult[TriviaResponse]],
        config: MainLoopConfig | None = None,
        workspace_dir: Path | None = None,
        overrides_store: PromptOverridesStore | None = None,
    ) -> None:
        """Initialize the trivia agent loop.

        Args:
            adapter: Provider adapter for evaluation.
            requests: Mailbox for incoming requests.
            config: Optional MainLoop configuration.
            workspace_dir: Optional workspace directory for seeding.
            overrides_store: Optional prompt overrides store for local customizations.
        """
        super().__init__(adapter=adapter, requests=requests, config=config)
        self._workspace_dir = workspace_dir or DEFAULT_WORKSPACE_DIR
        self._base_template = build_prompt_template()
        self._overrides_store = overrides_store

    def prepare(
        self,
        request: TriviaRequest,
        *,
        experiment: Experiment | None = None,
    ) -> tuple[Prompt[TriviaResponse], Session]:
        """Prepare the prompt and session for a trivia request.

        This method demonstrates:
        - Session creation per request
        - Workspace section with seeded files
        - Dynamic section composition
        - Experiment-driven overrides

        Args:
            request: The trivia request containing the question.
            experiment: Optional experiment for A/B testing.

        Returns:
            A tuple of (prompt, session) ready for evaluation.
        """
        session = Session()

        # Create workspace section with seeded files
        # This needs to be per-request because it references the session
        workspace_section = create_workspace_section(
            session=session,
            workspace_dir=self._workspace_dir,
        )

        # Build template with workspace section added
        # We create a new template to include the session-bound workspace section
        template = PromptTemplate[TriviaResponse](
            ns="trivia",
            key="main",
            sections=[  # type: ignore[list-item]
                QuestionSection(),
                GameRulesSection(),
                HintsSection(),
                LuckyDiceSection(),  # Lucky Dice mini-game with policy enforcement
                build_task_examples_section(),  # Multi-step workflow examples
                workspace_section,  # Session-bound workspace access
            ],
            feedback_providers=build_feedback_providers(),
        )

        # Determine overrides tag from experiment
        overrides_tag = experiment.overrides_tag if experiment else "latest"

        # Create prompt with overrides support
        prompt = Prompt[TriviaResponse](
            template,
            overrides_store=self._overrides_store,
            overrides_tag=overrides_tag,
        )

        # Seed overrides store with current prompt state (creates initial override files)
        if self._overrides_store is not None:
            self._overrides_store.seed(prompt, tag=overrides_tag)  # type: ignore[arg-type]

        # Bind parameters
        prompt.bind(QuestionParams(question=request.question))
        prompt.bind(EmptyParams())  # For sections without params (GameRules, Hints)

        return prompt, session


@FrozenDataclass()
class TriviaRuntime:
    """Runtime dependencies for the trivia worker.

    Used for dependency injection in tests.
    """

    adapter: ProviderAdapter[TriviaResponse] | None = None
    mailboxes: TriviaMailboxes | None = None
    out: TextIO = field(default_factory=lambda: sys.stdout)
    err: TextIO = field(default_factory=lambda: sys.stderr)


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime: TriviaRuntime | None = None,
) -> int:
    """Main entry point for the trivia agent worker.

    Args:
        argv: Command line arguments (unused, for compatibility).
        runtime: Optional runtime dependencies for testing.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    configure_logging(level="DEBUG")

    rt = runtime or TriviaRuntime()
    out = rt.out
    err = rt.err

    # Load configuration
    settings, error = load_redis_settings(os.environ)
    if error:
        err.write(f"Configuration error: {error}\n")
        return 1

    assert settings is not None  # for type checker

    # Validate API key early - this is the most common first-run error
    if rt.adapter is None and not os.environ.get(API_KEY_ENV):
        err.write(f"Missing {API_KEY_ENV}. Set it with: export {API_KEY_ENV}=your-api-key\n")
        return 1

    # Resolve isolation config with skills
    isolation = resolve_isolation_config(os.environ)

    # Use injected or create real dependencies
    try:
        adapter = rt.adapter or create_adapter(isolation=isolation)
    except Exception as e:
        err.write(f"Failed to create adapter: {e}\n")
        return 1

    try:
        mailboxes = rt.mailboxes or create_mailboxes(settings)
    except Exception as e:
        err.write(f"Failed to connect to Redis: {e}\n")
        return 1

    # Configure MainLoop with deadline and optional debug bundles
    default_deadline = Deadline(expires_at=datetime.now(UTC) + DEFAULT_DEADLINE_DURATION)
    config = MainLoopConfig(
        deadline=default_deadline,
        debug_bundle=(
            BundleConfig(target=settings.debug_bundles_dir) if settings.debug_bundles_dir else None
        ),
    )

    # Create prompt overrides store if configured
    overrides_store: PromptOverridesStore | None = None
    if settings.prompt_overrides_dir:
        overrides_store = LocalPromptOverridesStore(root_path=settings.prompt_overrides_dir)

    # Create the main loop
    loop = TriviaAgentLoop(
        adapter=adapter,
        requests=mailboxes.requests,
        config=config,
        overrides_store=overrides_store,
    )

    # Create the eval loop (imported here to avoid circular import)
    from trivia_agent.eval_loop import create_eval_loop

    eval_loop = create_eval_loop(
        loop,
        mailboxes.eval_requests,
        debug_bundle_dir=settings.debug_bundles_dir,
    )

    # Run both loops
    out.write("Starting trivia agent worker...\n")
    group = LoopGroup(loops=[loop, eval_loop])  # type: ignore[list-item]
    group.run()

    return 0
