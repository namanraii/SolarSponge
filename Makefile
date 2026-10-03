.PHONY: install test demo eval serve backtest lint

install:
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest tests -q

demo:
	python3 -m solarsponge.cli demo

eval:
	python3 -m solarsponge.cli eval --days 8 --out artifacts

backtest:
	python3 -m solarsponge.cli backtest

serve:
	python3 -m solarsponge.cli serve --port 8000

lint:
	python3 -m ruff check src tests || true
