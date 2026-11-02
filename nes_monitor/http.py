from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

USER_AGENT = "nes-45-monitor/1.0 (personal watch of public WTS listings)"


class FetchError(RuntimeError):
    pass


def fetch(url: str, *, timeout: float = 30, attempts: int = 3) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {403, 404, 429} or 500 <= exc.code < 600:
                log.warning("HTTP %s for %s (attempt %s)", exc.code, url, attempt)
            else:
                raise FetchError(f"HTTP {exc.code} for {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            log.warning("Fetch failed for %s (attempt %s): %s", url, attempt, exc)
        if attempt < attempts:
            time.sleep(2 * attempt)
    raise FetchError(f"Could not fetch {url}: {last_error}")
