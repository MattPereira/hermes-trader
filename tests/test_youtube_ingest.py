import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts/youtube_ingest.py"
SPEC = importlib.util.spec_from_file_location("youtube_ingest", SCRIPT)
assert SPEC and SPEC.loader
ingest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ingest
SPEC.loader.exec_module(ingest)


class YouTubeIngestTests(unittest.TestCase):
    def video(self, video_id="abcdefghijk", title="An Example: Video!"):
        return ingest.Video(
            video_id=video_id,
            title=title,
            channel_id="UC123456789",
            channel_name="Example Channel",
            url=f"https://www.youtube.com/watch?v={video_id}",
            published_at="2026-07-03T15:04:00Z",
        )

    def test_filename_uses_utc_publication_time_and_slug(self):
        self.assertEqual(
            ingest.filename_for(self.video()),
            "2026-07-03-1504-an-example-video.md",
        )

    def test_render_note_has_metadata_and_timestamped_transcript(self):
        note = ingest.render_note(
            self.video(),
            [{"text": "Hello", "start": 65.2, "duration": 1.0}],
            "en",
            "2026-07-03T16:00:00Z",
        )
        self.assertIn('video_id: "abcdefghijk"', note)
        self.assertIn('published_at: "2026-07-03T15:04:00Z"', note)
        self.assertIn("1:05 Hello", note)

    def test_existing_note_prevents_duplicate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            output.mkdir()
            (output / "existing.md").write_text('---\nvideo_id: "abcdefghijk"\n---\n')
            state = {"version": 1, "channels": {}, "videos": {}}
            with patch.object(ingest, "fetch_transcript") as fetch:
                counts = ingest.collect([self.video()], state, output, root / "state.json", False)
            fetch.assert_not_called()
            self.assertEqual(counts["seen"], 1)
            self.assertEqual(state["videos"]["abcdefghijk"]["status"], "ingested")

    def test_missing_transcript_is_pending_and_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {"version": 1, "channels": {}, "videos": {}}
            with patch.object(ingest, "fetch_transcript", side_effect=RuntimeError("captions disabled")):
                first = ingest.collect([self.video()], state, root / "out", root / "state.json", False)
                second = ingest.collect([self.video()], state, root / "out", root / "state.json", False)
            self.assertEqual(first["pending"], 1)
            self.assertEqual(second["pending"], 1)
            self.assertEqual(state["videos"]["abcdefghijk"]["attempts"], 2)

    def test_first_channel_run_selects_ten_and_skips_older_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "channels.toml"
            config.write_text('[youtube]\n[[youtube.channels]]\nid="UC123456789"\nname="Example"\n')
            feed = [
                self.video(f"video{i:06d}", f"Video {i}")
                for i in range(12)
            ]
            state = {"version": 1, "channels": {}, "videos": {}}
            with patch.object(ingest, "fetch_channel_feed", return_value=feed):
                selected = ingest.channel_candidates(config, state, False)
            self.assertEqual(len(selected), 10)
            self.assertTrue(state["channels"]["UC123456789"]["initialized"])
            self.assertEqual(state["channels"]["UC123456789"]["initial_backfill_limit"], 10)
            self.assertEqual(state["videos"]["video000010"]["status"], "skipped")
            self.assertEqual(state["videos"]["video000011"]["status"], "skipped")

    def test_backfill_limit_upgrade_reactivates_previously_skipped_videos(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "channels.toml"
            config.write_text('[youtube]\n[[youtube.channels]]\nid="UC123456789"\nname="Example"\n')
            feed = [self.video(f"video{i:06d}", f"Video {i}") for i in range(12)]
            state = {
                "version": 1,
                "channels": {"UC123456789": {"initialized": True}},
                "videos": {
                    video.video_id: ingest.video_record(video, "skipped", reason="initial_backfill_limit")
                    for video in feed[3:]
                },
            }
            for video in feed[:3]:
                state["videos"][video.video_id] = ingest.video_record(video, "ingested")
            with patch.object(ingest, "fetch_channel_feed", return_value=feed):
                selected = ingest.channel_candidates(config, state, False)
            self.assertEqual(len(selected), 12)
            for video in feed[3:10]:
                self.assertNotIn(video.video_id, state["videos"])
            self.assertEqual(state["videos"]["video000010"]["status"], "skipped")

    def test_channel_loader_ignores_other_ingestion_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "ingestion.toml"
            config.write_text(
                '[youtube]\n'
                '[[youtube.channels]]\nid="UC123456789"\nname="Example"\n'
                '[twitter]\n'
                '[[twitter.accounts]]\nhandle="example"\n'
                '[telegram]\n'
                '[[telegram.channels]]\nusername="example"\n'
            )
            self.assertEqual(
                ingest.load_channels(config),
                [{"id": "UC123456789", "name": "Example"}],
            )
            self.assertEqual(
                ingest.configured_output_dir(config),
                config.parent / "vault/content/inbox/youtube",
            )

    def test_success_writes_note_and_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {"version": 1, "channels": {}, "videos": {}}
            transcript = ([{"text": "Hello", "start": 0, "duration": 1}], "en")
            with patch.object(ingest, "fetch_transcript", return_value=transcript):
                counts = ingest.collect([self.video()], state, root / "out", root / "state.json", False)
            self.assertEqual(counts["created"], 1)
            notes = list((root / "out").glob("*.md"))
            self.assertEqual(len(notes), 1)
            persisted = json.loads((root / "state.json").read_text())
            self.assertEqual(persisted["videos"]["abcdefghijk"]["status"], "ingested")


if __name__ == "__main__":
    unittest.main()
