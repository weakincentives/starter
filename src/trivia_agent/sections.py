"""Prompt sections for the trivia agent.

This module provides reusable prompt sections that compose the trivia agent's
system prompt. Each section is created via a factory function, enabling
modular prompt construction.

Key WINK features demonstrated:
    - **Custom sections with typed parameters**: build_question_section() creates
      a section that uses QuestionParams to inject the player's question.
    - **Progressive disclosure**: build_game_rules_section() creates a section that
      starts collapsed (SUMMARY visibility) and expands when the agent calls
      read_section('rules').
    - **Tools attached to sections**: build_hints_section() bundles the hint_lookup
      tool, so it's only available when the hints section is included.
    - **Tool policies**: build_lucky_dice_section() uses SequentialDependencyPolicy
      to enforce that pick_up_dice must be called before throw_dice.
    - **Task examples**: build_task_examples_section() provides multi-step workflow
      demonstrations for proper tool sequencing.

Usage:
    To build a prompt with these sections, include them in a PromptTemplate::

        from trivia_agent.sections import (
            build_question_section,
            build_game_rules_section,
            build_hints_section,
            build_lucky_dice_section,
            build_task_examples_section,
        )

        template = PromptTemplate(
            sections=[
                build_question_section(),
                build_game_rules_section(),
                build_hints_section(),
                build_lucky_dice_section(),
                build_task_examples_section(),
            ]
        )

    Set the question dynamically using section parameters::

        prompt = template.render(
            section_params={"question": QuestionParams(question="What is 42?")}
        )
"""

from __future__ import annotations

from collections.abc import Sequence

from weakincentives import FrozenDataclass, MarkdownSection
from weakincentives.prompt import (
    SectionVisibility,
    SequentialDependencyPolicy,
    TaskExample,
    TaskExamplesSection,
    TaskStep,
    ToolExample,
)

from trivia_agent.models import TriviaResponse
from trivia_agent.tools import (
    HintLookupParams,
    HintLookupResult,
    PickUpDiceParams,
    PickUpDiceResult,
    ThrowDiceParams,
    ThrowDiceResult,
    hint_lookup_tool,
    pick_up_dice_tool,
    throw_dice_tool,
)

# =============================================================================
# Section Parameters
# =============================================================================


@FrozenDataclass()
class QuestionParams:
    """Parameters for the QuestionSection template.

    This frozen dataclass provides the dynamic content injected into the
    QuestionSection's template. Use this to set the player's trivia question.

    Attributes:
        question: The trivia question text to display to the agent. This value
            is substituted into the template's ${question} placeholder.

    Example:
        Create parameters with the player's question::

            params = QuestionParams(question="What is the secret number?")

        Pass to section rendering via section_params dict::

            prompt = template.render(
                section_params={"question": params}
            )
    """

    question: str
    """The trivia question to answer."""


@FrozenDataclass()
class EmptyParams:
    """Empty parameters for sections with static content.

    Use this frozen dataclass for sections that render fixed templates without
    any dynamic placeholders. GameRulesSection, HintsSection, and LuckyDiceSection
    all use EmptyParams since their content is constant.

    Example:
        Sections using EmptyParams don't require parameters at render time::

            rules_section = GameRulesSection()
            # No params needed - section uses static template

        If you need to explicitly pass params, use an empty instance::

            section_params={"rules": EmptyParams()}
    """

    pass


# =============================================================================
# Sections
# =============================================================================


def build_question_section(
    *,
    skills: Sequence[object] = (),
) -> MarkdownSection[QuestionParams]:
    """Build a section that displays the player's trivia question.

    Creates a MarkdownSection that renders the current question being asked by
    the player. It uses a simple template with a single ${question} placeholder
    that gets replaced with the actual question text from QuestionParams.

    Skills are attached to this section so the agent has access to secret
    knowledge during prompt rendering. Skills on sections participate in
    progressive disclosure alongside tools.

    The section is registered under the key "question", so parameters should be
    passed as {"question": QuestionParams(question="...")}.

    Args:
        skills: Sequence of SkillMount objects to attach to this section.
            Skills provide domain knowledge (e.g., secret answers) that the
            agent can access during execution.

    Returns:
        MarkdownSection[QuestionParams]: A configured section ready to be included
            in a PromptTemplate. The section key is "question".

    Example:
        Include in a prompt template::

            template = PromptTemplate(sections=[build_question_section(), ...])

        Render with a specific question::

            prompt = template.render(
                section_params={"question": QuestionParams(question="What is the secret color?")}
            )

    Note:
        The default_params provides an empty question string, so the section can
        render even without explicit parameters (useful for template validation).
    """
    return MarkdownSection[QuestionParams](
        title="Question",
        key="question",
        template="${question}",
        default_params=QuestionParams(question=""),
        skills=skills or None,
    )


