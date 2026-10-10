.PHONY: install test lint typecheck run clean

install:
	uv sync

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy .

run:
	uv run python -m elohim_gate --all

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache ruff_cache dist build *.egg-info