# VITAL_RESULT_SCHEMA (K2.2 – Khoa)

Định dạng kết quả chỉ số sinh tồn dùng chung giữa engine (Khang, Khoa) và API/DB/Frontend (Quang).

- Code: `aivitals_engine/contracts/result.py` (pydantic 2, `extra="forbid"`)
- JSON Schema: `aivitals_engine/contracts/schemas/vital_result.schema.json`
- Ví dụ: `aivitals_engine/contracts/schemas/example_vitals_result.json`
- Sinh lại các file trên: `python aivitals_engine/scripts/export_vitals_contracts.py`

## 1. VitalsResult (schema 1.0.0)

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `schema_version` | `"1.0.0"` | Phiên bản định dạng |
| `result_id` | UUID | Mã kết quả |
| `session_id` | string | Mã phiên đo / measurement |
| `engine_version` | string | Phiên bản khối vitals (`aivitals_engine/version.py`) |
| `created_at` | datetime UTC | Thời điểm tính |
| `source` | `SignalSource` | `rppg_method`, `rppg_method_version`, `sampling_rate_hz`, `signal_quality`, `missing_ratio` |
| `window` | `MeasurementWindow` | `start`, `end`, `duration_seconds` của cửa sổ BVP |
| `status` | `OK` / `BAD` / `INVALID` | Trạng thái chung, lấy theo nhịp tim |
| `vitals` | `VitalValue[]` | Danh sách chỉ số |
| `issues` | `ValidationIssue[]` | Vấn đề của nhịp tim |

## 2. VitalValue

| Trường | Ý nghĩa |
|---|---|
| `code` | `heart_rate`, `hrv_rmssd`, `hrv_sdnn`, `hrv_mean_ibi`, `respiratory_rate` |
| `value` | Giá trị đã làm tròn 1 chữ số; **bắt buộc `null` khi `status = INVALID`** |
| `unit` | Cố định theo code: `bpm`, `ms`, `ms`, `ms`, `brpm` |
| `quality` | 0–1, chất lượng tín hiệu (SQI của Khang, nếu thiếu thì suy từ SNR) |
| `confidence` | 0–1, độ tin cậy của riêng chỉ số đó |
| `status` | `OK` / `BAD` / `INVALID` |
| `issues` | `code`, `severity` (`WARNING` / `ERROR`), `message`, `details` |
| `algorithm` | `name`, `version`, ví dụ `hr_spectral_peak_fusion` 0.1.0 |
| `model` | Thông tin model (để trống với thuật toán cổ điển) |

## 3. Quy tắc trạng thái

- Có issue `ERROR` → `INVALID`, có `WARNING` → `BAD`, không có → `OK`.
- 17 mã issue trong `validation/issue_codes.py`: `COMPUTATION_FAILED`, `WINDOW_TOO_SHORT`, `MISSING_DATA_HIGH`, `MISSING_DATA_EXCESSIVE`, `SIGNAL_QUALITY_LOW`, `SIGNAL_QUALITY_UNUSABLE`, `OUT_OF_PHYSIOLOGICAL_RANGE`, `SUDDEN_JUMP`, `TEMPORAL_UNSTABLE`, `CROSS_ROI_INCONSISTENT`, `ROI_SIGNAL_DISAGREEMENT`, `SIGNAL_CONDITION_BLOCKING`, `LOW_CONFIDENCE`, `VERY_LOW_CONFIDENCE`, `MISSING_FEATURES`, `PULSE_PRESSURE_INVALID`, `FEATURES_OUT_OF_TRAINING_RANGE`.
- Ngưỡng chất lượng (Tuần 7, theo Engine Benchmark của Khang): SQI < 0,4 → `SIGNAL_QUALITY_UNUSABLE` (INVALID), SQI < 0,6 → `SIGNAL_QUALITY_LOW` (BAD), `r_mean` < 0,35 → `ROI_SIGNAL_DISAGREEMENT` (BAD).
- Cảnh báo điều kiện đo (Tuần 8): cửa sổ có cảnh báo mức `block` của Khang (`MOTION_HIGH`, `FACE_NOT_FOUND`) → `SIGNAL_CONDITION_BLOCKING` (BAD), `details.signal_warnings` ghi các mã đã gặp. Cảnh báo mức `warn` / `info` (`TOO_DARK`, `LOW_FPS`...) không đổi trạng thái.
- Khi một chỉ số không tính được, `details.reason` ghi lý do từ `vitals/failures.py` (ví dụ `WINDOW_TOO_SHORT`, `LOW_SIGNAL_TO_NOISE`, `SAMPLING_RATE_TOO_LOW` khi `sampling_rate_hz` < 15 Hz).
- Khoảng sinh lý hợp lệ (`config/vitals_config.py`): HR 40–180 bpm, RMSSD 5–250 ms, SDNN 5–300 ms, Mean IBI 330–1500 ms, RR 6–30 nhịp thở/phút.
- Cửa sổ tối thiểu: HR 6 giây (phân tích 10 giây cuối), HRV và RR 30 giây.

## 4. Chuyển sang API v0 của Frontend

`integration/frontend_mapper.py` chuyển `VitalsResult` sang `MeasurementResult` trong `frontend/lib/api-contract.ts`. Ví dụ: `aivitals_engine/contracts/schemas/example_measurement_result.json`.

| MeasurementResult | Lấy từ |
|---|---|
| `status` | Chưa có kết quả → `PENDING`; HR `INVALID` → `REJECTED`; còn lại `READY` |
| `quality` | `quality` của HR: ≥ 0,7 `GOOD`, ≥ 0,4 `FAIR`, < 0,4 `POOR`; HR `INVALID` → `REJECTED` |
| `quality_score` | `quality × 100` (0–100, khớp CHECK của `vital_measurements`) |
| `metrics.heart_rate` / `hrv_rmssd` / `respiration_rate` | Chỉ các chỉ số không `INVALID`; `respiratory_rate` đổi tên thành `respiration_rate`, đơn vị `breaths_per_minute`; kèm `confidence` |
| `algorithm_version` | `{rppg_method}-{version}+vitals-{engine_version}`, ví dụ `POS-1.0+vitals-0.1.0` |
| `measured_at` | `created_at` dạng ISO 8601 UTC |

Body PATCH measurement: `to_measurement_patch()` → `status`, `state`, `heart_rate`, `respiration_rate`, `hrv_rmssd`, `quality_score`; chỉ số `INVALID` gửi `null`. Dòng cho bảng `validations`: `to_validation_rows()`.
