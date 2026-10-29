# Data Dictionary V1 – Week 8 (Hào)

Cập nhật 30/10/2026. Đối chiếu với `main` @ `faffe86`. Contract engine là nguồn chuẩn; nếu tài liệu này lệch với code thì code thắng.

| Phần | Đối tượng | Nguồn chuẩn (read-only) |
|---|---|---|
| A | `VitalsResult`, `VitalValue` | `aivitals_engine/contracts/schemas/vital_result.schema.json`, `contracts/result.py` |
| B | Status, issue code, ngưỡng | `validation/issue_codes.py`, `config/vitals_config.py` |
| C | `HealthAssessment`, `ExplanationResponse` | `health_assessment.schema.json`, `explanation_response.schema.json` |
| D | Research-only BP / risk | `blood_pressure_estimate.schema.json`, `health_risk_output.schema.json` |
| E | Metadata phiên thu thập (57 cột) | `docs/CollectionPackage_V1/SESSION_METADATA_TEMPLATE.csv`; spec chi tiết trong `docs/ReferenceDataset/Reference_Dataset_Schema_V0.md` |
| F | Dataset validation (Week 6) | `scripts/data_qc/split_and_validate_dataset.py`, `RUN_GUIDE.md` |

Quy ước: "req" = bắt buộc trong JSON Schema; "null" = được phép null. Thời gian là ISO 8601 có múi giờ (engine dùng UTC).

## A. Kết quả đo (`VitalsResult` 1.0.0)

| Trường | Kiểu | Req | Ý nghĩa |
|---|---|---|---|
| `schema_version` | string | – | Phiên bản contract |
| `result_id` | string | – | ID duy nhất của kết quả |
| `session_id` | string | req | Phiên đo |
| `engine_version` | string | req | `aivitals_engine/version.py` (`ENGINE_VERSION` hiện là 0.1.0, trong khi `RELEASE_NOTES.md` ghi bản 0.2.0 cho tuần 8; xem `EVIDENCE_TRACEABILITY_V1.md` §3) |
| `created_at` | date-time | req | Thời điểm tạo kết quả |
| `source` | `SignalSource` | req | `rppg_method`, `rppg_method_version`, `sampling_rate_hz`, `missing_ratio` (req); `signal_quality` (tùy chọn) |
| `window` | `MeasurementWindow` | req | `start`, `end`, `duration_seconds` |
| `status` | `OK`/`BAD`/`INVALID` | req | Trạng thái tổng |
| `vitals` | `VitalValue[]` | req | Danh sách chỉ số |
| `issues` | `ValidationIssue[]` | – | `code`, `severity` (`WARNING`/`ERROR`), `message`, `details` |

`VitalValue`: `code`, `value`, `unit`, `timestamp`, `window`, `quality`, `confidence`, `status`, `algorithm` (`name`, `version`) là req; `issues` và `model` là tùy chọn.

| `code` | Đơn vị (bắt buộc khớp) | Khoảng sinh lý validator | Cửa sổ tối thiểu | Ý nghĩa |
|---|---|---|---|---|
| `heart_rate` | `bpm` | 40–180 | 6 s | Nhịp tim ước tính từ rPPG |
| `hrv_rmssd` | `ms` | 5–250 | 30 s | RMSSD của khoảng xung (PRV), không phải ECG HRV |
| `hrv_sdnn` | `ms` | 5–300 | 30 s | SDNN của khoảng xung |
| `hrv_mean_ibi` | `ms` | 330–1500 | 30 s | Khoảng xung trung bình |
| `respiratory_rate` | `brpm` | 6–30 | 30 s | Nhịp thở suy ra gián tiếp từ BVP |

`quality` và `confidence` là điểm chất lượng tín hiệu trong [0,1]. **Đây không phải độ chính xác hay xác suất đúng.**

## B. Status, ngưỡng và issue code

Ngưỡng mặc định (`ValidationConfig`) hiện tại:

