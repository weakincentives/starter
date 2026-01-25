# Prompt Overrides

This directory stores local prompt overrides for the trivia agent.

## What are Prompt Overrides?

Prompt overrides let you customize section visibility, tool behavior, and other prompt aspects without modifying the code. They're useful for:

- **Local development**: Test prompt variations without changing source
- **A/B testing**: Run experiments with different prompt configurations
- **Debugging**: Expand hidden sections to see full context

## How Overrides are Created

Override files are **automatically seeded** when the agent starts. The `LocalPromptOverridesStore` creates the initial override files based on the current prompt template. You can then edit these JSON files to customize behavior.

To seed overrides, simply run the agent:

```bash
make agent
```

This creates override files in the directory structure organized by namespace, prompt key, and tag.

## Override Format

Override files are JSON with section visibility and tool settings:

```json
{
  "sections": {
    "rules": {
      "visibility": "FULL"
    }
  },
  "tools": {
    "hint_lookup": {
      "enabled": true
    }
  }
}
```

## Using Overrides

Overrides are automatically loaded when the agent starts. Control override behavior via:

1. **Environment variable**: `TRIVIA_PROMPT_OVERRIDES_DIR` sets the directory for override files
2. **Experiment metadata**: Pass `--experiment` flag to dispatch-eval to use a specific overrides tag

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRIVIA_PROMPT_OVERRIDES_DIR` | `./prompt_overrides` | Override files directory |

Override files in this directory are gitignored by default (see `.gitignore`).
