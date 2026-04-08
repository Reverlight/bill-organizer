.PHONY: up test
# alembic revision --autogenerate -m "add leads table"
# alembic upgrade head
start-dev:
	docker compose up -d
stop-dev:
	docker compose down
autogenerate_and_migrate:
	docker compose exec web uv run alembic revision --autogenerate -m "receipt mapped columns timezone" && docker compose exec web uv run alembic upgrade head

start-test:
	docker compose -f test.docker-compose.yml -p mynewproject up --abort-on-container-exit --exit-code-from web_test
start-test-build:
	docker compose -f test.docker-compose.yml -p mynewproject up --abort-on-container-exit --exit-code-from web_test --build
stop-test:
	docker compose -f test.docker-compose.yml -p mynewproject down

pylint:
	docker compose exec web uv run pylint app

isort:
	docker compose exec web uv run isort . --skip .venv --skip .venv-1
black:
	docker compose exec web uv run black app/