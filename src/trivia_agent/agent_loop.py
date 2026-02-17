"""AgentLoop + EvalLoop entry point for the trivia agent.

This module demonstrates the full WINK architecture:
- AgentLoop for production request processing
- EvalLoop for evaluation with session-aware scoring
- PromptTemplate with multiple sections
- Feedback providers for soft course correction
- Progressive disclosure with SUMMARY visibility
- Custom tools attached to sections
- Skills attached to sections for section-level mounting
- Workspace seeding via WorkspaceSection
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from weakincentives import FrozenDataclass, Prompt
from weakincentives.adapters import ProviderAdapter
from weakincentives.debug.bundle import BundleConfig
from weakincentives.prompt import HostMount, PromptTemplate, WorkspaceSection
from weakincentives.prompt.overrides import LocalPromptOverridesStore, PromptOverridesStore
from weakincentives.runtime import (
    AgentLoop,
    AgentLoopConfig,
    AgentLoopRequest,
    AgentLoopResult,
    LoopGroup,
    Session,
)
from weakincentives.runtime.logging import configure_logging
from weakincentives.runtime.mailbox import Mailbox
from weakincentives.skills import SkillMount

from trivia_agent.adapters import SimpleTaskCompletionChecker, create_adapter
from trivia_agent.config import load_redis_settings
from trivia_agent.feedback import build_feedback_providers
from trivia_agent.isolation import API_KEY_ENV, has_auth, resolve_isolation_config, resolve_skills
from trivia_agent.mailboxes import TriviaMailboxes, create_mailboxes
from trivia_agent.models import TriviaRequest, TriviaResponse
from trivia_agent.sections import (
    EmptyParams,
    QuestionParams,
    build_game_rules_section,
    build_hints_section,
    build_lucky_dice_section,
    build_question_section,
    build_task_examples_section,  # pyright: ignore[reportUnknownVariableType]
)

if TYPE_CHECKING:
    from weakincentives.evals import Experiment

# Default workspace seed directory
DEFAULT_WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"


def enumerate_workspace_mounts(workspace_dir: Path) -> tuple[HostMount, ...]:
    """Enumerate files in a workspace directory and create mount configurations.

    Scans the given directory for files and creates HostMount objects that map
    each file from the host filesystem into the agent's workspace. Files are
    mounted at the workspace root level (preserving only the filename, not the
    full path hierarchy).

    Use this function when you need to seed an agent's workspace with files
    from the host system, such as configuration files, reference documents,
    or persona definitions.

    Args:
        workspace_dir: Path to the host directory containing files to mount.
            Must be an existing directory. Subdirectories are not recursed.

    Returns:
        tuple[HostMount, ...]: Tuple of HostMount objects sorted alphabetically
            by filename. Returns an empty tuple if the directory doesn't exist,
            is not a directory, or contains no files.

    Example:
        >>> mounts = enumerate_workspace_mounts(Path("./workspace"))
        >>> for mount in mounts:
        ...     print(f"{mount.host_path} -> {mount.mount_path}")
        /abs/path/workspace/CLAUDE.md -> CLAUDE.md
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
) -> WorkspaceSection:
    """Create a workspace section that seeds agent workspace with host files.

    Constructs a WorkspaceSection that mounts files from the host
    filesystem into the agent's sandboxed workspace. This enables the agent
    to access reference materials, persona definitions, or configuration files
    that shape its behavior.

    The workspace section must be created per-request because it binds to a
    specific Session instance. Include the returned section in your
    PromptTemplate's sections list.

    Args:
        session: The Session instance this workspace section binds to. Each
            request should have its own session for proper isolation.
        workspace_dir: Path to the host directory containing files to seed.
            All files in this directory (non-recursive) will be mounted at the
            agent's workspace root.

    Returns:
        WorkspaceSection: A configured section ready to be included
            in a PromptTemplate. The section handles mounting files and provides
            the agent with filesystem access tools.

    Example:
        >>> session = Session()
        >>> workspace_section = create_workspace_section(
        ...     session=session,
        ...     workspace_dir=Path("./workspace"),
        ... )
        >>> template = PromptTemplate(sections=[..., workspace_section])
    """
    mounts = enumerate_workspace_mounts(workspace_dir)
    return WorkspaceSection(
        session=session,
        mounts=mounts,
        allowed_host_roots=(str(workspace_dir.parent),),
    )


