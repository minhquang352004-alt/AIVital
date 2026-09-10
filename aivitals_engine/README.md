# AIVitals Engine - Signal & rPPG Module

Hệ thống trích xuất và xử lý tín hiệu xung mạch quang học từ xa (**rPPG - Remote Photoplethysmography**) từ Video/Camera và dữ liệu RGB phục vụ đo lường sinh hiệu không tiếp xúc (**AIVitals**).

---

## 1. Kiến trúc Pipeline tổng quan

```text
Input Video / RGB Sample (.mp4 / .csv)
        ↓
Face Detection & Sub-ROI Extraction (Trán + 2 bên Má -> Mean RGB)
        ↓
Signal Preprocessing (Linear Resampling FPS, Detrending, Butterworth Bandpass Filter)
        ↓
rPPG Transformation (POS / CHROM / GREEN)
        ↓
BVP Output Waveform (Blood Volume Pulse)
        ↓
Signal Quality Index (SQI & SNR: 0.0 ~ 1.0)
        ↓
Downstream Vitals Estimation (Heart Rate: FFT / Peak Detection)
```

---

## 2. Cấu trúc Module chuẩn hóa (9 Modules)

Toàn bộ project được cấu trúc thành 9 module chuyên biệt, độc lập và dễ bảo trì:

```text
aivitals_engine/
├── config/             # 1. Cấu hình tham số sinh lý (fps, window_sec, cutoffs 0.75-2.5Hz)
│   ├── __init__.py
│   └── settings.py
├── face/               # 2. Phát hiện khuôn mặt (Haar Cascade & Center Fallback)
│   ├── __init__.py
│   └── detector.py
├── roi/                # 3. Trích xuất vùng mao mạch da (Trán + 2 Má) -> Vector RGB
│   ├── __init__.py
│   └── extractor.py
├── signal/             # 4. Tiền xử lý tín hiệu
│   ├── __init__.py
│   ├── detrend.py      # Khử trôi đường cơ sở (Smoothness Priors Detrending, λ=100)
│   ├── filter.py       # Bộ lọc thông dải Butterworth 2 chiều zero-phase
│   ├── resample.py     # Nội suy tuyến tính xử lý trôi FPS của webcam
│   ├── preprocess.py   # Pipeline tiền xử lý RGB
│   └── reader.py       # Tự động đọc và parse Video (.mp4/.avi) hoặc CSV (.csv)
├── rppg/               # 5. Các thuật toán rPPG cốt lõi
│   ├── __init__.py
│   ├── base.py         # Interface chuẩn RPPGMethod (reset, update, get_signal, get_quality)
│   ├── pos.py          # Thuật toán POS (Wang et al., 2017 - Khuyên dùng mặc định)
│   ├── chrom.py        # Thuật toán CHROM (de Haan & Jeanne, 2013)
│   └── green.py        # Thuật toán GREEN (Verkruysse et al., 2008)
├── vitals/             # 6. Tính toán sinh hiệu từ sóng BVP (Khoa phụ trách)
│   ├── __init__.py
│   ├── hr.py           # Ước lượng nhịp tim (HR)
│   ├── hrv.py          # Ước lượng biến thiên nhịp tim (RMSSD, SDNN)
│   └── rr.py           # Ước lượng nhịp thở (RR)
├── quality/            # 7. Đánh giá chất lượng tín hiệu BVP
│   ├── __init__.py
│   └── sqi.py          # Tự suy phổ (Self-supervised SNR) và chuẩn hóa SQI (0.0 ~ 1.0)
├── validation/         # 8. Kiểm tra tính hợp lệ & sai số (Khoa phụ trách)
│   ├── __init__.py
│   ├── validator.py    # Quality gate: kiểm tra range sinh lý, sudden-jump, window
│   └── metrics.py      # Đánh giá sai số so với nhãn chuẩn: MAE, RMSE, Pearson
├── models/             # 9. Khung giao diện trừu tượng cho Deep Learning Models (V2)
│   ├── __init__.py
│   └── base.py         # BaseNeuralRPPGModel (PhysNet, DeepPhys, TS-CAN...)
├── samples/            # Dữ liệu mẫu kiểm thử
│   ├── sample_rgb.csv  # 900 mẫu RGB (30s @ 30 Hz)
│   └── sample_video.mp4# Video giả lập 300 frames (10s @ 30 FPS)
├── outputs/            # Thư mục lưu các file sóng BVP kết quả (.csv)
├── pipeline.py         # Lớp điều phối SignalRPPGPipeline
└── main.py             # Script kiểm thử đầu-cuối (CLI Test Runner)
```

---

## 3. Cài đặt & Chuẩn bị Môi trường

Dự án sử dụng Python 3.8+ và các thư viện xử lý tín hiệu lõi nhẹ:

```bash
# 1. Di chuyển vào thư mục dự án
cd AIVital

# 2. Khởi tạo môi trường ảo (virtual environment)
python3 -m venv .venv
# Hoặc trên Windows: python -m venv .venv

# 3. Kích hoạt môi trường ảo
source .venv/bin/activate
# Hoặc trên Windows: .venv\Scripts\activate

# 4. Cài đặt dependencies cần thiết
pip install -r aivitals_engine/requirements.txt
```

---

## 4. Hướng dẫn Chạy Kiểm thử (Test Runner)

Script `main.py` hỗ trợ tùy chọn thuật toán qua tham số `--method` (`POS`, `CHROM`, `GREEN`, hoặc `ALL`):

