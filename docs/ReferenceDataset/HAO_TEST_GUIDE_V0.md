# HAO ACTION #1 – Chạy mẫu và ghi bằng chứng thực tế

Tài liệu hướng dẫn; chưa có phép đo người thật hoặc kết quả chạy pipeline trong session chuẩn bị tài liệu. Hai sample có trong repo không tự chứng minh có ECG/PPG paired ground truth.

## 1. Chuẩn bị trên PowerShell

Chạy từ `E:\AIVitals_New`. Dùng Python >=3.11 vì engine dùng StrEnum.
Để giữ engine/tests/frontend/db read-only, dùng môi trường ngoài repo và chặn bytecode:

```powershell
Set-Location 'E:\AIVitals_New'
python --version
python -m venv 'E:\AIVitals_HAO_venv'
$haoPython = 'E:\AIVitals_HAO_venv\Scripts\python.exe'
& $haoPython -m pip install -r 'aivitals_engine\requirements.txt'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $haoPython -B -m aivitals_engine.scripts.run_vitals_pipeline --help
```

Nếu venv đã có, bỏ lệnh tạo và dùng lại. Nếu thiếu Python/pip hoặc mạng tải package, xử lý môi trường trước; không sửa engine để chữa lỗi cài đặt.

## 2. Video: runner vitals hiện có

```powershell
& $haoPython -B -m aivitals_engine.scripts.run_vitals_pipeline --video 'aivitals_engine\samples\sample_video.mp4' --method POS --measurement-id hao-w3-smoke
```

- Giữ console output và ngày chạy trong ghi chú kiểm tra. Nếu lưu log, chỉ lưu vùng docs/ReferenceDataset, kiểm tra nội dung không chứa thông tin cá nhân và không ghi đè log cũ.
- Khi có cập nhật, dòng summary có time/window/SQI và heart_rate, hrv_rmssd, respiratory_rate cùng status/issues. Video ngắn có thể không đủ window HRV/RR; INVALID không tự chứng minh runner hỏng.
- JSON cuối là **frontend wrapper** result/patch: READY/REJECTED/PENDING, metrics, quality_score…; không raw VitalsResult. `metrics.heart_rate.value` nếu có là **estimated HR**, không reference HR.
- PENDING hoặc không có cập nhật: chưa có vital result; ghi nguyên trạng, không tự tạo HR. File không mở/traceback: lưu lỗi và gửi Khang/Khoa, không sửa engine trong stream Hào.
- Runner dùng index/FPS làm timestamp video tương đối; smoke test không chứng minh đồng bộ camera–reference <=100 ms.

### Video điện thoại bị xoay ngang mặt

Runner hỗ trợ `--rotate 0/90/180/270` (theo chiều kim đồng hồ), mặc định 0 giữ luồng cũ. Chọn theo hướng frame được decoder trả về, không chỉ theo trình phát điện thoại; không tự xoay mọi video.
Với phone01.mp4 đã kiểm tra ngày 2026-10-14, mặt chỉ được detector nhận sau khi xoay ngược chiều kim đồng hồ 90°:

```powershell
& $haoPython -B -m aivitals_engine.scripts.run_vitals_pipeline --video 'E:\HAO_Recordings\phone01.mp4' --method POS --rotate 270 --measurement-id hao-phone-upright-01
```

Xoay không thay timestamps hoặc hạ ngưỡng. Có thể vẫn REJECTED nếu tín hiệu thực không đạt; không chọn hướng/thuật toán chỉ để ép PASS. Reference độc lập vẫn bắt buộc cho validation.

## 3. RGB CSV: runner khác, chỉ kiểm tra signal/BVP

run_vitals_pipeline dùng OpenCV video và **không nhận CSV RGB**. Không truyền sample_rgb.csv vào --video.

```powershell
& $haoPython -B -m aivitals_engine.main --input 'aivitals_engine\samples\sample_rgb.csv' --method POS --output-dir 'docs\ReferenceDataset\hao_smoke_rgb_run01'
```

