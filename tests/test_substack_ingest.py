import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts/substack_ingest.py"
SPEC = importlib.util.spec_from_file_location("substack_ingest", SCRIPT)
assert SPEC and SPEC.loader
ingest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ingest
SPEC.loader.exec_module(ingest)


class SubstackIngestTests(unittest.TestCase):
    def post(self, post_id="example-post", title="An Example: Post!"):
        return ingest.Post(
            post_id=post_id,
            title=title,
            author="Example Author",
            publication_handle="example",
            publication_name="Example Publication",
            url=f"https://example.substack.com/p/{post_id}",
            published_at="2026-07-03T15:04:00Z",
            html_content="<p>Hello <strong>world</strong>.</p>",
        )

    def test_normalize_handle_accepts_handle_and_profile_url(self):
        self.assertEqual(ingest.normalize_handle("@CryptoNarratives"), "cryptonarratives")
        self.assertEqual(
            ingest.normalize_handle("https://substack.com/@DegenTradingDaily"),
            "degentradingdaily",
        )

    def test_filename_uses_source_publication_and_title(self):
        self.assertEqual(
            ingest.filename_for(self.post()),
            "substack-example-an-example-post.md",
        )
        self.assertEqual(
            ingest.dated_dir(Path("inbox"), self.post().published_at),
            Path("inbox/2026/july/03"),
        )

    def test_resolve_publication_reads_primary_publication(self):
        payload = (
            r'prefix \"primaryPublication\":{\"id\":1,\"subdomain\":\"example\",'
            r'\"custom_domain\":null,\"name\":\"Example Publication\"} suffix'
        ).encode()
        with patch.object(ingest, "fetch_url", return_value=(payload, "https://substack.com/@example")):
            publication = ingest.resolve_publication("@example")
        self.assertEqual(publication.base_url, "https://example.substack.com")
        self.assertEqual(publication.name, "Example Publication")

    def test_parse_feed_uses_content_encoded_and_stable_slug_id(self):
        rss = b'''<?xml version="1.0"?>
        <rss xmlns:content="http://purl.org/rss/1.0/modules/content/"
             xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
          <title>Example Publication</title><item>
            <title>Example Post</title>
            <link>https://example.substack.com/p/example-post</link>
            <guid>https://example.substack.com/p/example-post</guid>
            <pubDate>Fri, 03 Jul 2026 15:04:00 GMT</pubDate>
            <dc:creator>Example Author</dc:creator>
            <content:encoded><![CDATA[<p>Full body</p>]]></content:encoded>
          </item>
        </channel></rss>'''
        publication = ingest.Publication("example", "Example", "https://example.substack.com")
        with patch.object(ingest, "fetch_url", return_value=(rss, publication.base_url + "/feed")):
            posts = ingest.fetch_feed(publication)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].post_id, "example-post")
        self.assertEqual(posts[0].author, "Example Author")
        self.assertEqual(posts[0].html_content, "<p>Full body</p>")

    def test_render_note_has_metadata_and_markdown_body(self):
        note = ingest.render_note(self.post(), "2026-07-03T16:00:00Z")
        self.assertIn('post_id: "example-post"', note)
        self.assertIn('source_type: "substack"', note)
        self.assertIn('publication_handle: "example"', note)
        self.assertIn("Hello **world**.", note)

    def test_existing_note_prevents_duplicate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            output.mkdir()
            (output / "existing.md").write_text('---\npost_id: "example-post"\n---\n')
            state = {"version": 1, "publications": {}, "posts": {}}
            counts = ingest.collect([self.post()], state, output, root / "state.json", False)
            self.assertEqual(counts["seen"], 1)
            self.assertEqual(state["posts"]["example-post"]["status"], "ingested")

    def test_empty_body_is_pending_and_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            post = self.post()
            post = ingest.Post(**{**ingest.asdict(post), "html_content": ""})
            state = {"version": 1, "publications": {}, "posts": {}}
            first = ingest.collect([post], state, root / "out", root / "state.json", False)
            second = ingest.collect([post], state, root / "out", root / "state.json", False)
            self.assertEqual(first["pending"], 1)
            self.assertEqual(second["pending"], 1)
            self.assertEqual(state["posts"][post.post_id]["attempts"], 2)

    def test_first_run_selects_five_and_skips_older_feed_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.toml"
            config.write_text(
                '[inbox]\noutput_dir="out"\ntimezone="America/Los_Angeles"\n'
                '[substack]\ninitial_backfill_limit=5\n'
                '[[substack.publications]]\nhandle="example"\n'
            )
            posts = [self.post(f"post-{index}", f"Post {index}") for index in range(12)]
            state = {"version": 1, "publications": {}, "posts": {}}
            publication = ingest.Publication("example", "Example", "https://example.substack.com")
            with (
                patch.object(ingest, "resolve_publication", return_value=publication),
                patch.object(ingest, "fetch_feed", return_value=posts),
            ):
                selected, output = ingest.publication_candidates(config, state, False)
            self.assertEqual(len(selected), 5)
            self.assertEqual(output, root / "out")
            self.assertTrue(state["publications"]["example"]["initialized"])
            self.assertEqual(state["posts"]["post-5"]["status"], "skipped")
            self.assertEqual(state["posts"]["post-11"]["status"], "skipped")

    def test_success_writes_note_and_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {"version": 1, "publications": {}, "posts": {}}
            counts = ingest.collect([self.post()], state, root / "out", root / "state.json", False)
            self.assertEqual(counts["created"], 1)
            self.assertEqual(len(list((root / "out").rglob("*.md"))), 1)
            persisted = json.loads((root / "state.json").read_text())
            self.assertEqual(persisted["posts"]["example-post"]["status"], "ingested")

    def test_dry_run_does_not_write_output_or_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {"version": 1, "publications": {}, "posts": {}}
            counts = ingest.collect([self.post()], state, root / "out", root / "state.json", True)
            self.assertEqual(counts["created"], 1)
            self.assertFalse((root / "out").exists())
            self.assertFalse((root / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
