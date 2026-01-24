"""Prompt sections for the trivia agent.

This module demonstrates:
- Custom sections with typed parameters
- Progressive disclosure (SectionVisibility.SUMMARY)
- Tools attached to sections
- TaskExamplesSection for multi-step workflow examples

Sections are composable building blocks for prompts. Each section has a key,
title, template, and optional tools. Sections can start hidden (SUMMARY) and
expand on demand.
"""

from __future__ import annotations

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
    """Parameters for the question section."""

    question: str
    """The trivia question to answer."""


@FrozenDataclass()
class EmptyParams:
    """Empty parameters for sections that don't need dynamic content."""

    pass


# =============================================================================
# Sections
# =============================================================================


class QuestionSection(MarkdownSection[QuestionParams]):
    """The trivia question to answer."""

    _params_type = QuestionParams

    def __init__(self) -> None:
        super().__init__(
            title="Question",
            key="question",
            template="${question}",
            default_params=QuestionParams(question=""),
        )


class GameRulesSection(MarkdownSection[EmptyParams]):
    """Game rules section with progressive disclosure.

    Starts summarized - the agent can expand it if needed to review the rules.
    This demonstrates SectionVisibility.SUMMARY for progressive disclosure.
    """

    _params_type = EmptyParams

    def __init__(self) -> None:
        super().__init__(
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


class HintsSection(MarkdownSection[EmptyParams]):
    """Hints section with the hint lookup tool attached.

    This demonstrates attaching tools to sections. Tools attached to a section
    are included in the prompt's tool set when the section is part of the template.
    """

    _params_type = EmptyParams

    def __init__(self) -> None:
        super().__init__(
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


class LuckyDiceSection(MarkdownSection[EmptyParams]):
    """Lucky Dice mini-game demonstrating tool policies.

    This section provides dice tools with an ordering constraint:
    you must pick_up_dice before you can throw_dice. This is enforced
    via a SequentialDependencyPolicy attached to the section.

    Tool policies gate tool calls based on invocation history, ensuring
    proper sequencing of operations.
    """

    _params_type = EmptyParams

    def __init__(self) -> None:
        # Policy: throw_dice requires pick_up_dice to have been called first
        dice_policy = SequentialDependencyPolicy(
            dependencies={
                "throw_dice": frozenset({"pick_up_dice"}),
            }
        )

        super().__init__(
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
    """Build the task examples section with typical workflow examples.

    TaskExamplesSection demonstrates multi-step workflows, showing the agent
    how to handle common scenarios with proper tool sequencing.

    Returns:
        TaskExamplesSection with trivia game workflow examples.
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
