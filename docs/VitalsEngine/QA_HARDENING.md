# QA và Hardening – Tuần 8 (Khoa)

Tuần 8 khóa hành vi của khối Vitals bằng golden regression, kiểm thử đầu vào bất thường và nối các cảnh báo tín hiệu mà Khang thêm ở Tuần 7 (`docs/ROBUSTNESS.md`) vào validator.

## 1. Golden regression

| Thành phần | File |
|---|---|
| Danh sách ca | `aivitals_engine/benchmark/regression_cases.py` |
| Snapshot | `tests/regression/golden_vitals.json` |
| Test | `tests/regression/test_golden_vitals.py` |
| Cập nhật snapshot | `python -m aivitals_engine.scripts.update_golden` |

| Ca | Mục đích | Kết quả nhịp tim |
|---|---|---|
| `rest_72bpm` | Nghỉ, nhiễu thấp | 72,8 bpm, OK |
| `low_54bpm` | Nhịp chậm | 54,3 bpm, OK |
| `high_118bpm` | Nhịp nhanh | 116,2 bpm, OK |
| `noisy_85bpm` | Nhiễu mạnh | 85,1 bpm, OK; RMSSD BAD (`LOW_CONFIDENCE`) |
| `short_12s` | Cửa sổ 12 s | HR OK; HRV, RR INVALID (`WINDOW_TOO_SHORT`) |
| `low_fs_10hz` | Camera 10 fps | INVALID (`SAMPLING_RATE_TOO_LOW`) |
| `low_sqi_035` | SQI 0,35 | INVALID (`SIGNAL_QUALITY_UNUSABLE`) |
| `motion_high` | Có cảnh báo `MOTION_HIGH` | BAD (`SIGNAL_CONDITION_BLOCKING`) |

Test so trạng thái, danh sách issue và giá trị (sai số cho phép: HR, RR 0,5; HRV 2 ms). Test cũng kiểm tra version thuật toán trong snapshot khớp với code, nên đổi thuật toán mà quên tăng version hoặc quên cập nhật snapshot sẽ bị báo.

Quy trình khi đổi thuật toán:

1. Tăng `version` trong `AlgorithmInfo` của thuật toán.
2. Chạy `python -m aivitals_engine.benchmark run ...` và so với báo cáo trước.
3. Chạy `python -m aivitals_engine.scripts.update_golden`, review diff của `golden_vitals.json`.
4. Ghi thay đổi vào `RELEASE_NOTES.md`.

## 2. Đầu vào bất thường

`tests/vitals/test_hardening.py`:

| Đầu vào | Trước Tuần 8 | Sau Tuần 8 |
|---|---|---|
| Tín hiệu toàn 0, hằng số, 1 mẫu, 5 mẫu, bậc thang, mảng rỗng | INVALID | INVALID (giữ nguyên, có test) |
| `sampling_rate_hz` = 1 Hz | Ném `ValueError` (crash) | INVALID, `SAMPLING_RATE_TOO_LOW` |
| `sampling_rate_hz` = 2 Hz | Trả HR **OK** (vô nghĩa vì Nyquist 1 Hz = 60 bpm) | INVALID, `SAMPLING_RATE_TOO_LOW` |
| `sampling_rate_hz` 5–14,9 Hz | INVALID nhưng lý do không rõ | INVALID, `SAMPLING_RATE_TOO_LOW` |
| Biên độ ×10⁻⁶ hoặc ×10⁶ | HR không đổi | HR không đổi (có test) |
| NaN / vô cực, mảng 2 chiều, `fs` = 0 | `BVPWindow` từ chối | Giữ nguyên (có test) |
| API: `fs` thấp, quá 32 mã cảnh báo | | 200 kèm INVALID / 400 `VALIDATION_ERROR` |

Ngưỡng 15 Hz (`HeartRateConfig.min_sampling_rate_hz`, `RespiratoryRateConfig.min_sampling_rate_hz`) trùng với `LOW_FS` trong feature guard của Khang.

## 3. Cảnh báo tín hiệu của Khang trong validator

Đường đi: `FrameResult.warnings` → `signal_warnings()` trong `integration/realtime_vitals.py` → `BVPWindow.signal_warnings` → `VitalCandidate.signal_warnings` → `SignalConditionRule`.

- Mã mức `block` theo `quality/signal_warnings.py` (`MOTION_HIGH`, `FACE_NOT_FOUND`) → issue `SIGNAL_CONDITION_BLOCKING` (WARNING) → vital `BAD`.
- Mã mức `warn` / `info` và mã lạ không đổi trạng thái; frontend vẫn đọc `FrameResult.warnings` và `MESSAGE_VI` để hướng dẫn người đo.
- Chỉ số không tính được thì không gắn thêm issue này.
- API `/vitals/compute` và `/validation/check` nhận thêm `signal_warnings` (tối đa 32 mã).

Feature guard: `RealtimeVitalsEngine` gọi `extract_checked()` thay cho `extract()`. Khi bị từ chối, `bvp_features = None` và `feature_validity.reasons` ghi lý do (`LOW_SQI`, `BLOCKING_WARNING`...).

## 4. Hiệu năng

`python -m aivitals_engine.benchmark latency --iterations 100 --window 30` sau Tuần 8: mean 7,41 ms, p50 7,18 ms, p95 8,87 ms (Tuần 7: mean 7,29 ms, p95 7,91 ms). Rule mới và kiểm tra `fs` không làm tăng latency đáng kể.

## 5. Giới hạn đã biết

- **Nhiễu trắng có thể được nhận là nhịp tim.** Thử 60 cửa sổ nhiễu trắng 30 s: không có SQI thì 2/60 ca HR `OK`; nếu bên gọi truyền SQI 0,85 thì 12/60 ca `OK`. SNR của nhiễu (p95 1,7 dB) chồng lên SNR của tín hiệu nhiễu mạnh nhưng vẫn đúng (p5 0,6 dB với `noise_std` 1,5), nên không thể chặn bằng một ngưỡng SNR cứng mà không loại cả kết quả đúng. Bảo vệ hiện tại dựa vào SQI thật của Khang; cần dữ liệu thật để hiệu chỉnh confidence.
- Ngưỡng `MOTION_HIGH`, luma, flicker của Khang chưa hiệu chỉnh trên nhiều thiết bị (device matrix).
- Mọi golden case là tín hiệu tổng hợp; chưa có video người thật có nhịp tham chiếu.
