"""Settings: model, Portkey client, prices, spend caps, paths.

PORTKEY_API_KEY (or OPENAI_API_KEY) is read from the nearest .env: first the repo folder,
then each folder above it (so a .env one level up, as the teaching staff use, works).
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
for folder in (ROOT, *ROOT.parents):
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env", override=False)

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

PROMPTS = BACKEND / "prompts"
DEMO_FILES = BACKEND / "demo_files"
DATA = ROOT / "data"
SESSIONS_DIR = DATA / "sessions"
UPLOADS = DATA / "uploads"
OUTPUT = ROOT / "output"
AUDIT_FILE = OUTPUT / "audit_trail.jsonl"
FRONTEND_DIST = ROOT / "frontend" / "dist"
for _d in (SESSIONS_DIR, UPLOADS, OUTPUT):
    _d.mkdir(parents=True, exist_ok=True)

# USD per 1M tokens, OpenAI standard short-context prices (Lecture 11 / OpenAI pricing page).
PRICES = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50},
}

# Spend guards. A public deployment shares one key, so there is a cap per visitor and a global
# daily cap across all visitors. Both stop agent runs with a friendly message when reached.
SESSION_CAP_USD = float(os.getenv("SESSION_CAP_USD", "0.75"))
GLOBAL_DAILY_CAP_USD = float(os.getenv("GLOBAL_DAILY_CAP_USD", "8.00"))
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "200"))
ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip()

# Per-run limits (harness stopping rules).
LEAD_REQUEST_LIMIT = 10
SUB_REQUEST_LIMIT = 6
MAX_TOOL_CALLS = 12
MAX_OUTPUT_TOKENS = 4000   # the full evaluation form (every section + tables) needs ~2-3k
HISTORY_MESSAGES = 24          # messages of chat memory kept per thread
PATIENT_BOT_MAX_TURNS = 3      # simulator: replies a patient bot gives per conversation burst

USD_RATE = float(os.getenv("USD_RATE", "18.5"))  # MXN per USD, for display only
VERSION = "1.4.0"


def api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if key:
        return key
    return os.getenv("OPENAI_API_KEY", "").strip()


def using_portkey() -> bool:
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
