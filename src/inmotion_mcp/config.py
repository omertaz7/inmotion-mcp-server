"""Configuration for the inMotion MCP server.

All credentials and endpoints are read from environment variables so that no
secrets are committed to source control. See `.env.example` for the full list.
Each service is independently optional: tools for a service raise a clear,
actionable error if that service has not been configured, rather than failing
at import time. This lets the server run with only the integrations you need.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Module-level constants ------------------------------------------------------
DEFAULT_TIMEOUT_SECONDS: float = 30.0
NOTION_API_BASE: str = "https://api.notion.com/v1"
NOTION_VERSION: str = "2022-06-28"
GMAIL_API_BASE: str = "https://gmail.googleapis.com/gmail/v1/users/me"


def _clean(value: Optional[str]) -> Optional[str]:
    """Trim whitespace and treat empty strings as unset."""
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class NotionConfig:
    """Notion integration settings (CRM / system-of-record layer)."""

    token: Optional[str]
    leads_database_id: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.token)


@dataclass(frozen=True)
class N8nConfig:
    """n8n integration settings (automation layer).

    `base_url` is the API root, e.g. ``https://your-n8n-host/api/v1``.
    `webhook_base_url` is the host that serves webhook triggers, e.g.
    ``https://your-n8n-host`` (the ``/webhook/<path>`` suffix is added per call).
    """

    base_url: Optional[str]
    api_key: Optional[str]
    webhook_base_url: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)


@dataclass(frozen=True)
class GmailConfig:
    """Gmail integration settings (outbound layer).

    Expects a short-lived OAuth 2.0 access token with the relevant Gmail
    scopes (e.g. ``gmail.readonly`` for search, ``gmail.compose`` for drafts).
    Token acquisition/refresh is intentionally left to the surrounding
    environment so this server stays a thin, auditable integration layer.
    """

    access_token: Optional[str]
    sender: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)


@dataclass(frozen=True)
class Settings:
    """Top-level settings aggregating every service configuration."""

    notion: NotionConfig
    n8n: N8nConfig
    gmail: GmailConfig
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the process environment.

        Reads (all optional):
            NOTION_TOKEN, NOTION_LEADS_DATABASE_ID
            N8N_BASE_URL, N8N_API_KEY, N8N_WEBHOOK_BASE_URL
            GMAIL_ACCESS_TOKEN, GMAIL_SENDER
            MCP_HTTP_TIMEOUT (float seconds, default 30)
        """
        timeout_raw = _clean(os.environ.get("MCP_HTTP_TIMEOUT"))
        try:
            timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT_SECONDS
        except ValueError:
            timeout = DEFAULT_TIMEOUT_SECONDS

        return cls(
            notion=NotionConfig(
                token=_clean(os.environ.get("NOTION_TOKEN")),
                leads_database_id=_clean(os.environ.get("NOTION_LEADS_DATABASE_ID")),
            ),
            n8n=N8nConfig(
                base_url=_clean(os.environ.get("N8N_BASE_URL")),
                api_key=_clean(os.environ.get("N8N_API_KEY")),
                webhook_base_url=_clean(os.environ.get("N8N_WEBHOOK_BASE_URL")),
            ),
            gmail=GmailConfig(
                access_token=_clean(os.environ.get("GMAIL_ACCESS_TOKEN")),
                sender=_clean(os.environ.get("GMAIL_SENDER")),
            ),
            timeout_seconds=timeout,
        )
