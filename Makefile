.PHONY: install test run dev docker-build docker-up docker-down lint clean

install:
	pip install -r requirements.txt

test:
	python -m pytest -q

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

lint:
	python tools/lint.py

clean:
	rm -rf .pytest_cache __pycache__ app/__pycache__ tests/__pycache__ app.db
