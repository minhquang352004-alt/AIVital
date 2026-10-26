# Release Notes – khối Vitals (phần Khoa)

Version thuật toán được ghi trong mọi `VitalValue.algorithm`; version engine nằm ở `aivitals_engine/version.py` và `VitalsResult.engine_version`.

## 0.2.0 – Tuần 8: QA và hardening

| Thuật toán | Version | Thay đổi |
|---|---|---|
| `hr_spectral_peak_fusion` | 0.1.0 → 0.1.1 | Từ chối `sampling_rate_hz` < 15 Hz (`SAMPLING_RATE_TOO_LOW`). Trước đây 1 Hz làm crash, 2 Hz trả HR OK vô nghĩa |
| `rr_modulation_fusion` | 0.1.0 → 0.1.1 | Từ chối `sampling_rate_hz` < 15 Hz |
| `hrv_time_domain` | 0.2.0 | Không đổi (phụ thuộc HR nên tự INVALID khi `fs` thấp) |

- Validator thêm `SignalConditionRule`: cảnh báo mức `block` của Khang (`MOTION_HIGH`, `FACE_NOT_FOUND`) → `SIGNAL_CONDITION_BLOCKING`, vital `BAD`.
- `BVPWindow.signal_warnings`, `VitalCandidate.signal_warnings`; API `/vitals/compute` và `/validation/check` nhận `signal_warnings`.
- `RealtimeVitalsEngine` dùng feature guard `extract_checked()` của Khang; đặc trưng BVP là `None` khi tín hiệu không đạt.
- Golden regression 8 ca (`tests/regression/`) và lệnh `python -m aivitals_engine.scripts.update_golden`.
- Test đầu vào bất thường (`tests/vitals/test_hardening.py`).
- Tài liệu: `QA_HARDENING.md`, file này, `KHOA_TASK_TRACKER.md`.

## 0.1.0 – Tuần 1–7

| Thuật toán | Version | Nội dung |
|---|---|---|
| `hr_spectral_peak_fusion` | 0.1.0 | HR từ phổ Hann + nội suy parabol, kiểm tra subharmonic, fusion với HR từ đỉnh xung, SNR theo tần số cơ bản và hài bậc 2 |
| `hrv_time_domain` | 0.2.0 | RMSSD, SDNN, Mean IBI; loại IBI theo median cục bộ; cổng SNR ≥ 5 dB |
| `rr_modulation_fusion` | 0.1.0 | Fusion RIAV, RIFV, RIIV |
| `wellness_rules` | 0.1.0 | HR 60–100, RR 12–20, ngữ cảnh HRV |
| `bp_ridge_baseline` | 0.1.0 | Baseline research-only |

- Contract `VitalsResult` 1.0.0, `BVPWindow`, state machine đo, JSON schema cho Quang.
- Validation framework (OK / BAD / INVALID), ngưỡng SQI 0,4 / 0,6 và `r_mean` 0,35 theo Engine Benchmark của Khang.
- Benchmark harness, đo latency, deep model adapter, model registry có checksum, hiệu chỉnh confidence.
- Interface và baseline huyết áp (research-only), health assessment wellness, tầng giải thích OpenAI có guard, REST API `/api/v1`.

## Quy trình khi đổi thuật toán

1. Tăng `version` trong `AlgorithmInfo` của thuật toán.
2. Chạy `python -m aivitals_engine.benchmark run ...` và so với báo cáo trước.
3. Chạy `python -m aivitals_engine.scripts.update_golden`, review diff của `tests/regression/golden_vitals.json`.
4. Ghi thay đổi vào file này.

## Giới hạn đã biết

- Chưa có dữ liệu người thật: mọi con số độ chính xác hiện tại đều trên tín hiệu tổng hợp.
- Nhiễu trắng có thể được nhận là nhịp tim khi SQI đầu vào cao (xem `QA_HARDENING.md` mục 4).
- HRV từ rPPG rất nhạy nhiễu; cổng SNR chưa hiệu chỉnh trên dữ liệu thật.
- Deep model mới có adapter, chưa có trọng số nên chưa benchmark độ chính xác.
- Knowledge base và prompt đang ở trạng thái `pending_medical_review` (chờ Hào).
