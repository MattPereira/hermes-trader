#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "beautifulsoup4>=4.12,<5",
#   "markdownify>=1,<2",
# ]
# ///
"""Deterministically ingest public Substack posts into Markdown notes."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import email.utils
import fcntl
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import tomllib
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


PROFILE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROFILE_DIR / "config.toml"
DEFAULT_STATE = PROFILE_DIR / "state/substack-ingest.json"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"
USER_AGENT = "hermes-substack-collector/1.0"
DEFAULT_TIMEZONE = ZoneInfo("America/Los_Angeles")
MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)


@dataclass(frozen=True)
class Publication:
    handle: str
    name: str
    base_url: str


@dataclass(frozen=True)
class Post:
    post_id: str
    title: str
    author: str
    publication_handle: str
    publication_name: str
    url: str
    published_at: str
    html_content: str


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def normalize_handle(value: str) -> str:
    value = value.strip()
    if value.startswith("https://substack.com/@"):
        value = urllib.parse.urlparse(value).path
    value = value.strip("/@").lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError(f"Invalid Substack handle: {value!r}")
    return value


def parse_datetime(value: str) -> dt.datetime:
    value = value.strip()
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = email.utils.parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_datetime(value: str) -> str:
    return parse_datetime(value).isoformat().replace("+00:00", "Z")


def slugify(title: str, limit: int = 100) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    return slug[:limit].rstrip("-") or "untitled"


def filename_for(post: Post) -> str:
    return f"substack-{slugify(post.publication_handle, 60)}-{slugify(post.title)}.md"


def dated_dir(output_dir: Path, published_at: str, timezone: ZoneInfo = DEFAULT_TIMEZONE) -> Path:
    local = parse_datetime(published_at).astimezone(timezone)
    return output_dir / f"{local:%Y}" / MONTH_NAMES[local.month - 1] / f"{local:%d}"


def fetch_url(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/rss+xml"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(), response.geturl()


def load_settings(path: Path) -> tuple[list[str], Path, int]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    inbox = data.get("inbox", {})
    substack = data.get("substack", {})
    if not isinstance(inbox, dict):
        raise ValueError("ingestion config section 'inbox' must be a table")
    if not isinstance(substack, dict):
        raise ValueError("ingestion config section 'substack' must be a table")
    handles: list[str] = []
    for item in substack.get("publications", []):
        if item.get("enabled", True):
            handles.append(normalize_handle(str(item.get("handle", ""))))
    configured = Path(str(inbox.get("output_dir", "vault/content/inbox")))
    output_dir = configured if configured.is_absolute() else path.parent / configured
    limit = int(substack.get("initial_backfill_limit", 5))
    if limit < 1:
        raise ValueError("substack.initial_backfill_limit must be at least 1")
    return handles, output_dir, limit


def _profile_value(text: str, field: str) -> str | None:
    patterns = (
        rf'\\"{field}\\":\\"([^"\\]+)\\"',
        rf'"{field}":"([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return html.unescape(match.group(1))
    return None


def resolve_publication(handle: str) -> Publication:
    payload, _ = fetch_url(f"https://substack.com/@{normalize_handle(handle)}")
    text = payload.decode("utf-8", errors="replace")
    primary = text.find("primaryPublication")
    scoped = text[primary : primary + 5000] if primary >= 0 else text
    subdomain = _profile_value(scoped, "subdomain")
    custom_domain = _profile_value(scoped, "custom_domain")
    name = _profile_value(scoped, "name") or normalize_handle(handle)
    if custom_domain and custom_domain != "null":
        base_url = f"https://{custom_domain.strip('/')}"
    elif subdomain:
        base_url = f"https://{subdomain}.substack.com"
    else:
        raise RuntimeError(f"Could not resolve a primary publication for @{handle}")
    return Publication(normalize_handle(handle), name, base_url)


def stable_post_id(guid: str, url: str) -> str:
    value = guid.strip() or url.strip()
    match = re.search(r"/p/([^/?#]+)", url)
    if match:
        return match.group(1)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def fetch_feed(publication: Publication) -> list[Post]:
    payload, _ = fetch_url(f"{publication.base_url.rstrip('/')}/feed")
    root = ET.fromstring(payload)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError(f"Feed for @{publication.handle} has no RSS channel")
    publication_name = (channel.findtext("title") or publication.name).strip()
    posts: list[Post] = []
    for item in channel.findall("item"):
        url = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "Untitled").strip()
        published = (item.findtext("pubDate") or "").strip()
        if not url or not published:
            continue
        guid = (item.findtext("guid") or "").strip()
        author = (item.findtext(f"{DC}creator") or item.findtext("author") or publication_name).strip()
        content = item.findtext(f"{CONTENT}encoded") or item.findtext("description") or ""
        posts.append(
            Post(
                post_id=stable_post_id(guid, url),
                title=title,
                author=author,
                publication_handle=publication.handle,
                publication_name=publication_name,
                url=url,
                published_at=iso_datetime(published),
                html_content=content.strip(),
            )
        )
    return sorted(posts, key=lambda post: parse_datetime(post.published_at), reverse=True)


def fetch_manual_post(url: str) -> Post:
    from bs4 import BeautifulSoup

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("A public HTTPS Substack post URL is required")
    payload, final_url = fetch_url(url)
    soup = BeautifulSoup(payload, "html.parser")

    def meta(*, property_name: str | None = None, name: str | None = None) -> str:
        node = soup.find("meta", attrs={"property": property_name}) if property_name else soup.find("meta", attrs={"name": name})
        return str(node.get("content", "")).strip() if node else ""

    title = meta(property_name="og:title") or (soup.title.string.strip() if soup.title and soup.title.string else "Untitled")
    published = meta(property_name="article:published_time")
    if not published:
        raise RuntimeError("Post page did not expose a publication date")
    article = soup.find("div", class_=re.compile(r"body markup")) or soup.find("article")
    if article is None:
        raise RuntimeError("Post page did not expose a public article body")
    host = urllib.parse.urlparse(final_url).netloc
    publication_name = meta(property_name="og:site_name") or host
    return Post(
        post_id=stable_post_id("", final_url),
        title=title,
        author=meta(name="author") or publication_name,
        publication_handle=host.split(".")[0],
        publication_name=publication_name,
        url=final_url,
        published_at=iso_datetime(published),
        html_content=str(article),
    )


def html_to_markdown(value: str) -> str:
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(value, "html.parser")
    for node in soup.select("script, style, form, button, .subscription-widget-wrap, .paywall, .captioned-button-wrap"):
        node.decompose()
    body = markdownify(str(soup), heading_style="ATX", bullets="-")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if not body:
        raise RuntimeError("Public post body was empty")
    return body


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_note(post: Post, fetched_at: str) -> str:
    body = html_to_markdown(post.html_content)
    return (
        "---\n"
        f"title: {yaml_string(post.title)}\n"
        "source_type: \"substack\"\n"
        f"source_name: {yaml_string(post.publication_handle)}\n"
        f"date: {yaml_string(parse_datetime(post.published_at).astimezone(DEFAULT_TIMEZONE).date().isoformat())}\n"
        f"post_id: {yaml_string(post.post_id)}\n"
        f"author: {yaml_string(post.author)}\n"
        f"publication_handle: {yaml_string(post.publication_handle)}\n"
        f"publication_name: {yaml_string(post.publication_name)}\n"
        f"source_url: {yaml_string(post.url)}\n"
        f"published_at: {yaml_string(post.published_at)}\n"
        f"fetched_at: {yaml_string(fetched_at)}\n"
        "---\n\n"
        f"# {post.title}\n\n{body}\n"
    )


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "publications": {}, "posts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"Could not read state file {path}: {error}") from error
    data.setdefault("version", 1)
    data.setdefault("publications", {})
    data.setdefault("posts", {})
    return data


def scan_existing_notes(output_dir: Path) -> set[str]:
    found: set[str] = set()
    if not output_dir.exists():
        return found
    pattern = re.compile(r'^post_id:\s*["\']?([^"\'\n]+)["\']?\s*$', re.MULTILINE)
    for note in output_dir.rglob("*.md"):
        with contextlib.suppress(OSError, UnicodeDecodeError):
            match = pattern.search(note.read_text(encoding="utf-8")[:5000])
            if match:
                found.add(match.group(1))
    return found


def output_path(output_dir: Path, post: Post) -> Path:
    preferred = dated_dir(output_dir, post.published_at) / filename_for(post)
    if not preferred.exists():
        return preferred
    text = preferred.read_text(encoding="utf-8", errors="ignore")[:5000]
    if re.search(rf'^post_id:\s*["\']?{re.escape(post.post_id)}["\']?\s*$', text, re.MULTILINE):
        return preferred
    return preferred.with_name(f"{preferred.stem}-{post.post_id[:12]}{preferred.suffix}")


def post_record(post: Post, status: str, **extra: Any) -> dict[str, Any]:
    record = asdict(post)
    record.pop("html_content", None)
    return {**record, "status": status, "updated_at": utc_now().isoformat().replace("+00:00", "Z"), **extra}


@contextlib.contextmanager
def state_lock(state_path: Path) -> Iterator[None]:
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def collect(posts: list[Post], state: dict[str, Any], output_dir: Path, state_path: Path, dry_run: bool) -> dict[str, int]:
    counts = {"created": 0, "seen": 0, "pending": 0}
    existing = scan_existing_notes(output_dir)
    for post_id in existing:
        prior = state["posts"].get(post_id, {})
        state["posts"][post_id] = {**prior, "status": "ingested"}
    for post in posts:
        prior = state["posts"].get(post.post_id, {})
        if post.post_id in existing or prior.get("status") in {"ingested", "skipped"}:
            counts["seen"] += 1
            continue
        try:
            note = render_note(post, utc_now().isoformat().replace("+00:00", "Z"))
            destination = output_path(output_dir, post)
            if not dry_run:
                atomic_write(destination, note)
                state["posts"][post.post_id] = post_record(post, "ingested", path=str(destination))
                atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            counts["created"] += 1
        except Exception as error:
            if not dry_run:
                state["posts"][post.post_id] = post_record(
                    post, "pending", attempts=int(prior.get("attempts", 0)) + 1,
                    last_error=f"{type(error).__name__}: {error}",
                )
                atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            counts["pending"] += 1
    return counts


def publication_candidates(config_path: Path, state: dict[str, Any], dry_run: bool) -> tuple[list[Post], Path]:
    handles, output_dir, initial_limit = load_settings(config_path)
    candidates: dict[str, Post] = {}
    for handle in handles:
        saved = state["publications"].get(handle, {})
        if saved.get("base_url"):
            publication = Publication(handle, saved.get("name", handle), saved["base_url"])
        else:
            publication = resolve_publication(handle)
        feed = fetch_feed(publication)
        initialized = bool(saved.get("initialized"))
        selected = feed if initialized else feed[:initial_limit]
        for post in selected:
            candidates[post.post_id] = post
        if not initialized and not dry_run:
            for post in feed[initial_limit:]:
                state["posts"].setdefault(post.post_id, post_record(post, "skipped", reason="initial_backfill_limit"))
        if not dry_run:
            state["publications"][handle] = {
                **saved,
                **asdict(publication),
                "initialized": True,
                "initialized_at": saved.get("initialized_at") or utc_now().isoformat().replace("+00:00", "Z"),
                "initial_backfill_limit": initial_limit,
            }
    return sorted(candidates.values(), key=lambda post: parse_datetime(post.published_at)), output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post", help="Public Substack post URL to ingest once")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="TOML ingestion configuration")
    parser.add_argument("--output-dir", type=Path, help="Override substack.output_dir from the config")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing files or state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with state_lock(args.state_file):
            state = load_state(args.state_file)
            if args.post:
                posts = [fetch_manual_post(args.post)]
                _, configured_output, _ = load_settings(args.config)
                output_dir = args.output_dir or configured_output
            else:
                posts, configured_output = publication_candidates(args.config, state, args.dry_run)
                output_dir = args.output_dir or configured_output
                if not args.dry_run:
                    atomic_write(args.state_file, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            counts = collect(posts, state, output_dir, args.state_file, args.dry_run)
    except Exception as error:
        print(f"Substack ingestion failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    if args.dry_run or counts["created"] or counts["pending"]:
        prefix = "Dry run: " if args.dry_run else ""
        print(prefix + ", ".join(f"{name}={value}" for name, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
