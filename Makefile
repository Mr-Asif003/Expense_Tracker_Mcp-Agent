.DEFAULT_GOAL := help
PY ?= python

.PHONY: help install lint format typecheck test check ui agent mcp docker-build clean

help:  ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package with all extras and dev tools (editable)
	$(PY) -m pip install -e ".[all,dev]"
	pre-commit install

lint:  ## Ruff lint + format check
	ruff check .
	ruff format --check .

format:  ## Auto-format and fix lint issues
	ruff check --fix .
	ruff format .

typecheck:  ## Static type checks (mypy --strict)
	mypy

test:  ## Run the test suite with coverage
	pytest --cov --cov-report=term-missing

check: lint typecheck test  ## Everything CI runs

ui:  ## Start the Streamlit UI
	expense-tracker-ui

agent:  ## Start the terminal chat agent
	expense-tracker-agent

mcp:  ## Run the MCP server over STDIO
	expense-tracker-mcp

docker-build:  ## Build the Docker image
	docker build -t expense-tracker .

clean:  ## Remove caches and build artefacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
