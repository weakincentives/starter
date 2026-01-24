"""Request and response models for the trivia agent."""

from weakincentives import FrozenDataclass


@FrozenDataclass()
class TriviaRequest:
    """A question submitted to the trivia agent."""

    question: str


@FrozenDataclass()
class TriviaResponse:
    """An answer from the trivia agent."""

    answer: str
