# AIVitals – Reference Dataset Schema V0

Cập nhật 2026-10-14; đối chiếu `main@5d9b4ae`.
Nguồn chuẩn: `aivitals_engine/contracts/schemas/vital_result.schema.json`,
`aivitals_engine/contracts/result.py`, `aivitals_engine/validation/issue_codes.py`.
Phục vụ estimation, wellness, research/screening support; không chẩn đoán hoặc thay thế thiết bị y tế.

## 1. Hai lớp dữ liệu riêng biệt

- **Dataset metadata** liên kết video, người tham gia mã hóa, reference và QC. Đây không phải JSON `VitalsResult`.
- **Engine result** giữ nguyên JSON theo schema version `1.0.0`, lưu riêng và liên kết bằng `session_id` / đường dẫn file.
- Không thêm `subject_id`, `reference_hr_bpm`, `quality_label`, `sync_error_ms` hoặc BP vào JSON engine. Mọi object contract có `additionalProperties: false`, trừ nội dung `issues[].details`.
- Metadata CSV Week 4 dùng header trong `../CollectionPackage_V1/SESSION_METADATA_TEMPLATE.csv`; không gửi CSV đó trực tiếp vào engine.

## 2. Dataset metadata V0 và mở rộng V1

Giữ tên trường V0 để không mất tương thích. `Có` là bắt buộc cho phân tích tương ứng, không phải required của engine.

| Field | Kiểu / ý nghĩa | Yêu cầu |
|---|---|---|
| sample_id | string, duy nhất cho sample | Có |
| subject_id | string, mã giả danh; không dùng tên thật | Có |
| session_id | string, khớp result khi có engine output | Có |
| video_filename | string, đường dẫn trong kho được cấp quyền | Có |
| video_start_timestamp, video_end_timestamp | ISO 8601 có offset, ưu tiên UTC Z | Có |
| video_duration_sec | number >0, thời lượng thực | Có |
| width_px, height_px | integer >0 | Có |
| fps_actual | number >0; không thay timestamp từng frame | Có |
| reference_filename | string, waveform/export hoặc bản ghi số đo độc lập | Có cho reference sample |
| reference_device | string, model thiết bị | Có |
| reference_type | ECG / PPG / SMARTWATCH / BP_CUFF; enum dataset | Có |
| reference_start_timestamp, reference_end_timestamp | ISO 8601, khoảng hỗ trợ số đo | Có cho đối chiếu |
| sync_error_ms | number >=0, cận sai số còn lại sau hiệu chỉnh | Có cho đối chiếu đồng bộ |
| reference_hr_bpm | number hoặc trống, HR từ reference độc lập | Chỉ khi đo/tính được |
| reference_quality, video_quality | PASS / WARNING / REJECT; QC dataset | Có sau QC |
| quality_label | PASS / WARNING / REJECT; QC tổng sample | Có sau QC |
| exclusion_reason | string, mã QC dataset cách nhau bằng `;` | Khi REJECT |
| scenario | Resting / Motion / Low-light; enum dataset | Có |
| notes | string, ghi chú không định danh | Không |
| consent_record_id, consent_version | string, liên kết hồ sơ đồng ý lưu riêng | Có trước thu thập V1 |
| collection_timestamp | ISO 8601 có offset | Có V1 |
| video_timebase, reference_timebase | string, clock/đơn vị/gốc timestamp | Có V1 |
| reference_sampling_rate_hz | number >0 hoặc trống nếu không có waveform | Khi waveform |
| reference_value_kind | waveform / device_hr_summary / bp_spot; enum dataset | Có V1 |
| sync_method | string, cách đồng bộ | Có V1 |
| sync_offset_ms | number có dấu, offset video → reference | Khi xác định được |
| sync_drift_ppm | number có dấu, drift video → reference | Khi xác định được |
| reference_sbp_mmhg, reference_dbp_mmhg | number hoặc trống, số đo cuff | Khi đo BP |
| bp_measurement_start_timestamp, bp_measurement_end_timestamp | ISO 8601, khoảng đo cuff | Khi đo BP |
| engine_result_filename | string hoặc trống, raw VitalsResult nếu có | Khi lưu raw result |
| engine_status | OK / BAD / INVALID hoặc trống; lấy từ raw result | Khi có raw result |
| engine_issue_codes | string, mã engine thực tế cách nhau bằng `;` | Khi có issue |

Trống CSV là chưa có/không áp dụng; `[USER_FILL_REQUIRED]` cần thay, không phải số đo hợp lệ.
Không lấy rPPG HR để điền `reference_hr_bpm`; không gán timestamp bằng thời điểm chạy script.

### Các trường collection bổ sung, cùng tên trong JSON/CSV

| Field | Kiểu / cách điền |
|---|---|
| subject_age_years | integer >=0 hoặc null; tự khai theo consent |
| subject_sex | string hoặc null; tự khai tùy chọn, không suy đoán |
| fitzpatrick_type | integer 1–6 hoặc null; theo cách đánh giá được chốt, không suy từ ảnh |
| camera_device | string hoặc null; model do người thu cung cấp |
| camera_facing | user / environment hoặc null, cùng enum cameras.facing |
| illuminance_lux | number >=0 hoặc null; cần phép đo thật |
| reference_hr_before_bpm, reference_hr_during_bpm, reference_hr_after_bpm | number >0 hoặc null; HR độc lập và khoảng hỗ trợ tương ứng |
| reference_bp_before_sbp_mmhg, reference_bp_before_dbp_mmhg | number >0 hoặc null; cuff BP trước phiên |
| reference_bp_during_sbp_mmhg, reference_bp_during_dbp_mmhg | number >0 hoặc null; cuff BP trong phiên |
| reference_bp_after_sbp_mmhg, reference_bp_after_dbp_mmhg | number >0 hoặc null; cuff BP sau phiên |
| initialization_timestamp | ISO 8601, thời điểm tạo metadata; không phải capture start |
| session_mode | video_only / paired_reference; do dữ liệu thực quyết định |

