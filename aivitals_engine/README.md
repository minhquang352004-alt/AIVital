# AIVitals Engine — Module Xử Lý Tín Hiệu & Sinh Hiệu (rPPG Core & Vitals)

> **Dự án:** AIVitals — Hệ thống đo lường sinh hiệu y tế không tiếp xúc thời gian thực (rPPG V1)  
> **Kiến trúc Monorepo:** Tầng tính toán xác định (Deterministic Signal & Clinical AI) chạy độc lập, cung cấp dữ liệu sinh hiệu đã kiểm định cho Backend & Frontend.

---

## 1. Phân Định Trách Nhiệm & Ranh Giới Kỹ Thuật (Module Ownership)

Hệ thống `aivitals_engine` được tổ chức thành 2 tầng xử lý khép kín, phân định ranh giới chức năng rõ ràng giữa **Thượng nguồn (Signal)** và **Hạ nguồn (Vitals)**:

```text
Camera / Video Stream
        │
┌───────▼────────────────────────────────────────────────────────────────────────┐
│  TẦNG THƯỢNG NGUỒN: CORE SIGNAL & rPPG ENGINE (Phụ trách: Hoàng Khang)         │
│  • Face Detection & Tracking (Google MediaPipe 478 landmarks / Haar Fallback) │
│  • Polygon Sub-ROI & Lọc màu da YCrCb (Trán + 2 Gò má)                        │
│  • Cửa sổ trượt thời gian thực (SlidingWindowBuffer 8.0s @ 30 FPS, Resampling)│
│  • Thuật toán rPPG cốt lõi: POS, CHROM, GREEN                                 │
│  • Cổng chất lượng tín hiệu đa chiều (Quality Gate: SNR, Periodicity, Motion) │
│  • Trích xuất 23 đặc trưng sinh lý hình thái học BVP (BVPFeatureExtractor)    │
└───────┬────────────────────────────────────────────────────────────────────────┘
        │ Sóng BVP đã lọc + SQI + 23 BVP Features
┌───────▼────────────────────────────────────────────────────────────────────────┐
│  TẦNG HẠ NGUỒN: VITALS ESTIMATION & CLINICAL AI (Phụ trách: Khoa)             │
│  • Ước lượng chỉ số sinh tồn: Nhịp tim (HR), Biến thiên tim (HRV), Nhịp thở (RR)│
│  • Kiểm định sinh lý y tế (Range validation, Sudden-jump guard)              │
│  • Nghiên cứu mô hình huyết áp (Blood Pressure baseline & Deep models)        │
│  • Đóng gói Hợp đồng dữ liệu JSON chuẩn mực bàn giao cho Frontend & Backend   │
└───────────────────────────────────────────────────────────────────────────────┘
```

| Tầng xử lý | Người phụ trách | Modules đảm nhiệm | Trách nhiệm chính |
| :--- | :--- | :--- | :--- |
| **Upstream (Signal Core)** | **Khang** | `face/`, `roi/`, `signal/`, `rppg/`, `quality/`, `features/`, `signal_pipeline_realtime.py`, `scripts/benchmarks/` | Biến đổi video thô thành sóng BVP chuẩn y tế, kiểm soát chất lượng tín hiệu (SQI), trích xuất 23 đặc trưng BVP (<3ms) và đo kiểm hiệu năng/độ bền hệ thống. |
| **Downstream (Vitals & Clinical)** | **Khoa** | `vitals/`, `validation/`, `models/`, `integration/`, `scripts/run_vitals_pipeline.py`, `scripts/run_bp_baseline.py` | Tiêu thụ sóng BVP và 23 đặc trưng BVP để tính HR, HRV, RR, huyết áp thử nghiệm, kiểm định sai số y tế và chuẩn hóa schema JSON. |

---

## 2. Cấu Trúc Cây Thư Mục Module

```text
aivitals_engine/
├── config/                 # Cấu hình hệ thống chung (SignalConfig, ROIConfig, FaceDetectorConfig)
├── face/                   # [Khang] Nhận diện mặt (MediaPipeFaceDetector 3D & HaarCascadeFaceDetector)
├── roi/                    # [Khang] Trích xuất vùng da mao mạch (Polygon Convex Hull & Lọc da YCrCb)
├── signal/                 # [Khang] Tiền xử lý tín hiệu & SlidingWindowBuffer (8s, Resampling, Outlier guard)
├── rppg/                   # [Khang] Bộ 3 thuật toán rPPG cốt lõi (POS, CHROM, GREEN)
├── quality/                # [Khang] Quality Gate đa chiều (SNR SQI, Periodicity ACF, Cross-ROI, Motion)
├── features/               # [Khang] Trích xuất 23 đặc trưng sinh lý BVP (Tuần 5, <3ms latency budget)
├── signal_pipeline_realtime.py # [Khang] Pipeline điều phối xử lý tín hiệu thời gian thực
│
├── vitals/                 # [Khoa] Ước lượng sinh hiệu (HR FFT/Peak, HRV RMSSD/SDNN, Respiration RR)
├── validation/             # [Khoa] Kiểm định ngưỡng y tế lâm sàng & Đánh giá sai số (MAE, RMSE, Pearson)
├── models/                 # [Khoa] Mô hình dự đoán huyết áp baseline & Deep Learning V2
├── integration/            # [Khoa] Bộ chuyển đổi dữ liệu và ánh xạ JSON cho Frontend
│
├── models/face_landmarker.task # Trọng số mô hình Google MediaPipe Face Mesh
├── samples/                # Video mẫu phục vụ kiểm thử (vid.avi, sample_video.mp4)
├── outputs/                # Thư mục lưu trữ kết quả sóng BVP (.csv) và báo cáo benchmark
└── scripts/                # Các công cụ dòng lệnh thực thi và kiểm thử
```

