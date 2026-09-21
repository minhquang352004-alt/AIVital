import unittest
import numpy as np

from aivitals_engine.roi.extractor import ROIExtractor
from aivitals_engine.config.settings import ROIConfig


class TestROIExtractor(unittest.TestCase):
    """Kiểm thử kỹ thuật cho roi/extractor.py."""

    def setUp(self):
        self.extractor = ROIExtractor(config=ROIConfig(crop_forehead=True, crop_cheeks=True))

    def test_sub_rois_geometry(self):
        """Kiểm tra tỷ lệ vị trí hộp Trán và 2 Má từ Face Bounding Box."""
        bbox = (100, 100, 200, 200)  # x, y, w, h
        rois = self.extractor.get_sub_rois(bbox)

        self.assertEqual(len(rois), 3, "Phải sinh ra đúng 3 vùng ROI: Trán, Má trái, Má phải")
        fh, lc, rc = rois

        # Trán: nằm ở nửa trên khuôn mặt
        self.assertLess(fh[1], 100 + 0.3 * 200)
        # Má trái: nằm ở nửa dưới bên trái
        self.assertGreaterEqual(lc[1], 100 + 0.4 * 200)
        self.assertLess(lc[0], 100 + 0.5 * 200)
        # Má phải: nằm ở nửa dưới bên phải
        self.assertGreater(rc[0], 100 + 0.5 * 200)

    def test_spatial_averaging_bgr_to_rgb(self):
        """Kiểm tra Spatial Averaging tính đúng giá trị trung bình và đổi đúng từ BGR sang RGB."""
        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        frame[:] = [10, 50, 200]  # B=10, G=50, R=200
        bbox = (50, 50, 150, 150)

        mean_rgb = self.extractor.extract_mean_rgb(frame, bbox)

        self.assertEqual(mean_rgb.shape, (3,))
        self.assertAlmostEqual(mean_rgb[0], 200.0, delta=0.1)  # R
        self.assertAlmostEqual(mean_rgb[1], 50.0, delta=0.1)   # G
        self.assertAlmostEqual(mean_rgb[2], 10.0, delta=0.1)   # B

    def test_roi_edge_cases(self):
        """Kiểm tra các trường hợp biên: frame=None, bbox=None hoặc bbox lệch ngoài ảnh."""
        self.assertTrue(np.all(self.extractor.extract_mean_rgb(None, (0, 0, 10, 10)) == 0))
        self.assertTrue(np.all(self.extractor.extract_mean_rgb(np.zeros((100, 100, 3)), None) == 0))

        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        out_bbox = (80, 80, 50, 50)
        mean_rgb = self.extractor.extract_mean_rgb(frame, out_bbox)
        self.assertTrue(np.all(mean_rgb > 0))


if __name__ == "__main__":
    unittest.main()
