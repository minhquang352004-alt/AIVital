# AIVitals – Reference Quality Labeling V0

Đối chiếu 2026-10-14 tại `main@5d9b4ae`: `validation/issue_codes.py`, `validation/rules.py`, `validation/vital_validator.py`, `config/vitals_config.py`.
Chỉ phục vụ estimation, wellness, research/screening support.

## 1. Dataset và engine là hai lớp riêng

| Lớp | Giá trị | Ý nghĩa |
|---|---|---|
| Dataset QC | PASS / WARNING / REJECT | Video, reference, timestamp và điều kiện dùng sample |
| Engine status | OK / BAD / INVALID | Root hoặc mỗi vital; sao chép đúng output |
| Engine severity | WARNING / ERROR | Không có INFO trong JSON contract |

`resolve_status`: có ERROR → INVALID; chỉ WARNING → BAD; không issue → OK.
Không chuyển tất cả sample PASS thành engine OK. Dataset REJECT vẫn có thể có engine OK. Kiểm tra từng vital và root riêng.

## 2. Đủ 15 mã engine hiện tại

Severity dưới đây lấy từ default rules, không cố định bởi enum IssueCode. Giữ severity/message/details thực tế từ output.

| IssueCode | Severity trong default rules | Điều kiện / phạm vi |
|---|---|---|
| COMPUTATION_FAILED | ERROR | Candidate không tính được value |
| WINDOW_TOO_SHORT | ERROR | Duration nhỏ hơn minimum của vital |
| MISSING_DATA_HIGH | WARNING | Missing ratio vượt ngưỡng OK, chưa vượt invalid |
| MISSING_DATA_EXCESSIVE | ERROR | Missing ratio vượt ngưỡng invalid |
| SIGNAL_QUALITY_LOW | WARNING | SQI dưới ngưỡng OK, chưa dưới invalid |
| SIGNAL_QUALITY_UNUSABLE | ERROR | SQI dưới ngưỡng invalid |
| OUT_OF_PHYSIOLOGICAL_RANGE | ERROR | Value ngoài khoảng config; không phải chẩn đoán |
| SUDDEN_JUMP | WARNING | Thay đổi > tolerance + rate × elapsed seconds |
| TEMPORAL_UNSTABLE | WARNING | Đủ lịch sử và standard deviation > limit |
| CROSS_ROI_INCONSISTENT | WARNING | >=2 ROI và spread/deviation > limit |
| LOW_CONFIDENCE | WARNING | Confidence dưới ngưỡng OK, chưa dưới invalid |
| VERY_LOW_CONFIDENCE | ERROR | Confidence dưới ngưỡng invalid |
| MISSING_FEATURES | Chưa có rule trong default vitals rules | Enum có khai báo; không suy đoán severity/activation |
| PULSE_PRESSURE_INVALID | Chưa có rule trong default vitals rules | Không chứng minh BP được hỗ trợ |
| FEATURES_OUT_OF_TRAINING_RANGE | Chưa có rule trong default vitals rules | Không suy đoán severity/activation |

## 3. Ngưỡng mặc định và biên chính xác

Ngưỡng thuộc ValidationConfig, không hard-code trong JSON Schema. Ghi config thực khi chạy có override.

| Đại lượng | Không phát issue này | WARNING | ERROR |
|---|---|---|---|
| signal_quality (SQI) | >=0.6 | 0.3 <= q <0.6 | q <0.3 |
| confidence | >=0.6 | 0.3 <= c <0.6 | c <0.3 |
| missing_ratio | <=0.1 | 0.1 < m <=0.3 | m >0.3 |

SignalQualityRule bỏ qua khi value hoặc signal_quality null; ConfidenceRule bỏ qua khi value null. Không có issue SQI không đồng nghĩa tín hiệu tốt.
Không mặc định vital.quality và source.signal_quality là cùng số nếu chưa kiểm tra cách tạo result.

