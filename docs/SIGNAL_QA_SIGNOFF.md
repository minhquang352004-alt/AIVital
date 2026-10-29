# Signal QA Sign-off & Algorithm Freeze — Tuần 8 (Khang)

**Owner:** Khang (Coding / AI Signal)  
**Phạm vi:** Kiểm thử đơn vị & tích hợp toàn diện (`tests/`), đánh giá Ma trận Thiết bị (`Device Matrix`) trực tiếp trên video thực tế (`aivitals_engine/samples/vid.avi`), khắc phục lỗi tồn đọng rPPG/ROI/SQI và đóng băng phiên bản thuật toán (`Algorithm Version Freeze v1.0.0`).  
**Trạng thái nghiệm thu:** **SIGNED_OFF** (Sẵn sàng tích hợp Production Candidate).

---

## 1. Ma Trận Kiểm Thử Thiết Bị & Cấu Hình Camera Trên Video Thực Tế (`vid.avi`)

Đánh giá khả năng thích ứng của `RealtimeSignalPipeline` (với **Google MediaPipe Face Mesh 478 điểm**) trực tiếp trên video người thật `aivitals_engine/samples/vid.avi` qua 6 cấu hình thiết bị và điều kiện thu nhận khung hình (Nhịp tim tham chiếu cấu hình gốc Native `640×480 @ 30fps`: **$77.56\text{ BPM}$**).

> **Cấu hình đo (cập nhật 2026-10-29):** chạy `python scripts/benchmarks/bench_week8_device_matrix_qa.py` trên **toàn bộ video** (2259 frames, 78.8s, 28.67 FPS). Nhịp tim tham chiếu do chính pipeline tính trên cấu hình gốc, **không phải** từ thiết bị đo độc lập (ECG/PPG). Số liệu cũ (tham chiếu 76.90 BPM) không tái hiện lại được ở lần đo này; khi chạy với `-d 10` tham chiếu là 76.25 BPM, nên kết quả phụ thuộc vào độ dài đoạn video được đo.

| Cấu hình thiết bị (Device Profile) | Độ phân giải & FPS | Độ trễ Median (ms) | Chỉ số chất lượng (SQI) | Nhịp tim đo được (Độ lệch $\Delta\text{Ref}$) | Trạng thái & Cảnh báo | Kết quả |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. HD Desktop Webcam (CFR)** | `1280×720 @ 30fps` | 18.94 ms | 0.73 | 77.56 BPM ($\pm 0.00$) | `OK` | ✅ PASS |
| **2. Standard Laptop / Web (MVP)** | `640×480 @ 30fps` | 16.11 ms | 0.72 | 77.56 BPM ($\pm 0.00$) | `OK` | ✅ PASS |
| **3. Low-Spec Mobile / QVGA** | `320×240 @ 24fps` | 18.96 ms | 0.72 | 77.52 BPM ($\pm 0.04$) | `OK` | ✅ PASS |
| **4. High-FPS Camera (BP Mode)** | `640×480 @ 60fps` | 19.06 ms | 0.70 | 77.78 BPM ($\pm 0.22$) | `OK` | ✅ PASS |
| **5. USB Webcam VFR Jitter (±4ms)**| `640×480 @ 25fps` | 20.39 ms | 0.79 | 77.53 BPM ($\pm 0.03$) | `OK` | ✅ PASS |
| **6. Throttled Browser Tab** | `640×480 @ 15fps` | 19.79 ms | 0.73 | 78.00 BPM ($\pm 0.44$) | `OK` (`WARN: LOW_FPS`) | ✅ PASS |

**Giới hạn đã biết của phép đo:**
- Chỉ dùng **một video** (`vid.avi`, một người, 78.8s); chưa đa dạng tông da, ánh sáng, chuyển động.
- Chưa đối chiếu độ chính xác HR với thiết bị tham chiếu độc lập (ECG/PPG) — chờ Reference Dataset. Kết quả chỉ chứng minh tính nhất quán của pipeline giữa các cấu hình thiết bị, chưa phải độ chính xác lâm sàng.
- `process_frame()` end-to-end (sau khi vector hóa vòng lặp POS, 2026-10-29): median 16.4 ms, p95 21.0 ms (≈ 63% ngân sách 33.3 ms của 30 FPS). Trước tối ưu: median 22.3 ms, p95 34.8 ms (vượt ngân sách). Phần còn lại chủ yếu là MediaPipe Face Mesh (~54% thời gian mỗi frame), nằm ngoài phạm vi tối ưu DSP.

