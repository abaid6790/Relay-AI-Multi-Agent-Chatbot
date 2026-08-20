import base64
import json
import os

from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

import providers  # noqa: E402  (import after load_dotenv so keys are read correctly)
import db  # noqa: E402
import tools  # noqa: E402

app = Flask(__name__)
db.init_db()
db.init_usage_table()

# Protects your free-tier quotas from being burned through accidentally
# (a bug, a retry loop, someone else finding your dev server). Adjust the
# numbers if they're too tight for how you're using it.
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per hour"])


@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify({"error": "Rate limit exceeded", "detail": str(e.description)}), 429


@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------

@app.route("/api/conversations", methods=["GET"])
def api_list_conversations():
    browser_id = request.args.get("browser_id", "").strip()
    if not browser_id:
        return jsonify({"error": "browser_id is required"}), 400
    return jsonify({"conversations": db.list_conversations(browser_id)})


@app.route("/api/conversations", methods=["POST"])
def api_create_conversation():
    body = request.get_json(force=True) or {}
    browser_id = (body.get("browser_id") or "").strip()
    if not browser_id:
        return jsonify({"error": "browser_id is required"}), 400
    title = (body.get("title") or "New chat").strip()
    system_prompt = (body.get("system_prompt") or "").strip()
    conv = db.create_conversation(browser_id, title=title, system_prompt=system_prompt)
    return jsonify({"conversation": conv})


@app.route("/api/conversations/<conversation_id>", methods=["PATCH"])
def api_update_conversation(conversation_id):
    body = request.get_json(force=True) or {}
    if "title" in body:
        db.rename_conversation(conversation_id, body["title"].strip())
    if "system_prompt" in body:
        db.set_system_prompt(conversation_id, body["system_prompt"].strip())
    return jsonify({"conversation": db.get_conversation(conversation_id)})


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def api_delete_conversation(conversation_id):
    db.delete_conversation(conversation_id)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------

@app.route("/api/history", methods=["GET"])
def api_history():
    conversation_id = request.args.get("conversation_id", "").strip()
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    return jsonify({"messages": db.get_history(conversation_id)})


@app.route("/api/history/clear", methods=["POST"])
def api_history_clear():
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    db.clear_history(conversation_id)
    return jsonify({"ok": True})


@app.route("/api/history/delete_last", methods=["POST"])
def api_delete_last():
    """Used by the 'edit last message' flow on the frontend: removes the
    trailing N messages (e.g. the last user+assistant pair) before the
    edited message gets resent through the normal chat flow."""
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    count = int(body.get("count", 1))
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    db.delete_last_messages(conversation_id, count=count)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Chat (non-streaming)
# --------------------------------------------------------------------------

def _load_context(conversation_id):
    """Returns (history_for_provider, system_prompt) for a conversation.
    Includes 'vision' turns (a past image question) as plain text — the
    image itself isn't persisted, so only the question/answer survives
    into later context, same as if it'd been a text-only turn."""
    conv = db.get_conversation(conversation_id)
    system_prompt = conv["system_prompt"] if conv else None
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in db.get_history(conversation_id)
        if m["kind"] in ("text", "vision")
    ]
    return history, system_prompt


def _extract_image(body):
    """Pulls {mime_type, data} off a request body, if present and well-formed."""
    image = body.get("image")
    if not image or not isinstance(image, dict):
        return None
    if not image.get("mime_type") or not image.get("data"):
        return None
    return {"mime_type": image["mime_type"], "data": image["data"]}


@app.route("/api/chat", methods=["POST"])
@limiter.limit("20 per minute")
def api_chat():
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    message = (body.get("message") or "").strip()
    image = _extract_image(body)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    if not message:
        return jsonify({"error": "No message provided"}), 400

    db.save_message(conversation_id, "user", message, kind="vision" if image else "text")
    history, system_prompt = _load_context(conversation_id)

    last_error = None
    for provider_name, fn in providers.CHAT_CHAIN:
        try:
            reply = fn(history, system_prompt, image)
            db.save_message(conversation_id, "assistant", reply, provider=provider_name)
            db.log_usage(provider_name, "chat")
            return jsonify({"reply": reply, "provider": provider_name})
        except Exception as exc:  # noqa: BLE001 - deliberately broad, we fall through
            last_error = str(exc)
            continue

    return jsonify({"error": "All chat providers failed", "detail": last_error}), 502


# --------------------------------------------------------------------------
# Chat (streaming) — shared generator reused by both /stream and /regenerate
# --------------------------------------------------------------------------

def sse(data):
    return f"data: {json.dumps(data)}\n\n"