| VitalCode | Minimum window (s) | Khoảng value mặc định, gồm hai biên |
|---|---:|---|
| heart_rate | 6 | 40–180 bpm |
| hrv_rmssd | 30 | 5–250 ms |
| hrv_sdnn | 30 | 5–300 ms |
| hrv_mean_ibi | 30 | 330–1500 ms |
| respiratory_rate | 30 | 6–30 brpm |

Duration đúng minimum không gây WINDOW_TOO_SHORT. Stability cần >=4 giá trị; std limit HR=8, RR=4. Jump tolerance HR=8, RR=4; rate/second HR=3, RR=0.5. Cross-ROI spread limit HR=10. Unit theo code.
Đây là gate nghiên cứu của engine, không tiêu chí chẩn đoán hoặc chứng minh clinical accuracy.

## 4. QC V0: không đưa mã thu thập vào engine issues

PASS: đủ metadata, consent phù hợp, video/reference đọc được, mặt/ROI hợp lệ, reference độc lập đủ chất lượng, timestamp và sai số đồng bộ xác định, không có điều kiện loại.
WARNING: hạn chế nhỏ đã ghi rõ, chỉ dùng cho phân tích cho phép; không mặc định là ground truth waveform.
REJECT: thiếu reference/timestamp/thời lượng/độ phân giải hoặc vi phạm gate V0. Không xóa raw data để che lỗi QC.

Giữ mã V0 trong **metadata exclusion_reason**, không trong issues[].code. Đây không phải mã engine:

| Mã QC dataset | Điều kiện V0 / lưu ý |
|---|---|
| SYNC_ERROR | Residual error >100 ms; unknown cũng chưa đủ PASS |
| MISSING_REFERENCE | Thiếu reference độc lập hoặc khoảng hỗ trợ |
| REFERENCE_SIGNAL_POOR | Không đủ chất lượng cho phân tích dự định |
| VIDEO_CORRUPTED | Không đọc được video |
| FPS_INVALID | FPS/timing không tin cậy; VFR bị REJECT theo V0 hiện tại |
| FRAME_DROP_GT_5_PERCENT | Frame drop >5%; khác engine missing_ratio 10%/30% |
| FACE_NOT_DETECTED | Không có mặt hợp lệ |
| ROI_OCCLUSION_GT_50_PERCENT | Che ROI nghiêm trọng >50%, gate dataset V0 |
| INSUFFICIENT_DURATION | Thiếu thời lượng/metadata; kiểm tra window từng vital riêng |
| INVALID_ILLUMINANCE | Lux <5 hoặc >700, gate V0 khi có phép đo lux |

Lux/occlusion/drop là gate thu thập, không phải SQI; không suy ra từ signal_quality. Chưa đo thì ghi chưa xác định, không bịa số. Thiếu timestamp ghi rõ notes và REJECT; không tự chế issue code engine.

## 5. Quy trình

Consent/metadata → video → reference độc lập → timestamp/overlap → offset/drift/residual → QC dataset → đối chiếu raw engine nếu có.
Ghi QC vào quality_label/exclusion_reason; giữ engine status/issues riêng. Không ghi đè reference bằng estimation.
Điểm dừng Hào và hướng dẫn chạy mẫu: `HAO_TEST_GUIDE_V0.md`.

## 6. Áp dụng cho sample hiện có

HAO_PHONE_001 là video-only, quality_label=REJECT cho reference dataset, exclusion_reason=MISSING_REFERENCE; HR/reference quality/sync unknown, không thay bằng số camera. User full CLI rotate 270 trả frontend REJECTED và score 23; đó là bằng chứng signal QC, không phép đo reference. Metadata/QC tự chạy được lưu riêng ở hao_phone_qc_run02; xem HAO_WEEK3_WEEK4_STATUS.md. Không map mọi issue trong lịch sử vào final result hoặc lấy HR BAD làm ground truth.
