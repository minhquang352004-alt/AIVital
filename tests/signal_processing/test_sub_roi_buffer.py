"""
tests/signal_processing/test_sub_roi_buffer.py
================================================
Tests for the per-region sub-ROI tracking added to SlidingWindowBuffer in Buoc 2.

Rules:
- Does NOT modify any existing test.
- Verifies: length sync, artifact rejection, time-gap reset, backward compat.
"""
import unittest
from types import SimpleNamespace

import numpy as np

from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer


def _make_sub(val: float):
    """Helper: create a duck-typed SubROIResult substitute (SimpleNamespace)."""
    arr = np.full(3, val, dtype=np.float64)
    return SimpleNamespace(
        forehead=arr.copy(),
        left_cheek=arr.copy(),
        right_cheek=arr.copy(),
    )


BASE_RGB = np.array([160.0, 110.0, 85.0])


class TestSubROIBuffer(unittest.TestCase):

    # ------------------------------------------------------------------
    # 1. Sub-ROI buffer lengths match main buffer after N accepted pushes
    # ------------------------------------------------------------------

    def test_sub_roi_lengths_match_main_buffer(self):
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None
        )
        for i in range(60):
            buf.push(BASE_RGB + i * 0.01, timestamp=i * 0.033, sub_rgbs=_make_sub(float(i)))

        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(len(fore),  buf.size, "forehead len must equal main buf size")
        self.assertEqual(len(left),  buf.size, "left_cheek len must equal main buf size")
        self.assertEqual(len(right), buf.size, "right_cheek len must equal main buf size")

    def test_sub_roi_values_correct(self):
        """Each pushed sub-ROI value is retrievable in FIFO order."""
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None
        )
        for i in range(10):
            buf.push(BASE_RGB, timestamp=i * 0.033, sub_rgbs=_make_sub(float(i + 1)))

        fore, _, _ = buf.get_sub_roi_raw_window()
        np.testing.assert_allclose(fore[:, 0], np.arange(1, 11, dtype=float),
                                   err_msg="forehead R channel must match pushed values")

    # ------------------------------------------------------------------
    # 2. Artifact rejection excludes from ALL 4 series atomically
    # ------------------------------------------------------------------

    def test_artifact_rejection_excludes_sub_rois(self):
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=3.5
        )
        rng = np.random.default_rng(0)

        # Push 20 normal frames (small Gaussian noise)
        for i in range(20):
            buf.push(
                BASE_RGB + rng.normal(0, 0.3, 3),
                timestamp=i * 0.033,
                sub_rgbs=_make_sub(1.0),
            )

        size_before = buf.size
        fore_before, _, _ = buf.get_sub_roi_raw_window()

        # Push 1 spike frame: should be rejected
        spike = BASE_RGB + np.array([60.0, 60.0, 60.0])
        accepted = buf.push(spike, timestamp=20 * 0.033, sub_rgbs=_make_sub(99.0))

        self.assertFalse(accepted, "spike frame must be rejected as artifact")
        self.assertEqual(buf.size, size_before, "main buffer must not grow on rejection")

        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(len(fore),  size_before, "forehead buf must not grow on rejection")
        self.assertEqual(len(left),  size_before, "left_cheek buf must not grow on rejection")
        self.assertEqual(len(right), size_before, "right_cheek buf must not grow on rejection")

        # Spike value 99.0 must NOT appear in any sub-ROI buffer
        self.assertFalse(
            np.any(fore == 99.0),
            "spike sub_rgbs value (99.0) must not appear in forehead buffer",
        )

    # ------------------------------------------------------------------
    # 3. Time-gap reset clears ALL 4 series atomically
    # ------------------------------------------------------------------

    def test_time_gap_reset_clears_all_series(self):
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0,
            artifact_threshold=None, time_gap_threshold=0.5
        )
        # Push 30 normal frames
        for i in range(30):
            buf.push(BASE_RGB, timestamp=i * 0.033, sub_rgbs=_make_sub(1.0))

        self.assertEqual(buf.size, 30)

        # Push 1 frame with large time gap (>0.5 s) → triggers reset
        buf.push(BASE_RGB, timestamp=30 * 0.033 + 1.0, sub_rgbs=_make_sub(2.0))

        # After reset + 1 push, all buffers must have size = 1
        self.assertEqual(buf.size, 1, "main buffer must have size 1 after reset + 1 push")
        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(len(fore),  1, "forehead buf must have len 1 after reset")
        self.assertEqual(len(left),  1, "left_cheek buf must have len 1 after reset")
        self.assertEqual(len(right), 1, "right_cheek buf must have len 1 after reset")

        # The one remaining entry must be the post-gap frame (val = 2.0)
        np.testing.assert_allclose(fore[0, 0], 2.0,
                                   err_msg="forehead buf must hold post-gap frame, not pre-reset frames")

    # ------------------------------------------------------------------
    # 4. Backward compat: push() without sub_rgbs leaves sub-ROI bufs empty
    # ------------------------------------------------------------------

    def test_backward_compat_no_sub_rgbs(self):
        """push() without sub_rgbs arg must work exactly as before."""
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None
        )
        for i in range(25):
            buf.push(BASE_RGB, timestamp=i * 0.033)   # no sub_rgbs

        self.assertEqual(buf.size, 25, "main buffer must accumulate normally")
        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(len(fore),  0, "forehead buf must be empty without sub_rgbs")
        self.assertEqual(len(left),  0, "left_cheek buf must be empty without sub_rgbs")
        self.assertEqual(len(right), 0, "right_cheek buf must be empty without sub_rgbs")

    # ------------------------------------------------------------------
    # 5. Sub-ROI array shapes are (N, 3) not (N,)
    # ------------------------------------------------------------------

    def test_sub_roi_window_shape(self):
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None
        )
        for i in range(10):
            buf.push(BASE_RGB, timestamp=i * 0.033, sub_rgbs=_make_sub(float(i)))

        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(fore.shape,  (10, 3))
        self.assertEqual(left.shape,  (10, 3))
        self.assertEqual(right.shape, (10, 3))

    def test_empty_sub_roi_window_shape(self):
        """Empty sub-ROI window should be (0, 3), not (0,)."""
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None
        )
        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(fore.shape,  (0, 3))
        self.assertEqual(left.shape,  (0, 3))
        self.assertEqual(right.shape, (0, 3))

    # ------------------------------------------------------------------
    # 6. Zero-pixel sub-ROI frame maintains exact buffer synchronization
    # ------------------------------------------------------------------

    def test_zero_pixel_sub_roi_synchronization(self):
        """
        When a frame has 0 pixels in one sub-ROI (e.g. forehead = zeros(3)
        due to face partly out of frame), the 4 buffers remain strictly
        synchronized in length.
        """
        buf = SlidingWindowBuffer(
            window_sec=5.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None
        )
        # 10 normal frames
        for i in range(10):
            buf.push(BASE_RGB, timestamp=i * 0.033, sub_rgbs=_make_sub(1.0))

        # 1 frame where forehead has 0 pixels (zeros(3)), cheeks have normal values
        zero_forehead_sub = SimpleNamespace(
            forehead=np.zeros(3, dtype=np.float64),
            left_cheek=BASE_RGB.copy(),
            right_cheek=BASE_RGB.copy(),
        )
        accepted = buf.push(BASE_RGB, timestamp=10 * 0.033, sub_rgbs=zero_forehead_sub)
        self.assertTrue(accepted)

        fore, left, right = buf.get_sub_roi_raw_window()
        self.assertEqual(buf.size, 11)
        self.assertEqual(len(fore),  11)
        self.assertEqual(len(left),  11)
        self.assertEqual(len(right), 11)
        np.testing.assert_array_equal(fore[-1], np.zeros(3))
        np.testing.assert_array_equal(left[-1], BASE_RGB)


if __name__ == "__main__":
    unittest.main()

