.PHONY: help setup run-api run-dashboard run-all test test-cov lint docker-up docker-down

PYTHON := python3
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' Makefile | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## Create venv and install dependencies
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	cp -n .env.example .env || true
	mkdir -p data/videos data/db data/exports data/frames
	@echo "\n✅ Setup complete. Place video files in data/videos/ then run: make run-api"

run-api:  ## Start FastAPI backend
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-dashboard:  ## Start Streamlit dashboard
	$(VENV)/bin/streamlit run dashboard/app.py --server.port 8501

run-all:  ## Start API + dashboard in parallel (requires tmux or separate terminals)
	@echo "Start API:       make run-api"
	@echo "Start Dashboard: make run-dashboard"

test:  ## Run all tests
	$(VENV)/bin/pytest tests/ -v

test-cov:  ## Run tests with coverage report
	$(VENV)/bin/pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

lint:  ## Run ruff linter
	$(VENV)/bin/ruff check app/ tests/ || true

docker-up:  ## Start via Docker Compose
	docker-compose up --build -d

docker-down:  ## Stop Docker Compose services
	docker-compose down