| Tham số | Giá trị | Hành vi |
|---|---|---|
| `signal_quality_invalid` | **0,4** | SQI < 0,4 → `SIGNAL_QUALITY_UNUSABLE`, vital INVALID |
| `signal_quality_ok` | 0,6 | 0,4 ≤ SQI < 0,6 → `SIGNAL_QUALITY_LOW` |
| `confidence_invalid` / `confidence_ok` | 0,3 / 0,6 | `VERY_LOW_CONFIDENCE` / `LOW_CONFIDENCE` |
| `missing_ratio_ok` / `missing_ratio_invalid` | 0,1 / 0,3 | `MISSING_DATA_HIGH` / `MISSING_DATA_EXCESSIVE` |
| `roi_agreement_warning` | 0,35 | `r_mean` < 0,35 → `ROI_SIGNAL_DISAGREEMENT`, vital BAD |
| `jump_tolerance` | HR 8, RR 4 | `SUDDEN_JUMP` |
| `stability_std_limit` | HR 8, RR 4 | `TEMPORAL_UNSTABLE` |
| Tần số lấy mẫu | < 15 Hz bị từ chối | Lý do lỗi tính toán `SAMPLING_RATE_TOO_LOW` (`vitals/failures.py`, không phải issue code của validator) |

Khác biệt với Week 6: tài liệu Week 6 ghi ngưỡng invalid là 0,3. Từ W7, Khoa đổi thành 0,4 (`HEALTH_OPENAI_BOUNDARY.md` §1). Xem `EVIDENCE_TRACEABILITY_V1.md` §3.

Issue code có trong `validation/issue_codes.py`: `COMPUTATION_FAILED`, `WINDOW_TOO_SHORT`, `MISSING_DATA_HIGH`, `MISSING_DATA_EXCESSIVE`, `SIGNAL_QUALITY_LOW`, `SIGNAL_QUALITY_UNUSABLE`, `OUT_OF_PHYSIOLOGICAL_RANGE`, `SUDDEN_JUMP`, `TEMPORAL_UNSTABLE`, `CROSS_ROI_INCONSISTENT`, `ROI_SIGNAL_DISAGREEMENT`, `SIGNAL_CONDITION_BLOCKING`, `LOW_CONFIDENCE`, `VERY_LOW_CONFIDENCE`, `MISSING_FEATURES`, `PULSE_PRESSURE_INVALID`, `FEATURES_OUT_OF_TRAINING_RANGE` (và các mã khác Khoa thêm sau; file code là nguồn chuẩn).

Status: `OK` là chỉ số được dùng cho health assessment và explanation; `BAD` là có giá trị nhưng chất lượng kém, không diễn giải; `INVALID` là không có giá trị dùng được.

## C. Health assessment và explanation

`HealthAssessment`: `assessment_id`, `source_result_id`, `created_at`, `intended_use` (const `wellness_screening_assist`), `is_diagnosis` (const `false`), `ruleset` (`wellness_rules` 0.1.0), `knowledge_version`, `review_status`, `findings[]`, `excluded_metrics[]`, `disclaimer`.

`HealthFinding`: `code`, `metric`, `observed_value`, `unit`, `severity` (`info`/`attention`), `evidence_level` (`established`/`promising`/`insufficient`/`not_recommended`), `interpretation`, `caution`. Danh sách 7 code và wording nằm trong `docs/EvidenceMatrix_BP/health_knowledge_v1/`.

`ExplanationResponse`: `explanation_id`, `kind` (`report`/`question`/`trend_summary`), `source_result_ids[]`, `text`, `guard_passed`, `violations[]` (`EMPTY_OUTPUT`, `UNVERIFIED_NUMBER`, `DIAGNOSTIC_CLAIM`), `llm_model`, `created_at`, `disclaimer`. Khi `guard_passed=false`, `text` là `FALLBACK_TEXT`.

## D. Research-only (không hiển thị cho người dùng cuối)

