"""
aivitals_engine/face/landmarks.py
=================================
Định nghĩa chỉ số các điểm mốc giải phẫu (Facial Landmark Indices)
thuộc mô hình MediaPipe Face Mesh (468 điểm 3D).

Cơ sở giải phẫu y sinh cho rPPG (Cardiovascular ROI Selection):
    1. Vùng Trán (Forehead):
       - Nằm dưới đường chân tóc và nằm trên cung lông mày.
       - Tín hiệu mạch máu trán rất mạnh do có động mạch trên ròng rọc
         (Supratrochlear artery) và động mạch trên ổ mắt (Supraorbital artery).
       - Chỉ số mốc: 10, 67, 109, 108, 151, 337, 338, 297.

    2. Vùng Má Trái (Left Cheek - theo góc nhìn camera):
       - Nằm dưới hốc mắt và nằm ngoài cánh mũi/khóe miệng.
       - Chứa mạng lưới mao mạch động mạch mặt (Facial artery).
       - Chỉ số mốc: 116, 117, 118, 123, 147, 187, 205, 207.

    3. Vùng Má Phải (Right Cheek - theo góc nhìn camera):
       - Đối xứng với má trái.
       - Chỉ số mốc: 345, 346, 347, 352, 376, 411, 425, 427.
"""
from typing import Tuple

# Chỉ số các điểm mốc tạo thành đa giác vùng Trán
FOREHEAD_LANDMARKS: Tuple[int, ...] = (
    10, 67, 109, 108, 151, 337, 338, 297
)

# Chỉ số các điểm mốc tạo thành đa giác vùng Má Trái (theo góc nhìn ảnh)
LEFT_CHEEK_LANDMARKS: Tuple[int, ...] = (
    116, 117, 118, 123, 147, 187, 205, 207
)

# Chỉ số các điểm mốc tạo thành đa giác vùng Má Phải (theo góc nhìn ảnh)
RIGHT_CHEEK_LANDMARKS: Tuple[int, ...] = (
    345, 346, 347, 352, 376, 411, 425, 427
)

# Tập hợp tất cả các điểm mốc sub-ROI
ALL_ROI_LANDMARKS: Tuple[int, ...] = (
    FOREHEAD_LANDMARKS + LEFT_CHEEK_LANDMARKS + RIGHT_CHEEK_LANDMARKS
)
