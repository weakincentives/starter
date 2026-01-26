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
    """Input parameters for the hint_lookup tool.

    Use this dataclass to request a hint for a specific trivia category.
    The tool performs case-insensitive partial matching, so 'Number',
    'secret number', or 'NUMBER' all match the 'number' category.

    Attributes:
        category: The trivia category to get a hint for. Valid categories
            are 'number', 'word', 'color', and 'phrase'. Partial matches
            are supported (e.g., 'secret number' matches 'number').

    Example:
        >>> params = HintLookupParams(category="number")
        >>> params = HintLookupParams(category="secret word")
    """

    category: str
    """The trivia category to get a hint for (e.g., 'number', 'word', 'color', 'phrase')."""


@FrozenDataclass()
class HintLookupResult:
    """Result returned by the hint_lookup tool.

    Contains the lookup status and hint text. Always check the `found`
    attribute before using the hint, as an unfound category returns
    an empty hint string.

    Attributes:
        found: True if a hint was found for the requested category,
            False otherwise. When False, the hint attribute will be empty.
        hint: The hint text providing a clue about the secret answer.
            Empty string if no hint was found for the category.

    Example:
        >>> result = HintLookupResult(found=True, hint="It's yellow.")
        >>> if result.found:
        ...     print(result.hint)
        It's yellow.
    """

    found: bool
    """Whether a hint was found for this category."""

    hint: str
    """The hint text, or empty if not found."""

    def render(self) -> str:
        """Render the result as a human-readable string for the model.

        Formats the hint result for display in conversation. Provides
        a clear message whether a hint was found or not.

        Returns:
            str: A formatted string. If found, returns "Hint: {hint_text}".
                If not found, returns "No hint available for this category."

        Example:
            >>> result = HintLookupResult(found=True, hint="Think of 6*7.")
            >>> result.render()
            'Hint: Think of 6*7.'
        """
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
    """Input parameters for the pick_up_dice tool.

    This is a parameterless action - no inputs are required. The tool
    must be called before throw_dice due to the SequentialDependencyPolicy
    enforced by LuckyDiceSection.

    The Lucky Dice mini-game flow is:
        1. Call pick_up_dice (this tool)
        2. Call throw_dice to roll

    Example:
        >>> params = PickUpDiceParams()
    """

    pass


@FrozenDataclass()
class PickUpDiceResult:
    """Result returned by the pick_up_dice tool.

    Confirms the dice has been picked up and is ready to throw.
    This result must be received before throw_dice can be called.

    Attributes:
        message: A confirmation message indicating the dice is ready.
            Typically "You picked up the lucky dice. You can now throw it!"

    Example:
        >>> result = PickUpDiceResult(message="Dice ready!")
        >>> print(result.message)
        Dice ready!
    """

    message: str
    """Confirmation message indicating dice pickup succeeded."""

    def render(self) -> str:
        """Render the result as a human-readable string for the model.

        Returns:
            str: The confirmation message indicating the dice is ready to throw.

        Example:
            >>> result = PickUpDiceResult(message="You picked up the dice!")
            >>> result.render()
            'You picked up the dice!'
        """
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
    """Input parameters for the throw_dice tool.

    This is a parameterless action - no inputs are required. However,
    pick_up_dice MUST be called first due to the SequentialDependencyPolicy
    enforced by LuckyDiceSection. Calling throw_dice without first calling
    pick_up_dice will result in a policy violation error.

    The Lucky Dice mini-game flow is:
        1. Call pick_up_dice first
        2. Call throw_dice (this tool) to roll

    Example:
        >>> params = ThrowDiceParams()
    """

    pass


@FrozenDataclass()
class ThrowDiceResult:
    """Result returned by the throw_dice tool.

    Contains the random dice roll value (1-6). Rolling a 6 is considered
    "lucky" and grants bonus points in the game.

    Attributes:
        value: The dice roll result, an integer from 1 to 6 inclusive.
            A value of 6 is a "lucky roll" with special formatting.

    Example:
        >>> result = ThrowDiceResult(value=4)
        >>> print(f"You rolled {result.value}")
        You rolled 4
    """

    value: int
    """The dice roll result (1-6)."""

    def render(self) -> str:
        """Render the result as a human-readable string for the model.

        Formats the dice roll with special messaging for lucky rolls (6).

        Returns:
            str: A formatted string showing the roll result. Lucky rolls
                (value=6) include a special "Bonus points!" message.

        Example:
            >>> ThrowDiceResult(value=4).render()
            'You rolled a 4.'
            >>> ThrowDiceResult(value=6).render()
            'Lucky roll! You got a 6! Bonus points!'
        """
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
