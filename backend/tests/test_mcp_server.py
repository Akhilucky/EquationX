"""Tests for the MCP server."""
from __future__ import annotations

import anyio
import pytest
from mcp.types import CallToolRequest, ListToolsRequest, PingRequest


class TestMCPServer:
    def test_create_server(self):
        from equationx.mcp_server import create_mcp_server
        server = create_mcp_server()
        assert server is not None

    def test_handlers_registered(self):
        from equationx.mcp_server import create_mcp_server
        server = create_mcp_server()
        expected = {PingRequest, ListToolsRequest, CallToolRequest}
        assert expected.issubset(server.request_handlers.keys())

    def _get_tools(self):
        from equationx.mcp_server import create_mcp_server
        server = create_mcp_server()
        handler = server.request_handlers[ListToolsRequest]
        result = anyio.run(handler, ListToolsRequest(method="tools/list", params={}))
        return result.root.tools

    def test_all_tools_present(self):
        tools = self._get_tools()
        tool_names = [t.name for t in tools]
        assert "discover_equation" in tool_names
        assert "forecast_system" in tool_names
        assert "explain_anomaly" in tool_names
        assert "simulate_scenario" in tool_names

    def test_discover_tool_schema(self):
        tools = self._get_tools()
        disc = [t for t in tools if t.name == "discover_equation"][0]
        props = disc.inputSchema["properties"]
        assert "csv_data" in props
        assert "target" in props
        assert "system_type" in props

    def test_forecast_tool_schema(self):
        tools = self._get_tools()
        fc = [t for t in tools if t.name == "forecast_system"][0]
        props = fc.inputSchema["properties"]
        assert "equation" in props
        assert "initial_conditions" in props
        assert "horizon_minutes" in props

    def test_explain_tool_schema(self):
        tools = self._get_tools()
        expl = [t for t in tools if t.name == "explain_anomaly"][0]
        props = expl.inputSchema["properties"]
        assert "equation" in props
        assert "actual" in props

    def test_simulate_tool_schema(self):
        tools = self._get_tools()
        sim = [t for t in tools if t.name == "simulate_scenario"][0]
        props = sim.inputSchema["properties"]
        assert "equation" in props
        assert "parameter_changes" in props
        assert "initial_conditions" in props
