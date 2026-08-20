"""
Tools the model can call. Kept deliberately small and dependency-free:
- calculator: safe arithmetic, no network needed
- get_current_time: server clock, no network needed
- get_weather: Open-Meteo (free, no API key required at all — fits the
  project's "free tier only" philosophy better than a keyed weather API)

Each tool function takes keyword arguments matching its JSON schema in
TOOLS_SCHEMA and returns a plain string result (what gets fed back to the
model as the tool's output).
"""

import ast
import operator
import datetime
import requests

REQUEST_TIMEOUT = 15

# --------------------------------------------------------------------------
# Calculator — evaluated via a whitelisted AST walk, NOT eval()/exec(), so
# there's no code-execution risk even though the input comes from the model.
# --------------------------------------------------------------------------

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval_node(node.left), _safe_eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def tool_calculator(expression):
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval_node(tree.body)
        return str(result)
    except Exception as exc:  # noqa: BLE001
        return f"Could not evaluate '{expression}': {exc}"


# --------------------------------------------------------------------------
# Current time
# --------------------------------------------------------------------------

def tool_get_current_time():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%A, %B %d, %Y, %H:%M UTC")


# --------------------------------------------------------------------------
# Weather — Open-Meteo, free and keyless
# --------------------------------------------------------------------------

def tool_get_weather(city):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=REQUEST_TIMEOUT,
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return f"Could not find a location matching '{city}'."

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        label = f"{place['name']}, {place.get('country', '')}".strip(", ")

        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=REQUEST_TIMEOUT,
        )
        weather.raise_for_status()
        current = weather.json().get("current_weather", {})
        temp = current.get("temperature")
        wind = current.get("windspeed")
        return f"Current weather in {label}: {temp}°C, wind {wind} km/h."
    except Exception as exc:  # noqa: BLE001
        return f"Weather lookup failed: {exc}"


TOOLS_MAP = {
    "calculator": tool_calculator,
    "get_current_time": tool_get_current_time,
    "get_weather": tool_get_weather,
}

# OpenAI-style function-calling schema, understood by both Groq and
# OpenRouter's OpenAI-compatible endpoints.
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression (+, -, *, /, **, parentheses).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "e.g. '(4 + 5) * 3 / 2'"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time (UTC).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a named city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Lahore' or 'Paris'"}
                },
                "required": ["city"],
            },
        },
    },
]
