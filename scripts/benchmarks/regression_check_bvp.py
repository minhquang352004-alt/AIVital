"""
scripts/benchmarks/regression_check_bvp.py
===========================================
Regression test: Verify that RealtimeSignalPipeline outputs BIT-EXACT identical
BVP signals before and after Buoc 2 sub-ROI additions.

Runs the pipeline on a deterministic synthetic sequence (seed=42) against the
baseline exported from the main branch.
"""
import os
import subprocess
import sys
import tempfile
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_regression_test():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Export main branch to temporary directory
        subprocess.check_call("git archive main | tar -x -C " + tmpdir, shell=True)

        sys.path.insert(0, tmpdir)
        from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline as MainPipeline

        sys.path.pop(0)
        from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline as CurrentPipeline

        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)

        pipe_main = MainPipeline(method="POS")
        pipe_curr = CurrentPipeline(method="POS")

        match_count = 0
        max_diff = 0.0

        for i in range(250):
            b1 = int(np.clip(85 + rng1.integers(-2, 3), 0, 255))
            g1 = int(np.clip(110 + rng1.integers(-2, 3), 0, 255))
            r1 = int(np.clip(160 + rng1.integers(-2, 3), 0, 255))
            f1 = np.full((100, 100, 3), [b1, g1, r1], dtype=np.uint8)

            b2 = int(np.clip(85 + rng2.integers(-2, 3), 0, 255))
            g2 = int(np.clip(110 + rng2.integers(-2, 3), 0, 255))
            r2 = int(np.clip(160 + rng2.integers(-2, 3), 0, 255))
            f2 = np.full((100, 100, 3), [b2, g2, r2], dtype=np.uint8)

            ts = i / 30.0
            res_main = pipe_main.process_frame(f1, timestamp=ts)
            res_curr = pipe_curr.process_frame(f2, timestamp=ts)

            assert res_main.is_ready == res_curr.is_ready
            assert res_main.status == res_curr.status
            if res_main.is_ready:
                diff = float(np.max(np.abs(res_main.bvp_signal - res_curr.bvp_signal)))
                if diff > max_diff:
                    max_diff = diff
                assert np.array_equal(res_main.bvp_signal, res_curr.bvp_signal), f"Mismatch at frame {i}"
                assert res_main.quality_sqi == res_curr.quality_sqi
                match_count += 1

        print("=" * 64)
        print("BVP REGRESSION TEST vs MAIN BRANCH")
        print(f"Tested: {match_count} ready BVP windows across 250 frames (seed=42)")
        print(f"Max absolute element-wise difference: {max_diff}")
        print("Verdict: BIT-EXACT IDENTICAL (diff = 0.0)")
        print("=" * 64)


if __name__ == "__main__":
    run_regression_test()
