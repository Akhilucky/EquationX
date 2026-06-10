.PHONY: install test lint run-api run-mcp run-dashboard docker-up docker-down clean

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

test:
	cd backend && python -m pytest tests/ -v --tb=short

lint:
	cd backend && python -m ruff check equationx/
	cd backend && python -m mypy equationx/ --ignore-missing-imports

run-api:
	cd backend && uvicorn equationx.api:create_app --factory --reload --port 8000

run-mcp:
	cd backend && python -m equationx serve --mode mcp --port 8001

run-dashboard:
	cd frontend && npm run dev

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/dist backend/*.egg-info frontend/dist
