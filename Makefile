.PHONY: help install agent dispatch redis redis-stop check format lint typecheck test integration-test clean clean-bundles

# Default target
help:
	@echo "WINK Starter - Secret Trivia Agent"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install dependencies"
	@echo "  make redis          Start Redis in Docker"
	@echo "  make redis-stop     Stop Redis container"
	@echo ""
	@echo "Run:"
	@echo "  make agent          Start the Secret Trivia agent worker"
	@echo "  make agent ADAPTER=codex     Start with Codex adapter"
	@echo "  make agent ADAPTER=opencode  Start with OpenCode adapter"
	@echo "  make dispatch       Submit a test question (set QUESTION=...)"
	@echo "  make dispatch-eval  Submit an eval case with experiment metadata"
	@echo ""
	@echo "Eval options (for dispatch-eval):"
	@echo "  QUESTION=...        The question to ask"
	@echo "  EXPECTED=...        Expected answer substring"
	@echo "  EXPERIMENT=...      Experiment name (default: cli-eval)"
	@echo "  OWNER=...           Experiment owner (optional)"
	@echo "  DESCRIPTION=...     Experiment description (optional)"
	@echo ""
	@echo "Development:"
	@echo "  make check            Run all checks (format, lint, typecheck, test)"
	@echo "  make format           Format code with ruff"
	@echo "  make lint             Run linter"
	@echo "  make typecheck        Run type checker"
	@echo "  make test             Run unit tests"
	@echo "  make integration-test Run integration tests (requires Redis + API key)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove build artifacts"
	@echo "  make clean-bundles  Remove debug bundles (.zip, .zip.sqlite, eval dirs)"

# =============================================================================
# Setup
# =============================================================================

install:
	uv sync

redis:
	@if docker ps -a --format '{{.Names}}' | grep -q '^wink-redis$$'; then \
		echo "Starting existing Redis container..."; \
		docker start wink-redis; \
	else \
		echo "Creating new Redis container..."; \
		docker run -d --name wink-redis -p 6379:6379 redis:7-alpine; \
	fi
	@echo "Redis running at redis://localhost:6379"

redis-stop:
	docker stop wink-redis || true

# =============================================================================
# Run
# =============================================================================

# Default settings
REDIS_URL ?= redis://localhost:6379
TRIVIA_DEBUG_BUNDLES_DIR ?= $(CURDIR)/debug_bundles
TRIVIA_PROMPT_OVERRIDES_DIR ?= $(CURDIR)/prompt_overrides
QUESTION ?= "What is the secret number?"
EXPECTED ?= ""
EXPERIMENT ?= cli-eval
OWNER ?=
DESCRIPTION ?=
ADAPTER ?= claude

agent:
	REDIS_URL=$(REDIS_URL) \
	TRIVIA_ADAPTER=$(ADAPTER) \
	TRIVIA_DEBUG_BUNDLES_DIR=$(TRIVIA_DEBUG_BUNDLES_DIR) \
	TRIVIA_PROMPT_OVERRIDES_DIR=$(TRIVIA_PROMPT_OVERRIDES_DIR) \
	uv run trivia-agent

dispatch:
	REDIS_URL=$(REDIS_URL) \
	uv run trivia-dispatch --question $(QUESTION)

dispatch-eval:
	REDIS_URL=$(REDIS_URL) \
	uv run trivia-dispatch --eval --question $(QUESTION) --expected $(EXPECTED) \
		--experiment $(EXPERIMENT) \
		$(if $(OWNER),--owner "$(OWNER)") \
		$(if $(DESCRIPTION),--description "$(DESCRIPTION)")

# =============================================================================
# Development
# =============================================================================

check: format lint typecheck test

format:
	uv run ruff format src tests

lint:
	uv run ruff check src tests --fix

typecheck:
	uv run pyright src

test:
	uv run pytest tests -v

integration-test:
	TRIVIA_ADAPTER=$(ADAPTER) uv run pytest integration-tests/ -v --timeout=300 --no-cov

# =============================================================================
# Cleanup
# =============================================================================

clean:
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-bundles:
	rm -f debug_bundles/*.zip
	rm -f debug_bundles/*.zip.sqlite
	@# Remove UUID directories from eval runs (preserve .gitignore, README.md)
	@find debug_bundles -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Debug bundles cleaned"
