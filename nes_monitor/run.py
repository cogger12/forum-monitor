from __future__ import annotations

import argparse
import logging
import re
import sys
import time

from nes_monitor.config import load_config
from nes_monitor.http import FetchError, fetch
from nes_monitor.match import evaluate, should_fetch_body, skip_prefix, snippet
from nes_monitor.notify import format_alert, send
from nes_monitor.parse import (
    activity_url,
    first_post_text,
    is_newer,
    page_url,
    parse_listings,
    parse_rss_bodies,
    rss_url,
)
from nes_monitor.store import Seen, Store

log = logging.getLogger("nes-45-monitor")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch NES handgun classifieds for new .45 pistols.")
    parser.add_argument("--config", default="config.ini", help="Path to config.ini")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print matches and do not save or notify")
    parser.add_argument(
        "--notify-existing",
        action="store_true",
        help="On an empty database, alert for .45 listings already on the first page",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Send one fake alert and exit, to check ntfy, webhook, or email",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = load_config(args.config)
    if args.test_notify:
        item = Seen(
            thread_id=0,
            title="Test alert",
            url=config.forum_url,
            prefix="WTS",
            author="nes-45-monitor",
            posted_at="",
            snippet="Notifications are working. This is not a listing.",
            reason="test",
            matched=True,
            notified=False,
        )
        log.info("Sending a test alert")
        return 0 if send(config, item) else 1
    if args.dry_run:
        return _dry_run(config.forum_url)

    store = Store(config.state_db)
    try:
        while True:
            try:
                _poll(config, store, notify_existing=args.notify_existing)
            except FetchError as exc:
                log.error("%s", exc)
                if args.once:
                    return 1
            if args.once:
                return 0
            log.info("Sleeping %s seconds", config.poll_seconds)
            time.sleep(config.poll_seconds)
    except KeyboardInterrupt:
        log.info("Stopped")
        return 0
    finally:
        store.close()


def _dry_run(forum_url: str) -> int:
    listings, bodies = _load(forum_url, pages=1)
    log.info("Read %s newest listings", len(listings))
    matches = 0
    for listing in listings:
        if skip_prefix(listing.prefix, listing.title):
            continue
        body, failed = _body(listing, bodies)
        if failed:
            log.warning("Could not read %s; leaving it unseen", listing.url)
            continue
        matched, reason = evaluate(listing.title, body)
        if not matched:
            continue
        matches += 1
        item = _seen(listing, body, reason, matched=True, notified=False)
        print(format_alert(item))
        print("---")
    log.info("%s current .45 listings on the first page (sold/wtb skipped)", matches)
    bumps = 0
    try:
        active = parse_listings(fetch(activity_url(forum_url, 1)), forum_url)
    except FetchError as exc:
        log.warning("Activity page unavailable: %s", exc)
        active = []
    for listing in active:
        if skip_prefix(listing.prefix, listing.title) or not is_newer(listing.bumped_at, listing.posted_at):
            continue
        body, failed = _body(listing, bodies)
        if failed:
            continue
        matched, reason = evaluate(listing.title, body)
        if not matched:
            continue
        bumps += 1
        print(format_alert(_seen(listing, body, reason, matched=True, notified=False)))
        print("---")
    log.info("%s bumped .45 listings on the recent-activity page", bumps)
    return 0


def _poll(config, store: Store, *, notify_existing: bool) -> None:
    for pending in store.pending():
        if send(config, pending):
            store.mark_notified(pending.thread_id)
            log.info("Retried alert for %s", pending.thread_id)

    listings, bodies = _load(config.forum_url, pages=config.max_pages, store=store)
    if not listings:
        raise FetchError("Forum page parsed zero threads. The page layout may have changed.")

    known = store.known_ids()
    seeding = not known and not notify_existing
    fresh = [listing for listing in listings if listing.thread_id not in known]
    log.info("Page scan: %s threads, %s unseen%s", len(listings), len(fresh), " (seeding)" if seeding else "")

    matched_now = 0
    for listing in fresh:
        if skip_prefix(listing.prefix, listing.title):
            store.save(_seen(listing, "", "", matched=False, notified=True))
            continue
        body, failed = _body(listing, bodies)
        if failed:
            log.warning("Could not read %s; will try again next check", listing.url)
            continue
        matched, reason = evaluate(listing.title, body)
        if not matched:
            store.save(_seen(listing, body, "", matched=False, notified=True))
            continue
        item = _seen(listing, body, reason, matched=True, notified=False)
        matched_now += 1
        if seeding:
            item = Seen(**{**item.__dict__, "notified": True})
            store.save(item)
            log.info("Already listed, not alerting: %s", listing.title)
            continue
        delivered = send(config, item)
        store.save(Seen(**{**item.__dict__, "notified": delivered}))
        if delivered:
            log.info("Alerted: %s", listing.title)
        else:
            log.error("Alert failed and will be retried: %s", listing.title)

    _note_activity(config, store, bodies, seeding=seeding)

    if seeding:
        log.info(
            "Seeded %s threads, including %s .45 listings already up. Newer listings and later bumps will alert.",
            len(fresh),
            matched_now,
        )


def _load(forum_url: str, pages: int, store: Store | None = None):
    bodies: dict[int, str] = {}
    try:
        bodies = parse_rss_bodies(fetch(rss_url(forum_url)))
    except FetchError as exc:
        log.warning("RSS unavailable, thread previews will be used instead: %s", exc)

    listings = []
    seen_ids: set[int] = set()
    known = store.known_ids() if store is not None else set()
    for page in range(1, pages + 1):
        html = fetch(page_url(forum_url, page))
        found = parse_listings(html, forum_url)
        if not found:
            break
        for listing in found:
            if listing.thread_id not in seen_ids:
                listings.append(listing)
                seen_ids.add(listing.thread_id)
        # The first run only needs the newest page. Later, read another page
        # when every thread on this one started after anything we have stored.
        if store is None or not known or found[-1].thread_id in known:
            break
        if page < pages:
            time.sleep(1)
    return listings, bodies


def activity_action(stored: Seen | None, bumped_at: str, *, seeding: bool) -> str:
    """What to do with one thread on the recent-activity page."""
    if stored is None:
        return "remember" if seeding else "alert"
    if not stored.last_activity:
        return "remember"
    if not is_newer(bumped_at, stored.last_activity):
        return "skip"
    return "alert"


def _note_activity(config, store: Store, bodies: dict[int, str], *, seeding: bool) -> None:
    try:
        active = parse_listings(fetch(activity_url(config.forum_url, 1)), config.forum_url)
    except FetchError as exc:
        log.warning("Activity page unavailable, bumps will wait for the next check: %s", exc)
        return
    bumped = 0
    for listing in active:
        stored = store.get(listing.thread_id)
        action = "remember" if skip_prefix(listing.prefix, listing.title) else activity_action(
            stored, listing.bumped_at, seeding=seeding
        )
        if action == "skip":
            continue
        if action == "remember":
            store.save(_remember(listing, stored, matched=False if skip_prefix(listing.prefix, listing.title) else None))
            continue
        body, failed = _body(listing, bodies)
        if failed:
            log.warning("Could not read %s; will try again next check", listing.url)
            continue
        matched, reason = evaluate(listing.title, body)
        if not matched:
            store.save(_remember(listing, stored, matched=False))
            continue
        item = _seen(listing, body, reason, matched=True, notified=False)
        delivered = send(config, item)
        store.save(Seen(**{**item.__dict__, "notified": delivered}))
        bumped += 1
        if delivered:
            log.info("Alerted activity: %s", listing.title)
        else:
            log.error("Activity alert failed and will be retried: %s", listing.title)
    if bumped:
        log.info("Sent %s bump alerts", bumped)


def _remember(listing, stored: Seen | None, matched: bool | None = None) -> Seen:
    if matched is None:
        matched = stored.matched if stored else False
    return Seen(
        thread_id=listing.thread_id,
        title=listing.title,
        url=listing.url,
        prefix=listing.prefix,
        author=listing.author or (stored.author if stored else ""),
        posted_at=(stored.posted_at if stored and stored.posted_at else listing.posted_at),
        snippet=stored.snippet if stored and matched else "",
        reason=stored.reason if stored and matched else "",
        matched=matched,
        notified=True if stored is None or stored.notified else False,
        last_activity=listing.bumped_at,
    )


def _body(listing, bodies: dict[int, str]) -> tuple[str, bool]:
    """Return the post text, and whether a needed fetch failed."""
    cached = bodies.get(listing.thread_id, "")
    matched, _reason = evaluate(listing.title, cached)
    truncated = bool(re.search(r"read more\s*$", cached.strip(), re.I))
    if matched or not should_fetch_body(listing.title) or (cached and not truncated):
        return cached, False
    log.info("Reading first post of %s", listing.thread_id)
    time.sleep(1.5)
    try:
        text = first_post_text(fetch(listing.preview_url))
    except FetchError as exc:
        log.warning("Preview failed for %s: %s", listing.url, exc)
        return "", True
    if not text:
        log.warning("No post text found for %s", listing.url)
    return text, False


def _seen(listing, body: str, reason: str, *, matched: bool, notified: bool) -> Seen:
    return Seen(
        thread_id=listing.thread_id,
        title=listing.title,
        url=listing.url,
        prefix=listing.prefix,
        author=listing.author,
        posted_at=listing.posted_at,
        snippet=snippet(body, listing.title) if matched else "",
        reason=reason,
        matched=matched,
        notified=notified,
        last_activity=listing.bumped_at,
    )


if __name__ == "__main__":
    sys.exit(main())
