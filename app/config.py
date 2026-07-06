"""Application configuration loaded from environment variables.

Settings are read once at import time. A local ``.env`` file (if present) is
loaded automatically so developers do not have to export variables by hand.
Secrets such as the API key are NEVER hard-coded in the source.
"""

import os

from dotenv import load_dotenv

# Load variables from a local .env file if one exists (no error if it does not).
load_dotenv()


class Settings:
    """Runtime settings for the MatchDay Ops Copilot service."""

    def __init__(self) -> None:
        # Gemini API key. When empty, the assistant runs in deterministic
        # "demo mode" so the service still works without any credentials.
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()

        # Model name is configurable so we never hard-code a single engine.
        # Swapping models is a deliberate, env-driven choice, not a code edit.
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

        # Base URL for the Gemini REST API (overridable for testing/proxies).
        self.gemini_base_url: str = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ).strip()

        # Timeout, in seconds, for outbound AI requests.
        self.request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "20"))

    @property
    def ai_enabled(self) -> bool:
        """Return True when a real API key is configured (live mode)."""
        return bool(self.gemini_api_key)


# A single shared settings instance used across the application.
settings = Settings()