### 4.1. Chạy với thuật toán POS (Khuyên dùng - Kháng nhiễu tốt nhất):
```bash
# Chạy với dữ liệu mẫu RGB:
python -m aivitals_engine.main --input aivitals_engine/samples/sample_rgb.csv --method POS

# Chạy với dữ liệu mẫu Video:
python -m aivitals_engine.main --input aivitals_engine/samples/sample_video.mp4 --method POS
```

### 4.2. Chạy baseline so sánh cả 3 thuật toán (Mặc định):
Khi không chỉ định `--method`, chương trình sẽ tự động chạy cả 3 thuật toán `POS`, `CHROM`, `GREEN` để so sánh:
```bash
python -m aivitals_engine.main --input aivitals_engine/samples/sample_rgb.csv
```

### 4.3. Chạy với video bất kỳ bên ngoài (hoặc dataset UBFC-rPPG):
```bash
python -m aivitals_engine.main --input /path/to/your_video.mp4 --method POS
```

### Kết quả đầu ra:
1. **Thông tin hiển thị trên Terminal**:
   * Tần số lấy mẫu (`sampling_rate`).
   * Độ dài chuỗi mẫu BVP (`BVP samples`).
   * Chỉ số chất lượng tín hiệu (`Quality: 0.0 ~ 1.0`).
2. **Các file sóng BVP kết quả** được lưu tại thư mục `aivitals_engine/outputs/`:
   * `pos_bvp.csv`
   * `chrom_bvp.csv`
   * `green_bvp.csv`
3. **File ghi lại metadata tổng hợp (sampling rate, method, quality)**:
   * `baseline_summary.csv` (dạng bảng đối soát)
   * `baseline_summary.json` (dạng JSON máy đọc)

---

## 5. Hướng dẫn Tích hợp Code (Python API)

### 5.1. Chạy Pipeline trích xuất BVP từ Video/RGB
```python
from aivitals_engine import SignalRPPGPipeline

# Khởi tạo pipeline
pipeline = SignalRPPGPipeline(fps=30.0)

# Chạy thuật toán POS trên file Video hoặc CSV
result = pipeline.run_on_file("aivitals_engine/samples/sample_video.mp4", algorithm_name="POS")

print(f"Thuật toán: {result.method}")
print(f"Chỉ số chất lượng SQI: {result.quality:.2f}")
print(f"Chuỗi sóng BVP: {result.bvp_signal.shape}")
```

### 5.2. Tính toán Nhịp tim (Heart Rate - BPM) từ BVP
*(Hàm tính HR kế thừa từ `rPPG-Toolbox/evaluation/post_process.py`; các hàm HRV và RR là skeleton interface chuẩn bị cho Khoa phát triển tiếp theo Task K2.1 vì `rPPG-Toolbox` chưa hỗ trợ theo `SOURCE_AUDIT.md`)*

```python
from aivitals_engine.vitals import calculate_fft_hr, calculate_peak_hr

# 1. Ước lượng nhịp tim qua biến đổi Fourier (FFT Periodogram) - REUSE từ rPPG-Toolbox
hr_fft = calculate_fft_hr(result.bvp_signal, fs=result.sampling_rate)
print(f"Nhịp tim (FFT): {hr_fft:.1f} BPM")

# 2. Ước lượng nhịp tim qua phát hiện đỉnh sóng (Peak Detection) - REUSE từ rPPG-Toolbox
hr_peak = calculate_peak_hr(result.bvp_signal, fs=result.sampling_rate)
print(f"Nhịp tim (Peak): {hr_peak:.1f} BPM")

# 3. Giao diện Skeleton chuẩn bị cho Task K2.1 của Khoa:
# from aivitals_engine.vitals import calculate_hrv_from_bvp, calculate_respiration_rate
# hrv_metrics = calculate_hrv_from_bvp(result.bvp_signal, fs=result.sampling_rate)
# rr = calculate_respiration_rate(result.bvp_signal, fs=result.sampling_rate)
```

### 5.3. Đánh giá sai số với nhãn thiết bị y tế (Validation & Quality Gate)
*(Hàm metrics kế thừa từ `rPPG-Toolbox/evaluation/metrics.py`; class `VitalsValidator` là skeleton interface cho Task K2.3 của Khoa)*

```python
from aivitals_engine.validation import evaluate_vital_predictions

# 1. Đánh giá sai số thống kê so với nhãn chuẩn y tế (Ground Truth) - REUSE từ rPPG-Toolbox
predicted_hrs = [72.0, 75.5, 68.0]
ground_truth_hrs = [71.0, 74.0, 69.0]

metrics = evaluate_vital_predictions(predicted_hrs, ground_truth_hrs)
print(f"MAE: {metrics['MAE']:.2f} BPM, RMSE: {metrics['RMSE']:.2f}, Pearson: {metrics['Pearson']:.2f}")

# 2. Quality Gate Framework chuẩn bị cho Task K2.3 của Khoa:
# from aivitals_engine.validation import VitalsValidator
# validator = VitalsValidator(max_hr_jump=25.0)
# report = validator.validate_vitals(hr=hr_fft, bvp_signal=result.bvp_signal, fs=result.sampling_rate)
```

---

## 6. Tiêu chí Đánh giá Chất lượng Tín hiệu (SQI)

* **SQI $\ge$ 0.70**: Tín hiệu BVP rõ nét, chu kỳ tim ổn định $\rightarrow$ Kết quả đo rất tin cậy.
* **0.40 $\le$ SQI $<$ 0.70**: Tín hiệu trung bình, có nhiễu nhẹ do ánh sáng hoặc cử động nhẹ $\rightarrow$ Chấp nhận được.
* **SQI $<$ 0.40**: Tín hiệu kém, nhiễu nặng $\rightarrow$ Cảnh báo người dùng ngồi im hoặc cải thiện góc sáng.
