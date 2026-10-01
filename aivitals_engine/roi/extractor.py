from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from aivitals_engine.config.settings import ROIConfig


@dataclass
class SubROIResult:
    """
    Per-region mean RGB vectors returned by ROIExtractor.extract_sub_roi_rgbs().

    Each channel vector is in RGB order (same as extract_mean_rgb), shape (3,).
    Regions with no valid pixels return zeros(3, dtype=float64).
    pixel_counts reports how many raw pixels contributed to each mean.

    Note: the grand mean of these three vectors is NOT numerically equal to
    extract_mean_rgb() because extract_mean_rgb() weights by pixel count
    (grand average over all pixels), while this dataclass stores unweighted
    per-region means.
    """
    forehead:    np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    left_cheek:  np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    right_cheek: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    pixel_counts: Dict[str, int] = field(
        default_factory=lambda: {"forehead": 0, "left_cheek": 0, "right_cheek": 0}
    )


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

    def extract_sub_roi_rgbs(
        self,
        frame: Optional[np.ndarray],
        bbox:  Optional[Tuple[int, int, int, int]],
    ) -> SubROIResult:
        """
        Extract the mean RGB vector for each sub-ROI (forehead, left cheek,
        right cheek) independently, without combining them.

        Intended use: building per-region time series for spatial signal
        quality analysis (cross-region correlation).  The returned vectors
        are in RGB order and dtype float64, matching extract_mean_rgb().

        Args:
            frame: BGR camera frame (np.ndarray, HxWx3).
            bbox:  Face bounding box (x, y, w, h).

        Returns:
            SubROIResult containing per-region mean RGB vectors and pixel
            counts.  Regions with no valid pixels carry zeros(3).
        """
        _zero = np.zeros(3, dtype=np.float64)

        if frame is None or bbox is None:
            return SubROIResult(
                forehead=_zero.copy(),
                left_cheek=_zero.copy(),
                right_cheek=_zero.copy(),
                pixel_counts={"forehead": 0, "left_cheek": 0, "right_cheek": 0},
            )

        frame_h, frame_w = frame.shape[:2]
        x, y, w, h = bbox
        cfg = self._cfg

        def _roi_mean(roi_bbox: Tuple[int, int, int, int]):
            patch = self._crop_pixels(frame, roi_bbox, frame_h, frame_w)
            if patch is None:
                return _zero.copy(), 0
            bgr_mean = np.mean(patch, axis=0)
            return np.array([bgr_mean[2], bgr_mean[1], bgr_mean[0]], dtype=np.float64), patch.shape[0]

        if cfg.crop_forehead:
            forehead_rgb, n_fore = _roi_mean(self._forehead_roi(x, y, w, h))
        else:
            forehead_rgb, n_fore = _zero.copy(), 0

        if cfg.crop_cheeks:
            left_rgb,  n_left  = _roi_mean(self._left_cheek_roi(x, y, w, h))
            right_rgb, n_right = _roi_mean(self._right_cheek_roi(x, y, w, h))
        else:
            left_rgb,  n_left  = _zero.copy(), 0
            right_rgb, n_right = _zero.copy(), 0

        return SubROIResult(
            forehead=forehead_rgb,
            left_cheek=left_rgb,
            right_cheek=right_rgb,
            pixel_counts={
                "forehead":   n_fore,
                "left_cheek": n_left,
                "right_cheek": n_right,
            },
        )

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
