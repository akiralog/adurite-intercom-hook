.PHONY: help install test test-cov lint format clean run setup

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt

install-dev:  ## Install development dependencies
	pip install -r requirements.txt
	pip install flake8 black isort safety

setup:  ## Initial setup (install deps, create venv)
	python -m venv venv
	@echo "Virtual environment created. Activate it with:"
	@echo "  source venv/bin/activate  # On Unix/Mac"
	@echo "  venv\\Scripts\\activate     # On Windows"
	@echo "Then run: make install"

test:  ## Run pytest tests
	pytest tests/ -v

test-cov:  ## Run pytest tests with coverage
	pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

test-fast:  ## Run pytest tests without coverage (faster)
	pytest tests/ -v --no-cov

test-standalone:  ## Run standalone test scripts
	python test_config.py
	python test_webhook.py

test-simple:  ## Run simple test runner
	python run_tests.py

lint:  ## Run linting checks
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics
	black --check .
	isort --check-only --diff .

format:  ## Format code with black and isort
	black .
	isort .

security:  ## Run security audit
	safety check --full-report

check:  ## Run all checks (lint, test, security)
	make lint
	make test
	make security

run:  ## Run the bot
	python main.py

run-test-config:  ## Run configuration test
	python test_config.py

run-test-webhook:  ## Run webhook test
	python test_webhook.py

clean:  ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete

venv:  ## Create virtual environment
	python -m venv venv

activate:  ## Show activation command
	@echo "To activate the virtual environment:"
	@echo "  source venv/bin/activate  # On Unix/Mac"
	@echo "  venv\\Scripts\\activate     # On Windows"

ci:  ## Run CI checks locally
	make install-dev
	make lint
	make test-cov
	make security
