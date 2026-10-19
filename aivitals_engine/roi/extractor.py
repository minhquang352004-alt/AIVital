from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from aivitals_engine.config.settings import ROIConfig
from aivitals_engine.face.landmarks import (
    FOREHEAD_LANDMARKS,
    LEFT_CHEEK_LANDMARKS,
    RIGHT_CHEEK_LANDMARKS,
)
from aivitals_engine.roi.skin_filter import filter_skin_pixels


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
        landmarks: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Tính vector [R, G, B] trung bình từ các sub-ROI trên frame.

        Hỗ trợ 2 chế độ:
        1. Level 2 (Đa giác mốc 3D): nếu truyền `landmarks` (shape 468x2).
        2. Level 1 / Baseline (Bounding Box %): nếu `landmarks` là None.

        Args:
            frame:     Ảnh BGR từ camera (np.ndarray, HxWx3).
            bbox:      Bounding box khuôn mặt (x, y, w, h).
            landmarks: Tọa độ pixel (N, 2) các điểm mốc 3D (tùy chọn).

        Returns:
            np.ndarray shape (3,) — [R, G, B] trung bình. Trả về zeros nếu không hợp lệ.
        """
        if frame is None:
            return np.zeros(3)

        # ── Ưu tiên trích xuất theo Đa giác mốc giải phẫu 3D (Level 2) ────────
        if landmarks is not None and len(landmarks) >= 468:
            pixel_batches = []
            if self._cfg.crop_forehead:
                pts = landmarks[list(FOREHEAD_LANDMARKS)]
                b = self._crop_polygon_pixels(frame, pts)
                if b is not None:
                    pixel_batches.append(b)
            if self._cfg.crop_cheeks:
                pts_l = landmarks[list(LEFT_CHEEK_LANDMARKS)]
                b_l = self._crop_polygon_pixels(frame, pts_l)
                if b_l is not None:
                    pixel_batches.append(b_l)
                pts_r = landmarks[list(RIGHT_CHEEK_LANDMARKS)]
                b_r = self._crop_polygon_pixels(frame, pts_r)
                if b_r is not None:
                    pixel_batches.append(b_r)

            if pixel_batches:
                mean_bgr = np.mean(np.vstack(pixel_batches), axis=0)
                return np.array([mean_bgr[2], mean_bgr[1], mean_bgr[0]], dtype=np.float64)

        # ── Fallback về Bounding Box theo tỷ lệ (Level 1 / Baseline) ───────────
        if bbox is None:
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
        landmarks: Optional[np.ndarray] = None,
    ) -> SubROIResult:
        """
        Extract the mean RGB vector for each sub-ROI (forehead, left cheek,
        right cheek) independently, without combining them.

        Args:
            frame:     BGR camera frame (np.ndarray, HxWx3).
            bbox:      Face bounding box (x, y, w, h).
            landmarks: Tọa độ pixel (N, 2) các điểm mốc 3D (tùy chọn).

        Returns:
            SubROIResult containing per-region mean RGB vectors and pixel
            counts.  Regions with no valid pixels carry zeros(3).
        """
        _zero = np.zeros(3, dtype=np.float64)

        if frame is None or (bbox is None and landmarks is None):
            return SubROIResult(
                forehead=_zero.copy(),
                left_cheek=_zero.copy(),
                right_cheek=_zero.copy(),
                pixel_counts={"forehead": 0, "left_cheek": 0, "right_cheek": 0},
            )

        cfg = self._cfg

        # ── Ưu tiên trích xuất theo Đa giác mốc giải phẫu 3D (Level 2) ────────
        if landmarks is not None and len(landmarks) >= 468:
            def _poly_mean(indices):
                pts = landmarks[list(indices)]
                patch = self._crop_polygon_pixels(frame, pts)
                if patch is None or patch.size == 0:
                    return _zero.copy(), 0
                bgr_mean = np.mean(patch, axis=0)
                return np.array([bgr_mean[2], bgr_mean[1], bgr_mean[0]], dtype=np.float64), patch.shape[0]

            if cfg.crop_forehead:
                forehead_rgb, n_fore = _poly_mean(FOREHEAD_LANDMARKS)
            else:
                forehead_rgb, n_fore = _zero.copy(), 0

            if cfg.crop_cheeks:
                left_rgb,  n_left  = _poly_mean(LEFT_CHEEK_LANDMARKS)
                right_rgb, n_right = _poly_mean(RIGHT_CHEEK_LANDMARKS)
            else:
                left_rgb,  n_left  = _zero.copy(), 0
                right_rgb, n_right = _zero.copy(), 0

            if n_fore > 0 or n_left > 0 or n_right > 0:
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

        if bbox is None:
            return SubROIResult(
                forehead=_zero.copy(),
                left_cheek=_zero.copy(),
                right_cheek=_zero.copy(),
                pixel_counts={"forehead": 0, "left_cheek": 0, "right_cheek": 0},
            )

        frame_h, frame_w = frame.shape[:2]
        x, y, w, h = bbox

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

    def _crop_pixels(
        self,
        frame: np.ndarray,
        roi: Tuple[int, int, int, int],
        frame_h: int,
        frame_w: int,
    ) -> Optional[np.ndarray]:
        """Cắt vùng ROI từ frame, kẹp trong biên ảnh và lọc pixel da nếu bật."""
        rx, ry, rw, rh = roi
        x1 = max(0, min(rx, frame_w - 1))
        y1 = max(0, min(ry, frame_h - 1))
        x2 = max(x1 + 1, min(rx + rw, frame_w))
        y2 = max(y1 + 1, min(ry + rh, frame_h))

        patch = frame[y1:y2, x1:x2]
        if patch.size == 0:
            return None

        if self._cfg.enable_skin_filter:
            pixels = filter_skin_pixels(
                patch,
                cr_range=(self._cfg.skin_cr_min, self._cfg.skin_cr_max),
                cb_range=(self._cfg.skin_cb_min, self._cfg.skin_cb_max),
                y_range=(self._cfg.skin_y_min, self._cfg.skin_y_max),
                min_skin_ratio=self._cfg.min_skin_ratio,
            )
            return pixels if pixels.size > 0 else None

        return patch.reshape(-1, 3).astype(np.float64)

    def _crop_polygon_pixels(
        self,
        frame: np.ndarray,
        pts: np.ndarray,
    ) -> Optional[np.ndarray]:
        """
        Trích xuất mảng pixel nằm bên trong đa giác bao (convex hull) của tập điểm mốc.

        Quy trình xử lý tối ưu:
        1. Tính Convex Hull và Bounding Rect cục bộ.
        2. Cắt sub-patch nhỏ từ frame theo Bounding Rect (tránh tạo mask toàn frame).
        3. Tạo mask đa giác trên sub-patch và lấy các pixel bên trong.
        4. Áp dụng filter_skin_pixels nếu enable_skin_filter=True.

        Args:
            frame: Ảnh gốc BGR (H, W, 3).
            pts:   Tập tọa độ pixel (M, 2) của các điểm mốc giải phẫu.

        Returns:
            Mảng 2D (K, 3) float64 các pixel BGR hợp lệ, hoặc None nếu không có pixel nào.
        """
        if frame is None or pts is None or len(pts) < 3:
            return None

        frame_h, frame_w = frame.shape[:2]
        hull = cv2.convexHull(pts.astype(np.int32))
        bx, by, bw, bh = cv2.boundingRect(hull)

        x1 = max(0, min(bx, frame_w - 1))
        y1 = max(0, min(by, frame_h - 1))
        x2 = max(x1 + 1, min(bx + bw, frame_w))
        y2 = max(y1 + 1, min(by + bh, frame_h))

        patch = frame[y1:y2, x1:x2]
        if patch.size == 0:
            return None

        local_hull = hull - np.array([x1, y1])
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        cv2.fillPoly(mask, [local_hull], 255)

        inside_pixels = patch[mask > 0]
        if inside_pixels.size == 0:
            return None

        if self._cfg.enable_skin_filter:
            pixels = filter_skin_pixels(
                inside_pixels,
                cr_range=(self._cfg.skin_cr_min, self._cfg.skin_cr_max),
                cb_range=(self._cfg.skin_cb_min, self._cfg.skin_cb_max),
                y_range=(self._cfg.skin_y_min, self._cfg.skin_y_max),
                min_skin_ratio=self._cfg.min_skin_ratio,
            )
            return pixels if pixels.size > 0 else None

        return inside_pixels.astype(np.float64)

