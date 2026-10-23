.PHONY: help install sync lock run test test-unit test-integration test-e2e test-cov clean

help:
	@echo "install          - установить все зависимости включая dev"
	@echo "sync             - синхронизировать окружение по uv.lock"
	@echo "lock             - обновить uv.lock"
	@echo "run              - запустить backend"
	@echo "test             - запустить все тесты"
	@echo "test-unit        - только unit-тесты"
	@echo "test-integration - только integration-тесты"
	@echo "test-e2e         - только e2e-тесты"
	@echo "test-cov         - все тесты с покрытием"
	@echo "clean            - удалить кэши pytest и __pycache__"

install:
	uv sync --all-groups

sync:
	uv sync --frozen --all-groups

lock:
	uv lock

run:
	uv run python main.py

test:
	uv run pytest tests -v

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-e2e:
	uv run pytest tests/e2e -v

test-cov:
	uv run pytest tests --cov=. --cov-report=term-missing -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov