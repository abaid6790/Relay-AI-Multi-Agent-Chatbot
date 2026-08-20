# Changelog

This project was built incrementally in phases. Dates approximate when
each phase landed during development.

## Phase 13 — Conversation rename
- Rename a conversation via double-click on its title or the ✎ button
  in the sidebar (previously only auto-titling from the first message)

## Phase 12 — Tool calling
- Model can call a calculator (safe AST-based eval, not `eval()`), a
  clock, and a live weather lookup (Open-Meteo, free/keyless)
- Routes through Groq → OpenRouter only (see README's Known limitations
  for why Gemini isn't included here)
- Non-streaming, capped at 3 tool-call rounds to prevent runaway loops

## Phase 11 — Multi-modal input
- Vision: attach an image, ask about it (routes to Gemini)
- Document Q&A: attach a `.txt`/`.md` file, its content gets folded into
  your question as context (no vector DB — not needed at this scale)
- 📎 attach button in the composer, image/document preview chips

## Phase 10 — Multi-conversation & control
- Data model shift: conversations are now first-class, each with its own
  message history and optional persona/system prompt
- Sidebar: new chat, switch, delete
- Auto-titling from the first message in a conversation
- Regenerate the last reply; edit your last message and resend

## Phase 9 — UI polish
- Markdown rendering with syntax-highlighted code blocks (marked.js +
  highlight.js)
- Copy buttons on code blocks and full messages
- Light/dark theme toggle
- Export a conversation to Markdown

## Phase 8 — Testing & deployment
- Usage tracking (`/api/usage`) — per-provider call counts, today and
  last 7 days
- Rate limiting via `flask-limiter`
- Production-safe startup (debug off by default, binds `0.0.0.0`)
- `Procfile` + `gunicorn` for free hosting (Render/Railway)
- `.gitignore` to keep secrets and local DB out of version control

## Phase 7 — Streaming + persistent history
- Server-Sent Events streaming for chat replies
- SQLite-backed history — conversations survive a page reload

## Phases 1–6 — Core build
- Flask backend, provider adapters for Groq/Gemini/OpenRouter (chat) and
  Pollinations/Hugging Face (images)
- Automatic fallback chain: if one provider fails or rate-limits, the
  next one in the chain answers instead — invisible to the user
- Chat UI with a live "relay rail" showing which provider is answering
