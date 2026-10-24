"""
signal_warnings.py
===========
Danh mục tập trung các mã cảnh báo tín hiệu (signal warnings) do
RealtimeSignalPipeline phát ra qua ``FrameResult.warnings`` (Tuần 7).

Giá trị của enum là chuỗi (``str``) nên so sánh trực tiếp với literal vẫn đúng:
    >>> SignalWarning.TOO_DARK == "TOO_DARK"
    True

Pipeline luôn lưu ``.value`` (chuỗi thuần) vào ``FrameResult.warnings`` để
dễ serialize. Module này chỉ mô tả; không chứa logic đo đạc.
"""

from enum import Enum
from typing import Dict


class SignalWarning(str, Enum):
    FACE_NOT_FOUND   = "FACE_NOT_FOUND"     # Không phát hiện mặt
    FACE_TOO_SMALL   = "FACE_TOO_SMALL"     # Mặt quá xa camera
    TOO_DARK         = "TOO_DARK"           # Thiếu sáng
    TOO_BRIGHT       = "TOO_BRIGHT"         # Cháy sáng / lóa
    LIGHT_UNSTABLE   = "LIGHT_UNSTABLE"     # Ánh sáng dao động (flicker / bật tắt đèn)
    MOTION_HIGH      = "MOTION_HIGH"        # Đầu / mặt di chuyển nhiều
    LOW_FPS          = "LOW_FPS"            # FPS thực tế dưới mức khuyến nghị
    TIME_GAP         = "TIME_GAP"           # Đứt đoạn timestamp, buffer đã reset
    ARTIFACT_DETECTED = "ARTIFACT_DETECTED"  # Frame bị loại do đột biến


class WarningSeverity(str, Enum):
    INFO  = "info"    # Chỉ thông báo
    WARN  = "warn"    # Chất lượng có thể giảm
    BLOCK = "block"   # Tín hiệu window hiện tại không nên tin cậy


SEVERITY: Dict[SignalWarning, WarningSeverity] = {
    SignalWarning.FACE_NOT_FOUND:    WarningSeverity.BLOCK,
    SignalWarning.FACE_TOO_SMALL:    WarningSeverity.WARN,
    SignalWarning.TOO_DARK:          WarningSeverity.WARN,
    SignalWarning.TOO_BRIGHT:        WarningSeverity.WARN,
    SignalWarning.LIGHT_UNSTABLE:    WarningSeverity.WARN,
    SignalWarning.MOTION_HIGH:       WarningSeverity.BLOCK,
    SignalWarning.LOW_FPS:           WarningSeverity.WARN,
    SignalWarning.TIME_GAP:          WarningSeverity.INFO,
    SignalWarning.ARTIFACT_DETECTED: WarningSeverity.INFO,
}

# Gợi ý hành động cho người dùng (chỉ là văn bản mô tả; UI do người khác quyết định).
MESSAGE_VI: Dict[SignalWarning, str] = {
    SignalWarning.FACE_NOT_FOUND:    "Không thấy khuôn mặt, hãy nhìn thẳng vào camera.",
    SignalWarning.FACE_TOO_SMALL:    "Khuôn mặt quá xa, hãy lại gần camera hơn.",
    SignalWarning.TOO_DARK:          "Ánh sáng quá yếu, hãy di chuyển đến nơi sáng hơn.",
    SignalWarning.TOO_BRIGHT:        "Ánh sáng quá chói, hãy tránh nguồn sáng trực tiếp.",
    SignalWarning.LIGHT_UNSTABLE:    "Ánh sáng đang thay đổi, hãy giữ nguồn sáng ổn định.",
    SignalWarning.MOTION_HIGH:       "Bạn đang di chuyển nhiều, hãy giữ yên đầu.",
    SignalWarning.LOW_FPS:           "Camera đang chạy chậm, hãy đóng ứng dụng khác hoặc đổi thiết bị.",
    SignalWarning.TIME_GAP:          "Luồng hình ảnh bị gián đoạn, hệ thống đang đo lại.",
    SignalWarning.ARTIFACT_DETECTED: "Phát hiện nhiễu đột ngột, khung hình đã bị bỏ qua.",
}


def severity_of(code: str) -> WarningSeverity:
    """Mức nghiêm trọng của một mã cảnh báo (chuỗi hoặc enum). Mã lạ → INFO."""
    try:
        return SEVERITY[SignalWarning(code)]
    except ValueError:
        return WarningSeverity.INFO


def has_blocking(codes) -> bool:
    """True nếu trong danh sách có ít nhất một cảnh báo mức BLOCK."""
    return any(severity_of(c) is WarningSeverity.BLOCK for c in (codes or ()))
