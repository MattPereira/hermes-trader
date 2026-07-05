import datetime as dt
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).parents[1] / "scripts/telegram_ingest.py"
SPEC = importlib.util.spec_from_file_location("telegram_ingest", SCRIPT)
assert SPEC and SPEC.loader
ingest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ingest
SPEC.loader.exec_module(ingest)


class TelegramIngestTests(unittest.TestCase):
    channel = ingest.Channel("cryptonarratives1", "Crypto Narratives")
    timezone = ZoneInfo("America/Los_Angeles")

    def post(self, message_id=42, published_at="2026-07-04T08:30:00Z", markdown="Hello [site](https://example.com)"):
        return ingest.Post(
            message_id,
            published_at,
            markdown,
            "photo",
            None,
            f"telegram-cryptonarratives1-{message_id}.jpg",
        )

    def test_normalize_username_accepts_url_and_at_name(self):
        self.assertEqual(ingest.normalize_username("https://t.me/CryptoNarratives1"), "cryptonarratives1")
        self.assertEqual(ingest.normalize_username("@CryptoNarratives1"), "cryptonarratives1")

    def test_default_target_is_previous_local_day(self):
        now = dt.datetime(2026, 7, 5, 6, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(ingest.target_date(None, self.timezone, now), dt.date(2026, 7, 3))

    def test_day_bounds_handle_dst(self):
        start, end = ingest.day_bounds(dt.date(2026, 3, 8), self.timezone)
        self.assertEqual(end - start, dt.timedelta(hours=23))
        start, end = ingest.day_bounds(dt.date(2026, 11, 1), self.timezone)
        self.assertEqual(end - start, dt.timedelta(hours=25))

    def test_load_settings_resolves_profile_relative_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.toml"
            config.write_text(
                '[inbox]\noutput_dir="out"\ntimezone="America/Los_Angeles"\n'
                '[telegram]\nsession_file="sessions/tg"\n'
                '[[telegram.channels]]\nusername="https://t.me/cryptonarratives1"\nname="Crypto Narratives"\n'
            )
            settings = ingest.load_settings(config)
        self.assertEqual(settings.output_dir, config.parent / "out")
        self.assertEqual(settings.session_file, config.parent / "sessions/tg")
        self.assertTrue(settings.download_media)
        self.assertEqual(settings.channels, [self.channel])

    def test_note_path_uses_year_month_day_and_source_filename(self):
        self.assertEqual(
            ingest.note_path(Path("telegram"), dt.date(2026, 7, 4), self.channel),
            Path("telegram/2026/july/04/telegram-cryptonarratives1.md"),
        )

    def test_render_note_orders_posts_and_includes_metadata(self):
        posts = [self.post(43, "2026-07-04T09:30:00Z", "Second"), self.post()]
        note = ingest.render_note(self.channel, dt.date(2026, 7, 4), self.timezone, posts, "2026-07-05T12:00:00Z")
        self.assertIn('title: "2026-07-04 — Crypto Narratives"', note)
        self.assertIn("message_count: 2", note)
        self.assertIn("## [01:30](https://t.me/cryptonarratives1/42)", note)
        self.assertLess(note.index("Hello"), note.index("Second"))
        self.assertIn("![photo](telegram-cryptonarratives1-42.jpg)", note)

    def test_media_metadata_preserves_document_name(self):
        document = SimpleNamespace(mime_type="video/mp4", attributes=[SimpleNamespace(file_name="clip.mp4")])
        message = SimpleNamespace(photo=None, document=document, media=document)
        self.assertEqual(ingest.media_metadata(message), ("video", "clip.mp4"))

    def test_safe_media_name_removes_paths_and_unsafe_characters(self):
        self.assertEqual(ingest.safe_media_name("../../Quarterly Report (final).PDF"), "quarterly-report-final.pdf")

    def test_non_image_media_renders_as_link(self):
        post = ingest.Post(
            44,
            "2026-07-04T10:30:00Z",
            "",
            "video",
            "clip.mp4",
            "telegram-cryptonarratives1-44-clip.mp4",
        )
        note = ingest.render_note(self.channel, dt.date(2026, 7, 4), self.timezone, [post], "2026-07-05T12:00:00Z")
        self.assertIn("[Media: video: clip.mp4](telegram-cryptonarratives1-44-clip.mp4)", note)


if __name__ == "__main__":
    unittest.main()
