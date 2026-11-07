"""LLM backend — OpenAI-compatible chat, defaults to Tencent CodeBuddy gateway.

Config via env:
    ANYTOMANIM_LLM_BASE_URL  (default https://copilot.tencent.com/v2)
    ANYTOMANIM_LLM_API_KEY   (falls back to CODEBUDDY_TOKEN, OPENCODE_GO_API_KEY, .env)
    ANYTOMANIM_LLM_MODEL     (default deepseek-v4.1-flash)

CodeBuddy gateway notes: streaming-only (non-streaming replies with error 11101),
plain `Authorization: Bearer <JWT>` is sufficient. OpenCode Go also works via
ANYTOMANIM_LLM_BASE_URL=https://opencode.ai/zen/go/v1 (needs x-opencode-session).
Retries on empty content (reasoning models can exhaust max_tokens inside thinking).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_BASE = "https://copilot.tencent.com/v2"
DEFAULT_MODEL = "deepseek-v4.1-flash"


def _env(key: str, fallback: str | None = None) -> str | None:
    v = os.environ.get(key)
    if v:
        return v
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return fallback


def chat(messages: list[dict], *, model: str | None = None,
         max_tokens: int = 8192, temperature: float = 0.7,
         retries: int = 3, base_url: str | None = None) -> str:
    """Single-shot chat completion -> content string."""
    from openai import OpenAI

    base = base_url or _env("ANYTOMANIM_LLM_BASE_URL", DEFAULT_BASE)
    key = (_env("ANYTOMANIM_LLM_API_KEY") or _env("CODEBUDDY_TOKEN")
           or _env("CODEBUDDY_JWT") or _env("OPENCODE_GO_API_KEY"))
    if not key:
        sys.exit("No LLM API key: set ANYTOMANIM_LLM_API_KEY or CODEBUDDY_TOKEN")
    headers = {"User-Agent": "AnyToManim/0.1"}
    if "opencode.ai" in base:
        headers["x-opencode-session"] = "anytomanim"
    client = OpenAI(api_key=key, base_url=base, default_headers=headers)
    mdl = model or _env("ANYTOMANIM_LLM_MODEL", DEFAULT_MODEL)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            # CodeBuddy requires stream=true; OpenAI SDK streams SSE either way.
            resp = client.chat.completions.create(
                model=mdl, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
                stream=True,
            )
            parts = [c.choices[0].delta.content or "" for c in resp
                     if c.choices and c.choices[0].delta]
            content = "".join(parts)
            if content.strip():
                return content
            last_err = RuntimeError("empty content (reasoning exhausted max_tokens?)")
            max_tokens = int(max_tokens * 1.5)
        except Exception as e:  # noqa: BLE001 — retry on transient API errors
            last_err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LLM chat failed after {retries} attempts: {last_err}")


def chat_json(messages: list[dict], **kw) -> dict:
    """chat() but parse a JSON object out of the reply (fences tolerated)."""
    import json
    import re

    text = chat(messages, **kw)
    m = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.S)
    raw = m.group(1) if m else text
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in reply:\n{text[:500]}")
    return json.loads(raw[start:end + 1])
