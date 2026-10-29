# AIVitals Signal Engine — Benchmark Suites & Research Scripts

Thư mục này chứa toàn bộ các kịch bản đo kiểm hiệu năng (Latency), độ chính xác sinh học (HR / SQI), khả năng chịu lỗi (Robustness), và các bài thực nghiệm DSP vi mô trên video thực tế (`aivitals_engine/samples/vid.avi`).

---

## 1. Core Benchmark Suites (Bộ Benchmark Chính Thức — QA & Handoff)

Đây là 3 kịch bản đo kiểm cấp cao dùng để nghiệm thu tiến độ hàng tuần và bàn giao cho các bên (Vitals, Model, Frontend):

| Script | Mục tiêu & Phạm vi | Tuần nghiệm thu |
| :--- | :--- | :--- |
| **[`bench_week8_device_matrix_qa.py`](bench_week8_device_matrix_qa.py)** | **Device Matrix QA Sign-off**: Đo kiểm ma trận 6 cấu hình thiết bị/camera (HD Desktop, Laptop 30fps, Mobile QVGA 24fps, High-FPS 60fps, Jitter VFR, Throttled 15fps) trên toàn bộ video thật. | **Tuần 8 (Official)** |
| **[`bench_week7_robustness_guard.py`](bench_week7_robustness_guard.py)** | **Robustness & Feature Guard**: Đo overhead của cơ chế cảnh báo môi trường (Warning Codes) và cổng kiểm duyệt đặc trưng BVP (`extract_checked`). | **Tuần 7 (Official)** |
| **[`bench_engine_performance.py`](bench_engine_performance.py)** | **Engine Benchmark Suite**: Đo độ trễ pipeline thời gian thực (POS/CHROM/GREEN, Multi-ROI) và kiểm thử 5 trường hợp lỗi biên (Face Lost, Jitter, Low Light, Skin Artifact,...). | **Tuần 6 (Official)** |

### Cách chạy:
```bash
# 1. Chạy nghiệm thu ma trận thiết bị Tuần 8 (mặc định toàn bộ video hoặc -d 10 cho 10s)
python scripts/benchmarks/bench_week8_device_matrix_qa.py -d 10

# 2. Chạy nghiệm thu cơ chế bảo vệ Tuần 7
python scripts/benchmarks/bench_week7_robustness_guard.py

# 3. Chạy tổng phổ hiệu năng Engine Tuần 6
python scripts/benchmarks/bench_engine_performance.py
```

---

## 2. Research & Micro-Benchmarks (Thực Nghiệm & Tối Ưu Hóa Vi Mô)

Các script dưới đây phục vụ quá trình nghiên cứu, khảo sát tham số toán học và tối ưu thuật toán DSP trong các tuần 4-5:

| Script | Nội dung nghiên cứu |
| :--- | :--- |
| **[`profile_process_frame.py`](profile_process_frame.py)** | Profiling chi tiết thời gian thực thi (ms) của từng bước trong `RealtimeSignalPipeline.process_frame`. |
| **[`bench_feature_extractor.py`](bench_feature_extractor.py)** | Đo latency và độ ổn định của bộ trích xuất 23 đặc trưng hình thái / phổ tần số BVP. |
| **[`bench_filter_edge.py`](bench_filter_edge.py)** | Đánh giá hiện tượng méo biên (boundary artifacts) khi áp dụng bộ lọc Butterworth bandpass. |
| **[`bench_periodicity_sqi.py`](bench_periodicity_sqi.py)** | Tinh chỉnh thuật toán đo tính tuần hoàn (PerSQI) dựa trên Autocorrelation function. |
| **[`bench_cross_roi_methods.py`](bench_cross_roi_methods.py)** | So sánh tương quan chéo sóng mạch giữa các vùng da: Trán, Má Trái, Má Phải. |
| **[`bench_sqi_window_length.py`](bench_sqi_window_length.py)** | Khảo sát tương quan giữa độ dài cửa sổ tín hiệu (4s, 6s, 8s, 10s) và chất lượng SQI. |
| **[`bench_sub_roi_cost.py`](bench_sub_roi_cost.py)** | Đo đạc chi phí CPU khi trích xuất nhiều vùng ROI con đồng thời. |
| **[`bench_step4b_comprehensive.py`](bench_step4b_comprehensive.py)** | Kiểm thử tổng hợp các chỉ số SQI (SNR, PerSQI, Skewness, Kurtosis, Zero-crossing). |
| **[`regression_check_bvp.py`](regression_check_bvp.py)** | Kiểm tra hồi quy hình dạng sóng BVP để đảm bảo không bị sai lệch biên độ/pha sau khi cập nhật DSP. |