def build_prompt_template(
    *,
    skills: tuple[SkillMount, ...] = (),
) -> PromptTemplate[TriviaResponse]:
    """Build the base prompt template for the trivia agent.

    Constructs a PromptTemplate with all the core sections and feedback
    providers for the trivia game. This template demonstrates several
    WINK capabilities:

    - **Multiple sections**: QuestionSection, GameRulesSection, HintsSection,
      LuckyDiceSection, and task examples each serve distinct purposes
    - **Progressive disclosure**: GameRulesSection uses SUMMARY visibility,
      showing condensed content until the agent needs full details
    - **Sections with tools**: HintsSection provides the hint_lookup tool;
      LuckyDiceSection provides pick_up_dice and throw_dice tools
    - **Tool policies**: LuckyDiceSection enforces sequential tool ordering
      via SequentialDependencyPolicy
    - **Feedback providers**: TriviaHostReminder nudges the agent to give
      direct answers without overthinking
    - **Skills on sections**: Skills are attached to the question section
      so the agent has access to secret knowledge during prompt rendering

    Note: This function returns a base template without the workspace section.
    The workspace section must be added per-request in TriviaAgentLoop.prepare()
    because it requires a Session reference.

    Args:
        skills: Tuple of SkillMount objects to attach to the question section.
            Skills provide domain knowledge (e.g., secret answers) that the
            agent can access during execution.

    Returns:
        PromptTemplate[TriviaResponse]: A configured template ready to be
            extended with a workspace section and bound to request parameters.
            The template uses namespace "trivia" and key "main".

    See Also:
        TriviaAgentLoop.prepare: Adds workspace section and binds parameters.
        sections.py: Contains the section implementations.
        feedback.py: Contains the feedback provider implementations.
    """
    return PromptTemplate[TriviaResponse](
        ns="trivia",
        key="main",
        sections=[  # type: ignore[list-item]
            build_question_section(skills=skills),
            build_game_rules_section(),  # Progressive disclosure - starts summarized
            build_hints_section(),  # Has attached hint_lookup tool
            build_lucky_dice_section(),  # Lucky Dice mini-game with policy enforcement
            build_task_examples_section(),  # Multi-step workflow examples
        ],
        feedback_providers=build_feedback_providers(),
        task_completion_checker=SimpleTaskCompletionChecker(),
    )


