"""CLI interface for EquationX."""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="equationx",
        description="EquationX — AI Scientist for Infrastructure",
    )
    parser.add_argument("--version", action="version", version=f"equationx {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # discover
    p_disc = subparsers.add_parser("discover", help="Discover equations from CSV data")
    p_disc.add_argument("csv", nargs="?", help="Path to CSV file")
    p_disc.add_argument("--target", default="queue_depth", help="Target variable")
    p_disc.add_argument("--generations", type=int, default=100, help="GP generations")
    p_disc.add_argument("--population", type=int, default=200, help="Population size")
    p_disc.add_argument("--max-depth", type=int, default=6, help="Max tree depth")
    p_disc.add_argument("--system", choices=["queue", "cpu", "db_connections", "cache"],
                        help="Generate synthetic data for system type")

    # forecast
    p_fc = subparsers.add_parser("forecast", help="Forecast using discovered equation")
    p_fc.add_argument("equation_file", help="Path to equation JSON file")
    p_fc.add_argument("--initial", required=True, help="Initial conditions JSON")
    p_fc.add_argument("--threshold", type=float, help="Alert threshold")
    p_fc.add_argument("--horizon", type=int, default=15, help="Forecast horizon (minutes)")

    # explain
    p_ex = subparsers.add_parser("explain", help="Explain an anomaly")
    p_ex.add_argument("equation_file", help="Path to equation JSON file")
    p_ex.add_argument("--actual", required=True, help="Actual values JSON")

    # simulate
    p_sim = subparsers.add_parser("simulate", help="Run what-if simulation")
    p_sim.add_argument("equation_file", help="Path to equation JSON file")
    p_sim.add_argument("--change", required=True, help="Parameter changes JSON")
    p_sim.add_argument("--initial", required=True, help="Initial conditions JSON")
    p_sim.add_argument("--horizon", type=int, default=60, help="Simulation horizon (minutes)")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start API or MCP server")
    p_serve.add_argument("--mode", choices=["api", "mcp", "mcp-sse"], default="api", help="Server mode (mcp=stdio, mcp-sse=HTTP)")
    p_serve.add_argument("--port", type=int, default=8000, help="Port number")
    p_serve.add_argument("--host", default="0.0.0.0", help="Host to bind to")

    # dashboard
    subparsers.add_parser("dashboard", help="Launch React dashboard")

    args = parser.parse_args(argv)

    if args.command == "discover":
        _cmd_discover(args)
    elif args.command == "forecast":
        _cmd_forecast(args)
    elif args.command == "explain":
        _cmd_explain(args)
    elif args.command == "simulate":
        _cmd_simulate(args)
    elif args.command == "serve":
        _cmd_serve(args)
    elif args.command == "dashboard":
        _cmd_dashboard(args)
    else:
        parser.print_help()


def _cmd_discover(args):
    from .orchestrator import run_discovery
    from .models import DiscoverRequest

    request = DiscoverRequest(
        csv_path=args.csv,
        target=args.target,
        max_generations=args.generations,
        population_size=args.population,
        max_depth=args.max_depth,
        system_type=args.system,
    )

    print(f"Starting equation discovery...")
    result = run_discovery(request)
    print(f"Job {result.job_id}: {result.status}")

    # Poll until complete
    from .orchestrator import get_job_status
    while True:
        time.sleep(1)
        status = get_job_status(result.job_id)
        print(f"  Progress: {status.progress:.0%}")
        if status.status == "completed":
            break
        elif status.status == "failed":
            print(f"  Failed: {status.error}")
            sys.exit(1)

    if status.best_equation:
        print(f"\nBest equation:")
        print(f"  LaTeX: {status.best_equation['latex']}")
        print(f"  MSE: {status.best_equation['mse']:.6f}")
        print(f"  Complexity: {status.best_equation['complexity']}")

        # Save to file
        out_file = "equation_result.json"
        with open(out_file, "w") as f:
            json.dump(status.best_equation, f, indent=2)
        print(f"\nSaved to {out_file}")

    if status.pareto_front:
        print(f"\nPareto frontier ({len(status.pareto_front)} points):")
        for p in status.pareto_front[:5]:
            print(f"  {p['latex']}  (MSE={p['mse']:.6f}, C={p['complexity']})")


def _cmd_forecast(args):
    from .orchestrator import run_forecast
    from .models import ForecastRequest

    with open(args.equation_file) as f:
        eq_data = json.load(f)

    initial = json.loads(args.initial)

    request = ForecastRequest(
        equation=eq_data.get("latex", ""),
        initial_conditions=initial,
        horizon_minutes=args.horizon,
        threshold=args.threshold,
    )

    result = run_forecast(request)
    print(f"Forecast ({len(result.trajectory)} points):")
    print(f"  Peak: {result.peak_value}")
    print(f"  Steady-state: {result.steady_state_value}")
    if result.threshold_breach:
        print(f"  THRESHOLD BREACH at t={result.time_to_breach_minutes:.1f} min")
    else:
        print(f"  No threshold breach")
    print(f"\nTrajectory:")
    for pt in result.trajectory[::5]:
        print(f"  t={pt.time_minutes:6.1f}  val={pt.value:8.2f}  CI=[{pt.lower_ci:.2f}, {pt.upper_ci:.2f}]")


def _cmd_explain(args):
    from .orchestrator import run_explanation
    from .models import ExplanationRequest

    with open(args.equation_file) as f:
        eq_data = json.load(f)

    actual = json.loads(args.actual)

    request = ExplanationRequest(
        equation=eq_data.get("latex", ""),
        actual=actual,
    )

    result = run_explanation(request)
    print(f"Explanation:")
    print(f"  {result.summary}")
    print(f"  Predicted: {result.predicted_value}, Actual: {result.actual_value}, Deviation: {result.deviation}")
    print(f"  Contributing factors:")
    for f in result.contributing_factors:
        print(f"    {f.variable}: {f.actual_value:.1f} vs {f.expected_value:.1f} ({f.impact_pct:+.1f}%)")
    print(f"  Recommendation: {result.recommendation}")


def _cmd_simulate(args):
    from .orchestrator import run_simulation
    from .models import SimulateRequest

    with open(args.equation_file) as f:
        eq_data = json.load(f)

    changes = json.loads(args.change)
    initial = json.loads(args.initial)

    request = SimulateRequest(
        equation=eq_data.get("latex", ""),
        parameter_changes=changes,
        initial_conditions=initial,
        horizon_minutes=args.horizon,
    )

    result = run_simulation(request)
    print(f"Simulation:")
    print(f"  Peak: {result.peak_value}")
    print(f"  Steady-state: {result.steady_state_value}")
    print(f"  Time to stabilize: {result.time_to_stabilize_minutes} min")
    if result.threshold_breach:
        print(f"  THRESHOLD BREACH")
    print(f"  Recommendation: {result.recommendation}")


def _cmd_serve(args):
    if args.mode == "api":
        from .api import create_app
        import uvicorn
        app = create_app()
        print(f"Starting API server on {args.host}:{args.port}...")
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.mode == "mcp":
        from .mcp_server import run_mcp_stdio
        print(f"Starting MCP server (stdio)...")
        run_mcp_stdio()
    elif args.mode == "mcp-sse":
        from .mcp_server import run_mcp_sse
        print(f"Starting MCP server (SSE) on {args.host}:{args.port}...")
        run_mcp_sse(host=args.host, port=args.port)


def _cmd_dashboard(args):
    import subprocess
    import os
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    if os.path.exists(frontend_dir):
        subprocess.run(["npm", "run", "dev"], cwd=frontend_dir)
    else:
        print("Frontend directory not found. Build it first.")


if __name__ == "__main__":
    main()
