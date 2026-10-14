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

## 3. Adapter (Tuần 6)

`aivitals_engine/models/deep/adapter.py`:

| Thành phần | Vai trò |
|---|---|
| `DeepRPPGAdapter` | Nhận `FramePacket` có `face_crop`, giữ đủ `chunk_frames`, dựng input theo spec, chạy model, trả `BVPWindow` để đi tiếp `VitalsService` như GREEN / CHROM / POS |
| `TorchInferenceRunner` / `OnnxInferenceRunner` | Chạy model PyTorch hoặc ONNX (tự chọn GPU nếu có) |
| `resample_frames` | Camera lệch quá 10% so với 30 fps thì nội suy chuỗi frame về 30 fps trước khi đưa vào model |
| `stride_frames` | Chỉ chạy lại model sau mỗi bước trượt (mặc định 1 giây), giữa hai lần trả lại kết quả cũ để giảm tải |

Khung `BaseNeuralRPPGModel` của Khang (`models/base.py`) nhận RGB trung bình theo ROI nên không đủ cho model deep (cần ảnh mặt 72×72); vì vậy deep model đi qua `DeepRPPGAdapter` với face crop.

```python
from aivitals_engine.models.deep import DEEP_MODEL_SPECS, DeepRPPGAdapter, TorchInferenceRunner
from aivitals_engine.models.registry import ModelRegistry

registry = ModelRegistry("model_store")
entry = registry.latest("tscan")
weights_path = registry.verify(entry)
adapter = DeepRPPGAdapter(DEEP_MODEL_SPECS["tscan"], TorchInferenceRunner(module), entry.version, entry.checksum_sha256)
```

## 4. Model registry, checksum và hiệu chỉnh confidence (Tuần 6)

- `models/registry.py`: lưu `model_registry.json` (ghi nguyên tử), mỗi model có `name`, `version` (semver), `kind`, `status` (experimental → research_only → validated → production → deprecated), `checksum_sha256`, `dataset_version`, `metrics`. `verify()` tính lại SHA-256, sai thì báo `ChecksumMismatchError`; artifact phải nằm trong thư mục registry.
- `models/calibration.py`: `ConfidenceCalibrator` (isotonic) học từ confidence thô và sai số HR, đánh giá bằng ECE; nạp kèm checksum. `VitalsService(confidence_calibrator=...)` áp dụng cho confidence nhịp tim.
- Báo cáo benchmark: `python aivitals_engine/scripts/run_model_benchmark.py` → `docs/VitalsEngine/MODEL_BENCHMARK_REPORT.md` (sai số HR theo kịch bản / trạng thái / mức confidence, hiệu chỉnh confidence, baseline huyết áp, trạng thái deep model). Model sinh ra được đăng ký vào registry; baseline huyết áp chỉ được đăng ký khi qua gate dữ liệu.

## 5. Việc còn lại

- Có trọng số pretrained và code kiến trúc mạng (kiểm tra license).
- Khang bổ sung face crop vào `FrameResult` để adapter chạy realtime.
- Đo độ chính xác deep model so với GREEN / CHROM / POS khi có trọng số và dữ liệu thật.