def build_game_rules_section() -> MarkdownSection[EmptyParams]:
    """Build a game rules section demonstrating progressive disclosure.

    Creates a MarkdownSection containing the complete rules for the secret trivia
    game. The section starts in SUMMARY visibility mode, so the agent initially
    sees only a brief summary hint and can expand the full content by calling
    read_section('rules').

    Progressive disclosure is useful for:
        - Reducing initial prompt size and token usage
        - Letting the agent decide when it needs detailed information
        - Keeping the main prompt focused on the immediate task

    Returns:
        MarkdownSection[EmptyParams]: A configured section ready to be included
            in a PromptTemplate. The section key is "rules".

    Section key: "rules"

    Visibility: SUMMARY (collapsed by default, expandable on demand)

    Example:
        Add to a prompt template for on-demand rules access::

            template = PromptTemplate(sections=[
                build_question_section(),
                build_game_rules_section(),  # Shows summary until agent expands
            ])

        The agent sees in the prompt::

            "Game rules available. Use read_section('rules') to review
            how the secret trivia game works."

        When the agent calls read_section('rules'), the full game rules
        (how to play, secret categories, guidelines) become visible.

    Note:
        The rules explain the four secret categories (number, word, color, phrase)
        and instruct the agent to give concise answers from its skill knowledge.
    """
    return MarkdownSection[EmptyParams](
        title="Game Rules",
        key="rules",
        template="""## Secret Trivia Game Rules

You are the host of a secret trivia game. Your job is to answer trivia questions
using secret knowledge that only you possess.

### How to Play

1. **Read the question** - Understand what secret is being asked for
2. **Check your secret knowledge** - You have secrets loaded via skills
3. **Give the answer** - Provide the exact secret answer
4. **Be concise** - Just give the answer, no need for lengthy explanations

### Secret Categories

- **Secret Number** - A special number with cosmic significance
- **Secret Word** - A fruity vocabulary item
- **Secret Color** - A royal hue
- **Magic Phrase** - Words of power from ancient tales

### Important

- Only give hints if explicitly asked
- The secrets are in your skill knowledge - trust what you know
- If asked about something that's not a secret, say you don't know
""",
        summary=(
            "Game rules available. Use read_section('rules') to review "
            "how the secret trivia game works."
        ),
        visibility=SectionVisibility.SUMMARY,
        default_params=EmptyParams(),
    )


def build_hints_section() -> MarkdownSection[EmptyParams]:
    """Build a hints section that bundles the hint_lookup tool.

    Creates a MarkdownSection that demonstrates attaching tools to sections.
    When this section is included in a prompt template, the hint_lookup tool
    automatically becomes available to the agent. This pattern keeps tools
    co-located with their documentation and usage instructions.

    The hint_lookup tool allows the agent to retrieve hints for each secret
    category without revealing the actual answer. Available categories are:
    number, word, color, and phrase.

    Returns:
        MarkdownSection[EmptyParams]: A configured section ready to be included
            in a PromptTemplate. The section key is "hints".

    Section key: "hints"

    Visibility: FULL (always expanded)

    Attached tools:
        - hint_lookup: Retrieves a hint for a given category.

    Example:
        Include to enable hint functionality::

            template = PromptTemplate(sections=[
                build_question_section(),
                build_hints_section(),  # Adds hint_lookup tool to available tools
            ])

        The agent can then call hint_lookup to help stuck players::

            # Agent calls: hint_lookup(category="number")
            # Returns: "Think of the answer to life, the universe, and everything."

    Note:
        Tools attached to sections are only available when the section is part
        of the active prompt. Remove the hints section to disable hint functionality.
    """
    return MarkdownSection[EmptyParams](
        title="Hints",
        key="hints",
        template="""## Hint System

If a player is stuck, you can provide hints using the hint_lookup tool.
Hints give clues without revealing the actual answer.

Available hint categories: number, word, color, phrase
""",
        visibility=SectionVisibility.FULL,
        tools=(hint_lookup_tool,),
        default_params=EmptyParams(),
    )


