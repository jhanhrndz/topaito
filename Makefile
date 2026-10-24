.PHONY: setup test lint bench run demo

PYTHON ?= .venv/Scripts/python.exe

setup:
	python -m venv .venv
	$(PYTHON) -m pip install -e ".[dev,ner]"
	-$(PYTHON) -m spacy download es_core_news_md
	ollama pull qwen3:4b

test:
	$(PYTHON) -m pytest -v

lint:
	$(PYTHON) -m ruff check .

bench:
	$(PYTHON) -m bench.generator.generate
	$(PYTHON) -m bench.run_bench --split test
	$(PYTHON) -m bench.utility_eval

run:
	$(PYTHON) -m uvicorn tapaito.api.app:app --host 127.0.0.1 --port 8080

demo:
	$(PYTHON) scripts/run_demo_offline.py
