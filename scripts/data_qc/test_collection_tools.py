"""Tests for missing-data and non-overwrite collection initialization."""
import json
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from init_collection_session import PACKAGE, initialize, session_directory
import run_video_qc


class CollectionToolsTest(unittest.TestCase):
    def test_initialization_does_not_invent_capture_or_reference(self):
        with tempfile.TemporaryDirectory(prefix="hao-test-", dir=PACKAGE) as base:
            path = initialize("SUBJ_TEST", "SESSION_TEST", Path(base))
            data = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(data["initialization_timestamp"])
            self.assertIsNone(data["collection_timestamp"])
            self.assertIsNone(data["video_start_timestamp"])
            self.assertIsNone(data["reference_hr_bpm"])
            self.assertIsNone(data["sync_error_ms"])
            with self.assertRaises(FileExistsError):
                initialize("SUBJ_TEST", "SESSION_TEST", Path(base))

    def test_dry_run_and_invalid_paths(self):
        with tempfile.TemporaryDirectory(prefix="hao-test-", dir=PACKAGE) as base:
            path = initialize("SUBJ_TEST", "SESSION_TEST", Path(base), dry_run=True)
            self.assertFalse(path.exists())
            with self.assertRaises(ValueError):
                session_directory("../escape", "s", Path(base))
            with self.assertRaises(ValueError):
                session_directory("subj", "s", Path(tempfile.gettempdir()))

    def test_qc_refuses_bad_ids_root_output_and_missing_input(self):
        cases = [
            ("bad/id", PACKAGE / "unused-test-run"),
            ("valid", PACKAGE),
            ("valid", PACKAGE / "unused-test-run"),
        ]
        for sample_id, output in cases:
            args = ["run_video_qc", "--video", "missing-video-fixture.mp4", "--sample-id", sample_id,
                    "--session-id", "test", "--output-dir", str(output)]
            with self.subTest(sample_id=sample_id, output=output), patch.object(sys, "argv", args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    run_video_qc.main()
                self.assertEqual(raised.exception.code, 2)
            if output != PACKAGE:
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