---

## 3. Hướng Dẫn Chạy Kiểm Thử (Runners & Testing Guide)

### 3.1. Dành cho phần của Khang (Core Signal & rPPG Engine)

#### A. Mô phỏng Camera Stream trên video (`run_signal_pipeline.py`)
Kiểm tra luồng xử lý từ Frame $\to$ MediaPipe $\to$ Đa giác ROI $\to$ Sóng BVP $\to$ SQI:
```powershell
# 1. Test nhanh 15 giây đầu với thuật toán POS (mặc định)
python aivitals_engine/scripts/run_signal_pipeline.py --video aivitals_engine/samples/vid.avi --max-sec 15

# 2. So sánh đồng thời cả 3 thuật toán (POS, CHROM, GREEN)
python aivitals_engine/scripts/run_signal_pipeline.py --video aivitals_engine/samples/vid.avi --all-methods --max-sec 15

# 3. Chạy toàn bộ video (Full 84 giây)
python aivitals_engine/scripts/run_signal_pipeline.py --video aivitals_engine/samples/vid.avi
```

#### B. Benchmark Đo kiểm Hiệu năng & Khảo sát 5 Tình huống Lỗi Tuần 6 (`bench_engine_performance.py`)
Đo đạc FPS, Latency p95, tải CPU/RAM, Single-ROI vs Multi-ROI và kiểm định độ bền khi mất mặt, chói sáng, thiếu sáng:
```powershell
# Chạy benchmark nhanh (10 giây mỗi test)
python scripts/benchmarks/bench_engine_performance.py --video aivitals_engine/samples/vid.avi --quick --save-docs

# Chạy benchmark toàn diện và cập nhật báo cáo nghiệm thu chính thức
python scripts/benchmarks/bench_engine_performance.py --video aivitals_engine/samples/vid.avi --full --save-docs
```
*(Báo cáo tự động lưu vào [`docs/ENGINE_BENCHMARK.md`](../docs/ENGINE_BENCHMARK.md)).*

#### C. Chạy Unit Tests riêng cho tầng Signal
```powershell
# Kiểm tra Pipeline thời gian thực
python -m pytest tests/test_signal_pipeline_realtime.py -v

# Kiểm tra MediaPipe Detector & Đa giác ROI
python -m pytest tests/face/test_mediapipe_detector.py tests/roi/test_polygon_roi.py -v

# Kiểm tra Lọc pixel da YCrCb
python -m pytest tests/roi/test_skin_filter.py -v

# Kiểm tra Trích xuất 23 đặc trưng BVP (<3ms latency budget)
python -m pytest tests/features/test_bvp_feature_extractor.py -v
```

---

### 3.2. Dành cho phần của Khoa (Vitals, Validation & Blood Pressure)

#### A. Chạy toàn trình tích hợp Vitals $\to$ JSON Frontend (`run_vitals_pipeline.py`)
Tiêu thụ sóng BVP từ pipeline của Khang để tính toán sinh hiệu và xuất JSON:
```powershell
python aivitals_engine/scripts/run_vitals_pipeline.py --video aivitals_engine/samples/vid.avi --max-sec 30
```

#### B. Chạy mô hình Baseline Huyết áp (`run_bp_baseline.py`)
Huấn luyện và đánh giá mô hình hồi quy Ridge trên bộ đặc trưng BVP:
```powershell
python aivitals_engine/scripts/run_bp_baseline.py --subjects 100 --folds 5
```

---

### 3.3. Chạy Toàn Bộ Test Suite Dự Án (All 350+ Tests)
```powershell
python -m pytest tests -q
```

---

## 4. Hướng Dẫn Tích Hợp Code (Python Developer API)

### 4.1. Khởi tạo Pipeline và Xử lý từng Frame
```python
import cv2
import time
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

# Khởi tạo pipeline (mặc định POS + MediaPipe Face Mesh)
pipeline = RealtimeSignalPipeline(method="POS")

cap = cv2.VideoCapture("aivitals_engine/samples/vid.avi")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Gửi từng frame BGR cùng timestamp vào pipeline
    result = pipeline.process_frame(frame, timestamp=time.perf_counter())

    if result.status == "FACE_LOST":
        print("Cảnh báo: Không tìm thấy mặt!")
    elif result.status == "ARTIFACT":
        print("Cảnh báo: Khung hình bị rung giật hoặc lóa sáng!")
    elif result.is_ready:
        print(f"BVP Ready | SQI: {result.quality_sqi:.3f} | BBox: {result.bbox}")
        bvp_waveform = result.bvp_signal  # np.ndarray dạng sóng BVP (8 giây)
```

### 4.2. Hợp đồng Giao tiếp: Trích xuất 23 Đặc trưng BVP bàn giao cho Hạ nguồn
```python
# Khi buffer sẵn sàng (is_ready == True), gọi trích xuất đặc trưng cho mô hình của Khoa:
features = pipeline.extract_features()

if features is not None:
    feature_dict = features.to_feature_dict()
    print(f"Trích xuất thành công 23 đặc trưng (Độ trễ <3ms):")
    print(f"• Rise Time: {features.rise_time_mean_ms:.2f} ms")
    print(f"• Stiffness Index: {features.stiffness_index:.2f}")
    print(f"• IBI SDNN: {features.ibi_sdnn_ms:.2f} ms")
```
