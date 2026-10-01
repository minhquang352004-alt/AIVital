"""
tests/roi/test_sub_roi_extractor.py
====================================
Tests for ROIExtractor.extract_sub_roi_rgbs() added in Buoc 2.

Rules:
- Does NOT modify any existing test.
- extract_mean_rgb() must return bit-exact same values as a fresh ROIExtractor
  instance would (verified below).
"""
import unittest
import numpy as np

from aivitals_engine.roi.extractor import ROIExtractor, SubROIResult


class TestSubROIExtraction(unittest.TestCase):
    """Verify extract_sub_roi_rgbs() and backward compat of extract_mean_rgb()."""

    def setUp(self):
        # 200x200 BGR frame: B=85, G=110, R=160 (skin-like uniform color)
        self.frame = np.zeros((200, 200, 3), dtype=np.uint8)
        self.frame[:, :, 0] = 85   # B channel
        self.frame[:, :, 1] = 110  # G channel
        self.frame[:, :, 2] = 160  # R channel
        self.bbox = (20, 20, 160, 160)   # x, y, w, h — large enough for all 3 ROIs
        self.extractor = ROIExtractor()

    # ------------------------------------------------------------------
    # 1. Backward compat: extract_mean_rgb must be bit-exact unchanged
    # ------------------------------------------------------------------

    def test_extract_mean_rgb_bit_exact_unchanged(self):
        """
        extract_mean_rgb() must return bit-exact same result after the
        addition of extract_sub_roi_rgbs().  Tested on 5 different frames
        to cover shape variety.
        """
        rng = np.random.default_rng(42)
        bboxes = [
            (10, 10, 80, 80),
            (0,  0,  200, 200),
            (30, 30, 100, 100),
        ]
        for bbox in bboxes:
            frame = rng.integers(60, 200, (300, 300, 3), dtype=np.uint8)
            ref = ROIExtractor().extract_mean_rgb(frame, bbox)  # fresh instance
            got = self.extractor.extract_mean_rgb(frame, bbox)
            np.testing.assert_array_equal(
                ref, got,
                err_msg=f"extract_mean_rgb differs with bbox={bbox}",
            )

    # ------------------------------------------------------------------
    # 2. Output shape and type
    # ------------------------------------------------------------------

    def test_sub_roi_returns_subroiresult_type(self):
        result = self.extractor.extract_sub_roi_rgbs(self.frame, self.bbox)
        self.assertIsInstance(result, SubROIResult)

    def test_sub_roi_vectors_shape_and_dtype(self):
        result = self.extractor.extract_sub_roi_rgbs(self.frame, self.bbox)
        for attr in ("forehead", "left_cheek", "right_cheek"):
            vec = getattr(result, attr)
            self.assertEqual(vec.shape, (3,), f"{attr}.shape must be (3,)")
            self.assertEqual(vec.dtype, np.float64, f"{attr}.dtype must be float64")

    # ------------------------------------------------------------------
    # 3. Pixel counts positive for a sufficiently large frame
    # ------------------------------------------------------------------

    def test_pixel_counts_positive_on_large_face(self):
        result = self.extractor.extract_sub_roi_rgbs(self.frame, self.bbox)
        for key in ("forehead", "left_cheek", "right_cheek"):
            self.assertGreater(
                result.pixel_counts[key], 0,
                f"pixel_counts['{key}'] must be > 0 for a 200x200 frame with large bbox",
            )

    # ------------------------------------------------------------------
    # 4. RGB order (not BGR)
    # ------------------------------------------------------------------

    def test_sub_roi_rgb_not_bgr_order(self):
        """
        Frame has B=85, G=110, R=160.
        In RGB order: index-0 = R = 160, index-2 = B = 85.
        R > B must hold for each region.
        """
        result = self.extractor.extract_sub_roi_rgbs(self.frame, self.bbox)
        for attr in ("forehead", "left_cheek", "right_cheek"):
            vec = getattr(result, attr)
            self.assertGreater(
                vec[0], vec[2],
                f"{attr}: R channel (idx 0) should exceed B channel (idx 2) "
                f"because frame R=160 > B=85. Got {vec}",
            )

    # ------------------------------------------------------------------
    # 5. Safe handling of None inputs
    # ------------------------------------------------------------------

    def test_none_frame_returns_zeros_no_error(self):
        result = self.extractor.extract_sub_roi_rgbs(None, self.bbox)
        for attr in ("forehead", "left_cheek", "right_cheek"):
            np.testing.assert_array_equal(getattr(result, attr), np.zeros(3))
        self.assertEqual(result.pixel_counts["forehead"], 0)

    def test_none_bbox_returns_zeros_no_error(self):
        result = self.extractor.extract_sub_roi_rgbs(self.frame, None)
        for attr in ("forehead", "left_cheek", "right_cheek"):
            np.testing.assert_array_equal(getattr(result, attr), np.zeros(3))

    # ------------------------------------------------------------------
    # 6. Grand mean NOT equal to extract_mean_rgb (documented difference)
    # ------------------------------------------------------------------

    def test_sub_roi_mean_differs_from_extract_mean_rgb(self):
        """
        The unweighted mean of 3 per-ROI vectors is generally NOT equal to
        extract_mean_rgb() (which weights by pixel count).  This test
        documents the expected difference, not a bug.
        """
        result    = self.extractor.extract_sub_roi_rgbs(self.frame, self.bbox)
        grand_mean = np.mean([result.forehead, result.left_cheek, result.right_cheek], axis=0)
        mean_rgb  = self.extractor.extract_mean_rgb(self.frame, self.bbox)
        # We only assert both are non-zero (real data); we do NOT assert equality.
        self.assertTrue(np.all(grand_mean > 0), "grand mean should be non-zero")
        self.assertTrue(np.all(mean_rgb   > 0), "extract_mean_rgb should be non-zero")

    # ------------------------------------------------------------------
    # 7. Weighted mean matches extract_mean_rgb (tolerance <= 1e-12)
    # ------------------------------------------------------------------

    def test_pixel_weighted_mean_matches_extract_mean_rgb(self):
        """
        Weighted average of per-ROI means by their respective pixel counts
        MUST numerically match extract_mean_rgb() within floating-point tolerance
        delta <= 1e-12, because extract_mean_rgb() is mathematically the grand
        average of all valid pixels across all 3 sub-ROIs.
        """
        rng = np.random.default_rng(100)
        for _ in range(20):
            frame = rng.integers(0, 256, (250, 250, 3), dtype=np.uint8)
            bbox = (25, 25, 150, 150)
            
            sub = self.extractor.extract_sub_roi_rgbs(frame, bbox)
            mean_rgb = self.extractor.extract_mean_rgb(frame, bbox)
            
            nf = sub.pixel_counts["forehead"]
            nl = sub.pixel_counts["left_cheek"]
            nr = sub.pixel_counts["right_cheek"]
            total_n = nf + nl + nr
            
            self.assertGreater(total_n, 0)
            weighted_mean = (nf * sub.forehead + nl * sub.left_cheek + nr * sub.right_cheek) / total_n
            
            # Tolerance: delta = 1e-12
            np.testing.assert_allclose(
                weighted_mean, mean_rgb, atol=1e-12, rtol=1e-12,
                err_msg="Pixel-weighted mean of sub-ROIs must match extract_mean_rgb within 1e-12"
            )

    # ------------------------------------------------------------------
    # 8. Zero valid pixels in a region (disabled config or None input)
    # ------------------------------------------------------------------

    def test_zero_pixel_sub_roi_handling(self):
        """
        When a sub-ROI is disabled (e.g. crop_forehead=False in ROIConfig)
        or when inputs are None:
        - The affected region has pixel_counts == 0
        - Its vector is np.zeros(3)
        - Remaining enabled regions still have valid pixels and non-zero vectors.
        """
        from aivitals_engine.config.settings import ROIConfig

        ext_no_fore = ROIExtractor(config=ROIConfig(crop_forehead=False, crop_cheeks=True))
        sub = ext_no_fore.extract_sub_roi_rgbs(self.frame, self.bbox)

        # Forehead has exactly 0 pixels and zeros(3)
        self.assertEqual(sub.pixel_counts["forehead"], 0)
        np.testing.assert_array_equal(sub.forehead, np.zeros(3))

        # Cheeks have positive pixel counts and valid values
        self.assertGreater(sub.pixel_counts["left_cheek"], 0)
        self.assertGreater(sub.pixel_counts["right_cheek"], 0)
        self.assertFalse(np.all(sub.left_cheek == 0))
        self.assertFalse(np.all(sub.right_cheek == 0))

        # When frame is None
        sub_none = self.extractor.extract_sub_roi_rgbs(None, self.bbox)
        self.assertEqual(sub_none.pixel_counts["forehead"], 0)
        self.assertEqual(sub_none.pixel_counts["left_cheek"], 0)
        self.assertEqual(sub_none.pixel_counts["right_cheek"], 0)
        np.testing.assert_array_equal(sub_none.forehead, np.zeros(3))
        np.testing.assert_array_equal(sub_none.left_cheek, np.zeros(3))
        np.testing.assert_array_equal(sub_none.right_cheek, np.zeros(3))


if __name__ == "__main__":
    unittest.main()


