# Security

## Reporting an issue

This is a small hobby project without a formal security team. If you
find a real vulnerability (not just a free-tier quota concern), please
open an issue describing it — for anything sensitive, avoid posting
exploit details publicly until it's addressed.

## API keys

- Keys live only in your local `.env` file, read server-side via
  `python-dotenv`. The frontend never sees them — all provider calls go
  through your Flask backend.
- `.env` is excluded via `.gitignore`. **Before committing or pushing,
  double check `git status` doesn't show `.env`** — accidentally
  committing a key is the most likely real risk in a project like this.
- If a key ever leaks (committed by mistake, shared in a screenshot),
  revoke and regenerate it immediately from the provider's dashboard
  (links in `README.md`) — don't just remove it from a future commit,
  since it remains in git history.

## Running this publicly

If you deploy this somewhere reachable by others (Render, Railway, etc.)
rather than just running it locally:

- There's **no authentication** — anyone with the URL can use it, and
  every request burns your API quota. Don't share the URL publicly
  unless you're comfortable with that.
- `flask-limiter` caps request rates per route, but that limits abuse
  from a single source, not multiple people using it at once — it's not
  a substitute for auth.
- Consider adding basic auth (or a proper login) before sharing a
  deployed instance beyond yourself. See "Roadmap ideas not yet built"
  in `README.md`.

## Dependencies

Pinned versions are in `requirements.txt`. Run `pip list --outdated`
periodically and update deliberately — this project doesn't have
automated dependency scanning set up.
