"""LLM agent layer for guided equation discovery and explanation."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .logging_config import get_logger

logger = get_logger(__name__)


class LLMAgent:
    """Agent that uses LLMs to guide equation discovery and explain results.

    Uses OpenRouter or OpenAI-compatible API.
    Set OPENROUTER_API_KEY or OPENAI_API_KEY env var, or
    EQUATIONX_LLM_ENDPOINT for a custom endpoint.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-4o-mini",
        endpoint: Optional[str] = None,
        temperature: float = 0.3,
    ):
        self.api_key = api_key or os.environ.get(
            "OPENROUTER_API_KEY",
            os.environ.get("OPENAI_API_KEY", ""),
        )
        self.model = model
        self.endpoint = endpoint or os.environ.get(
            "EQUATIONX_LLM_ENDPOINT",
            "https://openrouter.ai/api/v1",
        )
        self.temperature = temperature

    def _call_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Make a chat completion call to the LLM API."""
        if not self.api_key:
            logger.warning("No API key set for LLM agent. Skipping LLM call.")
            return None
        try:
            import httpx
            response = httpx.post(
                f"{self.endpoint}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": 2000,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def suggest_variables(
        self, column_names: List[str], sample_data: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """Suggest which variables are relevant and their roles."""
        prompt = f"""You are an SRE monitoring expert. Given these infrastructure metrics:
Columns: {column_names}
Sample data (first 3 rows): {json.dumps(sample_data, indent=2)}

Identify:
1. Which variable is most likely the target (dependent variable) to model? 
2. Which variables are likely independent variables?
3. What kind of system does this look like? (queue, CPU, DB, cache, network, memory, etc.)
4. Suggest plausible functional forms for d(target)/dt

Return JSON: {{"target": "...", "features": [...], "system_type": "...", "suggested_forms": [...]}}
"""
        response = self._call_llm([
            {"role": "system", "content": "You are an infrastructure monitoring AI that helps discover system dynamics."},
            {"role": "user", "content": prompt},
        ])

        if not response:
            return {"target": column_names[0] if column_names else "value",
                    "features": column_names[1:], "system_type": "unknown",
                    "suggested_forms": []}

        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"target": column_names[0] if column_names else "value",
                    "features": column_names[1:], "system_type": "unknown",
                    "suggested_forms": []}

    def seed_equations(
        self, system_type: str, variables: List[str], target: str
    ) -> List[str]:
        """Generate seed equations to kickstart GP."""
        prompt = f"""For a {system_type} system with variables {variables} and target {target},
suggest 3 simple candidate differential equations for d({target})/dt.
Use only these operators: +, -, *, /
Use the variables exactly as named.
Return ONLY a JSON array of strings, no markdown."""
        response = self._call_llm([
            {"role": "system", "content": "You are a mathematical modeling expert."},
            {"role": "user", "content": prompt},
        ])
        if not response:
            return []
        try:
            start = response.index("[")
            end = response.rindex("]") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return []

    def explain_equation(
        self, latex: str, variables: List[str], target: str, mse: float
    ) -> str:
        """Generate a natural language explanation of a discovered equation."""
        prompt = f"""Explain this discovered equation in plain English for an SRE:
Equation: d({target})/dt = {latex}
Variables: {variables}
Fit error (MSE): {mse:.6f}

Describe what this equation reveals about the system's behavior:
- What drives the target variable?
- What would happen if each variable increased?
- Any insights about stability or capacity?
Keep it concise."""
        response = self._call_llm([
            {"role": "system", "content": "You explain mathematical models to infrastructure engineers."},
            {"role": "user", "content": prompt},
        ])
        return response or "LLM explanation unavailable."

    def enhanced_explain_anomaly(
        self,
        equation_str: str,
        actual: Dict[str, float],
        predicted_value: float,
        contributing_factors: List[Dict],
    ) -> Dict[str, str]:
        """Generate a richer explanation of an anomaly using the LLM."""
        prompt = f"""Given this system equation: d(target)/dt = {equation_str}
Actual values: {json.dumps(actual)}
Predicted value: {predicted_value}
Contributing factors: {json.dumps(contributing_factors)}

Write a concise incident report summary explaining what's happening.
Include: root cause, impact, and recommended action (1-2 sentences each).
Return JSON: {{"root_cause": "...", "impact": "...", "action": "..."}}
"""
        response = self._call_llm([
            {"role": "system", "content": "You are an SRE on call. Write clear incident summaries."},
            {"role": "user", "content": prompt},
        ])
        if not response:
            return {
                "root_cause": "See contributing factors above.",
                "impact": f"Deviation of {predicted_value - actual.get(list(actual.keys())[0], 0):.1f}",
                "action": "Investigate top contributing factor.",
            }
        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return {
                "root_cause": response[:200],
                "impact": "See anomaly details above.",
                "action": "See recommendation above.",
            }
