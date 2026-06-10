# EquationX — AI Scientist for Infrastructure

[![CI](https://github.com/Akhilucky/EquationX/actions/workflows/ci.yml/badge.svg)](https://github.com/Akhilucky/EquationX/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Newton watched apples and discovered F=ma. **EquationX watches your infrastructure** — CPU, queue depth, request rate, DB connections — and automatically discovers the mathematical laws governing it. Then it predicts failures, explains anomalies, and simulates "what if" scenarios.

```
┌─────────────────────────────────────────────────────────────┐
│  CSV Data ──→ [Genetic Programming] ──→ d(q)/dt = 0.95·a  │
│                      │                        - 1.21·s     │
│                      ▼                                     │
│              ┌──────────────┐                              │
│              │ Pareto       │ ──→ Forecast (15min ahead)   │
│              │ Frontier     │ ──→ Explain (why 95 ≠ 67?)   │
│              │              │ ──→ Simulate (2x capacity?)   │
│              └──────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

### 1. Equation Discovery
Feed CSV time-series data, get back **differential equations (ODEs)** in LaTeX.
- Uses genetic programming (DEAP) + symbolic regression
- Supports operators: `+ - * / exp log sin cos sqrt d/dt`
- Returns Pareto frontier (accuracy vs complexity trade-off)
- Automatically simplifies equations

### 2. Forecasting
Predict 5/15/30/60 minutes ahead with confidence intervals.
- Monte Carlo perturbation for CI estimation
- Threshold detection with time-to-breach in minutes
- Alert when threshold will be exceeded

### 3. Explanation Engine
When reality diverges from prediction, tells you **why**.
- Detects deviation from equation prediction
- Identifies contributing factors with impact percentages
- Returns natural language summary + actionable recommendations

### 4. What-If Simulation
Modify any parameter and see the new trajectory.
- Compares baseline vs modified trajectories
- Reports peak value, steady-state, time to stabilize
- Generates recommendations based on results

---

## Quick Start

### Install

```bash
# Backend
cd backend
pip install -e .

# Frontend
cd ../frontend
npm install
```

### Discover Equations

```bash
# Use synthetic queue data
equationx discover --system queue

# Use your own CSV
equationx discover data.csv --target queue_depth

# Forecast from discovered equation
equationx forecast equation.json --initial '{"queue_depth":10,"arrival_rate":8.0,"service_rate":1.0}' --threshold 100

# Explain an anomaly
equationx explain equation.json --actual '{"queue_depth":95,"arrival_rate":12.4,"service_rate":1.2}'

# Simulate what-if
equationx simulate equation.json --change '{"service_rate":16}' --initial '{"queue_depth":10,"arrival_rate":8.0,"service_rate":1.0}'
```

### Start Servers

```bash
# REST API (port 8000)
equationx serve --mode api --port 8000

# MCP Server — stdio (for Claude Desktop)
equationx serve --mode mcp

# MCP Server — SSE (for Cursor, HTTP clients)
equationx serve --mode mcp-sse --port 8001

# Dashboard
equationx dashboard
```

---

## Docker

### Quick Start

```bash
docker-compose up --build
```

- **API:** http://localhost:8000
- **Dashboard:** http://localhost:3000

### Pull from Docker Hub

```bash
# Pull images
docker pull akhilucky/equationx-backend:latest
docker pull akhilucky/equationx-frontend:latest

# Run directly
docker run -p 8000:8000 akhilucky/equationx-backend:latest
docker run -p 3000:80 akhilucky/equationx-frontend:latest
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /discover` | POST | Start equation discovery job |
| `GET /discover/{id}/status` | GET | Check discovery progress |
| `GET /equations` | GET | List all discovered equations |
| `GET /equations/{id}` | GET | Get equation details |
| `POST /forecast` | POST | Generate forecast + time-to-breach |
| `POST /explain` | POST | Explain anomaly |
| `POST /simulate` | POST | Run what-if scenario |
| `GET /health` | GET | Service health check |

### Example: Forecast

```bash
curl -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "equation": "0.95 * arrival_rate - 1.21 * service_rate",
    "initial_conditions": {"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0},
    "horizon_minutes": 15,
    "threshold": 100
  }'
```

---

## MCP Integration

EquationX provides 4 MCP tools for use with Claude Desktop, Cursor, and other MCP-compatible clients.

### Tools

| Tool | Description |
|------|-------------|
| `discover_equation` | CSV → LaTeX equation + Pareto frontier |
| `forecast_system` | Predictions + time-to-breach + confidence intervals |
| `explain_anomaly` | Natural language explanation + factor breakdown |
| `simulate_scenario` | Modified trajectory + recommendations |

### Claude Desktop Setup

Copy `mcp-config/claude_desktop_config.json` to your Claude Desktop config:

```bash
# macOS
cp mcp-config/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Linux
cp mcp-config/claude_desktop_config.json ~/.config/claude/claude_desktop_config.json
```

### Cursor Setup

Add to your Cursor MCP settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "equationx": {
      "url": "http://localhost:8001/sse"
    }
  }
}
```

Then start the SSE server:
```bash
equationx serve --mode mcp-sse --port 8001
```

### Example MCP Usage

Ask Claude/Cursor:
> "Use EquationX to discover the equation governing this queue system, then forecast if it'll breach 100 in the next 15 minutes"

---

## Dashboard

5 pages, all connected to the backend API:

- **Discover** — Upload CSV or use synthetic data, watch Pareto frontier evolve
- **Equations** — Browse discovered equations with LaTeX rendering
- **Forecast** — Set threshold, see prediction chart + breach alerts
- **Explain** — Paste anomaly data, see root cause + recommendations
- **Simulate** — Change parameters, compare trajectories

---

## Synthetic Data Generator

Generates data from known ground-truth equations with configurable noise:

| System | ODE | Variables |
|--------|-----|-----------|
| Queue | `d(q)/dt = arrival_rate - service_rate · q/(K+q)` | queue_depth, arrival_rate, service_rate |
| CPU | `d(c)/dt = α·(load - c) - β·c` | cpu_usage, load |
| DB | `d(conn)/dt = λ - μ·conn` | connections |
| Cache | `d(hit)/dt = γ·(1 - hit) - δ·hit` | hit_rate |

```python
from equationx.data_generator import generate_data

df = generate_data("queue", n_points=500, noise_pct=0.05)
```

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.10+, FastAPI, SymPy, DEAP, SciPy, NumPy, Pandas, Prometheus |
| **Frontend** | React 18, TypeScript, Tailwind CSS, Recharts, Vitest |
| **AI Agent** | LLM agent (OpenRouter/OpenAI) for guided discovery + explanation |
| **Storage** | SQLite (persistent equation store) |
| **MCP** | MCP SDK (stdio + SSE transport) |
| **Observability** | Prometheus metrics, structured logging, rate limiting, API key auth |
| **Deployment** | Docker, Docker Compose, GitHub Actions |

---

## Project Structure

```
EquationX/
├── backend/
│   ├── equationx/
│   │   ├── grammar.py        # AST, SymPy conversion, LaTeX
│   │   ├── gp_engine.py      # Genetic programming (DEAP)
│   │   ├── pareto.py         # Pareto frontier
│   │   ├── ode_solver.py     # ODE solving + forecasting
│   │   ├── explanation.py    # Root cause analysis
│   │   ├── simulation.py     # What-if simulation
│   │   ├── data_generator.py # Synthetic data (4 systems)
│   │   ├── orchestrator.py   # High-level API
│   │   ├── cli.py            # CLI interface
│   │   ├── api.py            # REST API (8 endpoints)
│   │   └── mcp_server.py     # MCP server (4 tools)
│   ├── tests/                # 54 tests
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/            # 5 React pages
│   │   └── App.tsx
│   └── package.json
├── examples/                 # Pre-discovered equations
├── mcp-config/               # MCP client configs
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── Makefile
└── README.md
```

---

## New in v0.2.0

- **Rewritten GP Engine** — Proper subtree crossover/mutation, scipy constant optimization, configurable hall of fame
- **LLM Agent** — AI-powered variable suggestions, equation explanations, and enriched anomaly reports (OpenRouter/OpenAI)
- **Persistent SQLite Store** — Equations survive restarts; query, export, and compare across sessions
- **Async Background Tasks** — CPU-intensive discovery runs in thread pool, doesn't block the API
- **Prometheus Metrics** — Track discovery duration, forecast counts, active jobs (`GET /metrics`)
- **Rate Limiting & API Key Auth** — Production-ready with configurable limits and optional Bearer auth
- **Real-time Data Connectors** — Fetch data from Prometheus or Datadog APIs directly
- **Confidence Interval Charts** — Forecase page now renders 90% CI bands using Recharts AreaChart
- **CSV Upload in UI** — Drag-and-drop or select CSV files on the Discover page
- **Frontend Testing** — Vitest + React Testing Library setup with navigation tests
- **Structured Logging** — Timestamped, leveled logs throughout the backend

## Development

```bash
# Run tests
cd backend && python -m pytest tests/ -v

# Run with coverage
cd backend && python -m pytest tests/ --cov=equationx --cov-report=html

# Lint
cd backend && python -m ruff check equationx/

# Type check
cd backend && python -m mypy equationx/ --ignore-missing-imports
```

---

## Pre-discovered Equations

Example equations are in `examples/`:

```bash
# Forecast using a pre-discovered equation
equationx forecast examples/pre_discovered_queue.json \
  --initial '{"queue_depth":10,"arrival_rate":8.0,"service_rate":1.0}' \
  --threshold 100
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
