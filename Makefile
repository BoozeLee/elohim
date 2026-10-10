.PHONY: install test lint typecheck run gate clean

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

gate:
	python3 tests/test_all.py

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache ruff_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +