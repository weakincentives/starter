"""Request and response models for the trivia agent.

This module defines the input and output data structures used to communicate
with the trivia agent. Both models are immutable frozen dataclasses.

Example:
    >>> from trivia_agent.models import TriviaRequest, TriviaResponse
    >>> request = TriviaRequest(question="What is the secret number?")
    >>> response = TriviaResponse(answer="42")
"""

from weakincentives import FrozenDataclass


@FrozenDataclass()
class TriviaRequest:
    """A question submitted to the trivia agent for processing.

    Use this model to structure questions sent to the trivia agent. The agent
    will process the question and return a TriviaResponse with the answer.

    Attributes:
        question: The trivia question to ask the agent. Can be any string,
            but typically asks about one of the secret values (number, word,
            color, or magic phrase) or requests hints.

    Example:
        >>> request = TriviaRequest(question="What is the secret color?")
        >>> request.question
        'What is the secret color?'

    Note:
        This is an immutable frozen dataclass. Once created, the question
        attribute cannot be modified.
    """

    question: str


@FrozenDataclass()
class TriviaResponse:
    """An answer returned by the trivia agent.

    This model wraps the agent's response to a TriviaRequest. The answer
    contains the agent's reply, which may be a direct secret value, a hint,
    or other contextual response based on the question asked.

    Attributes:
        answer: The agent's response to the trivia question. For secret-related
            questions, this will contain the secret value (e.g., "42", "banana",
            "purple", or "Open sesame!").

    Example:
        >>> response = TriviaResponse(answer="The secret number is 42")
        >>> response.answer
        'The secret number is 42'

    Note:
        This is an immutable frozen dataclass. Once created, the answer
        attribute cannot be modified.
    """

    answer: str
