"""Non-identifying fixtures for subject isolation, QC, metrics and snapshot safety."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import split_and_validate_dataset as tool


def fixture(count=10):
    return [tool.normalize({"sample_id": f"sample_{i}_{j}", "subject_id": f"subject_{i}",
            "age_years": 20 + i, "sex": "unknown", "hr_reference_bpm": 60 + i,
            "hr_estimated_bpm": 62 + i, "sbp_reference_mmhg": 110 + i,
            "dbp_reference_mmhg": 70 + i, "sbp_estimated_mmhg": 112 + i,
            "dbp_estimated_mmhg": 69 + i, "sqi": .6, "signal_status": "OK", "hr_status": "OK",
            "bp_status": "OK", **{f: True for f in tool.FLAGS}})
            for i in range(count) for j in range(2)]


class DatasetValidationTests(unittest.TestCase):
    def test_grouped_holdout_deterministic_and_order_invariant(self):
        rows = fixture()
        report = tool.build_report(rows, "holdout", 42, 5, "bp")
        allocation = {r["sample_id"]: r["candidate_split"] for r in rows}
        again = list(reversed(fixture()))
        tool.build_report(again, "holdout", 42, 5, "bp")
        self.assertEqual(allocation, {r["sample_id"]: r["candidate_split"] for r in again})
        self.assertEqual(sorted(p["inventory"]["subjects"] for p in report["partitions"].values()), [1, 2, 7])
        self.assertEqual(report["eligible"]["rows"], 20)

    def test_kfold_has_disjoint_subjects_and_once_only_test(self):
        report = tool.build_report(fixture(5), "kfold", 42, 5, "bp")
        all_test = []
        for fold in report["fold_roles"].values():
            self.assertFalse(set(fold["train_subjects"]) & set(fold["test_subjects"]))
            all_test.extend(fold["test_subjects"])
        self.assertEqual(len(all_test), len(set(all_test)))
        with self.assertRaises(ValueError):
            tool.build_report(fixture(1), "kfold", 42, 2, "hr")
        with self.assertRaises(ValueError):
            tool.build_report(fixture(5), "holdout", 42, 5, "bp")

    def test_single_subject_audit_and_valid_existing_folds(self):
        report = tool.build_report(fixture(1), "audit", 42, 5, "hr")
        self.assertFalse(report["usable_supervised_partitions"])
        self.assertEqual(report["evaluation"]["paired_rows"], 0)
        self.assertEqual(set(report["partitions"]), {"unassigned"})
        rows = fixture(5)
        for row in rows:
            row["fold"] = row["subject_id"].split("_")[-1]
        report = tool.build_report(rows, "existing", 42, 5, "bp")
        self.assertEqual(report["folds"], 5)
        rows[0]["fold"] = "1"
        with self.assertRaisesRegex(ValueError, "leakage"):
            tool.validate_identity(rows)

    def test_existing_leakage_and_partial_assignments_rejected(self):
        rows = fixture()
        for r in rows:
            r["split"] = "train"
        rows[0]["split"] = "test"
        with self.assertRaisesRegex(ValueError, "leakage"):
            tool.build_report(rows, "existing", 42, 5, "bp")
        rows[0]["split"] = ""
        with self.assertRaisesRegex(ValueError, "Partial"):
            tool.validate_identity(rows)

    def test_duplicates_parent_alias_and_demographics(self):
        rows = fixture()
        with self.assertRaises(ValueError):
            tool.validate_identity(rows + [rows[0]])
        rows[0]["video_sha256"] = "a" * 64
        rows[2]["video_sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            tool.validate_identity(rows)
        rows = fixture()
        rows[0]["parent_sample_id"] = rows[2]["sample_id"]
        with self.assertRaises(ValueError):
            tool.validate_identity(rows)
        rows = fixture()
        rows[0]["age_years"] = 99
        with self.assertRaisesRegex(ValueError, "demographic"):
            tool.build_report(rows, "holdout", 42, 5, "hr")

    def test_missing_gt_and_sqi_boundaries_preserve_extreme_bp(self):
        row = fixture()[0]
        for sqi, code in ((.299, "SQI_UNUSABLE"), (.3, "SQI_LOW"), (.599, "SQI_LOW"), (.6, None)):
            row["sqi"] = sqi
            reasons = tool.qc_reasons(row, "bp")
            self.assertEqual([r for r in reasons if r.startswith("SQI")], [code] if code else [])
        row["sbp_reference_mmhg"], row["dbp_reference_mmhg"] = 180, 121
        self.assertEqual(tool.label_reasons(row, "bp"), [])
        row["sbp_reference_mmhg"] = 100
        self.assertTrue(tool.label_reasons(row, "bp"))
        row["hr_reference_bpm"] = None
        self.assertTrue(tool.label_reasons(row, "hr"))
        self.assertFalse(tool.normalize({})["usage_authorized"])
        for value in ("NaN", "inf", "-inf"):
            with self.assertRaises(ValueError):
                tool.normalize({"hr_reference_bpm": value})
        with self.assertRaises(ValueError):
            tool.normalize({"usage_authorized": "maybe"})

    def test_metrics_match_both_engine_modules_and_wrong_provenance_excluded(self):
        rows = fixture(5)
        first = tool.build_report(rows, "kfold", 42, 5, "bp")
        self.assertEqual(first["evaluation"]["paired_rows"], 0)
        for row in rows:
            row["prediction_provenance"] = "synthetic test only"
            row["prediction_holdout"] = row["candidate_fold"]
            row["prediction_assignment_sha256"] = first["assignment_sha256"]
        report = tool.build_report(rows, "kfold", 42, 5, "bp")["evaluation"]
        self.assertEqual(report["paired_rows"], 10)
        self.assertEqual(report["metrics"]["sbp"]["mae"], 2)
        self.assertEqual(report["metrics"]["dbp"]["bias"], -1)
        for name, engine in (("sbp", "systolic"), ("dbp", "diastolic")):
            self.assertEqual(report["metrics"][name]["mae"], report["bp_engine_stats"][engine]["mean_absolute_error"])
            self.assertEqual(report["metrics"][name]["bias"], report["bp_engine_stats"][engine]["mean_error"])
        constant = tool.compute_error_metrics([70, 70, 70], [71, 72, 73], 5)
        self.assertIsNone(constant.pearson_r)
        varied = tool.compute_error_metrics([60, 70, 80], [62, 69, 83], 5)
        self.assertAlmostEqual(varied.loa_lower, np.mean([2, -1, 3]) - 1.96 * np.std([2, -1, 3], ddof=1))
        self.assertIsNone(tool.compute_error_metrics([], [], 5).mae)

    def test_output_scope_nonoverwrite_and_csv_validation(self):
        with self.assertRaises(ValueError):
            tool.validate_output(tool.ROOT / "aivitals_engine/output_run01")
        with self.assertRaises(ValueError):
            tool.validate_output(tool.BASE)
        with patch.object(Path, "exists", return_value=True):
            with self.assertRaises(FileExistsError):
                tool.validate_output(tool.BASE / "test_run01")
        with tempfile.TemporaryDirectory(prefix="test_run", dir=tool.BASE) as folder:
            path = Path(folder) / "fixture.csv"
            tool.write_csv(path, fixture())
            rows, _ = tool.read_csv(path)
            self.assertEqual(len(rows), 20)
            with path.open("w", encoding="utf-8") as stream:
                stream.write("sample_id,subject_id\na,b,extra\n")
            with self.assertRaises(ValueError):
                tool.read_csv(path)
            mixed = fixture()
            mixed[-1]["source_evidence"] = "synthetic optional provenance"
            fields = sorted({k for row in mixed for k in row})
            tool.write_csv(Path(folder) / "eligible.csv", [mixed[-1]], fields)
            tool.write_csv(Path(folder) / "empty.csv", [], fields)
            with (Path(folder) / "empty.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(csv.DictReader(stream).fieldnames, fields)


if __name__ == "__main__":
    unittest.main()
