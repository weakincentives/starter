"""Custom tools for the trivia agent.

This module demonstrates:
- Custom tool definition with typed parameters and results
- Tool handlers with context access
- Tools attached to sections
- ToolExample for showing typical usage

Tools are the capability surface where side effects occur. Everything else
in WINK (prompts, sections, reducers) is meant to be pure and deterministic.

Tool policies (enforcing call ordering) are attached at the section level -
see sections.py for the LuckyDiceSection which uses SequentialDependencyPolicy.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from weakincentives import FrozenDataclass
from weakincentives.prompt import Tool, ToolExample, ToolResult

if TYPE_CHECKING:
    from weakincentives.prompt import ToolContext


# =============================================================================
# Custom Tool: Trivia Hint Lookup
# =============================================================================


@FrozenDataclass()
class HintLookupParams:
    """Parameters for the hint lookup tool."""

    category: str
    """The trivia category to get a hint for (e.g., 'number', 'word', 'color')."""


@FrozenDataclass()
class HintLookupResult:
    """Result from the hint lookup tool."""

    found: bool
    """Whether a hint was found for this category."""

    hint: str
    """The hint text, or empty if not found."""

    def render(self) -> str:
        """Render the result for the model."""
        if self.found:
            return f"Hint: {self.hint}"
        return "No hint available for this category."


def _handle_hint_lookup(
    params: HintLookupParams,
    *,
    context: ToolContext,
) -> ToolResult[HintLookupResult]:
    """Handle hint lookup requests.

    Provides clues for trivia categories without giving away the answer.
    The actual secret answers are loaded via skills - this tool only gives hints.
    """
    # Hints for each trivia category (clues, not answers!)
    hints = {
        "number": "Think of the answer to life, the universe, and everything.",
        "word": "It's a yellow fruit that monkeys love.",
        "color": "Mix red and blue together.",
        "phrase": "Ali Baba said this to enter the cave of treasures.",
    }

    category_lower = params.category.lower()

    for key, hint in hints.items():
        if key in category_lower:
            return ToolResult[HintLookupResult].ok(
                HintLookupResult(found=True, hint=hint),
                message=f"Found hint for {key} category.",
            )

    return ToolResult[HintLookupResult].ok(
        HintLookupResult(found=False, hint=""),
        message="No hint available for this category.",
    )


# Examples showing typical hint_lookup usage
hint_lookup_examples = (
    ToolExample(
        description="Get a hint for the secret number",
        input=HintLookupParams(category="number"),
        output=HintLookupResult(
            found=True,
            hint="Think of the answer to life, the universe, and everything.",
        ),
    ),
    ToolExample(
        description="Get a hint for an unknown category",
        input=HintLookupParams(category="animal"),
        output=HintLookupResult(found=False, hint=""),
    ),
)

# Create the tool with concrete type arguments
hint_lookup_tool = Tool[HintLookupParams, HintLookupResult](
    name="hint_lookup",
    description=(
        "Get a hint for a trivia category. Use this when the player is stuck. "
        "Categories: 'number', 'word', 'color', 'phrase'."
    ),
    handler=_handle_hint_lookup,
    examples=hint_lookup_examples,
)


# =============================================================================
# Lucky Dice Tools (demonstrates tool policies via section-level config)
# =============================================================================


@FrozenDataclass()
class PickUpDiceParams:
    """Parameters for picking up the dice."""

    pass


@FrozenDataclass()
class PickUpDiceResult:
    """Result from picking up the dice."""

    message: str
    """Confirmation message."""

    def render(self) -> str:
        """Render the result for the model."""
        return self.message


def _handle_pick_up_dice(
    params: PickUpDiceParams,
    *,
    context: ToolContext,
) -> ToolResult[PickUpDiceResult]:
    """Handle picking up the lucky dice."""
    return ToolResult[PickUpDiceResult].ok(
        PickUpDiceResult(message="You picked up the lucky dice. You can now throw it!"),
        message="Dice picked up successfully.",
    )


# Example showing pick_up_dice usage
pick_up_dice_examples = (
    ToolExample(
        description="Pick up the dice before rolling",
        input=PickUpDiceParams(),
        output=PickUpDiceResult(message="You picked up the lucky dice. You can now throw it!"),
    ),
)

pick_up_dice_tool = Tool[PickUpDiceParams, PickUpDiceResult](
    name="pick_up_dice",
    description="Pick up the lucky dice. You must do this before you can throw it.",
    handler=_handle_pick_up_dice,
    examples=pick_up_dice_examples,
)


@FrozenDataclass()
class ThrowDiceParams:
    """Parameters for throwing the dice."""

    pass


@FrozenDataclass()
class ThrowDiceResult:
    """Result from throwing the dice."""

    value: int
    """The dice roll result (1-6)."""

    def render(self) -> str:
        """Render the result for the model."""
        if self.value == 6:
            return f"🎲 Lucky roll! You got a {self.value}! Bonus points!"
        return f"🎲 You rolled a {self.value}."


def _handle_throw_dice(
    params: ThrowDiceParams,
    *,
    context: ToolContext,
) -> ToolResult[ThrowDiceResult]:
    """Handle throwing the lucky dice.

    Returns a random value 1-6. Rolling a 6 is extra lucky!
    """
    value = random.randint(1, 6)
    return ToolResult[ThrowDiceResult].ok(
        ThrowDiceResult(value=value),
        message=f"Dice thrown: {value}",
    )


# Examples showing throw_dice usage
throw_dice_examples = (
    ToolExample(
        description="Roll the dice and get a normal result",
        input=ThrowDiceParams(),
        output=ThrowDiceResult(value=4),
    ),
    ToolExample(
        description="Roll the dice and get a lucky 6",
        input=ThrowDiceParams(),
        output=ThrowDiceResult(value=6),
    ),
)

throw_dice_tool = Tool[ThrowDiceParams, ThrowDiceResult](
    name="throw_dice",
    description=(
        "Throw the lucky dice to roll for bonus points (1-6). You must pick up the dice first!"
    ),
    handler=_handle_throw_dice,
    examples=throw_dice_examples,
)
