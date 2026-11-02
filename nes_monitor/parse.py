from __future__ import annotations

import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass


THREAD_SPLIT = "js-threadListItem-"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


@dataclass(frozen=True)
class Listing:
    thread_id: int
    title: str
    url: str
    preview_url: str
    prefix: str
    author: str
    posted_at: str


def page_url(forum_url: str, page: int) -> str:
    parts = urllib.parse.urlsplit(forum_url)
    path = parts.path.rstrip("/")
    if page > 1:
        path = f"{path}/page-{page}"
    query = urllib.parse.parse_qs(parts.query)
    query["order"] = ["post_date"]
    query["direction"] = ["desc"]
    encoded = urllib.parse.urlencode({key: values[0] for key, values in query.items()})
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path + "/", encoded, ""))


def rss_url(forum_url: str) -> str:
    parts = urllib.parse.urlsplit(forum_url)
    path = parts.path.rstrip("/") + "/index.rss"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def absolute(forum_url: str, href: str) -> str:
    origin = urllib.parse.urlsplit(forum_url)
    base = urllib.parse.urlunsplit((origin.scheme, origin.netloc, "/", "", ""))
    return urllib.parse.urljoin(base, href)


def parse_listings(page_html: str, forum_url: str) -> list[Listing]:
    listings: list[Listing] = []
    for chunk in page_html.split(THREAD_SPLIT)[1:]:
        id_match = re.match(r"(\d+)", chunk)
        if not id_match:
            continue
        title_html = _div(chunk, "structItem-title")
        if not title_html:
            continue
        preview = re.search(r'data-preview-url="([^"]+)"', title_html)
        link = re.search(
            r'<a href="([^"]+/threads/[^"]+)"[^>]*data-preview-url=',
            title_html,
        )
        if not preview or not link:
            continue
        label = re.search(r'class="label [^"]*"[^>]*>\s*([^<]+?)\s*<', title_html)
        title = _anchor_text(title_html)
        author = re.search(r'class="username [^"]*"[^>]*>\s*([^<]+?)\s*<', chunk)
        posted = re.search(r'<time[^>]*datetime="([^"]+)"', chunk)
        href = html.unescape(link.group(1))
        listings.append(
            Listing(
                thread_id=int(id_match.group(1)),
                title=title,
                url=absolute(forum_url, href),
                preview_url=absolute(forum_url, html.unescape(preview.group(1))),
                prefix=_clean(label.group(1)) if label else "",
                author=_clean(author.group(1)) if author else "",
                posted_at=posted.group(1) if posted else "",
            )
        )
    return listings


def parse_rss_bodies(rss_xml: str) -> dict[int, str]:
    try:
        root = ET.fromstring(rss_xml)
    except ET.ParseError:
        return {}
    channel = root.find("channel")
    if channel is None:
        return {}
    bodies: dict[int, str] = {}
    for item in channel.findall("item"):
        thread_id = _thread_id(item.findtext("guid") or "", item.findtext("link") or "")
        if thread_id is None:
            continue
        encoded = item.find(CONTENT_NS)
        raw = encoded.text if encoded is not None and encoded.text else ""
        bodies[thread_id] = html_to_text(raw)
    return bodies


def first_post_text(page_html: str) -> str:
    marker = 'class="bbWrapper"'
    start = page_html.find(marker)
    if start < 0:
        return ""
    open_end = page_html.find(">", start)
    if open_end < 0:
        return ""
    depth = 1
    for match in re.finditer(r"</?div\b[^>]*>", page_html[open_end + 1 :], re.I):
        depth += -1 if match.group(0).lower().startswith("</") else 1
        if depth == 0:
            return html_to_text(page_html[open_end + 1 : open_end + 1 + match.start()])
    return html_to_text(page_html[open_end + 1 : open_end + 8000])


def html_to_text(fragment: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _thread_id(guid: str, link: str) -> int | None:
    match = re.search(r"thread:(\d+)", guid) or re.search(r"\.(\d+)/?$", link)
    if not match:
        return None
    return int(match.group(1))


def _div(chunk: str, class_name: str) -> str:
    match = re.search(rf'class="{class_name}">(.*?)</div>', chunk, re.S)
    return match.group(1) if match else ""


def _anchor_text(title_html: str) -> str:
    match = re.search(r'data-preview-url="[^"]+"[^>]*>\s*(.*?)\s*</a>', title_html, re.S)
    if not match:
        return ""
    return _clean(re.sub(r"<[^>]+>", " ", match.group(1)))


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()
