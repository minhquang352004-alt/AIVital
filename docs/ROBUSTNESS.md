# Signal Robustness — Tuần 7 (Khang)

**Owner:** Khang (Coding / AI Signal)  
**Phạm vi:** `RealtimeSignalPipeline` (face → ROI → buffer → rPPG → BVP/SQI) và cổng chất lượng cho `features/`.  
**Ranh giới:** Tài liệu này chỉ mô tả những gì engine tín hiệu *phát ra*. Việc hiển thị, lưu trữ hay dùng cảnh báo để điều chỉnh confidence thuộc về người dùng các output này (Quang, Khoa) — họ tự quyết định.

---

## 1. Cách lấy cảnh báo

`FrameResult.warnings` (list[str]) — luôn có ở mọi trạng thái (`FACE_LOST`, `ARTIFACT`, `BUFFERING`, `OK`, `LOW_QUALITY`).
Các trường đi kèm: `luma` (ánh sáng khuôn mặt, đã làm mượt), `face_width_ratio`, `face_lost_duration_sec`.

Danh mục mã nằm tại [`quality/signal_warnings.py`](../aivitals_engine/quality/signal_warnings.py) (`SignalWarning`, `SEVERITY`, `MESSAGE_VI`, `severity_of()`, `has_blocking()`). Giá trị enum là `str`, nên `"TOO_DARK" in result.warnings` hoạt động bình thường.

Ngoài các mã dưới đây, `warnings` còn chứa các lý do của Quality Gate (`LOW_SNR`, `NOT_PERIODIC`, `ROI_DISAGREE`, `HIGH_MOTION`, `HIGH_ARTIFACT`, `WINDOW_TOO_SHORT`) — mức INFO với `severity_of()`.

## 2. Bảng cảnh báo

| Mã | Mức | Điều kiện | Tham số (`SignalConfig`) | Hành động engine |
|---|---|---|---|---|
| `FACE_NOT_FOUND` | block | Không phát hiện mặt / frame không dùng được | `max_face_lost_sec = 1.0` | Mất ≤ 1s: giữ buffer. Mất > 1s: reset buffer + cache SQI |
| `FACE_TOO_SMALL` | warn | Bề rộng mặt / bề rộng frame < ngưỡng | `min_face_ratio = 0.12` | Chỉ cảnh báo |
| `TOO_DARK` | warn | Median luma (7 frame) < ngưỡng | `min_luma_acceptable = 40`, `luma_smooth_frames = 7` | Chỉ cảnh báo |
| `TOO_BRIGHT` | warn | Median luma > ngưỡng | `max_luma_acceptable = 225` | Chỉ cảnh báo |
| `LIGHT_UNSTABLE` | warn | std/mean của luma trong 2s > ngưỡng (flicker, bật/tắt đèn) | `light_window_sec = 2.0`, `light_unstable_cv = 0.10` | Chỉ cảnh báo |
| `MOTION_HIGH` | **block** | Biên độ dịch chuyển tâm mặt trong 1s > 12% bề rộng mặt, hoặc tâm mặt nhảy > 60% bề rộng giữa 2 frame | `motion_window_sec = 1.0`, `motion_amp_threshold = 0.12`, `bbox_jump_ratio = 0.60` | Hạ `status` từ `OK` xuống `LOW_QUALITY`. Nếu bbox nhảy: reset buffer |
| `LOW_FPS` | warn | FPS thực tế của buffer < ngưỡng (khi buffer ≥ 15 frame) | `min_fps_acceptable = 20`, `min_frames_for_fps_check = 15` | Chỉ cảnh báo |
| `TIME_GAP` | info | Đứt đoạn timestamp lớn hơn ngưỡng, buffer đã reset | `max(time_gap_threshold_sec = 0.5, max_face_lost_sec = 1.0)` | Reset buffer + cache SQI |
| `ARTIFACT_DETECTED` | info | Frame bị loại do đột biến (3σ trên ≥ 2/3 kênh) | `artifact_threshold = 3.5` | Frame bị bỏ; xem mục 3 |

*Mức* chỉ là phân loại gợi ý (`SEVERITY`). Duy nhất mức **block** có tác dụng lên engine: hạ `OK` → `LOW_QUALITY` và chặn trích xuất đặc trưng (mục 4).

## 3. Tình huống biên và cách engine xử lý

