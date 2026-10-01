# DEEP_MODEL_ADAPTER_PLAN (K2.5 – Khoa)

Mục tiêu: biết model deep rPPG nào nên tích hợp trước, model nào chỉ dùng cho benchmark / nghiên cứu.

- Spec dạng code: `aivitals_engine/models/deep/specs.py`
- Tiền xử lý frame: `aivitals_engine/models/deep/preprocessing.py`
- Bản JSON: `aivitals_engine/contracts/schemas/deep_model_adapter_plan.json`

## 1. Bảng so sánh

Thông số theo cấu hình phổ biến của rPPG-Toolbox (UBFC / PURE). Latency và độ chính xác trên dữ liệu AIVitals **chưa đo** vì chưa có trọng số.

| Ưu tiên | Model | Input | Layout tensor | Output | Frame | Chunk | Frame depth | Tài nguyên | Phân loại |
|---|---|---|---|---|---|---|---|---|---|
| 1 | TS-CAN | DiffNormalized + Standardized (6 kênh) | `(T, 6, 72, 72)` | Đạo hàm xung | 72×72 | 180 (6 giây @ 30 fps) | 10 | CNN 2D + temporal shift, chạy được CPU | Realtime candidate |
| 2 | EfficientPhys | Standardized (3 kênh) | `(T, 3, 72, 72)` | Đạo hàm xung | 72×72 | 180 | 10 | CNN 2D nhẹ | Realtime candidate |
| 3 | DeepPhys | DiffNormalized + Standardized | `(T, 6, 72, 72)` | Đạo hàm xung | 72×72 | 180 | – | CNN 2D hai nhánh | Benchmark only |
| 4 | PhysNet | DiffNormalized (3 kênh) | `(1, 3, T, 72, 72)` | Xung BVP | 72×72 | 128 | – | 3D CNN, nên có GPU | Benchmark only |

## 2. Lý do phân loại

- **TS-CAN:** thiết kế cho on-device, xử lý theo frame nên hợp với sliding window realtime.
- **EfficientPhys:** chỉ cần frame chuẩn hóa, dễ ghép với face crop.
- **DeepPhys:** baseline deep kinh điển, TS-CAN là bản cải tiến trực tiếp; dùng làm mốc so sánh.
- **PhysNet:** 3D CNN phải chờ đủ 128 frame mới suy luận, độ trễ lớn; hợp với benchmark offline.

## 3. Cách tích hợp vào repo nhóm

| Hạng mục | Yêu cầu |
|---|---|
| Lớp cơ sở | Kế thừa `BaseNeuralRPPGModel` của Khang (`models/base.py`), cài `load_weights`, `predict` |
| Input | Face crop RGB 72×72 từ khối face/ROI của Khang (pipeline hiện chỉ trả RGB trung bình theo ROI, cần thêm crop) |
| Tiền xử lý | `build_representation()` → `to_model_layout()` theo `layout` và `frame_depth` của spec |
| FPS | 30 fps ổn định; camera khác 30 fps phải resample trước vì model train ở 30 fps |
| Output | `restore_pulse()` đổi đạo hàm xung về BVP, sau đó đi vào `VitalsService` như GREEN / CHROM / POS |
| Trọng số / license | Kiểm tra license của kiến trúc và trọng số pretrained trước khi đưa vào sản phẩm |

## 4. Việc còn lại

- Có trọng số pretrained và code kiến trúc mạng.
- Khang bổ sung face crop vào `FrameResult`.
- Chạy benchmark so với GREEN / CHROM / POS bằng `python -m aivitals_engine.benchmark`.