class TriviaAgentLoop(AgentLoop[TriviaRequest, TriviaResponse]):
    """Main processing loop for the trivia agent.

    Extends AgentLoop to handle TriviaRequest inputs and produce TriviaResponse
    outputs. This loop demonstrates key WINK patterns for production agents:

    - **Per-request preparation**: The prepare() method creates a fresh Session
      and workspace section for each request, ensuring proper isolation
    - **Workspace seeding**: Files from the host workspace directory are mounted
      into each agent session (e.g., CLAUDE.md for persona definition)
    - **Prompt overrides**: Supports LocalPromptOverridesStore for runtime
      customization of prompt content without code changes
    - **Evaluation integration**: Compatible with EvalLoop for running
      evaluations with session-aware scoring

    To use this loop, instantiate it with an adapter and mailbox, then either:
    1. Call run() directly for single-threaded processing
    2. Add to a LoopGroup with other loops (e.g., EvalLoop) for concurrent processing

    Attributes:
        _workspace_dir: Path to the directory containing workspace seed files.
        _base_template: The base PromptTemplate (without workspace section).
        _overrides_store: Optional store for prompt content overrides.
        _skills: Skills to attach to prompt sections.

    Example:
        >>> adapter = create_adapter(isolation=isolation_config)
        >>> loop = TriviaAgentLoop(
        ...     adapter=adapter,
        ...     requests=mailboxes.requests,
        ...     config=AgentLoopConfig(),
        ...     workspace_dir=Path("./workspace"),
        ... )
        >>> loop.run()  # Process requests until shutdown
    """

    _workspace_dir: Path
    _base_template: PromptTemplate[TriviaResponse]
    _skills: tuple[SkillMount, ...]

    def __init__(
        self,
        *,
        adapter: ProviderAdapter[TriviaResponse],
        requests: Mailbox[AgentLoopRequest[TriviaRequest], AgentLoopResult[TriviaResponse]],
        config: AgentLoopConfig | None = None,
        workspace_dir: Path | None = None,
        overrides_store: PromptOverridesStore | None = None,
        skills: tuple[SkillMount, ...] = (),
    ) -> None:
        """Initialize the trivia agent loop with required dependencies.

        Sets up the loop with an adapter for executing agent sessions, a mailbox
        for receiving requests, and optional configuration for deadlines, debug
        bundles, and prompt customization.

        Args:
            adapter: ProviderAdapter[TriviaResponse] that executes agent sessions.
                Typically created via create_adapter() with appropriate isolation
                configuration (skills, sandbox settings, API keys).
            requests: Mailbox for receiving AgentLoopRequest[TriviaRequest] and
                sending AgentLoopResult[TriviaResponse]. Connect this to your
                message queue (e.g., Redis via TriviaMailboxes).
            config: Optional AgentLoopConfig with debug bundle settings.
                If None, uses default AgentLoop configuration.
            workspace_dir: Path to directory containing files to seed into agent
                workspace. Defaults to DEFAULT_WORKSPACE_DIR (project's workspace/
                directory). Files here become accessible to the agent.
            overrides_store: Optional PromptOverridesStore for runtime prompt
                customization. Use LocalPromptOverridesStore to edit prompt
                sections via files without restarting the worker.
            skills: Tuple of SkillMount objects to attach to prompt sections.
                Skills provide domain knowledge that the agent can access.
        """
        super().__init__(adapter=adapter, requests=requests, config=config)
        self._workspace_dir = workspace_dir or DEFAULT_WORKSPACE_DIR
        self._skills = skills
        self._base_template = build_prompt_template(skills=skills)
        self._overrides_store = overrides_store

    def prepare(
        self,
        request: TriviaRequest,
        *,
        experiment: Experiment | None = None,
    ) -> tuple[Prompt[TriviaResponse], Session]:
        """Prepare the prompt and session for processing a trivia request.

        Called by the AgentLoop for each incoming request. Creates a fresh Session
        for isolation, builds the complete PromptTemplate with workspace section,
        binds request parameters, and optionally applies experiment overrides.

        This method demonstrates key WINK patterns:

        - **Session per request**: Each request gets its own Session for proper
          isolation between concurrent requests
        - **Dynamic workspace section**: WorkspaceSection is created here (not in
          build_prompt_template) because it needs the Session
        - **Parameter binding**: Binds QuestionParams with the user's question
          and EmptyParams for parameterless sections
        - **Experiment support**: Uses experiment.overrides_tag to select prompt
          variants for A/B testing; defaults to "latest"
        - **Override seeding**: Automatically seeds the overrides store with
          current prompt state, creating editable files for customization

        Args:
            request: TriviaRequest containing the question field. The question
                is bound to QuestionSection via QuestionParams.
            experiment: Optional Experiment instance for evaluation runs. When
                provided, uses experiment.overrides_tag to select prompt variant.
                Pass None for production requests.

        Returns:
            tuple[Prompt[TriviaResponse], Session]: A 2-tuple containing:
                - Prompt: Fully configured prompt with all sections and bound
                  parameters, ready for adapter.run()
                - Session: Fresh session instance for this request's execution
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
                build_question_section(skills=self._skills),
                build_game_rules_section(),
                build_hints_section(),
                build_lucky_dice_section(),  # Lucky Dice mini-game with policy enforcement
                build_task_examples_section(),  # Multi-step workflow examples
                workspace_section,  # Session-bound workspace access
            ],
            feedback_providers=build_feedback_providers(),
            task_completion_checker=SimpleTaskCompletionChecker(),
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
    """Container for trivia worker runtime dependencies.

    Provides dependency injection for the main() function, enabling test
    isolation without mocking. In production, pass None or omit to use
    real implementations. In tests, inject mock or fake dependencies.

    This pattern allows testing the full main() flow without requiring:
    - A real Redis connection
    - A real Claude API adapter
    - Real stdout/stderr (capture output for assertions)

    Attributes:
        adapter: Optional ProviderAdapter for executing agent sessions.
            If None, main() creates a real adapter using create_adapter().
            Inject a mock adapter in tests to avoid API calls.
        mailboxes: Optional TriviaMailboxes for request/response queues.
            If None, main() creates real Redis-backed mailboxes.
            Inject mock mailboxes in tests to control request flow.
        out: TextIO stream for standard output messages (startup, status).
            Defaults to sys.stdout. Inject StringIO in tests to capture output.
        err: TextIO stream for error messages (configuration errors, failures).
            Defaults to sys.stderr. Inject StringIO in tests to capture errors.

    Example:
        >>> # Production usage - use real dependencies
        >>> main(runtime=None)

        >>> # Test usage - inject fakes
        >>> from io import StringIO
        >>> runtime = TriviaRuntime(
        ...     adapter=MockAdapter(),
        ...     mailboxes=FakeMailboxes(),
        ...     out=StringIO(),
        ...     err=StringIO(),
        ... )
        >>> exit_code = main(runtime=runtime)
        >>> assert exit_code == 0
        >>> assert "Starting trivia agent" in runtime.out.getvalue()
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
    """Start the trivia agent worker and process requests until shutdown.

    Entry point for running the trivia agent as a long-lived worker process.
    Initializes all dependencies (adapter, mailboxes, loops), then runs both
    the AgentLoop (for production requests) and EvalLoop (for evaluation
    requests) concurrently via a LoopGroup.

    The worker performs these steps:
    1. Configures logging at DEBUG level
    2. Loads Redis settings from environment variables
    3. Validates ANTHROPIC_API_KEY is set
    4. Creates the provider adapter with isolation config
    5. Discovers skills for section-level mounting
    6. Connects to Redis mailboxes for request/response queues
    7. Creates TriviaAgentLoop with debug bundle config and skills
    8. Creates EvalLoop for evaluation requests
    9. Runs both loops in a LoopGroup until shutdown

    Required Environment Variables:
        ANTHROPIC_API_KEY: API key for Claude (validated early with clear error)
        REDIS_URL: Redis connection URL (e.g., redis://localhost:6379)

    Optional Environment Variables:
        DEBUG_BUNDLES_DIR: Path for debug bundle output (ZIP files)
        PROMPT_OVERRIDES_DIR: Path for prompt override files

    Args:
        argv: Command line arguments. Currently unused but accepted for
            compatibility with standard CLI entry point patterns.
        runtime: Optional TriviaRuntime for dependency injection. Pass None
            in production to use real dependencies. Pass a configured
            TriviaRuntime in tests to inject mocks/fakes.

    Returns:
        int: Exit code. Returns 0 on successful shutdown. Returns 1 on
            configuration errors (missing env vars), adapter creation
            failure, or Redis connection failure.

    Example:
        >>> # Run as CLI entry point
        >>> if __name__ == "__main__":
        ...     sys.exit(main())

        >>> # Run with test dependencies
        >>> runtime = TriviaRuntime(adapter=mock_adapter, mailboxes=mock_mailboxes)
        >>> exit_code = main(runtime=runtime)
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

    # Validate authentication early - this is the most common first-run error
    if rt.adapter is None and not has_auth(os.environ):
        err.write(f"Missing {API_KEY_ENV}. Set it with: export {API_KEY_ENV}=your-api-key\n")
        return 1

    # Unset CLAUDECODE to allow nested Claude Code sessions.
    # The Claude Agent SDK spawns a claude subprocess, which refuses to run
    # if it detects it's inside another Claude Code session.
    os.environ.pop("CLAUDECODE", None)

    # Resolve isolation config (sandbox, API key — no longer includes skills)
    isolation = resolve_isolation_config(os.environ)

    # Discover skills for section-level mounting
    skills = resolve_skills(os.environ)

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

    # Configure AgentLoop with optional debug bundles
    config = AgentLoopConfig(
        debug_bundle=(
            BundleConfig(target=settings.debug_bundles_dir) if settings.debug_bundles_dir else None
        ),
    )

    # Create prompt overrides store if configured
    overrides_store: PromptOverridesStore | None = None
    if settings.prompt_overrides_dir:
        overrides_store = LocalPromptOverridesStore(root_path=settings.prompt_overrides_dir)

    # Create the main loop with skills attached to sections
    loop = TriviaAgentLoop(
        adapter=adapter,
        requests=mailboxes.requests,
        config=config,
        overrides_store=overrides_store,
        skills=skills,
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
