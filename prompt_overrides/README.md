# Prompt Overrides

This directory stores local prompt overrides for the trivia agent.

## What are Prompt Overrides?

Prompt overrides let you customize section visibility, tool behavior, and other prompt aspects without modifying the code. They're useful for:

- **Local development**: Test prompt variations without changing source
- **A/B testing**: Run experiments with different prompt configurations
- **Debugging**: Expand hidden sections to see full context

## Directory Structure

Override files are organized by namespace, prompt key, and tag:

```
prompt_overrides/
├── trivia/
│   └── main/
│       ├── latest/           # Default tag
│       │   └── overrides.json
│       └── experiment-v2/    # Custom experiment tag
│           └── overrides.json
```

## Creating Overrides

Use the WINK CLI to seed and manage overrides:

```bash
# Seed overrides from the current prompt template
uv run wink overrides seed trivia:main --tag latest

# List available overrides
uv run wink overrides list

# Edit overrides
uv run wink overrides edit trivia:main --tag latest
```

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

Overrides are automatically loaded when the agent starts. Set the tag via:

1. **Environment variable**: `TRIVIA_PROMPT_OVERRIDES_DIR`
2. **Experiment metadata**: Pass `--experiment` flag to dispatch-eval

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRIVIA_PROMPT_OVERRIDES_DIR` | `./prompt_overrides` | Override files directory |

Override files in this directory are gitignored by default.
