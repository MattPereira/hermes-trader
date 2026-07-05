#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "telethon>=1.40,<2",
# ]
# ///
"""Deterministically ingest one local day of Telegram channel posts into Markdown."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import sys
import tempfile
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROFILE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROFILE_DIR / "config.toml"
DEFAULT_LOCK = PROFILE_DIR / "state/telegram-ingest.lock"
MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)


@dataclass(frozen=True)
class Channel:
    username: str
    name: str


@dataclass(frozen=True)
class Post:
    message_id: int
    published_at: str
    markdown: str
    media_type: str | None = None
    media_name: str | None = None
    media_path: str | None = None


@dataclass(frozen=True)
class Settings:
    channels: list[Channel]
    output_dir: Path
    timezone: ZoneInfo
    session_file: Path
    download_media: bool


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_username(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"https?://t\.me/([^/?#]+)/*", value, re.IGNORECASE)
    if match:
        value = match.group(1)
    value = value.lstrip("@").lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{3,31}", value):
        raise ValueError(f"Invalid Telegram channel username: {value!r}")
    return value


def slugify(value: str, limit: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:limit].rstrip("-") or "telegram-channel"


def resolve_path(config_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else config_path.parent / path


def load_settings(path: Path) -> Settings:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    inbox = data.get("inbox", {})
    telegram = data.get("telegram", {})
    if not isinstance(inbox, dict):
        raise ValueError("ingestion config section 'inbox' must be a table")
    if not isinstance(telegram, dict):
        raise ValueError("ingestion config section 'telegram' must be a table")
    try:
        timezone = ZoneInfo(str(inbox.get("timezone", "America/Los_Angeles")))
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown Telegram ingestion timezone: {error.args[0]}") from error
    channels: list[Channel] = []
    for item in telegram.get("channels", []):
        if item.get("enabled", True):
            username = normalize_username(str(item.get("username", "")))
            channels.append(Channel(username, str(item.get("name", username)).strip() or username))
    return Settings(
        channels=channels,
        output_dir=resolve_path(path, str(inbox.get("output_dir", "vault/content/inbox"))),
        timezone=timezone,
        session_file=resolve_path(path, str(telegram.get("session_file", "sessions/telegram-ingest"))),
        download_media=bool(telegram.get("download_media", True)),
    )


def target_date(value: str | None, timezone: ZoneInfo, now: dt.datetime | None = None) -> dt.date:
    if value:
        return dt.date.fromisoformat(value)
    current = now or utc_now()
    return current.astimezone(timezone).date() - dt.timedelta(days=1)


def day_bounds(day: dt.date, timezone: ZoneInfo) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(day, dt.time.min, timezone)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, timezone)
    return start.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)


def bundle_dir(output_dir: Path, day: dt.date, channel: Channel) -> Path:
    return output_dir / f"{day:%Y}" / MONTH_NAMES[day.month - 1] / f"{day:%d}"


def note_path(output_dir: Path, day: dt.date, channel: Channel) -> Path:
    return bundle_dir(output_dir, day, channel) / f"telegram-{slugify(channel.username)}.md"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def message_url(channel: Channel, message_id: int) -> str:
    return f"https://t.me/{channel.username}/{message_id}"


def render_note(channel: Channel, day: dt.date, timezone: ZoneInfo, posts: list[Post], fetched_at: str) -> str:
    ordered = sorted(posts, key=lambda post: (post.published_at, post.message_id))
    first = ordered[0].published_at
    last = ordered[-1].published_at
    title = f"{day.isoformat()} — {channel.name}"
    parts = [
        "---",
        f"title: {yaml_string(title)}",
        'source_type: "telegram"',
        f"source_name: {yaml_string(channel.username)}",
        f"channel_username: {yaml_string(channel.username)}",
        f"channel_name: {yaml_string(channel.name)}",
        f"source_url: {yaml_string(f'https://t.me/{channel.username}')}",
        f"date: {yaml_string(day.isoformat())}",
        f"timezone: {yaml_string(str(timezone))}",
        f"message_count: {len(ordered)}",
        f"first_message_at: {yaml_string(first)}",
        f"last_message_at: {yaml_string(last)}",
        f"fetched_at: {yaml_string(fetched_at)}",
        "---",
        "",
        f"# {title}",
    ]
    for post in ordered:
        local = dt.datetime.fromisoformat(post.published_at.replace("Z", "+00:00")).astimezone(timezone)
        url = message_url(channel, post.message_id)
        parts.extend(["", f"## [{local:%H:%M}]({url})", ""])
        if post.markdown.strip():
            parts.append(post.markdown.strip())
        if post.media_type:
            label = f"{post.media_type}: {post.media_name}" if post.media_name else post.media_type
            if post.markdown.strip():
                parts.append("")
            if post.media_path and post.media_type in {"photo", "image"}:
                parts.append(f"![{label}]({post.media_path})")
            elif post.media_path:
                parts.append(f"[Media: {label}]({post.media_path})")
            else:
                parts.append(f"*Media: {label}*")
    return "\n".join(parts).rstrip() + "\n"


def media_metadata(message: Any) -> tuple[str | None, str | None]:
    if getattr(message, "photo", None) is not None:
        return "photo", None
    document = getattr(message, "document", None)
    if document is not None:
        name = None
        for attribute in getattr(document, "attributes", []):
            candidate = getattr(attribute, "file_name", None)
            if candidate:
                name = str(candidate)
                break
        mime_type = str(getattr(document, "mime_type", "") or "")
        return (mime_type.split("/", 1)[0] or "document"), name
    media = getattr(message, "media", None)
    if media is not None:
        name = type(media).__name__.removeprefix("MessageMedia").lower()
        return name or "media", None
    return None, None


def safe_media_name(value: str) -> str:
    name = Path(value).name
    stem = slugify(Path(name).stem, limit=80)
    suffix = re.sub(r"[^a-zA-Z0-9.]", "", Path(name).suffix.lower())[:12]
    return f"{stem}{suffix}"


async def download_message_media(
    client: Any,
    message: Any,
    channel: Channel,
    day: dt.date,
    output_dir: Path,
    media_type: str,
    media_name: str | None,
) -> str:
    from telethon import utils

    if media_name:
        filename = f"telegram-{slugify(channel.username)}-{message.id}-{safe_media_name(media_name)}"
    else:
        extension = ".jpg" if media_type == "photo" else utils.get_extension(message.media) or ".bin"
        filename = f"telegram-{slugify(channel.username)}-{message.id}{extension}"
    destination = bundle_dir(output_dir, day, channel) / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.part")
    try:
        downloaded = await client.download_media(message, file=str(temporary))
        if not downloaded:
            raise RuntimeError(f"Telegram returned no media for message {message.id}")
        os.replace(downloaded, destination)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        raise
    return filename


async def fetch_posts(
    client: Any,
    channel: Channel,
    day: dt.date,
    start: dt.datetime,
    end: dt.datetime,
    output_dir: Path,
    download_media: bool,
) -> list[Post]:
    from telethon.extensions import markdown

    entity = await client.get_entity(channel.username)
    posts: list[Post] = []
    async for message in client.iter_messages(entity, offset_date=end):
        published = message.date.astimezone(dt.timezone.utc)
        if published < start:
            break
        if published >= end:
            continue
        body = markdown.unparse(message.message or "", message.entities or [])
        media_type, media_name = media_metadata(message)
        if not body.strip() and not media_type:
            continue
        media_path = None
        if media_type and download_media:
            media_path = await download_message_media(
                client, message, channel, day, output_dir, media_type, media_name
            )
        posts.append(Post(message.id, iso_utc(published), body, media_type, media_name, media_path))
    return sorted(posts, key=lambda post: (post.published_at, post.message_id))


def credentials() -> tuple[int, str]:
    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    if not api_id or not api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in the profile .env")
    try:
        return int(api_id), api_hash
    except ValueError as error:
        raise RuntimeError("TELEGRAM_API_ID must be an integer") from error


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


@contextlib.contextmanager
def ingestion_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


async def run(args: argparse.Namespace) -> dict[str, int]:
    from telethon import TelegramClient

    settings = load_settings(args.config)
    api_id, api_hash = credentials()
    settings.session_file.parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(str(settings.session_file), api_id, api_hash)
    if args.login:
        await client.start()
        me = await client.get_me()
        await client.disconnect()
        print(f"Telegram session authorized for user {me.id}")
        return {"created": 0, "empty": 0}

    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized; run telegram-ingest.sh --login interactively")
        day = target_date(args.date, settings.timezone)
        start, end = day_bounds(day, settings.timezone)
        output_dir = args.output_dir or settings.output_dir
        counts = {"created": 0, "empty": 0, "media": 0}
        for channel in settings.channels:
            posts = await fetch_posts(
                client,
                channel,
                day,
                start,
                end,
                output_dir,
                settings.download_media and not args.dry_run,
            )
            if not posts:
                counts["empty"] += 1
                continue
            counts["media"] += sum(post.media_type is not None for post in posts)
            note = render_note(channel, day, settings.timezone, posts, iso_utc(utc_now()))
            if not args.dry_run:
                atomic_write(note_path(output_dir, day, channel), note)
            counts["created"] += 1
        return counts
    finally:
        await client.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="TOML ingestion configuration")
    parser.add_argument("--output-dir", type=Path, help="Override telegram.output_dir from the config")
    parser.add_argument("--date", help="Local calendar date to ingest (YYYY-MM-DD); defaults to yesterday")
    parser.add_argument("--login", action="store_true", help="Interactively create or refresh the Telegram session")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing notes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with ingestion_lock(DEFAULT_LOCK):
            counts = asyncio.run(run(args))
    except Exception as error:
        print(f"Telegram ingestion failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    if not args.login and (args.dry_run or counts["created"]):
        prefix = "Dry run: " if args.dry_run else ""
        print(prefix + ", ".join(f"{name}={value}" for name, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
