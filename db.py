"""
SQLite persistence layer.

Two-level structure now: a browser (identified by a random id stored in
localStorage) owns multiple conversations; each conversation owns its own
messages and an optional system prompt/persona.
"""

import sqlite3
import uuid
from contextlib import contextmanager

DB_PATH = "chat_history.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                browser_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'New chat',
                system_prompt TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,          -- 'user' or 'assistant'
                content TEXT NOT NULL,
                provider TEXT,               -- which provider answered, if assistant
                kind TEXT DEFAULT 'text',    -- 'text' or 'image'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)"
        )


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------

def create_conversation(browser_id, title="New chat", system_prompt=""):
    conv_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, browser_id, title, system_prompt) VALUES (?, ?, ?, ?)",
            (conv_id, browser_id, title, system_prompt),
        )
    return get_conversation(conv_id)


def list_conversations(browser_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, system_prompt, created_at, updated_at FROM conversations "
            "WHERE browser_id = ? ORDER BY updated_at DESC",
            (browser_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conversation_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, browser_id, title, system_prompt, created_at, updated_at "
            "FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    return dict(row) if row else None


def rename_conversation(conversation_id, title):
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id)
        )


def set_system_prompt(conversation_id, system_prompt):
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET system_prompt = ? WHERE id = ?",
            (system_prompt, conversation_id),
        )


def touch_conversation(conversation_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )


def delete_conversation(conversation_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------

def save_message(conversation_id, role, content, provider=None, kind="text"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, provider, kind) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, provider, kind),
        )
    touch_conversation(conversation_id)


def get_history(conversation_id, limit=50):
    """Returns messages oldest-first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, provider, kind, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def delete_last_messages(conversation_id, count=1):
    """Deletes the most recent `count` messages in a conversation.
    Used for regenerate (removes the last assistant reply) and edit
    (removes the last user+assistant pair before resending)."""
    with get_conn() as conn:
        ids = conn.execute(
            "SELECT id FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, count),
        ).fetchall()
        ids = [r["id"] for r in ids]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids)


def clear_history(conversation_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))


# --------------------------------------------------------------------------
# Usage tracking
# --------------------------------------------------------------------------

def init_usage_table():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                kind TEXT NOT NULL,          -- 'chat' or 'image'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def log_usage(provider, kind):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO usage_log (provider, kind) VALUES (?, ?)",
            (provider, kind),
        )


def get_usage_summary(days=7):
    with get_conn() as conn:
        today = conn.execute(
            """
            SELECT provider, kind, COUNT(*) as count
            FROM usage_log
            WHERE date(created_at) = date('now')
            GROUP BY provider, kind
            """
        ).fetchall()
        recent = conn.execute(
            """
            SELECT provider, kind, COUNT(*) as count
            FROM usage_log
            WHERE created_at >= datetime('now', ?)
            GROUP BY provider, kind
            """,
            (f"-{days} days",),
        ).fetchall()
    return {
        "today": [dict(r) for r in today],
        f"last_{days}_days": [dict(r) for r in recent],
    }
