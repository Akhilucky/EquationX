"""MCP Server for EquationX — 4 tools with SSE transport."""
from __future__ import annotations

import json
import asyncio
from typing import Any, Dict

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from .orchestrator import (
    run_discovery,
    run_forecast,
    run_explanation,
    run_simulation,
    get_job_status,
)
from .models import (
    DiscoverRequest,
    ForecastRequest,
    ExplanationRequest,
    SimulateRequest,
)


def create_mcp_server() -> Server:
    server = Server("equationx")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="discover_equation",
                description=(
                    "Discover mathematical equations (ODEs) from CSV time-series data. "
                    "Uses genetic programming + symbolic regression to find differential equations. "
                    "Returns LaTeX equation, Pareto frontier (accuracy vs complexity), and metadata. "
                    "Supports operators: +, -, *, /, exp, log, sin, cos, sqrt, d/dt."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "csv_data": {
                            "type": "string",
                            "description": "CSV data as a string (with header row). Each column is a variable, 't' is time.",
                        },
                        "target": {
                            "type": "string",
                            "description": "Target variable to discover equation for (e.g. 'queue_depth', 'cpu_usage')",
                        },
                        "system_type": {
                            "type": "string",
                            "enum": ["queue", "cpu", "db_connections", "cache"],
                            "description": (
                                "Predefined system type for synthetic data generation. "
                                "Queue: d(q)/dt = arrival - service*q/(K+q). "
                                "CPU: d(c)/dt = α*(load-c) - β*c. "
                                "DB: d(conn)/dt = λ - μ*conn. "
                                "Cache: d(hit)/dt = γ*(1-hit) - δ*hit."
                            ),
                        },
                        "max_generations": {
                            "type": "integer",
                            "default": 100,
                            "description": "Number of GP generations (higher = better equations, slower)",
                        },
                        "population_size": {
                            "type": "integer",
                            "default": 200,
                            "description": "Population size per generation",
                        },
                    },
                },
            ),
            Tool(
                name="forecast_system",
                description=(
                    "Generate time-series forecasts with confidence intervals. "
                    "Predicts future values of the target variable using the discovered ODE. "
                    "Optionally detects threshold breaches and returns time-to-breach in minutes. "
                    "Uses Monte Carlo perturbation for confidence interval estimation."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "equation": {
                            "type": "string",
                            "description": "LaTeX or sympy-format equation string (e.g. '0.95 * arrival_rate - 1.21 * service_rate')",
                        },
                        "initial_conditions": {
                            "type": "object",
                            "description": "Initial values for all variables (e.g. {'queue_depth': 10, 'arrival_rate': 8.0})",
                        },
                        "horizon_minutes": {
                            "type": "integer",
                            "default": 15,
                            "description": "How far ahead to forecast (in minutes)",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Optional threshold value. If the trajectory crosses this, a breach time is reported.",
                        },
                    },
                    "required": ["equation", "initial_conditions"],
                },
            ),
            Tool(
                name="explain_anomaly",
                description=(
                    "Explain why actual observed values differ from equation predictions. "
                    "Identifies contributing factors with impact percentages. "
                    "Returns a natural language summary, root cause analysis, and actionable recommendations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "equation": {
                            "type": "string",
                            "description": "LaTeX or sympy-format equation string",
                        },
                        "actual": {
                            "type": "object",
                            "description": "Actual observed values for all variables (e.g. {'queue_depth': 95, 'arrival_rate': 12.4})",
                        },
                    },
                    "required": ["equation", "actual"],
                },
            ),
            Tool(
                name="simulate_scenario",
                description=(
                    "Run what-if simulations by modifying system parameters. "
                    "Simulates the new trajectory using the modified equation and compares with baseline. "
                    "Returns peak value, steady-state, time to stabilize, and recommendations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "equation": {
                            "type": "string",
                            "description": "LaTeX or sympy-format equation string",
                        },
                        "parameter_changes": {
                            "type": "object",
                            "description": "Parameters to modify (e.g. {'service_rate': 16})",
                        },
                        "initial_conditions": {
                            "type": "object",
                            "description": "Initial values for all variables",
                        },
                        "horizon_minutes": {
                            "type": "integer",
                            "default": 60,
                            "description": "How far to simulate (in minutes)",
                        },
                    },
                    "required": ["equation", "parameter_changes", "initial_conditions"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
        if name == "discover_equation":
            request = DiscoverRequest(
                csv_data=arguments.get("csv_data"),
                target=arguments.get("target", "queue_depth"),
                system_type=arguments.get("system_type"),
                max_generations=arguments.get("max_generations", 100),
                population_size=arguments.get("population_size", 200),
            )
            result = run_discovery(request)
            status = get_job_status(result.job_id)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "job_id": result.job_id,
                    "status": status.status,
                    "progress": status.progress,
                    "best_equation": status.best_equation,
                    "pareto_front": status.pareto_front,
                }, indent=2),
            )]

        elif name == "forecast_system":
            request = ForecastRequest(
                equation=arguments["equation"],
                initial_conditions=arguments["initial_conditions"],
                horizon_minutes=arguments.get("horizon_minutes", 15),
                threshold=arguments.get("threshold"),
            )
            result = run_forecast(request)
            trajectory_out = []
            for pt in result.trajectory:
                if isinstance(pt, dict):
                    trajectory_out.append({
                        "time": pt["time_minutes"],
                        "value": pt["value"],
                        "ci": [pt["lower_ci"], pt["upper_ci"]],
                    })
                else:
                    trajectory_out.append({
                        "time": pt.time_minutes,
                        "value": pt.value,
                        "ci": [pt.lower_ci, pt.upper_ci],
                    })
            return [TextContent(
                type="text",
                text=json.dumps({
                    "trajectory": trajectory_out,
                    "threshold_breach": result.threshold_breach,
                    "time_to_breach_minutes": result.time_to_breach_minutes,
                    "peak_value": result.peak_value,
                    "steady_state_value": result.steady_state_value,
                }, indent=2),
            )]

        elif name == "explain_anomaly":
            request = ExplanationRequest(
                equation=arguments["equation"],
                actual=arguments["actual"],
            )
            result = run_explanation(request)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "summary": result.summary,
                    "predicted_value": result.predicted_value,
                    "actual_value": result.actual_value,
                    "deviation": result.deviation,
                    "contributing_factors": [
                        {
                            "variable": f.variable,
                            "actual_value": f.actual_value,
                            "expected_value": f.expected_value,
                            "impact_pct": f.impact_pct,
                            "direction": f.direction,
                        }
                        for f in result.contributing_factors
                    ],
                    "recommendation": result.recommendation,
                }, indent=2),
            )]

        elif name == "simulate_scenario":
            request = SimulateRequest(
                equation=arguments["equation"],
                parameter_changes=arguments["parameter_changes"],
                initial_conditions=arguments["initial_conditions"],
                horizon_minutes=arguments.get("horizon_minutes", 60),
            )
            result = run_simulation(request)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "peak_value": result.peak_value,
                    "steady_state_value": result.steady_state_value,
                    "time_to_stabilize_minutes": result.time_to_stabilize_minutes,
                    "threshold_breach": result.threshold_breach,
                    "recommendation": result.recommendation,
                }, indent=2),
            )]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    return server


def run_mcp_stdio():
    """Run MCP server over stdio (for Claude Desktop integration)."""
    from mcp.server.stdio import stdio_server

    server = create_mcp_server()

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_run())


def run_mcp_sse(host: str = "0.0.0.0", port: int = 8001):
    """Run MCP server over SSE transport (HTTP)."""
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    import uvicorn

    server = create_mcp_server()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    print(f"EquationX MCP server running on http://{host}:{port}")
    print(f"  SSE endpoint: http://{host}:{port}/sse")
    print(f"  Messages endpoint: http://{host}:{port}/messages/")
    uvicorn.run(app, host=host, port=port)
