# HAO – Week 3/4 evidence và điểm còn thiếu

Cập nhật 2026-10-14. Kết quả phục vụ estimation, wellness, research/screening support; không clinical diagnosis.

| Hạng mục | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| Week 3 schema/issue alignment | Hoàn tất tài liệu | 15 IssueCodes; phân biệt JSON/runtime/dataset/mapper |
| Fixture video/RGB smoke test | User đã chạy | Engine samples; không ground truth người thật |
| Phone video đã quay | 4 file xác nhận | Mỗi file ~60–64 s; đủ số lượng pilot, không tự trở thành paired samples |
| Đúng hướng mặt | Đã xử lý | Runner --rotate 270, defaults unchanged; 18 tests trước đã pass |
| Signal QC | Chưa đạt tốt | phone01 REJECTED/23; phone02 READY/POOR/34; phone03 READY/POOR/33; phone04 PENDING, no vital |
| Reference HR / ECG / PPG | Thiếu | Không có thiết bị, file hoặc paired reference; không tính MAE/RMSE |
| Timestamp capture / sync | Thiếu | Timestamp processing không phải capture; sync_error chưa xác định |
| Week 3 reference DoD | Chưa hoàn thành | 0 accepted paired reference samples |
| Public dataset investigation / exploratory baseline | Đã thực hiện | 4 nguồn đánh giá; MPU public sample tải/checksum, 2 cửa sổ test, estimate null và sync chưa xác minh |
| Week 4 collection package | Đã bổ sung | Consent/sync, JSON+CSV 57 cột, DB mapping, init/QC scripts |
| Week 4 official 3–5 paired sessions | Chưa hoàn thành | Đã 4 video-only; số lượng pilot đủ nhưng không có paired reference/full policy/timing |
| BP nếu khả thi | Chưa có | Không bịa BP; không có BP VitalCode hiện tại |

## Automated evidence

Lượt hao_phone_qc_run02 đã chạy hoàn tất, exit 0: 1906/1906 frame decode, 64.372 s, FPS decoder 29.609, raw 848x480, rotate 270. Có 16 cập nhật; cửa sổ tính toán lớn nhất 57.482 s. Final raw engine INVALID; frontend REJECTED, quality score 23. Đã xuất raw contract, frontend payload, update evidence, summary và metadata; không có reference nên không đổi DoD.

- Bằng chứng: hao_phone_qc_run02/qc_summary.json, raw_vitals_result.json, frontend_result.json, updates.jsonl.
- Metadata thực đã điền các trường đo được: ../CollectionPackage_V1/SESSION_METADATA_ACTUAL_V1.json và .csv. Template giữ 3 dòng placeholder để tạo phiên mới; không thay bằng số giả.
- Người tham gia tự xác nhận: SUBJ_001 (mã được gán), OPPO A16, camera trước; đồng ý nghiên cứu nội bộ qua chat, record CONSENT_SUBJ_001_CHAT_V1.json. Unknowns vẫn null/trống: demographics, lux, capture UTC, full consent policy/signature và mọi reference/sync field. Timestamp run/init không phải timestamp quay. Run evidence trước xác nhận được giữ nguyên để không sửa lịch sử.
- Kiểm tra: 57 trường JSON/CSV khớp, 3 dòng template, runtime-generated schema bằng tracked vital_result.schema.json; 3 test init/QC-path pass và 18 test rotation/buffer từ lượt fix trước. Kiểm tra DB thật không chạy; raw contract được kiểm tra Pydantic.

## Những gì Hào còn phải cung cấp

1. Consent hợp lệ và thông tin session/camera thực (không gửi chữ ký/identity lên Git).
2. Reference độc lập: mượn thiết bị và thu đồng thời, hoặc dữ liệu paired có provenance/license/sync đủ theo protocol. HR summary chỉ đáp ứng phép so sánh tương ứng, không thay waveform.
3. Timestamp/marker/uncertainty thật và các trường chưa đo. Không có lux meter thì ghi missing, không ước lượng số lux từ camera.
4. 3–5 phiên đúng protocol cho Week 4; sample không đạt giữ evidence và loại rõ ràng. Không hạ gate hoặc nhân bản một video để đủ số sample.

Không có các bằng chứng này thì không thể trung thực đánh dấu Week 3/4 SUCCESS; phần chuẩn bị và tự động hóa có thể hoàn tất độc lập.

## Kế hoạch không có thiết bị (cập nhật theo user)

Nhóm xác nhận không có thiết bị. Đã bổ sung nhánh video_only trong TIMESTAMP_SYNC_PROTOCOL.md: thu 3–4 phiên riêng, ghi start/end/source/precision, QC hướng/frame timing/tín hiệu, sensor-sync/PTT/reference giữ missing. Pilot video-only không thay DoD reference. Dataset paired công khai là hướng cho Week 3 sau kiểm tra nguồn/quyền/timing; Week 4 cần nhóm chốt scope pilot hoặc có reference thật. Khuyến nghị QC một phiên mới trước khi quay hết; không đếm video lỗi thành accepted reference samples.

phone02 full automated QC completed: 1798 frames, 7 updates, root BAD/frontend READY/POOR, score 34. User-reported recording 2026-10-14 23:11 UTC+07, minute precision, start/end unspecified. Decoder intervals 33.678–48.578 ms, CFR/sync not certified. Current sample metadata is SESSION_METADATA_HAO_PHONE_002.json/.csv; COLLECTION_MANIFEST_V1.json indexes both current samples. Reference accepted count stays 0; keep gates unchanged.

## Deliverables completed in latest task

- Full phone03/04 QC completed; manifest now indexes four distinct recordings. phone03: 13 updates, BAD/READY/POOR/33, HRV/RR unavailable. phone04: 0 updates, no raw result/PENDING. Metadata date/time for these two is missing, not copied from previous sessions.
- Week 4 preparation and four-video pilot QC: completed as a subtask, details ../CollectionPackage_V1/WEEK4_VIDEO_ONLY_PILOT_REPORT.md. Original paired-reference collection DoD remains incomplete; no implicit scope approval.
- Dataset decision matrix: PUBLIC_DATASET_ASSESSMENT_V1.md. MPU exploratory test: WEEK3_PUBLIC_REFERENCE_BENCHMARK_V1.md; actual first-60-second test has 0 non-null HR estimates, so MAE/RMSE unavailable. Candidate alignment assumptions do not satisfy strict reference acceptance.
- Next group decision/action: obtain verified pairing/timebase/sync and review failed baseline with engine owners, or explicitly approve video-only pilot + external exploratory benchmark as revised milestones. No need to shoot more identical no-reference videos merely to increase count.
