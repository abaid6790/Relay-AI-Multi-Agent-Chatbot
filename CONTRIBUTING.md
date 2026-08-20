# Contributing to Relay

Thanks for taking a look. This is a small solo/hobby project, so the bar
is "does it work and is it explained" rather than a formal process.

## Getting set up

```bash
git clone <repo-url>
cd ai-chat-app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env
# add at least one provider key so you can test against something real —
# or leave it empty and rely on the mocked test suite below
```

## Running things while you work

```bash
python app.py           # dev server at http://localhost:5000
python test_keys.py     # sanity-check your real API keys
pytest                  # full test suite — mocked, costs nothing, no keys needed
```

## Before opening a PR

- [ ] `pytest` passes
- [ ] If you touched `providers.py`, run `python test_keys.py` against a
      real key for the provider you changed — model IDs and API shapes
      drift over time (this has already happened twice in this project:
      Groq deprecated a model, Hugging Face retired an entire endpoint)
- [ ] If you added a new backend route, add a mocked test for it in
      `tests/test_app.py` following the existing pattern (see
      `test_chat_success_with_mocked_provider` for the shape)
- [ ] If you changed the database schema (`db.py`), note it in the PR —
      there's no migration system, so schema changes currently mean
      "delete your local `chat_history.db` and start fresh"
- [ ] Update `README.md` if you added a feature, changed setup steps, or
      hit a new provider/API quirk worth documenting

## Code style

Nothing enforced by a linter yet — just match what's already there:
- Small, single-purpose functions in `providers.py`, one per
  provider/capability
- Comments explain *why*, not *what* (the code should already say what)
- Frontend is plain JS, no build step, no framework — keep it that way
  unless there's a strong reason not to

## Reporting a provider/API break

Free-tier APIs change often — models get deprecated, endpoints move,
rate limits shift. If something that used to work now fails:

1. Run `python test_keys.py` to confirm which provider is actually broken
2. Check the error message — 404s are usually a renamed/retired model,
   401/403 are usually a key or permissions issue, 429 is just a rate limit
3. Open an issue with the exact error and which provider/route it's on

## Ideas for contributions

See the "Roadmap ideas not yet built" section in `README.md` for a list
of features that would be welcome: conversation search, pinning,
folders, a real usage dashboard, multi-user accounts, PDF support for
document Q&A, Gemini tool-calling support.

## Questions

Open an issue — there's no separate mailing list or chat for this project.
