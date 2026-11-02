from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


MIN_POLL_SECONDS = 300


@dataclass(frozen=True)
class Config:
    forum_url: str
    poll_seconds: int
    max_pages: int
    state_db: Path
    ntfy_url: str
    webhook_url: str
    webhook_format: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_to: str

    @property
    def notifies(self) -> bool:
        return bool(self.ntfy_url or self.webhook_url or (self.smtp_host and self.smtp_to))


def _env(name: str, fallback: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return fallback.strip()
    return value.strip()


def load_config(path: str | Path) -> Config:
    parser = configparser.ConfigParser()
    read = parser.read(path)
    if not read:
        raise SystemExit(f"Config file not found: {path}")

    forum = parser["forum"]
    notify = parser["notify"] if parser.has_section("notify") else {}

    poll = int(forum.get("poll_seconds", "900"))
    poll = max(MIN_POLL_SECONDS, min(poll, 24 * 60 * 60))
    pages = max(1, min(int(forum.get("max_pages", "2")), 5))

    webhook_format = _env("NES_WEBHOOK_FORMAT", notify.get("webhook_format", "json")).lower()
    if webhook_format not in {"json", "discord", "slack"}:
        raise SystemExit("webhook_format must be json, discord, or slack")

    return Config(
        forum_url=forum.get("url", "https://www.northeastshooters.com/xen/forums/wts-wtt-handguns.213/").strip(),
        poll_seconds=poll,
        max_pages=pages,
        state_db=Path(forum.get("state_db", "data/state.sqlite")).expanduser(),
        ntfy_url=_env("NES_NTFY_URL", notify.get("ntfy_url", "")),
        webhook_url=_env("NES_WEBHOOK_URL", notify.get("webhook_url", "")),
        webhook_format=webhook_format,
        smtp_host=_env("NES_SMTP_HOST", notify.get("smtp_host", "")),
        smtp_port=int(_env("NES_SMTP_PORT", notify.get("smtp_port", "587") or "587")),
        smtp_user=_env("NES_SMTP_USER", notify.get("smtp_user", "")),
        smtp_password=_env("NES_SMTP_PASSWORD", notify.get("smtp_password", "")),
        smtp_from=_env("NES_SMTP_FROM", notify.get("smtp_from", "")),
        smtp_to=_env("NES_SMTP_TO", notify.get("smtp_to", "")),
    )