| Tình huống | Hành vi |
|---|---|
| Frame `None`, rỗng, không phải `ndarray`, số kênh ≠ 1/3/4, `ndim` lạ | Coi như mất mặt (`FACE_LOST`), không crash |
| Ảnh xám, BGRA, dtype float (kể cả NaN/inf) | Chuẩn hóa về BGR `uint8` trước khi dò mặt |
| Bước nhảy ánh sáng (đèn bật/tắt) | Frame đầu bị loại là artifact; sau `max_consecutive_artifacts = 10` frame liên tiếp, buffer tự thích nghi baseline mới và **xóa cache SQI** |
| Mất mặt ngắn (≤ 1s) | Buffer giữ nguyên, tiếp tục ngay khi thấy mặt |
| Mất mặt dài (> 1s) | Reset buffer, cache SQI và lịch sử chuyển động |
| Đứt timestamp | `TIME_GAP`, reset buffer + cache SQI |
| Timestamp trùng/lùi | Không crash; FPS ước lượng bằng median khoảng cách dương |
| Jitter timestamp ±5ms | Không sinh `TIME_GAP`, vẫn `is_ready` |

> **Lưu ý thiết kế — ngưỡng đứt timestamp.** `time_gap_threshold_sec` (0.5s) vốn dành cho đứt luồng giữa các frame được nạp. Để dung nạp mất mặt tạm thời đến 1s mà không reset, pipeline dùng `max(time_gap_threshold_sec, max_face_lost_sec)`. Cấu hình `time_gap_threshold_sec` không bị thay đổi; nếu muốn hành vi cũ (0.5s), đặt `max_face_lost_sec = 0.5`.

## 4. Cổng chất lượng cho đặc trưng sinh lý

Xem thêm [`FEATURE_CONTRACT.md`](FEATURE_CONTRACT.md) mục "Điều kiện hợp lệ".

- `BVPFeatureExtractor.extract()` — **không đổi** (luôn trả `BVPFeatures`, field không tính được là NaN).
- `BVPFeatureExtractor.extract_checked(bvp, fs, sqi=, warnings=, artifact_ratio=, metadata=)` → `GuardedFeatures(features | None, validity)`.
- `RealtimeSignalPipeline.extract_features_checked()` — dùng cửa sổ hiện tại; metadata gồm `method`, `method_version`, `fs`, `sqi`, `artifact_ratio`, `signal_warnings`, `valid_beat_count`.

Lý do từ chối (`reasons`): `SIGNAL_TOO_SHORT`, `SIGNAL_DEGENERATE`, `NON_FINITE_SAMPLES`, `LOW_FS`, `LOW_SQI`, `BLOCKING_WARNING`, `HIGH_ARTIFACT`, `TOO_FEW_BEATS`.

## 5. Hiệu năng

Đo trên máy dev (640×480, `ScriptedDetector`, 3000 lần gọi):

| Bước thêm vào mỗi frame | Median |
|---|---|
| Chuẩn hóa frame | ~0.0004 ms |
| Đo luma (subsample 1/4) | ~0.033 ms |
| Cập nhật/làm mượt luma | ~0.012 ms |
| Kiểm tra `LIGHT_UNSTABLE` | ~0.016 ms |
| Cập nhật/kiểm tra chuyển động | ~0.017 ms |
| **Tổng ước tính** | **≈ 0.08 ms** |

So với median `process_frame` ≈ 8 ms trên video tổng hợp → < 1%. Chi tiết A/B với Tuần 6: xem [`ENGINE_BENCHMARK.md`](ENGINE_BENCHMARK.md).

## 6. Giới hạn đã biết

- Ngưỡng luma/chuyển động/flicker **chưa hiệu chỉnh trên nhiều thiết bị**; được đặt trong `SignalConfig` để Tuần 8 (device matrix) tinh chỉnh.
- `LIGHT_UNSTABLE` dựa trên luma ở tần số khung hình của camera; flicker 50/60Hz bị alias theo FPS nên chỉ phát hiện được phần biến thiên còn lại.
- `MOTION_HIGH` dùng bbox đã được làm mịn; chuyển động rất nhỏ nhưng ở tần số nhịp tim (rung đầu theo mạch) vẫn do `motion_score` của Quality Gate (`HIGH_MOTION`) xử lý.
- Dung nạp mất mặt 1s có nội suy tuyến tính qua khoảng trống; HR trong test tổng hợp vẫn lệch < 3 BPM, nhưng chưa kiểm chứng trên video thật có chuyển động.
- Không có cảnh báo về màu da/độ tương phản/đeo kính/khẩu trang.
- Mọi cảnh báo chỉ nói về **chất lượng tín hiệu**, không phải đánh giá y khoa.
