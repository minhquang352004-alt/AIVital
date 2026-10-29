# AIVitals – HR Reference Validation V0

## 1. Mục tiêu
Kiểm tra HR lấy từ ECG/PPG reference trước khi đưa sample vào Reference Dataset V0.

**Không dùng bước này để đánh giá thuật toán rPPG.**

## 2. Quy trình
ECG/PPG → kiểm tra tín hiệu → xác định HR reference → kiểm tra timestamp → kiểm tra đồng bộ → gán nhãn → ACCEPT/EXCLUDE.

## 3. Kiểm tra
- Có file reference và đọc được.
- Có timestamp.
- Có dữ liệu tương ứng với video.
- Tín hiệu không mất dữ liệu nghiêm trọng.
- Thiết bị reference được ghi rõ.
- Có `reference_hr_bpm`.
- Có `reference_quality`.
- Có `sync_error_ms`.

## 4. Đồng bộ
Ngưỡng hiện tại kế thừa Week 2:
`sync_error_ms > 100 ms` → REJECT.

## 5. Bảng kiểm tra

| Sample | Reference | HR | Sync error | Quality | Result |
|---|---|---:|---:|---|---|
| HAO_PHONE_001 | Không có thiết bị/file reference độc lập | Chưa có | Chưa xác định | REJECT cho reference dataset | EXCLUDE — MISSING_REFERENCE; thiếu timestamp reference/sync |
| HAO_PHONE_002 | Không có thiết bị/file reference độc lập | Chưa có | Chưa xác định | REJECT cho reference dataset | EXCLUDE — MISSING_REFERENCE; HR camera BAD không phải reference |
| HAO_PHONE_003 | Không có thiết bị/file reference độc lập | Chưa có | Chưa xác định | REJECT cho reference dataset | EXCLUDE — MISSING_REFERENCE; không dùng HR estimation 88.1 làm reference |
| HAO_PHONE_004 | Không có thiết bị/file reference độc lập | Chưa có | Chưa xác định | REJECT cho reference dataset | EXCLUDE — MISSING_REFERENCE; không có eligible vital output |

**Không tự điền HR nếu reference signal không đủ chất lượng.**

## 6. Bằng chứng hiện có (2026-10-14)

- Một file hiện tại phone01.mp4; các lần quay ghi đè trước không được coi là sample độc lập còn lưu.
- User chạy POS, rotate 270, session hao-phone-upright-01: cửa sổ 40.7–57.7 s; cuối frontend REJECTED/FAILED, quality score 23, các vital null. Một số HR BAD là estimation, không reference.
- measured_at 2026-10-14T15:28:13.073805Z là thời gian tính toán của engine, không timestamp bắt đầu quay hay reference.
- Agent đã chạy full QC độc lập: exit 0, 1906 frame, 16 cập nhật, cửa sổ tính toán lớn nhất 57.482 s, final engine INVALID/frontend REJECTED, quality score 23. Raw result/summary lưu ở hao_phone_qc_run02; metadata thực ở ../CollectionPackage_V1/SESSION_METADATA_ACTUAL_V1.json/.csv. Đây không phải reference validation.
- Không tính MAE/RMSE/bias khi không có paired reference. Week 3 empirical reference validation chưa hoàn thành; EXCLUDE là quyết định QC hợp lệ, không bằng chứng estimator đã được validation.

## 7. Public reference candidate (không thuộc video của Hào)

| Candidate | Khoảng HR tương đối | Reference HR mean | Engine HR | Sync error | Quyết định |
|---|---|---:|---|---|---|
| MPU file 55553426/55553429, window 1 | [20,30) s theo giả định index/60 Hz | 71.0 bpm | null INVALID | Chưa xác minh sample | EXCLUDE strict acceptance; giữ exploratory |
| Cùng candidate, window 2 | [50,60) s theo giả định index/60 Hz | 71.0 bpm | null INVALID | Chưa xác minh sample | EXCLUDE strict acceptance; giữ exploratory |

Hai cửa sổ không phải hai subject/sample độc lập. Reference lấy từ HR của CSV thiết bị, không camera. Bằng chứng, attribution và các giả định: WEEK3_PUBLIC_REFERENCE_BENCHMARK_V1.md. Không tính error metrics với estimate null hoặc gán published ±8 ms thành sai số thực đã đo.
