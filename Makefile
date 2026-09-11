.PHONY: setup format lint typecheck test check audit build
setup:
	uv sync --frozen --dev
format:
	uv run ruff format .
lint:
	uv run ruff check .
	uv run ruff format --check .
typecheck:
	uv run pyright
test:
	uv run pytest
check: lint typecheck test
audit:
	uv audit --preview-features audit-command --locked --no-dev
	uv run python tools/check_licenses.py
build:
	uv build