- `BloodPressureEstimate`: `sbp_mmhg`, `dbp_mmhg`, `unit`, `confidence`, `status`, `intended_use`, `model`, `feature_set_version`, `missing_features`, `issues`.
- `HealthRiskOutput`: `risk_code`, `score`, `category`, `status`, `evidence_level`, `intended_use`, `is_diagnosis`, `model`, `source_result_id`, `issues`.
- Chưa có validation BP (paired=0). Xem `docs/EvidenceMatrix_BP/MEDICAL_EVIDENCE_MATRIX_V1.md`.

## E. Metadata phiên thu thập (57 cột, Week 4)

Cùng tên cột trong JSON/CSV. Ô trống nghĩa là **chưa biết, có ghi lý do**, không phải 0. Không suy timestamp từ mtime hoặc thời điểm chạy script.

| Nhóm | Cột | Ghi chú |
|---|---|---|
| Định danh | 1 `sample_id`, 2 `subject_id`, 3 `session_id`, 57 `session_mode` | `subject_id` là bí danh (ví dụ `SUBJ_001`), không chứa danh tính |
| Consent | 4 `consent_record_id`, 5 `consent_version` | Trỏ tới hồ sơ consent; không chứa chữ ký |
| Thời gian | 6 `collection_timestamp`, 8 `video_start_timestamp`, 9 `video_end_timestamp`, 56 `initialization_timestamp` | Cột 56 là thời điểm tạo bản ghi, **không** phải thời điểm quay |
| Video | 7 `video_filename`, 10 `video_duration_sec`, 11 `width_px`, 12 `height_px`, 13 `fps_actual`, 14 `video_timebase` | Video gốc giữ ngoài Git |
| Tham chiếu | 15 `reference_filename`, 16 `reference_device`, 17 `reference_type`, 18 `reference_value_kind`, 19–20 `reference_start/end_timestamp`, 21 `reference_sampling_rate_hz`, 22 `reference_timebase` | Thiết bị độc lập (ECG/PPG/cuff) |
| Đồng bộ | 23 `sync_method`, 24 `sync_offset_ms`, 25 `sync_drift_ppm`, 26 `sync_error_ms` | Offset/drift đồng hồ khác với độ trễ sinh lý |
| Giá trị tham chiếu | 27 `reference_hr_bpm`, 28 `reference_sbp_mmhg`, 29 `reference_dbp_mmhg`, 30–31 `bp_measurement_start/end_timestamp`, 47–49 `reference_hr_before/during/after_bpm`, 50–55 `reference_bp_{before,during,after}_{sbp,dbp}_mmhg` | BP theo `GROUND_TRUTH_BP_PROTOCOL_V1.md` |
| QC | 32 `reference_quality`, 33 `video_quality`, 34 `quality_label`, 35 `exclusion_reason`, 36 `scenario` | Nhãn theo `Reference_Quality_Labeling_V0.md` |
| Kết quả engine | 37 `engine_result_filename`, 38 `engine_status`, 39 `engine_issue_codes` | Copy từ output engine, không sửa tay |
| Bối cảnh | 40 `notes`, 41 `subject_age_years`, 42 `subject_sex`, 43 `fitzpatrick_type`, 44 `camera_device`, 45 `camera_facing`, 46 `illuminance_lux` | Không đoán khi người tham gia không cung cấp |

## F. Dataset validation (Week 6)

Output mỗi run: `DATASET_SNAPSHOT.csv`, `ELIGIBLE_ROWS.csv`, `VALIDATION_REPORT.json`, `DATASET_LOCK.json`. Trong lock: `status` (`INVENTORY_SNAPSHOT_LOCKED`), `training_dataset_ready`, `inputs_sha256`, `rules_and_code_sha256`, `artifacts_sha256`, `runtime`. Metrics trong report: `count`, `mae`, `rmse`, `mape`, `bias`, `loa_lower`, `loa_upper`, `pearson_r`, `within_tolerance_ratio`; tất cả là `null` khi `count = 0`.