---

## 2. Tổng Hợp Sửa Lỗi Thuật Toán rPPG / ROI / SQI & Tối Ưu Hóa DSP (Tuần 8)

| Mã hạng mục | Module / File | Vấn đề kỹ thuật phát hiện | Giải pháp khắc phục & Kết quả đo kiểm trên `vid.avi` |
| :--- | :--- | :--- | :--- |
| **FIX-W8-01** | `rppg/pos.py` | Cộng chồng chập `H[m:n] += h` không chia trọng số làm biên độ 2 rìa cửa sổ bị suy hao (hình quả trám), bỏ sót mẫu `N-1`. | Chuẩn hóa trọng số chồng chập `weights[m:n]` và mở rộng vòng lặp `range(l, N+1)`. Tỷ lệ biên độ Rìa/Giữa trên `vid.avi` tăng từ **0.66 lên 1.341** ($\ge 0.75$). |
| **FIX-W8-02** | `rppg/chrom.py` | Mảng độ dài lẻ bị khuyết đoạn `0.0` ở cuối; lọc IIR trên cửa sổ con 48 mẫu gây suy hao biên độ. | Bổ sung cửa sổ neo cuối `N - win_len`, chuẩn hóa Hanning và lọc Bandpass trên toàn chuỗi `N`. Độ lệch chuẩn đuôi trên `vid.avi` đạt **0.0022 (> 0.0000)**. |
| **FIX-W8-03** | `signal/sliding_buffer.py` | `maxlen` cố định theo `target_fps=30` làm camera 60 FPS bị tràn sớm trước khi đạt `min_sec`, kẹt ở trạng thái `BUFFERING`. | Cơ chế cắt mẫu theo thời gian thực `_evict_expired(ts)` hỗ trợ tới 120 FPS. Camera 60 FPS trên `vid.avi` hoạt động mượt với độ lệch **0.00 BPM** (`SQI = 0.78`). |
| **FIX-W8-04** | `signal/detrend.py`<br>`signal/filter.py` | Giải lại ma trận thưa `spsolve` và tính lại hệ số Butterworth ở mỗi khung hình (30 lần/giây). | Cache phân rã LU thưa `splu(A)` và hệ số `(b, a)` bằng `@lru_cache`, kết hợp `padtype="odd"`. Thời gian khử trôi giảm còn **0.0091 ms/lần**. |
| **FIX-W8-05** | `signal_pipeline_realtime.py` | `QualityGate` dùng `perf_counter()` làm kết quả `ACCEPTED` dao động theo tốc độ CPU; lọt trạng thái `OK` khi nhiễu tuần hoàn. | Đồng bộ theo `timestamp` khung hình `ts`, loại bỏ lệnh gọi thừa `get_metadata()` và hạ xuống `LOW_QUALITY` khi `QualityGate` trả `REJECTED`. |

---

## 3. Danh Mục Đóng Băng Phiên Bản Thuật Toán (Frozen Algorithm Manifest)

Thông tin định danh được khóa cố định trong [`aivitals_engine/version.py`](../aivitals_engine/version.py) (`get_signal_version_manifest()`):

- **Engine & Pipeline Version:** `aivitals_engine v0.1.0` | `SIGNAL_PIPELINE_VERSION = 1.0.0`
- **Thuật toán rPPG đóng băng:**
  - `POS`: **v1.0** (*Thuật toán mặc định Production*)
  - `CHROM`: **v1.0** (*Thuật toán dự phòng kháng đổi màu ánh sáng*)
  - `GREEN`: **v1.0** (*Thuật toán cơ sở đối chuẩn tốc độ cao*)
- **Cấu hình chuẩn đóng băng (`SignalConfig`):**
  - `fps = 30.0 Hz`, `window_sec = 8.0s`, `sub_window_sec = 1.6s`, `min_window_sec = 3.0s`
  - `detrend_lambda = 100.0`, `low_cutoff_hz = 0.75 Hz`, `high_cutoff_hz = 2.50 Hz`, `filter_order = 1`
  - `artifact_threshold = 3.5`, `time_gap_threshold_sec = 0.5s`, `max_face_lost_sec = 1.0s`
- **Mã kiểm tra toàn vẹn (Config SHA-256 Short Checksum):** `83ee029cfe975147`
- **Tổng số bài kiểm thử tự động (Unit & Integration Tests):** **438 passed, 1 skipped** (0 failed; cập nhật 2026-10-29).
