.PHONY: setup format lint typecheck test check audit build notebook notebook-check
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
notebook:
	uv run --frozen --group notebook jupyter lab --ip=127.0.0.1 notebooks/signal-report.ipynb
notebook-check:
	uv run --frozen --group notebook jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=120 --output-dir build --output executed-signal-report.ipynb notebooks/signal-report.ipynb
