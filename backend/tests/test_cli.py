"""Tests for CLI commands."""
import json
import os
import tempfile
import pytest
from equationx.cli import main


class TestCLI:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_discover_system(self, capsys):
        main(["discover", "--system", "queue", "--generations", "2", "--population", "5"])
        captured = capsys.readouterr()
        assert "Starting equation discovery" in captured.out or "Job" in captured.out

    def test_forecast(self, capsys, tmp_path):
        # Create a temporary equation file
        eq_file = tmp_path / "eq.json"
        eq_file.write_text(json.dumps({
            "latex": "0.95 * arrival_rate - 1.21 * service_rate",
            "variables": ["queue_depth", "arrival_rate", "service_rate"],
            "target": "queue_depth",
        }))

        main(["forecast", str(eq_file), "--initial", '{"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0}'])
        captured = capsys.readouterr()
        assert "Forecast" in captured.out or "Peak" in captured.out

    def test_explain(self, capsys, tmp_path):
        eq_file = tmp_path / "eq.json"
        eq_file.write_text(json.dumps({
            "latex": "0.95 * arrival_rate - 1.21 * service_rate",
        }))

        main(["explain", str(eq_file), "--actual", '{"queue_depth": 95, "arrival_rate": 12.4, "service_rate": 1.2}'])
        captured = capsys.readouterr()
        assert "Explanation" in captured.out or "summary" in captured.out.lower()

    def test_simulate(self, capsys, tmp_path):
        eq_file = tmp_path / "eq.json"
        eq_file.write_text(json.dumps({
            "latex": "0.95 * arrival_rate - 1.21 * service_rate",
        }))

        main(["simulate", str(eq_file), "--change", '{"service_rate": 2.0}',
              "--initial", '{"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0}'])
        captured = capsys.readouterr()
        assert "Simulation" in captured.out or "Peak" in captured.out
