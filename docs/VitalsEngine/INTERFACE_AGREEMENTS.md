# INTERFACE_AGREEMENTS – khối Vitals (Khoa)

Các điểm nối giữa phần của Khoa với Khang, Quang và Hào, đúng theo code hiện tại trên repo.

## 1. Khang → Khoa: Signal pipeline → Vitals

| Hạng mục | Thỏa thuận hiện tại | File |
|---|---|---|
| Nguồn dữ liệu | `RealtimeSignalPipeline.process_frame(frame, timestamp)` trả `FrameResult` | `signal_pipeline_realtime.py` |
| Thuật toán rPPG | Dùng `RPPGMethod` của Khang (GREEN / CHROM / POS, hàm `process`) | `rppg/` |
| Trường Khoa dùng | `is_ready`, `status`, `raw_rgb`, `quality_sqi`, `method_name`, `method_version`, `quality_state` | |
| Cửa sổ | Pipeline của Khang giữ 8 giây cho BVP + SQI. `RealtimeVitalsEngine` giữ thêm buffer 60 giây từ `raw_rgb` để HRV và RR đủ 30 giây | `integration/realtime_vitals.py` |
| Tần suất tính | Mỗi 1 giây khi pipeline đã sẵn sàng | `RealtimeVitalsConfig` |
| Quality Gate | `quality_state = REJECTED` → không tính vitals | |
| Tín hiệu cho nhịp thở | Cường độ kênh G chưa lọc (BVP của Khang đã lọc 0,75–2,5 Hz nên mất dải hô hấp 0,1–0,5 Hz) | |
| Tỷ lệ mất khung hình | Tỷ lệ frame `FACE_LOST` / `ARTIFACT` trong 60 giây gần nhất | |

Đầu vào của khối vitals là `BVPWindow` (`contracts/bvp_window.py`): `samples`, `sampling_rate_hz`, `start_timestamp`, `method`, `method_version`, `signal_quality`, `missing_ratio`, `raw_samples`, `roi_samples`.

Việc cần Khang hỗ trợ:
1. Quality Gate đang lấy thời gian bằng `time.perf_counter()` nên khi chạy video offline bị kẹt `REJECTED`; đề nghị dùng `timestamp` của frame.
2. Trả BVP riêng của trán / má (cùng độ dài cửa sổ) để rule `CROSS_ROI_INCONSISTENT` chạy được realtime.
3. Thống nhất ngưỡng SQI: pipeline dùng 0,4, validator của Khoa dùng 0,6 (OK) và 0,3 (INVALID).

## 2. Khoa → Quang: Result → API / DB / Frontend

| Hạng mục | Thỏa thuận hiện tại | File |
|---|---|---|
| Kết quả | `VitalsResult` → `MeasurementResult` | `docs/VitalsEngine/VITAL_RESULT_SCHEMA.md` |
| Ghi DB | Body PATCH measurement phẳng, chỉ số `INVALID` gửi `null` | `integration/frontend_mapper.py` |
| Bảng `validations` | `status` OK / BAD / INVALID, `reason`, `validator_version`, `details` | `to_validation_rows()` |
| Trạng thái đo | `measurement_states.json`: 11 trạng thái, 17 sự kiện, 5 mã lỗi kèm thông báo tiếng Việt | `quality/measurement_state.py` |
| Ánh xạ sang bảng `measurements` | 9 trạng thái lưu thẳng vào `state`; `FAILED` → `status = FAILED`, `CANCELLED` → `status = STOPPED` (giữ `state` cuối); `IDLE` → `CREATED`, `RESULT_READY` → `COMPLETED`, còn lại `RUNNING` | `database_mapping()` |

Đề nghị Quang: PATCH nhận thêm `confidence` và `algorithm_version` (hiện đang ghi cứng `rppg-v1`).

Test `tests/vitals/test_week1_week2_contracts.py` đọc trực tiếp `db/001_week2_camera_demo.sql` và `frontend/lib/api-contract.ts`, nên khi Quang đổi danh sách trạng thái thì test sẽ báo.

## 3. Hào ↔ Khoa: dữ liệu tham chiếu và benchmark

| Hạng mục | Thỏa thuận hiện tại | File |
|---|---|---|
| Dữ liệu hiện có | Chỉ có dữ liệu mô phỏng (6 kịch bản) | `benchmark/synthetic.py` |
| Định dạng recording | `.npz` gồm RGB theo ROI, timestamp và nhịp tham chiếu | `benchmark/dataset.py` |
| Metric | MAE, RMSE, MAPE, bias, Bland-Altman, Pearson, tỷ lệ sai số ≤ 5 bpm | `benchmark/metrics.py` |
| Dataset thật | Theo `docs/ReferenceDataset/Reference_Dataset_Schema_V0.md`, chỉ lấy mẫu `PASS` | Chưa có loader |

Cần chốt với Hào: ngưỡng đạt (MAE, giới hạn Bland-Altman) cho từng kịch bản Resting / Motion / Low-light.
