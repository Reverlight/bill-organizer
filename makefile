.PHONY: up test
# alembic revision --autogenerate -m "add leads table"
# alembic upgrade head
start-dev:
	docker compose up -d
stop-dev:
	docker compose down

start-test:
	docker compose -f test.docker-compose.yml -p mynewproject up --abort-on-container-exit --exit-code-from web_test
stop-test:
	docker compose -f test.docker-compose.yml -p mynewproject down

pylint:
	docker compose exec web uv run pylint app

isort:
	docker compose exec web uv run isort . --skip .venv --skip .venv-1