def _stream_reply(conversation_id, history, system_prompt, image=None):
    resp = None
    provider_name = None
    extractor = None
    last_error = None

    for name, opener, extract_fn in providers.STREAM_CHAIN:
        try:
            resp = opener(history, system_prompt, image)
            provider_name = name
            extractor = extract_fn
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue

    if resp is None:
        yield sse({"type": "error", "detail": last_error})
        return

    yield sse({"type": "provider", "provider": provider_name})

    full_text = ""
    try:
        for raw_line in resp.iter_lines():
            delta = extractor(raw_line)
            if delta:
                full_text += delta
                yield sse({"type": "delta", "text": delta})
    except Exception as exc:  # noqa: BLE001
        yield sse({"type": "error", "detail": str(exc)})
        return

    db.save_message(conversation_id, "assistant", full_text, provider=provider_name)
    db.log_usage(provider_name, "chat")
    yield sse({"type": "done"})


@app.route("/api/chat/stream", methods=["POST"])
@limiter.limit("20 per minute")
def api_chat_stream():
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    message = (body.get("message") or "").strip()
    image = _extract_image(body)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    if not message:
        return jsonify({"error": "No message provided"}), 400

    db.save_message(conversation_id, "user", message, kind="vision" if image else "text")
    history, system_prompt = _load_context(conversation_id)

    return Response(
        stream_with_context(_stream_reply(conversation_id, history, system_prompt, image)),
        mimetype="text/event-stream",
    )


@app.route("/api/chat/regenerate", methods=["POST"])
@limiter.limit("20 per minute")
def api_chat_regenerate():
    """Re-answers the last user message with a fresh reply, discarding the
    previous assistant reply (if any) first."""
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    history, system_prompt = _load_context(conversation_id)
    if history and history[-1]["role"] == "assistant":
        db.delete_last_messages(conversation_id, count=1)
        history = history[:-1]

    if not history:
        return jsonify({"error": "Nothing to regenerate"}), 400

    return Response(
        stream_with_context(_stream_reply(conversation_id, history, system_prompt)),
        mimetype="text/event-stream",
    )


# --------------------------------------------------------------------------
# Chat with tool calling (non-streaming — see providers.py for why)
# --------------------------------------------------------------------------

MAX_TOOL_ROUNDS = 3  # hard cap so a confused model can't loop forever


@app.route("/api/chat/tools", methods=["POST"])
@limiter.limit("20 per minute")
def api_chat_tools():
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    message = (body.get("message") or "").strip()

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    if not message:
        return jsonify({"error": "No message provided"}), 400

    db.save_message(conversation_id, "user", message)
    history, system_prompt = _load_context(conversation_id)

    last_error = None
    for provider_name, fn in providers.TOOL_CHAT_CHAIN:
        try:
            working_messages = list(history)
            tool_log = []

            result = fn(working_messages, system_prompt, tools=tools.TOOLS_SCHEMA)
            msg = result["choices"][0]["message"]

            rounds = 0
            while msg.get("tool_calls") and rounds < MAX_TOOL_ROUNDS:
                working_messages.append({
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": msg["tool_calls"],
                })
                for call in msg["tool_calls"]:
                    name = call["function"]["name"]
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tool_fn = tools.TOOLS_MAP.get(name)
                    try:
                        tool_result = tool_fn(**args) if tool_fn else f"Unknown tool: {name}"
                    except Exception as exc:  # noqa: BLE001
                        tool_result = f"Tool error: {exc}"
                    tool_log.append({"name": name, "args": args, "result": tool_result})
                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": str(tool_result),
                    })

                result = fn(working_messages, system_prompt, tools=tools.TOOLS_SCHEMA)
                msg = result["choices"][0]["message"]
                rounds += 1

            final_text = msg.get("content") or ""
            if not final_text and rounds >= MAX_TOOL_ROUNDS:
                final_text = "(Reached the tool-call limit before getting a final answer — try rephrasing.)"
            db.save_message(conversation_id, "assistant", final_text, provider=provider_name)
            db.log_usage(provider_name, "chat")
            return jsonify({"reply": final_text, "provider": provider_name, "tool_calls": tool_log})
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue

    return jsonify({"error": "All tool-capable providers failed", "detail": last_error}), 502


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

@app.route("/api/image", methods=["POST"])
@limiter.limit("10 per minute")
def api_image():
    body = request.get_json(force=True) or {}
    conversation_id = (body.get("conversation_id") or "").strip()
    prompt = (body.get("prompt") or "").strip()

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    db.save_message(conversation_id, "user", prompt, kind="image")

    last_error = None
    for provider_name, fn in providers.IMAGE_CHAIN:
        try:
            image_bytes = fn(prompt)
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            # Note: we don't store the base64 blob itself in SQLite (that
            # would bloat the DB fast) — just a marker that an image was
            # generated here, so history replay shows something sensible.
            db.save_message(
                conversation_id, "assistant", "[image generated]",
                provider=provider_name, kind="image",
            )
            db.log_usage(provider_name, "image")
            return jsonify({
                "image_base64": encoded,
                "provider": provider_name,
            })
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue

    return jsonify({"error": "All image providers failed", "detail": last_error}), 502


# --------------------------------------------------------------------------
# Usage
# --------------------------------------------------------------------------

@app.route("/api/usage", methods=["GET"])
def api_usage():
    days = request.args.get("days", 7, type=int)
    return jsonify(db.get_usage_summary(days=days))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
