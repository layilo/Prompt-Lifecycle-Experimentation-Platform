PYTHON ?= python

.PHONY: install test lint demo smoke clean

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

test:
	pytest -q

lint:
	ruff check src tests

demo:
	$(PYTHON) -m prompt_platform.cli demo run --profile local-demo --output-dir artifacts/generated/demo

smoke:
	$(PYTHON) -m prompt_platform.cli doctor --profile ci-smoke
	$(PYTHON) -m prompt_platform.cli demo run --profile ci-smoke --output-dir artifacts/generated/smoke

clean:
	Remove-Item -Recurse -Force artifacts/generated -ErrorAction SilentlyContinue