Template JSON dùng null, CSV mẫu dùng placeholder; tổng 57 trường. Từng số đo trước/trong/sau cần lưu thời gian hỗ trợ ở hồ sơ session được cấp quyền (notes hoặc tài liệu đi kèm), không xem các số summary là waveform. DB mapping xem ../CollectionPackage_V1/DB_MAPPING_AND_USAGE_V1.md.

## 3. JSON VitalsResult: tên trường và tính bắt buộc

`Có` thuộc `required` của JSON Schema. `Không` không có nghĩa được truyền null: chỉ trường nullable ghi rõ mới nhận null.

| Field (root) | Kiểu / ràng buộc | Required |
|---|---|---|
| schema_version | string const `1.0.0`, default `1.0.0` | Không |
| result_id | string; runtime sinh UUID khi bỏ qua, schema không ép UUID | Không |
| session_id | string minLength 1 | Có |
| engine_version | string minLength 1 | Có |
| created_at | string date-time | Có |
| source | object SignalSource | Có |
| window | object MeasurementWindow | Có |
| status | OK / BAD / INVALID | Có |
| vitals | array VitalValue; không có minItems/uniqueItems trong schema | Có |
| issues | array ValidationIssue; runtime default [] | Không |

| Field (source) | Kiểu / ràng buộc | Required |
|---|---|---|
| rppg_method | string minLength 1; schema không giới hạn enum thuật toán | Có |
| rppg_method_version | string minLength 1 | Có |
| sampling_rate_hz | number >0 | Có |
| signal_quality | number [0,1] hoặc null, default null | Không |
| missing_ratio | number [0,1] | Có |

`window` ở root và mỗi vital cùng cấu trúc:

| Field (window) | Kiểu / ràng buộc | Required |
|---|---|---|
| start | string date-time | Có |
| end | string date-time | Có |
| duration_seconds | number >=0 | Có |

| Field (vitals[]) | Kiểu / ràng buộc | Required |
|---|---|---|
| code | enum VitalCode bên dưới | Có |
| value | number hoặc null | Có |
| unit | string; runtime kiểm tra unit theo code | Có |
| timestamp | string date-time | Có |
| window | object MeasurementWindow | Có |
| quality | number [0,1] | Có |
| confidence | number [0,1] | Có |
| status | OK / BAD / INVALID | Có |
| issues | array ValidationIssue, runtime default [] | Không |
| algorithm | object AlgorithmInfo | Có |
| model | object ModelInfo hoặc null, default null | Không |

| VitalCode | Unit runtime (`contracts/result.py`) |
|---|---|
| heart_rate | bpm |
| hrv_rmssd | ms |
| hrv_sdnn | ms |
| hrv_mean_ibi | ms |
| respiratory_rate | brpm |

Không có blood_pressure/sbp/dbp trong VitalCode hiện tại. `respiration_rate` và `breaths_per_minute` là tên/đơn vị payload frontend, không phải raw contract.

| Object | Field | Kiểu / ràng buộc | Required |
|---|---|---|---|
| algorithm | name | string minLength 1 | Có |
| algorithm | version | string minLength 1 | Có |
| model | name | string minLength 1 | Có khi object |
| model | version | string minLength 1 | Có khi object |
| model | checksum_sha256 | string regex `^[a-f0-9]{64}$` hoặc null, default null | Không |
| issues[] (root hoặc vital) | code | string minLength 1; đối chiếu IssueCode | Có |
| issues[] | severity | WARNING / ERROR | Có |
| issues[] | message | string; schema cho phép chuỗi rỗng | Có |
| issues[] | details | object; giá trị number/integer/string/boolean/null, không nested object/array; runtime default {} | Không |

Schema giới hạn `issues[].code` là string, không enum. Danh mục chuẩn nằm trong `issue_codes.py`; không tự chế mã engine. Danh mục đủ 15 mã: `Reference_Quality_Labeling_V0.md`.

## 4. Runtime và QC ngoài schema

- Runtime VitalValue: INVALID phải có value null; OK/BAD phải có số và unit đúng. Đây là kiểm tra Pydantic ngoài JSON Schema.
- Schema không tự kiểm tra end >= start hoặc duration = end − start; QC thu thập phải kiểm tra riêng.
- SQI và confidence nằm [0,1], không phải phần trăm; ngưỡng và toán tử biên xem tài liệu labeling.
- `sync_error_ms >100` là gate dataset V0 kế thừa, không engine issue hay ngưỡng y khoa. Unknown error chưa đủ điều kiện đối chiếu đồng bộ.
- Video/reference cùng subject/session, có khoảng thời gian chồng lấp; sample_id không trùng. QC dataset không suy ra từ engine status đơn thuần.
- Runner run_vitals_pipeline xuất wrapper `{result, patch}` của frontend, không raw VitalsResult; không validate wrapper bằng schema này.
