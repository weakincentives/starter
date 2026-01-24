# CLAUDE.md

Quick reference for Claude Code working in `wink-starter`.

## Project Summary

A **Secret Trivia Agent** demonstrating how to build background agents with [Weak Incentives (WINK)](https://github.com/weakincentives/weakincentives). The agent knows secret answers (42, banana, purple, "Open sesame!") loaded via skills, and players ask questions to discover them.

## The Trivia Game Concept

| Secret | Answer |
|--------|--------|
| Secret Number | 42 |
| Secret Word | banana |
| Secret Color | purple |
| Magic Phrase | Open sesame! |

This simple game naturally demonstrates all WINK capabilities:
- **Skills** → load secret answers
- **Tools** → provide hints without revealing answers
- **Tool policies** → enforce ordering (Lucky Dice mini-game)
- **Progressive disclosure** → hide game rules until needed
- **Feedback** → remind agent to give direct answers
- **Evaluators** → check secrets with custom scoring logic

## Essential Commands

```bash
# Setup
make install

# Run all checks
make check

# Start Redis and run the agent
make redis
make agent

# Ask about secrets
make dispatch QUESTION="What is the secret number?"
make dispatch QUESTION="What is the secret word?"

# Run evals
make dispatch-eval QUESTION="What is the secret number?" EXPECTED="42"
```

## Repository Structure

```
src/trivia_agent/
├── worker.py       # MainLoop entry point
├── eval_loop.py    # EvalLoop factory
├── sections.py     # Question, GameRules, Hints, LuckyDice sections
├── tools.py        # hint_lookup, pick_up_dice, throw_dice tools
├── feedback.py     # TriviaHostReminder (stay on task)
├── evaluators.py   # trivia_evaluator (checks secrets + brevity)
├── isolation.py    # Skills and sandbox config
└── ...             # Config, adapters, mailboxes, dispatch

skills/secret-trivia/SKILL.md  # The secret answers
workspace/CLAUDE.md            # Agent persona (trivia host)
debug_bundles/                 # Execution artifacts (*.zip)
tests/                         # 100% coverage
```

## WINK Features → Trivia Game Mapping

| Feature | File | Trivia Use Case |
|---------|------|-----------------|
| Skills | `skills/secret-trivia/SKILL.md` | Secret answers only the agent knows |
| Custom Tools | `tools.py` | `hint_lookup` gives clues; Lucky Dice tools for bonus rolls |
| Tool Policies | `sections.py` | `SequentialDependencyPolicy` enforces dice pickup before throw |
| Progressive Disclosure | `sections.py` | Game rules hidden until agent needs them |
| Tools in Sections | `sections.py` | Hints tool attached to HintsSection |
| Feedback Providers | `feedback.py` | "Just give the answer, don't overthink!" |
| Evaluators | `evaluators.py` | Check secret + brevity |
| Workspace Seeding | `workspace/CLAUDE.md` | Trivia host persona |

## WINK CLI

```bash
# Documentation
uv run wink docs list
uv run wink docs search "Feedback"
uv run wink docs read guide TOOLS

# Query debug bundles (use latest bundle or specify by name)
uv run wink query "debug_bundles/*.zip" --schema
uv run wink query "debug_bundles/*.zip" "SELECT * FROM tool_calls"
```

## Debug Bundle Tables

| Table | Description |
|-------|-------------|
| `manifest` | Bundle metadata (status, timestamps) |
| `errors` | Aggregated errors |
| `tool_calls` | Tool invocations (hint_lookup usage) |
| `metrics` | Token usage |
| `session_slices` | Session state |
| `files` | Workspace files |
