"""
Provider adapters.

Each chat_* function takes a list of {"role": "user"|"assistant", "content": str}
messages plus an optional system_prompt (used for personas), and returns a
plain string reply, or raises an exception on failure (caught by the router
in app.py so it can fall through to the next provider).

Each image_* function takes a prompt string and returns raw image bytes,
or raises an exception on failure.
"""

import json
import os
import time
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
HF_API_KEY = os.environ.get("HF_API_KEY")

REQUEST_TIMEOUT = 30


def _with_system(messages, system_prompt):
    """Prepends an OpenAI-style system message if a persona is set."""
    if not system_prompt:
        return messages
    return [{"role": "system", "content": system_prompt}] + messages


def _gemini_contents(messages, image=None):
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    # Attach an uploaded image to the current (last) user turn only — we
    # don't persist uploaded images across turns, so there's nothing to
    # attach to earlier turns even if this is a multi-turn conversation.
    if image and contents:
        contents[-1]["parts"].append({
            "inline_data": {"mime_type": image["mime_type"], "data": image["data"]}
        })
    return contents


# --------------------------------------------------------------------------
# Chat providers (non-streaming)
# --------------------------------------------------------------------------

def chat_groq(messages, system_prompt=None, image=None, model="openai/gpt-oss-120b"):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")
    if image:
        # This app doesn't wire up Groq's vision-capable models — raising
        # here makes the chain fall through to Gemini automatically rather
        # than silently ignoring the image.
        raise RuntimeError("Groq path in this app does not support image input")

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": model, "messages": _with_system(messages, system_prompt), "temperature": 0.7},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def chat_gemini(messages, system_prompt=None, image=None, model="gemini-2.5-flash"):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    body = {"contents": _gemini_contents(messages, image)}
    if system_prompt:
        body["system_instruction"] = {"parts": [{"text": system_prompt}]}

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": GEMINI_API_KEY},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def chat_openrouter(messages, system_prompt=None, image=None, model="openrouter/free"):
    # "openrouter/free" is OpenRouter's own auto-router: it picks whichever
    # free model is currently live instead of a hardcoded slug, so this
    # keeps working even as the free-model roster rotates week to week.
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")
    if image:
        # The auto-router isn't guaranteed to land on a vision-capable
        # model, so — same as Groq — we don't risk it here and let the
        # chain fall through to Gemini instead.
        raise RuntimeError("OpenRouter path in this app does not support image input")

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": model, "messages": _with_system(messages, system_prompt)},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# Ordered fallback chain. Each entry is (provider_name, function).
# If one raises, the router in app.py tries the next.
CHAT_CHAIN = [
    ("groq", chat_groq),
    ("gemini", chat_gemini),
    ("openrouter", chat_openrouter),
]


# --------------------------------------------------------------------------
# Tool-calling chat (non-streaming — a tool-call round trip needs the full
# response to inspect before deciding whether to call a tool or answer
# directly, so this doesn't fit the token-streaming path). Groq and
# OpenRouter both speak OpenAI-style function calling; Gemini uses a
# different request/response shape for this and isn't included here to
# keep this feature's scope manageable — plain chat and vision still fall
# back to Gemini as before, just not tool calls specifically.
# --------------------------------------------------------------------------

def chat_groq_tools(messages, system_prompt=None, tools=None, model="openai/gpt-oss-120b"):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")
    body = {"model": model, "messages": _with_system(messages, system_prompt), "temperature": 0.3}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def chat_openrouter_tools(messages, system_prompt=None, tools=None, model="openrouter/free"):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")
    body = {"model": model, "messages": _with_system(messages, system_prompt)}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


TOOL_CHAT_CHAIN = [
    ("groq", chat_groq_tools),
    ("openrouter", chat_openrouter_tools),
]


# --------------------------------------------------------------------------
# Streaming chat providers
# --------------------------------------------------------------------------
#
# Each "opener" makes the request with stream=True and calls
# raise_for_status() immediately, so failures (bad key, rate limit, dead
# model) surface right away — before any tokens are read. That's what lets
# app.py fall through to the next provider cleanly: if the opener raises,
# nothing has been streamed to the client yet, so switching providers is
# invisible. Once an opener succeeds, the caller commits to that provider
# for the rest of the reply.
#
# Each "extractor" takes one raw line from the response and returns either
# a text delta (str) or None (for lines that carry no new text, like
# "[DONE]" markers or keep-alives).

def open_groq_stream(messages, system_prompt=None, image=None, model="openai/gpt-oss-120b"):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")
    if image:
        raise RuntimeError("Groq path in this app does not support image input")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": model,
            "messages": _with_system(messages, system_prompt),
            "temperature": 0.7,
            "stream": True,
        },
        stream=True,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp


def open_openrouter_stream(messages, system_prompt=None, image=None, model="openrouter/free"):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")
    if image:
        raise RuntimeError("OpenRouter path in this app does not support image input")
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": model, "messages": _with_system(messages, system_prompt), "stream": True},
        stream=True,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp


def extract_openai_chunk(line):
    """Groq and OpenRouter both speak the OpenAI streaming format."""
    if not line:
        return None
    text = line.decode("utf-8") if isinstance(line, bytes) else line
    if not text.startswith("data: "):
        return None
    payload = text[len("data: "):].strip()
    if payload == "[DONE]":
        return None
    try:
        obj = json.loads(payload)
        return obj["choices"][0]["delta"].get("content")
    except (KeyError, IndexError, json.JSONDecodeError):
        return None


def open_gemini_stream(messages, system_prompt=None, image=None, model="gemini-2.5-flash"):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    body = {"contents": _gemini_contents(messages, image)}
    if system_prompt:
        body["system_instruction"] = {"parts": [{"text": system_prompt}]}

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
        params={"key": GEMINI_API_KEY, "alt": "sse"},
        json=body,
        stream=True,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp


def extract_gemini_chunk(line):
    if not line:
        return None
    text = line.decode("utf-8") if isinstance(line, bytes) else line
    if not text.startswith("data: "):
        return None
    payload = text[len("data: "):].strip()
    try:
        obj = json.loads(payload)
        return obj["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, json.JSONDecodeError):
        return None


# Each entry: (provider_name, opener_fn, extractor_fn)
STREAM_CHAIN = [
    ("groq", open_groq_stream, extract_openai_chunk),
    ("gemini", open_gemini_stream, extract_gemini_chunk),
    ("openrouter", open_openrouter_stream, extract_openai_chunk),
]


# --------------------------------------------------------------------------
# Image providers
# --------------------------------------------------------------------------

def image_pollinations(prompt, width=1024, height=1024):
    """No API key required. Returns raw image bytes."""
    import urllib.parse

    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}"
    resp = requests.get(
        url,
        params={"width": width, "height": height, "seed": int(time.time())},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def image_hf(prompt, model="black-forest-labs/FLUX.1-schnell"):
    if not HF_API_KEY:
        raise RuntimeError("HF_API_KEY not configured")

    # Hugging Face retired api-inference.huggingface.co (returns HTTP 410).
    # Requests now go through the router at router.huggingface.co instead.
    resp = requests.post(
        f"https://router.huggingface.co/hf-inference/models/{model}",
        headers={"Authorization": f"Bearer {HF_API_KEY}"},
        json={"inputs": prompt},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


IMAGE_CHAIN = [
    ("pollinations", image_pollinations),
    ("huggingface", image_hf),
]
