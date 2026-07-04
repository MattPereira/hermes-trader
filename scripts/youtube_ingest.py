#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "youtube-transcript-api>=1,<2",
#   "yt-dlp>=2025.1.1",
# ]
# ///
"""Deterministically ingest YouTube transcripts into Markdown notes."""

from __future__ import annotations

import argparse
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
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator


PROFILE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROFILE_DIR / "config.toml"
DEFAULT_STATE = PROFILE_DIR / "state/youtube-ingest.json"
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")
INITIAL_BACKFILL_LIMIT = 10


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    channel_id: str
    channel_name: str
    url: str
    published_at: str


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_datetime(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def slugify(title: str, limit: int = 100) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    return (slug[:limit].rstrip("-") or "untitled")


def filename_for(video: Video) -> str:
    published = parse_datetime(video.published_at)
    return f"{published:%Y-%m-%d-%H%M}-{slugify(video.title)}.md"


def extract_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    match = VIDEO_ID_RE.search(value)
    if not match:
        raise ValueError(f"Could not extract a YouTube video ID from: {value}")
    return match.group(1)


def load_channels(path: Path) -> list[dict[str, str]]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    youtube = data.get("youtube", {})
    if not isinstance(youtube, dict):
        raise ValueError("ingestion config section 'youtube' must be a table")
    channels: list[dict[str, str]] = []
    for item in youtube.get("channels", []):
        if item.get("enabled", True):
            channel_id = str(item.get("id", "")).strip()
            name = str(item.get("name", channel_id)).strip()
            if not channel_id.startswith("UC"):
                raise ValueError(f"Invalid YouTube channel ID: {channel_id!r}")
            channels.append({"id": channel_id, "name": name})
    return channels


def configured_output_dir(path: Path) -> Path:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    youtube = data.get("youtube", {})
    if not isinstance(youtube, dict):
        raise ValueError("ingestion config section 'youtube' must be a table")
    configured = Path(str(youtube.get("output_dir", "vault/content/inbox/youtube")))
    return configured if configured.is_absolute() else path.parent / configured


def fetch_channel_feed(channel_id: str, channel_name: str) -> list[Video]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "youtube-transcript-collector/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    videos: list[Video] = []
    for entry in root.findall(f"{ATOM}entry"):
        video_id = (entry.findtext(f"{YT}videoId") or "").strip()
        title = (entry.findtext(f"{ATOM}title") or "Untitled").strip()
        published = (entry.findtext(f"{ATOM}published") or "").strip()
        if video_id and published:
            videos.append(
                Video(
                    video_id=video_id,
                    title=title,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=parse_datetime(published).isoformat().replace("+00:00", "Z"),
                )
            )
    return sorted(videos, key=lambda video: parse_datetime(video.published_at), reverse=True)


def fetch_manual_metadata(url_or_id: str) -> Video:
    from yt_dlp import YoutubeDL

    video_id = extract_video_id(url_or_id)
    url = f"https://www.youtube.com/watch?v={video_id}"
    options = {"quiet": True, "no_warnings": True, "skip_download": True}
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    timestamp = info.get("release_timestamp") or info.get("timestamp")
    if timestamp:
        published = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
    elif info.get("upload_date"):
        published = dt.datetime.strptime(info["upload_date"], "%Y%m%d").replace(tzinfo=dt.timezone.utc)
    else:
        raise ValueError("yt-dlp did not return a publication date")
    return Video(
        video_id=video_id,
        title=str(info.get("title") or "Untitled"),
        channel_id=str(info.get("channel_id") or info.get("uploader_id") or ""),
        channel_name=str(info.get("channel") or info.get("uploader") or "Unknown"),
        url=str(info.get("webpage_url") or url),
        published_at=published.isoformat().replace("+00:00", "Z"),
    )


def fetch_transcript(video_id: str) -> tuple[list[dict[str, Any]], str]:
    from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    try:
        transcript = api.fetch(video_id, languages=["en"])
        language = getattr(transcript, "language_code", "en")
    except NoTranscriptFound:
        available = api.list(video_id)
        selected = next(iter(available), None)
        if selected is None:
            raise
        transcript = selected.fetch()
        language = selected.language_code
    segments = [
        {"text": segment.text, "start": float(segment.start), "duration": float(segment.duration)}
        for segment in transcript
    ]
    if not segments:
        raise RuntimeError("Transcript was empty")
    return segments, str(language)


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_note(video: Video, segments: list[dict[str, Any]], language: str, fetched_at: str) -> str:
    transcript = "\n".join(f"{format_timestamp(segment['start'])} {segment['text']}" for segment in segments)
    return (
        "---\n"
        f"title: {yaml_string(video.title)}\n"
        f"video_id: {yaml_string(video.video_id)}\n"
        f"channel_id: {yaml_string(video.channel_id)}\n"
        f"channel_name: {yaml_string(video.channel_name)}\n"
        f"source_url: {yaml_string(video.url)}\n"
        f"published_at: {yaml_string(video.published_at)}\n"
        f"transcript_language: {yaml_string(language)}\n"
        f"fetched_at: {yaml_string(fetched_at)}\n"
        "---\n\n"
        f"# {video.title}\n\n"
        f"{transcript}\n"
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
        return {"version": 1, "channels": {}, "videos": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"Could not read state file {path}: {error}") from error
    data.setdefault("version", 1)
    data.setdefault("channels", {})
    data.setdefault("videos", {})
    return data


def scan_existing_notes(output_dir: Path) -> set[str]:
    found: set[str] = set()
    if not output_dir.exists():
        return found
    pattern = re.compile(r'^video_id:\s*["\']?([A-Za-z0-9_-]{11})["\']?\s*$', re.MULTILINE)
    for note in output_dir.glob("*.md"):
        with contextlib.suppress(OSError, UnicodeDecodeError):
            match = pattern.search(note.read_text(encoding="utf-8")[:5000])
            if match:
                found.add(match.group(1))
    return found


def output_path(output_dir: Path, video: Video) -> Path:
    preferred = output_dir / filename_for(video)
    if not preferred.exists():
        return preferred
    text = preferred.read_text(encoding="utf-8", errors="ignore")[:5000]
    if re.search(rf'^video_id:\s*["\']?{re.escape(video.video_id)}["\']?\s*$', text, re.MULTILINE):
        return preferred
    return preferred.with_name(f"{preferred.stem}-{video.video_id}{preferred.suffix}")


def video_record(video: Video, status: str, **extra: Any) -> dict[str, Any]:
    return {**asdict(video), "status": status, "updated_at": utc_now().isoformat().replace("+00:00", "Z"), **extra}


def classify_error(error: Exception) -> str:
    name = type(error).__name__.lower()
    message = str(error).lower()
    if any(token in name or token in message for token in ("videounavailable", "invalidvideoid", "private video", "deleted video")):
        return "failed"
    return "pending"


@contextlib.contextmanager
def state_lock(state_path: Path) -> Iterator[None]:
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def collect(
    videos: list[Video], state: dict[str, Any], output_dir: Path, state_path: Path, dry_run: bool
) -> dict[str, int]:
    counts = {"created": 0, "seen": 0, "pending": 0, "failed": 0}
    existing = scan_existing_notes(output_dir)
    for video_id in existing:
        prior = state["videos"].get(video_id, {})
        state["videos"][video_id] = {**prior, "status": "ingested"}

    for video in videos:
        prior = state["videos"].get(video.video_id, {})
        if video.video_id in existing or prior.get("status") in {"ingested", "skipped", "failed"}:
            counts["seen"] += 1
            continue
        try:
            segments, language = fetch_transcript(video.video_id)
            note = render_note(video, segments, language, utc_now().isoformat().replace("+00:00", "Z"))
            destination = output_path(output_dir, video)
            if not dry_run:
                atomic_write(destination, note)
                state["videos"][video.video_id] = video_record(video, "ingested", path=str(destination))
                atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            counts["created"] += 1
        except Exception as error:
            status = classify_error(error)
            attempts = int(prior.get("attempts", 0)) + 1
            if not dry_run:
                state["videos"][video.video_id] = video_record(
                    video, status, attempts=attempts, last_error=f"{type(error).__name__}: {error}"
                )
                atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            counts[status] += 1
    return counts


def pending_videos(state: dict[str, Any], channel_ids: set[str] | None = None) -> list[Video]:
    videos: list[Video] = []
    for record in state["videos"].values():
        if record.get("status") != "pending":
            continue
        if channel_ids is not None and record.get("channel_id") not in channel_ids:
            continue
        videos.append(Video(**{key: record[key] for key in Video.__dataclass_fields__}))
    return videos


def channel_candidates(config_path: Path, state: dict[str, Any], dry_run: bool) -> list[Video]:
    channels = load_channels(config_path)
    candidates: dict[str, Video] = {
        video.video_id: video for video in pending_videos(state, {channel["id"] for channel in channels})
    }
    for channel in channels:
        feed = fetch_channel_feed(channel["id"], channel["name"])
        channel_state = state["channels"].get(channel["id"], {})
        initialized = bool(channel_state.get("initialized"))
        previous_limit = int(channel_state.get("initial_backfill_limit", 3 if initialized else 0))
        if initialized and previous_limit < INITIAL_BACKFILL_LIMIT:
            for video in feed[:INITIAL_BACKFILL_LIMIT]:
                record = state["videos"].get(video.video_id, {})
                if record.get("status") == "skipped" and record.get("reason") == "initial_backfill_limit":
                    state["videos"].pop(video.video_id)
        selected = feed if initialized else feed[:INITIAL_BACKFILL_LIMIT]
        for video in selected:
            candidates[video.video_id] = video
        if not initialized and not dry_run:
            for video in feed[INITIAL_BACKFILL_LIMIT:]:
                state["videos"].setdefault(video.video_id, video_record(video, "skipped", reason="initial_backfill_limit"))
        if not dry_run and (not initialized or previous_limit < INITIAL_BACKFILL_LIMIT):
            state["channels"][channel["id"]] = {
                **channel_state,
                "initialized": True,
                "initialized_at": channel_state.get("initialized_at")
                or utc_now().isoformat().replace("+00:00", "Z"),
                "initial_backfill_limit": INITIAL_BACKFILL_LIMIT,
            }
    return sorted(candidates.values(), key=lambda video: parse_datetime(video.published_at))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", help="YouTube URL or video ID to ingest once")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="TOML ingestion configuration")
    parser.add_argument("--output-dir", type=Path, help="Override youtube.output_dir from the config")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing files or state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config
    try:
        with state_lock(args.state_file):
            state = load_state(args.state_file)
            output_dir = args.output_dir or configured_output_dir(config_path)
            if args.video:
                videos = [fetch_manual_metadata(args.video)]
            else:
                videos = channel_candidates(config_path, state, args.dry_run)
                if not args.dry_run:
                    atomic_write(args.state_file, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            counts = collect(videos, state, output_dir, args.state_file, args.dry_run)
    except Exception as error:
        print(f"YouTube ingestion failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    if args.dry_run or counts["created"] or counts["pending"] or counts["failed"]:
        prefix = "Dry run: " if args.dry_run else ""
        print(prefix + ", ".join(f"{name}={value}" for name, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
