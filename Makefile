# Makefile: shortcuts for the common project commands.
# Usage: make <target>   (e.g. make lint)

.PHONY: help install hooks fmt lint test check data update build api dashboard docs up down clean

help:  ## List the available targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Create the venv and install the dependencies
	uv sync

hooks:  ## Enable the pre-commit hooks in the git repository
	uv run pre-commit install

fmt:  ## Format the code and fix what can be fixed
	uv run ruff format .
	uv run ruff check . --fix

lint:  ## Check the style without changing anything
	uv run ruff format --check .
	uv run ruff check .

test:  ## Run the tests with the coverage report
	uv run pytest --cov=cabrera_twin --cov-report=term-missing

check: lint test  ## Checks to run before committing

data:  ## Download and harmonise the sources (needs copernicusmarine login)
	uv run cabrera-twin fetch

update:  ## Append the days published since the last run, then rebuild
	uv run cabrera-twin update

build:  ## Compute the indicators into data/exports
	uv run cabrera-twin build

api:  ## Run the HTTP API on http://localhost:8000 (docs at /docs)
	uv run uvicorn cabrera_twin.api:app --reload --port 8000

dashboard:  ## Run the Streamlit dashboard on http://localhost:8501
	uv run streamlit run dashboard/streamlit_app.py

docs:  ## Preview the documentation on http://localhost:8001
	uv run --group docs mkdocs serve -a localhost:8001

up:  ## Build and run the API and the dashboard with Docker
	docker compose up --build

down:  ## Stop the containers
	docker compose down

clean:  ## Remove caches and temporary files
	rm -rf .ruff_cache .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