Dùng thư mục run mới mỗi lần để tránh ghi đè. Runner này tạo BVP CSV và baseline summary, **không tạo HR reference hoặc raw VitalsResult**. Không dùng output-dir mặc định vì nó ghi vào engine/outputs. RGB không phải ECG/PPG độc lập.

## 4. Điền bảng reference mà không nhầm estimation

Mở HR_Reference_Validation_V0.md; chỉ điền khi có dữ liệu thực:

| Cột hiện có | Điền gì |
|---|---|
| Sample | sample_id có liên kết video/reference/session |
| Reference | Thiết bị/loại ECG/PPG và file độc lập; summary smartwatch phải ghi rõ |
| HR | reference_hr_bpm từ reference đủ chất lượng trong cùng khoảng hỗ trợ, không lấy rPPG |
| Sync error | Residual/cận bất định thực theo TIMESTAMP_SYNC_PROTOCOL, không đoán 0 |
| Quality | PASS/WARNING/REJECT của reference/sample, không engine status |
| Result | ACCEPT/EXCLUDE cho reference sample; thiếu reference/timing phải ghi chưa đủ điều kiện |

Nếu sample có sẵn không kèm reference, để HR/sync chưa xác định và đánh dấu chưa đủ điều kiện; không kết luận validation accuracy. Không bắt buộc điền ba sample khi chỉ có bằng chứng cho một.
Ghi estimated HR, engine status/issues, command, window và log ở phần ghi chú hoặc bảng đối chiếu **riêng** dưới đây; raw status/issues không có trong wrapper cuối thì ghi unavailable, không suy ra từ READY.

| sample_id | command / run time | reference HR (bpm) | estimated HR (bpm) | matched interval | sync error (ms) | engine HR status/issues | evidence path | decision |
|---|---|---|---|---|---|---|---|---|
| [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] | [USER_FILL_REQUIRED] |

Chỉ tính sai số HR khi cả reference và estimation có cùng matched interval đủ QC. Nếu cần raw VitalsResult đầy đủ để kiểm tra schema, nhờ Khoa/Khang cung cấp exporter được nhóm hỗ trợ; không sửa runner trong stream Hào.

## 5. Thử collection trước phiên thật

1. Điền thông tin nghiên cứu, contact, quyền truy cập, retention, withdrawal vào consent; giải thích và ký trước ghi. Lưu bản ký ngoài repo.
2. Chạy phiên thử đồng bộ có marker thực ở cả hai luồng; kiểm tra offset, drift, residual và overlap. Không có marker đủ thì báo hạn chế.
3. Điền CSV bằng số đo thật; mỗi sample_id duy nhất, subject_id giả danh, session_id nhất quán. Trường không áp dụng để trống và giải thích notes; xóa placeholder trước dùng QC.
4. Kiểm tra parse và số dòng bằng `Import-Csv 'docs\CollectionPackage_V1\SESSION_METADATA_TEMPLATE.csv'`. PASS chỉ khi vượt tất cả gate liên quan.
5. Gửi log không nhạy cảm, lỗi nếu có và đường dẫn bằng chứng được cấp quyền để tiếp tục Week 3. Chỉ Hào xác nhận dữ liệu reference thực; tài liệu sẵn không đồng nghĩa Week 3 đã validated.

## 6. Quy trình tự động đã bổ sung

`scripts/data_qc/run_video_qc.py` xuất raw contract và metadata từ file thật; `scripts/data_qc/init_collection_session.py` tạo phiên trống không bịa timestamp quay. Lệnh và mapping DB: ../CollectionPackage_V1/DB_MAPPING_AND_USAGE_V1.md. Giữ template JSON/CSV làm mẫu; số liệu thực nằm trong từng run, không điền các dòng placeholder bằng số giả. Tiến độ/DoD và phần Hào còn phải cung cấp: HAO_WEEK3_WEEK4_STATUS.md.
