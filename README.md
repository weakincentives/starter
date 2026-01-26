# WINK Starter: Secret Trivia Agent

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/weakincentives/starter)

A minimal starter project demonstrating how to build background agents with [Weak Incentives (WINK)](https://github.com/weakincentives/weakincentives). This example implements a **secret trivia game** where the agent knows hidden answers that players must discover.

> **Note**: This repository is optimized for Claude to implement features end-to-end. It maintains 100% test coverage, includes comprehensive project context in `AGENTS.md` (symlinked as `CLAUDE.md`), and follows patterns that enable Claude to understand, modify, and test the codebase autonomously. Claude can explore WINK documentation via `uv run wink docs` and inspect execution artifacts via `uv run wink query debug_bundles/*.zip`.

## The Secret Trivia Game

The agent possesses secret knowledge loaded via **skills**:
- **Secret Number**: 42
- **Secret Word**: banana
- **Secret Color**: purple
- **Magic Phrase**: Open sesame!

Players ask questions like "What is the secret number?" and the agent responds with the answer. The agent can also provide **hints** if asked.

This simple concept naturally demonstrates all of WINK's key capabilities:
- **Skills** load the secret answers into the agent
- **Tools** provide hints without revealing answers
- **Tool policies** enforce ordering constraints (Lucky Dice mini-game)
- **Progressive disclosure** hides game rules until needed
- **Feedback providers** remind the agent to stay on task
- **Evaluators** check answers with custom scoring logic

## What is WINK?

**Weak Incentives (WINK)** is the agent-definition layer for unattended agents. It separates what you own from what the runtime provides:

**Your Agent Definition (what you own and iterate):**
- **Prompt**: Structured decision procedure, not a loose string
- **Tools**: The capability surface where side effects occur
- **Feedback**: Soft course correction during execution
- **Evaluators**: Scoring functions for testing agent behavior

**The Execution Harness (what the runtime provides):**
- Planning/act loop, sandboxing, tool-call orchestration
- Scheduling, crash recovery, operational guardrails

**WINK's thesis**: Harnesses keep changing (and increasingly come from vendor runtimes), but your agent definition should not. WINK makes the definition a first-class artifact you can version, review, test, and port across runtimes via adapters.

## Project Structure

```
starter/
├── README.md               # You are here
├── AGENTS.md               # Project context for Claude
├── CLAUDE.md -> AGENTS.md  # Symlink for Claude Code
├── Makefile                # Commands for running and development
├── pyproject.toml          # Dependencies and project config
├── debug_bundles/          # Execution artifacts (gitignored zips)
├── workspace/              # Agent persona (CLAUDE.md)
├── skills/
│   └── secret-trivia/      # Secret answers loaded via skill
│       └── SKILL.md
├── src/
│   └── trivia_agent/
│       ├── worker.py       # MainLoop entry point
│       ├── eval_loop.py    # EvalLoop factory
│       ├── dispatch.py     # Submit questions to the agent
│       ├── models.py       # Request/Response dataclasses
│       ├── sections.py     # Question, GameRules, Hints, LuckyDice sections
│       ├── tools.py        # hint_lookup, pick_up_dice, throw_dice tools
│       ├── feedback.py     # TriviaHostReminder feedback provider
│       ├── evaluators.py   # Trivia evaluator (checks secrets)
│       └── ...             # Config, adapters, mailboxes, isolation
├── tests/                  # Unit tests (100% coverage)
├── integration-tests/      # Integration tests (requires Redis + API key)
└── prompt_overrides/       # Custom prompt overrides (optional)
```

## Quick Start

### 1. Install dependencies

```bash
make install
```

### 2. Start Redis

```bash
make redis
```

### 3. Set your API key

```bash
export ANTHROPIC_API_KEY=your-api-key
```

### 4. Run the agent

In one terminal, start the worker:
```bash
make agent
```

In another terminal, ask about secrets:
```bash
make dispatch QUESTION="What is the secret number?"
# Answer: 42

make dispatch QUESTION="What is the secret word?"
# Answer: banana

make dispatch QUESTION="Can I get a hint about the color?"
# Hint: Mix red and blue together.
```

## WINK Features Demonstrated

### 1. Skills (`skills/secret-trivia/SKILL.md`)

Skills load domain knowledge into the agent. Each skill has YAML frontmatter for metadata, then markdown content:

```markdown
---
name: secret-trivia
description: Answer secret trivia questions that only this agent knows.
---

### The Secret Number
If asked "What is the secret number?", the answer is: **42**

### The Secret Word
If asked "What is the secret word?", the answer is: **banana**
```

The `name` and `description` are used by WINK for skill discovery and documentation.

### 2. Custom Tools (`tools.py`)

The hint lookup tool provides clues without revealing answers:

```python
@FrozenDataclass()
class HintLookupParams:
    category: str  # 'number', 'word', 'color', 'phrase'

@FrozenDataclass()
class HintLookupResult:
    found: bool
    hint: str

hint_lookup_tool = Tool[HintLookupParams, HintLookupResult](
    name="hint_lookup",
    description="Get a hint for a trivia category.",
    handler=_handle_hint_lookup,
)
```

The lucky dice tools (`pick_up_dice`, `throw_dice`) let players roll for bonus points - see section 4.1 below.

### 3. Progressive Disclosure (`sections.py`)

Game rules start hidden and expand on demand. WINK provides a built-in `read_section` tool that agents can use to expand summarized sections:

```python
class GameRulesSection(MarkdownSection[EmptyParams]):
    def __init__(self) -> None:
        super().__init__(
            title="Game Rules",
            key="rules",
            template="## Secret Trivia Game Rules...",
            summary="Game rules available. Use read_section('rules') to review.",
            visibility=SectionVisibility.SUMMARY,  # Hidden until needed
        )
```

### 4. Tools Attached to Sections (`sections.py`)

The hints section provides the hint tool:

```python
class HintsSection(MarkdownSection[EmptyParams]):
    def __init__(self) -> None:
        super().__init__(
            title="Hints",
            key="hints",
            template="...",
            tools=(hint_lookup_tool,),  # Tool scoped to this section
        )
```

### 4.1. Tool Policies (`sections.py`)

Tool policies enforce ordering constraints. The **Lucky Dice** mini-game demonstrates this - players can roll for bonus points, but must pick up the dice before throwing:

```python
class LuckyDiceSection(MarkdownSection[EmptyParams]):
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
            template="...",
            tools=(pick_up_dice_tool, throw_dice_tool),
            policies=(dice_policy,),  # Enforce tool ordering
        )
```

If the agent tries to call `throw_dice` before `pick_up_dice`, the policy blocks the call with an error message. Try it:

```bash
make dispatch QUESTION="Roll the lucky dice for me!"
```

### 5. Feedback Providers (`feedback.py`)

Custom feedback reminds the agent to give direct answers:

```python
@dataclass(frozen=True, slots=True)
class TriviaHostReminder:
    max_calls_before_reminder: int = 5

    def provide(self, *, context: FeedbackContext) -> Feedback:
        return Feedback(
            provider_name=self.name,
            summary=(
                f"You have made {context.tool_call_count} tool calls. "
                "Remember: you already know the secret answers from your skills. "
                "Just give the answer directly!"
            ),
            severity="info",
        )
```

### 6. Evaluators (`evaluators.py`)

The trivia evaluator checks secrets and brevity:

```python
def trivia_evaluator(
    output: TriviaResponse,
    expected: str,
    session: Any = None,  # Session for behavioral checks
) -> Score:
    scores = []

    # Check 1: Does answer contain the expected secret?
    if expected.lower() in output.answer.lower():
        scores.append((1.0, f"Correct! Secret '{expected}' found"))

    # Check 2: Is the answer brief?
    word_count = len(output.answer.split())
    if word_count <= 20:
        scores.append((1.0, f"Perfect brevity ({word_count} words)"))

    return Score(value=avg(scores), passed=..., reason=...)
```

The session parameter enables behavioral checks (e.g., inspecting tool usage) when WINK's slice architecture is used. See the SESSIONS spec for typed state dispatch and queries.

### 7. Workspace Seeding (`workspace/CLAUDE.md`)

The agent's persona is defined in the workspace:

```markdown
# Secret Trivia Agent

You are the host of a secret trivia game. Players ask you about secrets
that only you know. When asked about a secret, give the answer directly.
```

### Workspace vs Skills

| Directory | Purpose | Example |
|-----------|---------|---------|
| `workspace/` | Agent persona and behavior instructions | "You are a trivia host" |
| `skills/` | Domain knowledge the agent can access | Secret answers (42, banana, etc.) |

**Workspace** files define *how* the agent should behave. **Skills** provide *what* the agent knows. Both are mounted into the agent's sandbox but serve different purposes.

## Running Evaluations

Test that the agent knows its secrets:

```bash
make dispatch-eval QUESTION="What is the secret number?" EXPECTED="42"
make dispatch-eval QUESTION="What is the secret word?" EXPECTED="banana"
make dispatch-eval QUESTION="What is the secret color?" EXPECTED="purple"
make dispatch-eval QUESTION="What is the magic phrase?" EXPECTED="Open sesame"
```

The evaluator checks:
1. The secret answer is present in the response
2. The answer is concise (trivia answers should be brief)

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection URL |
| `TRIVIA_REQUESTS_QUEUE` | No | `trivia:requests` | Request queue name |
| `TRIVIA_EVAL_REQUESTS_QUEUE` | No | `trivia:eval:requests` | Eval queue name |
| `TRIVIA_DEBUG_BUNDLES_DIR` | No | `./debug_bundles` | Debug bundle output (bundles named `{run_id}_{timestamp}.zip`) |
| `TRIVIA_PROMPT_OVERRIDES_DIR` | No | `./prompt_overrides` | Custom prompt overrides directory |

## Development

```bash
make check             # Format, lint, typecheck, test
make test              # Run unit tests with coverage
make integration-test  # Run integration tests (requires Redis + API key)
make format            # Format code
```

## Architecture Overview

```
┌────────────────────┐     ┌─────────────────┐     ┌────────────────────┐
│  trivia-dispatch   │────▶│  Redis Queues   │◀────│  trivia-dispatch   │
│    (questions)     │     │                 │     │     (--eval)       │
└────────────────────┘     └────────┬────────┘     └────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
┌────────────────────────────┐  ┌────────────────────────────┐
│        MainLoop            │  │        EvalLoop            │
│   (production requests)    │  │   (evaluation samples)     │
└─────────────┬──────────────┘  └─────────────┬──────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   Trivia Agent Definition                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  - Sections: Question, GameRules, Hints, LuckyDice       │  │
│  │  - Tools: hint_lookup, pick_up_dice, throw_dice          │  │
│  │  - Policies: SequentialDependencyPolicy (dice ordering)  │  │
│  │  - Skills: secret-trivia (loaded from skills/)           │  │
│  │  - Feedback: DeadlineFeedback, TriviaHostReminder        │  │
│  │  - Evaluator: trivia_evaluator (correctness + brevity)   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   Claude Agent SDK (Harness)                   │
│  - Planning/act loop, sandboxing, tool-call orchestration      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  "42" / "banana"│
                     └─────────────────┘
```

## Next Steps

Now that you've forked this repository, you're ready to customize it for your own use case. We recommend a **spec-first workflow**: write a specification, check it in under `specs/`, then implement.

### Learn About This Example

Start by asking Claude to explain the codebase:

```
Explain how this trivia agent works. Walk me through the flow from
receiving a question to returning an answer.
```

```
What WINK features does this example demonstrate? Show me where each
feature is implemented.
```

```
Run `uv run wink docs list` and summarize what documentation is available.
Then read the TOOLS guide and explain how tools work in WINK.
```

### Manual Testing

With `ANTHROPIC_API_KEY` and `REDIS_URL` set in your environment, Claude can perform end-to-end manual testing:

```
Start Redis and the agent, then test all four secrets by dispatching
questions. Verify each answer is correct.
```

```
Run an eval for each secret and confirm they all pass. If any fail,
investigate and fix.
```

You can also run the integration test suite which automatically starts the agent, runs all evals, and verifies they pass:

```bash
make integration-test
```

### Customize for Your Use Case

**Step 1: Write a spec.** Create `specs/` and describe your agent:

```
Create a spec under specs/my-agent.md for a [describe your use case].
Include: what the agent does, what tools it needs, what skills/knowledge
it requires, and how to evaluate correctness. Don't implement yet.
```

**Step 2: Implement from the spec.**

```
Read specs/my-agent.md and implement it. Replace the trivia game with
the new agent definition. Update models, tools, sections, and evaluators.
Maintain 100% test coverage.
```

**Step 3: Iterate with evals.**

```
Run evals against the new agent. If any fail, analyze the debug bundles
with `uv run wink query debug_bundles/*.zip` to understand what went wrong,
then fix the issue.
```

### Example Prompts for Common Customizations

**Add a new tool:**
```
Add a tool called [tool_name] that [description]. Include it in the
appropriate section. Add tests and update AGENTS.md.
```

**Add a new section with progressive disclosure:**
```
Add a new section called [section_name] that starts hidden (SUMMARY visibility)
and contains [content]. The agent should expand it when [condition].
```

**Integrate an external API:**
```
Add a tool that calls [API name] to [do something]. Handle errors gracefully.
The API key should come from the environment variable [VAR_NAME].
```

**Add behavioral feedback:**
```
Add a feedback provider that reminds the agent to [behavior] after
[condition]. Use severity "info" for gentle reminders, "caution" for
stronger guidance.
```

### Learn More About WINK

```
Run `uv run wink docs search "[topic]"` and read the relevant guides.
Summarize the key concepts.
```

```
Query the debug bundles to show me what data is captured during execution:
`uv run wink query debug_bundles/*.zip --schema`
```

## Troubleshooting

**"Connection refused" errors**: Make sure Redis is running (`make redis`).

**"API key not found"**: Ensure `ANTHROPIC_API_KEY` is set.

**Agent doesn't know secrets**: Check that `skills/secret-trivia/SKILL.md` exists and contains the answers.
