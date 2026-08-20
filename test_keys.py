"""
Run this to test every API key in your .env in one go.

Usage:
    python test_keys.py
"""

from dotenv import load_dotenv
load_dotenv()

import providers  # noqa: E402

TEST_MESSAGE = [{"role": "user", "content": "Reply with exactly one word: hi"}]
TEST_PROMPT = "a red apple on a white table"

results = []


def check(label, fn):
    try:
        result = fn()
        preview = result if isinstance(result, str) else f"{len(result)} bytes"
        print(f"[ OK ] {label:12s} -> {str(preview)[:70]}")
        results.append((label, True, None))
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {label:12s} -> {exc}")
        results.append((label, False, str(exc)))


print("Testing chat providers...\n")
check("Groq", lambda: providers.chat_groq(TEST_MESSAGE))
check("Gemini", lambda: providers.chat_gemini(TEST_MESSAGE))
check("OpenRouter", lambda: providers.chat_openrouter(TEST_MESSAGE))

print("\nTesting image providers...\n")
check("Pollinations", lambda: providers.image_pollinations(TEST_PROMPT))
check("HuggingFace", lambda: providers.image_hf(TEST_PROMPT))

print("\n--- Summary ---")
for label, ok, err in results:
    status = "working" if ok else "NOT working"
    print(f"{label:12s} {status}")

failed = [r for r in results if not r[1]]
if failed:
    print(f"\n{len(failed)} provider(s) failed. Check the key or account status for those above.")
else:
    print("\nAll configured providers are working.")
