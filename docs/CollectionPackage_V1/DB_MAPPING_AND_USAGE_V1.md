# Collection V1 – DB mapping và cách dùng

Đối chiếu read-only `db/001_week2_camera_demo.sql`, `db/002_engine_metadata.sql` tại main@5d9b4ae. Đây là mapping thiết kế, không migration/import và chưa được kiểm tra với DB chạy thật.

## Mapping giữ đúng ý nghĩa

| Nguồn nghiên cứu/engine | DB đích / điều kiện |
|---|---|
| subject_id, session_id, sample_id | Mã nghiên cứu, không tự cast thành UUID. Quang cấp mapping sang users.id/sessions.id/measurements.id; không tự tạo hàng DB |
| consent_record_id/version | Liên kết riêng tới consents.id/policy_version. sessions.consent_accepted và consents.accepted cần bằng chứng đồng ý, chưa có thì không tạo session chính thức |
| consent accepted_at | Cần thời gian thực khi accepted=true; migration 002 có CHECK. Không lấy initialization_timestamp thay accepted_at |
| camera_facing | cameras.facing: user/environment, bắt buộc khi insert |
| camera_device, width_px, height_px, fps_actual | cameras.device_label/width/height/fps; kích thước raw khác frame đã xoay, ghi rõ rotation trong QC |
| permission_status | cameras yêu cầu unknown/granted/denied/error. Phân tích file không chứng minh permission camera trên frontend |
| capture start/end | measurements.started_at/stopped_at; không dùng measured_at của lần xử lý offline |
| frontend patch status/state | measurements.status/state theo enum 001. Dataset REJECT không phải giá trị measurements.status |
| raw vital value | vital_measurements.heart_rate/respiration_rate/hrv_rmssd qua mapper hiện tại; raw respiratory_rate unit brpm, frontend breaths_per_minute |
| raw source.signal_quality | measurement_quality.bvp_sqi [0,1]; không đổi sang 0–100 |
| frontend quality_score | vital_measurements.quality_score [0,100] |
| raw status/issues/engine_version | validations.status OK/BAD/INVALID; reason/details/validator_version. READY/REJECTED không phải validations.status |
| algorithm/method/model version | Lookup rppg_methods/model_versions; FK không được điền bằng tên phương pháp |
| age/sex/Fitzpatrick/lux/reference HR/BP/sync | Không có cột tương ứng trong 001/002. Giữ nghiên cứu ngoài DB hoặc đề xuất contract cho Quang; không tự thêm cột hoặc nhét vào bảng khác |

Không có exporter DB trong task này; file JSON/CSV là metadata nghiên cứu với mapping nêu trên, không payload insert đã hoàn chỉnh. Với consent/reference thiếu, để null/trống, không tự gán false như thể đã từ chối hoặc 0 như thể đã đo.

## Khởi tạo phiên metadata-only

```powershell
& $haoPython -B scripts/data_qc/init_collection_session.py --subject-id SUBJ_001 --session-id SESSION_001 --dry-run
& $haoPython -B scripts/data_qc/init_collection_session.py --subject-id SUBJ_001 --session-id SESSION_001
```

Tạo docs/CollectionPackage_V1/data_samples/SUBJ_001/SESSION_001/metadata.json. Không ghi đè phiên cũ, không copy video vào Git, không bịa capture start. Điền consent/measurement thực sau thu; signed consent/raw video giữ ở kho riêng.

## Tự động QC file có sẵn

```powershell
& $haoPython -B scripts/data_qc/run_video_qc.py --video 'E:\HAO_Recordings\phone01.mp4' --rotate 270 --sample-id HAO_PHONE_001 --session-id hao-phone-upright-01 --output-dir docs/ReferenceDataset/hao_phone_qc_run03
```

Chọn run ID mới mỗi lần. Script đọc full video bằng engine hiện có, giữ gates, xuất raw_vitals_result.json, frontend_result.json, updates.jsonl, qc_summary.json và metadata.json/csv. Không ghi lại video hoặc ghi DB. Status rejected vẫn là kết quả QC hợp lệ; reference_dataset vẫn REJECT khi không có reference. File updates chứa estimation theo phiên, phải quản lý như dữ liệu nghiên cứu, không public/push khi chưa chốt consent/phạm vi chia sẻ.

## Chưa có thì không được tự điền

Subject ID do người thu cấp, tuổi/giới tính/Fitzpatrick tự khai/đánh giá theo protocol, model thiết bị, lux thật, consent/time, capture UTC, reference và sync. Script không suy đoán các trường này từ video hoặc filesystem mtime.
