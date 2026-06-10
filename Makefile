.PHONY: install test lint run-api run-mcp run-dashboard docker-up docker-down clean test-all

install:
	cd backend && pip install -e ".[all]"
	cd frontend && npm install

test:
	cd backend && python -m pytest tests/ -v --tb=short

test-all:
	cd backend && python -m pytest tests/ -v --tb=short --cov=equationx --cov-report=term
	cd frontend && npm test

lint:
	cd backend && python -m ruff check equationx/
	cd frontend && npm run lint

run-api:
	cd backend && uvicorn equationx.api:create_app --factory --reload --port 8000

run-mcp:
	cd backend && python -m equationx serve --mode mcp --port 8001

run-dashboard:
	cd frontend && npm run dev

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-push:
	docker tag equationx-backend:latest akhilucky/equationx-backend:latest
	docker tag equationx-frontend:latest akhilucky/equationx-frontend:latest
	docker push akhilucky/equationx-backend:latest
	docker push akhilucky/equationx-frontend:latest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/dist backend/*.egg-info frontend/dist