def build_lucky_dice_section() -> MarkdownSection[EmptyParams]:
    """Build a Lucky Dice mini-game section demonstrating tool policies.

    Creates a MarkdownSection that showcases SequentialDependencyPolicy, which
    enforces tool call ordering. The throw_dice tool cannot be called until
    pick_up_dice has been called first. If the agent tries to throw without
    picking up, the policy blocks the call and returns an error message.

    Tool policies are useful for:
        - Enforcing proper operation sequences (e.g., connect before query)
        - Preventing invalid state transitions
        - Teaching agents correct workflows through guardrails

    Returns:
        MarkdownSection[EmptyParams]: A configured section ready to be included
            in a PromptTemplate. The section key is "dice".

    Section key: "dice"

    Visibility: FULL (always expanded)

    Attached tools:
        - pick_up_dice: Picks up the lucky dice. Must be called first.
        - throw_dice: Throws the dice and returns a random value 1-6.
          Blocked by policy until pick_up_dice has been called.

    Attached policies:
        - SequentialDependencyPolicy: Requires pick_up_dice before throw_dice.

    Example:
        Include to enable the dice mini-game::

            template = PromptTemplate(sections=[
                build_question_section(),
                build_lucky_dice_section(),  # Adds dice tools with ordering policy
            ])

        Correct tool sequence::

            # 1. Agent calls pick_up_dice()
            # Returns: "You picked up the lucky dice. You can now throw it!"

            # 2. Agent calls throw_dice()
            # Returns: {"value": 4}  # random 1-6

        Incorrect sequence (blocked by policy)::

            # Agent calls throw_dice() without picking up first
            # Policy blocks the call and returns an error

    Note:
        The policy state resets between agent sessions. Each new session
        requires pick_up_dice to be called before throw_dice.
    """
    # Policy: throw_dice requires pick_up_dice to have been called first
    dice_policy = SequentialDependencyPolicy(
        dependencies={
            "throw_dice": frozenset({"pick_up_dice"}),
        }
    )

    return MarkdownSection[EmptyParams](
        title="Lucky Dice",
        key="dice",
        template="""## Lucky Dice Mini-Game

Players can roll the lucky dice for bonus points! But there's a rule:
you must pick up the dice before you can throw it.

1. Use pick_up_dice to grab the lucky dice
2. Use throw_dice to roll it (only works if you've picked up the dice)
3. Rolling a 6 is extra lucky!

The throw_dice tool has a policy that enforces this ordering.
If someone asks to roll the dice, make sure to pick it up first!
""",
        visibility=SectionVisibility.FULL,
        tools=(pick_up_dice_tool, throw_dice_tool),
        policies=(dice_policy,),
        default_params=EmptyParams(),
    )


# =============================================================================
# Task Examples Section
# =============================================================================


def build_task_examples_section() -> TaskExamplesSection:  # type: ignore[type-arg]
    """Build a TaskExamplesSection with trivia game workflow demonstrations.

    This factory function creates a section containing multi-step task examples
    that teach the agent proper tool usage patterns. Each example shows:
        - An objective (what the agent should accomplish)
        - A sequence of tool calls with expected inputs and outputs
        - The final outcome/response

    The examples included are:

    1. **hint-then-answer**: Shows the agent how to use hint_lookup when a player
       asks for help with the secret number. Demonstrates single-tool workflow.

    2. **roll-lucky-dice**: Shows the correct sequence for the dice mini-game:
       pick_up_dice first, then throw_dice. Demonstrates policy-compliant
       multi-step workflow.

    Returns:
        TaskExamplesSection: A section containing the workflow examples, ready
        to be included in a PromptTemplate. The section key is "examples".

    Example:
        Include in a prompt template for agent guidance::

            template = PromptTemplate(sections=[
                QuestionSection(),
                HintsSection(),
                LuckyDiceSection(),
                build_task_examples_section(),  # Shows proper tool usage
            ])

        The rendered prompt will include formatted examples showing
        the agent exactly how to sequence tool calls for common tasks.

    Note:
        Task examples use the actual tool parameter and result types
        (HintLookupParams, PickUpDiceParams, etc.) to ensure type safety
        and accurate demonstration of real tool interfaces.
    """
    # Example 1: Player asks for a hint, then guesses correctly
    hint_workflow = TaskExample(  # type: ignore[var-annotated]
        key="hint-then-answer",
        objective="Help a player who asks for a hint about the secret number",
        steps=(
            TaskStep(
                tool_name="hint_lookup",
                example=ToolExample(
                    description="Look up a hint for the number category",
                    input=HintLookupParams(category="number"),
                    output=HintLookupResult(
                        found=True,
                        hint="Think of the answer to life, the universe, and everything.",
                    ),
                ),
            ),
        ),
        outcome=TriviaResponse(
            answer="Here's a hint: Think of the answer to life, the universe, and "
            "everything. Can you guess the secret number?"
        ),
    )

    # Example 2: Rolling the lucky dice (demonstrates policy-compliant sequence)
    dice_workflow = TaskExample(  # type: ignore[var-annotated]
        key="roll-lucky-dice",
        objective="Roll the lucky dice for a player who wants bonus points",
        steps=(
            TaskStep(
                tool_name="pick_up_dice",
                example=ToolExample(
                    description="First, pick up the dice (required before throwing)",
                    input=PickUpDiceParams(),
                    output=PickUpDiceResult(
                        message="You picked up the lucky dice. You can now throw it!"
                    ),
                ),
            ),
            TaskStep(
                tool_name="throw_dice",
                example=ToolExample(
                    description="Now throw the dice",
                    input=ThrowDiceParams(),
                    output=ThrowDiceResult(value=6),
                ),
            ),
        ),
        outcome=TriviaResponse(answer="You rolled a lucky 6! That's bonus points for you!"),
    )

    return TaskExamplesSection(  # type: ignore[return-value]
        key="examples",
        examples=(hint_workflow, dice_workflow),  # type: ignore[arg-type]
    )
