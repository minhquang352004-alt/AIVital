from abc import ABC, abstractmethod
from typing import Optional, Tuple
import cv2
import numpy as np

class BaseFaceDetector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Nhận diện khuôn mặt lớn nhất. Trả về bbox: (x, y, w, h) hoặc None."""
        pass

class SimpleFaceDetector(BaseFaceDetector):
    """Bộ phát hiện khuôn mặt hỗ trợ CascadeClassifier (nếu có) hoặc ước lượng vùng trung tâm"""

    def __init__(self):
        self._has_cascade = hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades")
        if self._has_cascade:
            try:
                self.detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            except Exception:
                self._has_cascade = False

    def detect(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]

        if self._has_cascade:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
                faces = self.detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
                if len(faces) > 0:
                    largest = max(faces, key=lambda b: b[2] * b[3])
                    return tuple(int(v) for v in largest)
            except Exception:
                pass

        # Fallback vùng trung tâm 50%
        bw = int(0.50 * w)
        bh = int(0.50 * h)
        bx = int(0.25 * w)
        by = int(0.20 * h)
        return (bx, by, bw, bh)
