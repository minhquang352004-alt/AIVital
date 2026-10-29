# Khoa – Task Tracker (8 tuần)

Trạng thái:
- **Xong**: đã có code, test và tài liệu, đã merge vào `main`.
- **Xong – chờ dữ liệu**: chạy được với tín hiệu tổng hợp, cần dữ liệu hoặc trọng số thật để ra kết quả chính thức.
- **Chờ phụ thuộc**: cần đầu vào từ thành viên khác.

| Tuần | PR | Nội dung chính | Trạng thái |
|---|---|---|---|
| 1–4 | #4 | Contract `VitalsResult`, validation, face quality, state machine, HR / HRV / RR, confidence, kết nối pipeline realtime của Khang | Xong |
| 5 | #5 | Interface và baseline huyết áp / rủi ro sức khỏe (research-only), gate dữ liệu | Xong – chờ dữ liệu |
| 6 | #7 | Model registry có checksum, hiệu chỉnh confidence, deep model adapter, model benchmark report | Xong – chờ trọng số và dữ liệu |
| 7 | #9 | Ngưỡng SQI / `r_mean`, health assessment, tầng giải thích OpenAI có guard, REST API `/api/v1`, latency | Xong |
| 8 | (nhánh `feature/khoa-week8-qa-hardening`) | Golden regression, test đầu vào bất thường, ngưỡng `fs`, nối cảnh báo tín hiệu và feature guard của Khang, release notes | Chờ review |

## Week 8 – QA + Hardening

| Task | File | Trạng thái |
|---|---|---|
| Vitals / validation regression | `tests/regression/`, `benchmark/regression_cases.py`, `scripts/update_golden.py` | Xong |
| Đo không hợp lệ | `tests/vitals/test_hardening.py`, golden `short_12s`, `low_fs_10hz`, `low_sqi_035` | Xong |
| Cảnh báo tín hiệu của Khang → validator | `validation/rules.py` (`SignalConditionRule`), `integration/realtime_vitals.py` | Xong |
| Feature guard cho mô hình huyết áp | `integration/realtime_vitals.py` (`extract_checked`) | Xong |
| Release notes | `docs/VitalsEngine/RELEASE_NOTES.md` | Xong |

## Phụ thuộc đang chờ

| Từ | Cần gì | Dùng cho |
|---|---|---|
| Khang | Thêm `mediapipe` vào `aivitals_engine/requirements.txt`, sửa `test_detection_with_mocked_landmarker` | Cài đặt sạch, CI xanh |
| Khang | BVP riêng trán / má cùng độ dài cửa sổ | Rule `CROSS_ROI_INCONSISTENT` chạy realtime |
| Hào | Dataset có nhịp tham chiếu (ECG / PPG), BP tham chiếu; review knowledge base và prompt | Benchmark thật, calibration, BP baseline, gỡ `pending_medical_review` |
| Quang | Gọi `/api/v1` từ frontend, hiển thị issue `SIGNAL_CONDITION_BLOCKING` và `FrameResult.warnings` | Hiển thị kết quả |
| Team | Trọng số deep model, key OpenAI chung | Benchmark TS-CAN / EfficientPhys, demo giải thích |
