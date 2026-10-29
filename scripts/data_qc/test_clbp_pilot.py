"""Targeted, file-free safety checks for CLBP pilot preparation."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_clbp_pilot import ROOT, validate_output, validate_rows


class CLBPSafetyTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((ROOT / "docs/EvidenceMatrix_BP/CLBP_SAMPLE_SOURCE_ROWS_V1.json").read_text(encoding="utf-8"))["rows"]

    def test_verified_rows(self):
        validate_rows(self.rows)
        self.assertEqual(len(self.rows), 5)

    def test_mismatched_or_unsafe_label_rejected(self):
        changed = copy.deepcopy(self.rows)
        changed[0]["sbp_mmhg"] += 1
        with self.assertRaises(ValueError):
            validate_rows(changed)
        changed[0]["filename"] = "../" + changed[0]["filename"]
        with self.assertRaises(ValueError):
            validate_rows(changed)

    def test_duplicate_and_empty_rejected(self):
        with self.assertRaises(ValueError):
            validate_rows(self.rows + [self.rows[0]])
        with self.assertRaises(ValueError):
            validate_rows([])

    def test_output_scope(self):
        with self.assertRaises(ValueError):
            validate_output(ROOT / "aivitals_engine/outputs")
        with self.assertRaises(ValueError):
            validate_output(ROOT / "docs/EvidenceMatrix_BP")

    def test_existing_output_not_overwritten(self):
        with patch.object(Path, "exists", return_value=True):
            with self.assertRaises(FileExistsError):
                validate_output(ROOT / "docs/EvidenceMatrix_BP/existing_run")


if __name__ == "__main__":
    unittest.main()
