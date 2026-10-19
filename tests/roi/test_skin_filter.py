"""
tests/roi/test_skin_filter.py
=============================
Unit tests cho bộ lọc màu da YCrCb (Level 1 Skin Pixel Filtering).

Kiểm tra:
  - Lọc chính xác pixel da người.
  - Loại bỏ hoàn toàn tóc đen, râu, viền kính.
  - Xử lý biên an toàn (None, mảng rỗng, ảnh đơn sắc không có da).
  - Tích hợp với ROIExtractor (loại bỏ tóc mái trên vùng trán).
"""
import numpy as np
import pytest

from aivitals_engine.config.settings import ROIConfig
from aivitals_engine.roi.extractor import ROIExtractor
from aivitals_engine.roi.skin_filter import filter_skin_pixels


class TestSkinPixelFilter:
    """Kiểm tra chức năng cốt lõi của hàm filter_skin_pixels."""

    @pytest.fixture
    def skin_bgr(self) -> np.ndarray:
        """Pixel màu da chuẩn (B=85, G=110, R=160)."""
        return np.array([85, 110, 160], dtype=np.uint8)

    @pytest.fixture
    def hair_bgr(self) -> np.ndarray:
        """Pixel sợi tóc đen (B=15, G=15, R=15)."""
        return np.array([15, 15, 15], dtype=np.uint8)

    def test_pure_skin_patch_retains_all_pixels(self, skin_bgr):
        patch = np.zeros((10, 10, 3), dtype=np.uint8)
        patch[:, :] = skin_bgr
        filtered = filter_skin_pixels(patch)

        assert filtered.shape == (100, 3)
        np.testing.assert_allclose(np.mean(filtered, axis=0), skin_bgr.astype(np.float64))

    def test_hair_pixels_filtered_out(self, skin_bgr, hair_bgr):
        """Mảng gồm 70% da và 30% tóc đen -> chỉ giữ lại 70 pixel da."""
        patch = np.zeros((10, 10, 3), dtype=np.uint8)
        patch[:7, :] = skin_bgr  # 70 pixel da
        patch[7:, :] = hair_bgr  # 30 pixel tóc đen

        filtered = filter_skin_pixels(patch)

        assert filtered.shape[0] == 70
        # Giá trị trung bình sau lọc phải là màu da chuẩn, không bị tóc kéo tối xuống
        np.testing.assert_allclose(np.mean(filtered, axis=0), skin_bgr.astype(np.float64))

    def test_empty_patch_safe(self):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        result = filter_skin_pixels(empty)
        assert result.shape == (0, 3)

    def test_none_patch_safe(self):
        result = filter_skin_pixels(None)
        assert result.shape == (0, 3)

    def test_all_black_fallback(self, hair_bgr):
        """Khi 100% là màu đen (0% da) -> fallback lấy toàn bộ, không chia cho 0."""
        patch = np.zeros((10, 10, 3), dtype=np.uint8)
        patch[:, :] = hair_bgr
        filtered = filter_skin_pixels(patch)

        assert filtered.shape == (100, 3)
        np.testing.assert_allclose(np.mean(filtered, axis=0), hair_bgr.astype(np.float64))

    def test_specular_reflection_filtered(self, skin_bgr):
        """Điểm lóa sáng chói lóa (Y > 240) bị loại bỏ."""
        glare_bgr = np.array([255, 255, 255], dtype=np.uint8)
        patch = np.zeros((10, 10, 3), dtype=np.uint8)
        patch[:8, :] = skin_bgr   # 80 pixel da
        patch[8:, :] = glare_bgr  # 20 pixel lóa sáng

        filtered = filter_skin_pixels(patch)
        assert filtered.shape[0] == 80
        np.testing.assert_allclose(np.mean(filtered, axis=0), skin_bgr.astype(np.float64))


class TestROIExtractorSkinFilterIntegration:
    """Kiểm tra tích hợp giữa ROIExtractor và bộ lọc màu da."""

    def test_forehead_with_bangs_comparison(self):
        """
        Tạo khung hình giả lập khuôn mặt:
        - Vùng trán bị tóc mái đen che phủ 40%.
        - So sánh khi BẬT và TẮT enable_skin_filter.
        """
        frame = np.full((300, 300, 3), [85, 110, 160], dtype=np.uint8)  # Toàn mặt là da
        bbox = (50, 50, 200, 200)

        # Tạo một vệt tóc đen che 40% phần trên trán
        extractor_raw = ROIExtractor(config=ROIConfig(enable_skin_filter=False))
        forehead_roi = extractor_raw.get_sub_rois(bbox)[0]
        fx, fy, fw, fh = forehead_roi
        frame[fy : fy + int(fh * 0.4), fx : fx + fw] = [15, 15, 15]  # Tóc đen

        # 1. Khi TẮT lọc: giá trị màu bị tóc đen kéo sụt giảm
        rgb_no_filter = extractor_raw.extract_mean_rgb(frame, bbox)

        # 2. Khi BẬT lọc: loại bỏ tóc đen, giữ nguyên màu da chuẩn
        extractor_filtered = ROIExtractor(config=ROIConfig(enable_skin_filter=True))
        rgb_with_filter = extractor_filtered.extract_mean_rgb(frame, bbox)

        # Kênh Đỏ (R): khi có tóc sẽ bị giảm mạnh, khi lọc sạch sẽ cao hơn và đúng chuẩn 160
        assert rgb_with_filter[0] > rgb_no_filter[0]
        assert rgb_with_filter[0] == pytest.approx(160.0, abs=1.0)
        assert rgb_with_filter[1] == pytest.approx(110.0, abs=1.0)
        assert rgb_with_filter[2] == pytest.approx(85.0, abs=1.0)

    def test_sub_roi_result_carries_valid_pixel_counts(self):
        """SubROIResult.pixel_counts phản ánh số lượng pixel da thực sự sau khi lọc."""
        frame = np.full((300, 300, 3), [85, 110, 160], dtype=np.uint8)
        bbox = (50, 50, 200, 200)

        extractor = ROIExtractor(config=ROIConfig(enable_skin_filter=True))
        sub_res = extractor.extract_sub_roi_rgbs(frame, bbox)

        assert sub_res.pixel_counts["forehead"] > 0
        assert sub_res.pixel_counts["left_cheek"] > 0
        assert sub_res.pixel_counts["right_cheek"] > 0
        assert sub_res.forehead[0] == pytest.approx(160.0, abs=1.0)
