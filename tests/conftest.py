"""Pytest configuration: makes sure main.py can be imported without a real
OpenAI API key, and that the project root is on sys.path."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("CORS_ALLOW_ORIGINS", "*")


import pytest


@pytest.fixture(autouse=True, scope="session")
def _disable_rate_limit():
    """slowapi in Tests abschalten: die Suite postet inzwischen genug auf
    rate-limitierte Endpoints (/board/move, /resonanz, /compare), dass das
    6/minute-Limit sonst flaky 429s produziert."""
    import main
    if getattr(main, "limiter", None) is not None:
        main.limiter.enabled = False
    yield
