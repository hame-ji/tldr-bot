.PHONY: setup test run

setup:
	uv sync --frozen
	uv run python -m playwright install chromium
	git config core.hooksPath .githooks

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

run:
	uv run python -m src
