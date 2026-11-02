from __future__ import annotations

import json
import logging
import smtplib
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage

from nes_monitor.config import Config
from nes_monitor.store import Seen

log = logging.getLogger(__name__)


def format_alert(item: Seen) -> str:
    heading = f"{item.prefix}: {item.title}".strip()
    if heading.startswith(": "):
        heading = heading[2:]
    lines = [heading]
    if item.author:
        lines.append(f"Seller: {item.author}")
    posted = _format_posted(item.posted_at)
    if posted:
        lines.append(f"Posted: {posted}")
    if item.reason:
        lines.append(f"Matched: {item.reason}")
    if item.snippet:
        lines.extend(["", item.snippet])
    lines.extend(["", item.url])
    return "\n".join(lines)


def send(config: Config, item: Seen) -> bool:
    message = format_alert(item)
    subject = f"NES .45: {item.title}"
    ok = True
    if config.ntfy_url:
        ok = _ntfy(config.ntfy_url, subject, message, item.url) and ok
    if config.webhook_url:
        ok = _webhook(config.webhook_url, config.webhook_format, subject, message) and ok
    if config.smtp_host and config.smtp_to:
        ok = _smtp(config, subject, message) and ok
    if not config.notifies:
        log.info("No notifier configured. Alert:\n%s", message)
        return True
    return ok


def _ntfy(url: str, title: str, message: str, link: str) -> bool:
    endpoint = url if url.startswith("http") else f"https://ntfy.sh/{url}"
    request = urllib.request.Request(
        endpoint,
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Click": link,
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    return _post(request, "ntfy")


def _webhook(url: str, fmt: str, title: str, message: str) -> bool:
    if fmt == "discord":
        payload = {"content": f"**{title}**\n{message}"[:1900]}
    elif fmt == "slack":
        payload = {"text": f"*{title}*\n{message}"}
    else:
        payload = {"title": title, "text": message, "content": message}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "nes-45-monitor/1.0"},
        method="POST",
    )
    return _post(request, "webhook")


def _smtp(config: Config, subject: str, message: str) -> bool:
    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = config.smtp_from or config.smtp_user
    email["To"] = config.smtp_to
    email.set_content(message)
    try:
        if config.smtp_port == 465:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30)
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30)
            smtp.starttls()
        with smtp:
            if config.smtp_user:
                smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(email)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        log.error("Email failed: %s", exc)
        return False


def _post(request: urllib.request.Request, name: str) -> bool:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            if 200 <= response.status < 300:
                return True
            log.error("%s returned HTTP %s", name, response.status)
            return False
    except urllib.error.HTTPError as exc:
        log.error("%s returned HTTP %s", name, exc.code)
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.error("%s failed: %s", name, exc)
        return False


def _format_posted(value: str) -> str:
    if not value:
        return ""
    text = value.strip()
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
        text = text[:-2] + ":" + text[-2:]
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return value
    hour = parsed.strftime("%I").lstrip("0") or "12"
    return parsed.strftime(f"%b %d, %Y, {hour}:%M %p")
