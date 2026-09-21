from typing import List, Optional, Tuple

import numpy as np

from aivitals_engine.config.settings import ROIConfig


class ROIExtractor:
    """
    Trích xuất các vùng quan tâm (ROI: Trán, Má trái, Má phải) từ Face Bounding Box
    và tính vector trung bình không gian [R, G, B] (Spatial Averaging).

    Input:  frame BGR (np.ndarray) + bbox (x, y, w, h)
    Output: vector RGB trung bình (np.ndarray, shape (3,))
    """

    def __init__(self, config: Optional[ROIConfig] = None) -> None:
        self._cfg = config if config is not None else ROIConfig()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def get_sub_rois(
        self, bbox: Tuple[int, int, int, int]
    ) -> List[Tuple[int, int, int, int]]:
        """
        Tính tọa độ các sub-ROI từ Face Bounding Box.

        Args:
            bbox: (x, y, w, h) — tọa độ và kích thước bounding box khuôn mặt.

        Returns:
            Danh sách các sub-ROI (x, y, w, h).
        """
        x, y, w, h = bbox
        cfg = self._cfg
        rois: List[Tuple[int, int, int, int]] = []

        if cfg.crop_forehead:
            rois.append(self._forehead_roi(x, y, w, h))

        if cfg.crop_cheeks:
            rois.append(self._left_cheek_roi(x, y, w, h))
            rois.append(self._right_cheek_roi(x, y, w, h))

        if not rois:
            rois.append(self._fallback_roi(x, y, w, h))

        return rois

    def extract_mean_rgb(
        self,
        frame: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]],
    ) -> np.ndarray:
        """
        Tính vector [R, G, B] trung bình từ các sub-ROI trên frame.

        OpenCV đọc ảnh dạng BGR — hàm này tự chuyển đổi sang RGB trước khi trả về.

        Args:
            frame: Ảnh BGR từ camera (np.ndarray, HxWx3).
            bbox:  Bounding box khuôn mặt (x, y, w, h).

        Returns:
            np.ndarray shape (3,) — [R, G, B] trung bình. Trả về zeros nếu không hợp lệ.
        """
        if frame is None or bbox is None:
            return np.zeros(3)

        frame_h, frame_w = frame.shape[:2]
        pixel_batches = [
            self._crop_pixels(frame, roi, frame_h, frame_w)
            for roi in self.get_sub_rois(bbox)
        ]
        valid_batches = [batch for batch in pixel_batches if batch is not None]

        if not valid_batches:
            return np.zeros(3)

        mean_bgr = np.mean(np.vstack(valid_batches), axis=0)
        return np.array([mean_bgr[2], mean_bgr[1], mean_bgr[0]], dtype=np.float64)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers — tính tọa độ từng vùng
    # ──────────────────────────────────────────────────────────────────────────

    def _forehead_roi(self, x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        cfg = self._cfg
        return (
            int(x + cfg.forehead_x_offset * w),
            int(y + cfg.forehead_y_offset * h),
            int(cfg.forehead_width_ratio * w),
            int(cfg.forehead_height_ratio * h),
        )

    def _left_cheek_roi(self, x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        cfg = self._cfg
        return (
            int(x + cfg.left_cheek_x_offset * w),
            int(y + cfg.left_cheek_y_offset * h),
            int(cfg.left_cheek_width_ratio * w),
            int(cfg.left_cheek_height_ratio * h),
        )

    def _right_cheek_roi(self, x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        cfg = self._cfg
        return (
            int(x + cfg.right_cheek_x_offset * w),
            int(y + cfg.right_cheek_y_offset * h),
            int(cfg.right_cheek_width_ratio * w),
            int(cfg.right_cheek_height_ratio * h),
        )

    def _fallback_roi(self, x: int, y: int, w: int, h: int) -> Tuple[int, int, int, int]:
        cfg = self._cfg
        return (
            int(x + cfg.fallback_x_offset * w),
            int(y + cfg.fallback_y_offset * h),
            int(cfg.fallback_width_ratio * w),
            int(cfg.fallback_height_ratio * h),
        )

    @staticmethod
    def _crop_pixels(
        frame: np.ndarray,
        roi: Tuple[int, int, int, int],
        frame_h: int,
        frame_w: int,
    ) -> Optional[np.ndarray]:
        """Cắt vùng ROI từ frame, kẹp trong biên ảnh. Trả None nếu vùng rỗng."""
        rx, ry, rw, rh = roi
        x1 = max(0, min(rx, frame_w - 1))
        y1 = max(0, min(ry, frame_h - 1))
        x2 = max(x1 + 1, min(rx + rw, frame_w))
        y2 = max(y1 + 1, min(ry + rh, frame_h))

        patch = frame[y1:y2, x1:x2]
        return patch.reshape(-1, 3) if patch.size > 0 else None
