from typing import Tuple, List, Optional
import numpy as np

class ROIExtractor:
    """
    Trích xuất các vùng quan tâm (ROI: Trán, Má) từ Bounding Box khuôn mặt
    và tính toán vector trung bình không gian [R, G, B].
    """

    def __init__(self, crop_forehead: bool = True, crop_cheeks: bool = True):
        self.crop_forehead = crop_forehead
        self.crop_cheeks = crop_cheeks

    def get_sub_rois(self, bbox: Tuple[int, int, int, int]) -> List[Tuple[int, int, int, int]]:
        """
        Tính toán tọa độ các sub-ROIs (Trán, 2 bên Má) từ Face Bounding Box.
        bbox: (x, y, w, h)
        """
        x, y, w, h = bbox
        rois = []

        if self.crop_forehead:
            # Vùng trán: 50% bề ngang ở giữa, 20% chiều cao trên cùng
            fh_x = int(x + 0.25 * w)
            fh_y = int(y + 0.08 * h)
            fh_w = int(0.50 * w)
            fh_h = int(0.18 * h)
            rois.append((fh_x, fh_y, fh_w, fh_h))

        if self.crop_cheeks:
            # Má trái (theo góc nhìn ảnh)
            lc_x = int(x + 0.15 * w)
            lc_y = int(y + 0.50 * h)
            lc_w = int(0.25 * w)
            lc_h = int(0.20 * h)
            rois.append((lc_x, lc_y, lc_w, lc_h))

            # Má phải (theo góc nhìn ảnh)
            rc_x = int(x + 0.60 * w)
            rc_y = int(y + 0.50 * h)
            rc_w = int(0.25 * w)
            rc_h = int(0.20 * h)
            rois.append((rc_x, rc_y, rc_w, rc_h))

        # Nếu không bật tách vùng con, lấy 60% vùng giữa mặt
        if not rois:
            rois.append((int(x + 0.2 * w), int(y + 0.2 * h), int(0.6 * w), int(0.6 * h)))

        return rois

    def extract_mean_rgb(
        self,
        frame: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]]
    ) -> np.ndarray:
        """
        Trích xuất giá trị trung bình [R, G, B] từ các vùng ROI.
        Lưu ý: OpenCV đọc ảnh dạng BGR, hàm này tự động chuyển đổi sang [R, G, B].
        """
        if frame is None or bbox is None:
            return np.zeros(3)

        h_frame, w_frame = frame.shape[:2]
        rois = self.get_sub_rois(bbox)
        
        all_pixels = []
        for rx, ry, rw, rh in rois:
            # Kẹp tọa độ trong khung ảnh
            x1 = max(0, min(rx, w_frame - 1))
            y1 = max(0, min(ry, h_frame - 1))
            x2 = max(x1 + 1, min(rx + rw, w_frame))
            y2 = max(y1 + 1, min(ry + rh, h_frame))

            roi_patch = frame[y1:y2, x1:x2]
            if roi_patch.size > 0:
                all_pixels.append(roi_patch.reshape(-1, 3))

        if not all_pixels:
            return np.zeros(3)

        combined = np.vstack(all_pixels)
        mean_bgr = np.mean(combined, axis=0)

        # Chuyển BGR sang RGB
        mean_rgb = np.array([mean_bgr[2], mean_bgr[1], mean_bgr[0]], dtype=np.float64)
        return mean_rgb
