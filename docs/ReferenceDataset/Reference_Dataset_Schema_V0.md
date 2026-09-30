# AIVitals – Reference Dataset Schema V0

## 1. Mục tiêu
Chuẩn hóa cấu trúc dữ liệu liên kết video với ECG/PPG reference và kết quả kiểm tra chất lượng.

## 2. Các trường chính

| Field | Ý nghĩa | Bắt buộc |
|---|---|---|
| sample_id | Mã sample duy nhất | Có |
| subject_id | Mã người tham gia | Có |
| session_id | Mã phiên | Có |
| video_filename | Tên video | Có |
| video_start_timestamp | Bắt đầu video | Có |
| video_end_timestamp | Kết thúc video | Có |
| video_duration_sec | Thời lượng | Có |
| width_px | Chiều rộng | Có |
| height_px | Chiều cao | Có |
| fps_actual | FPS thực tế | Có |
| reference_filename | File ECG/PPG | Có |
| reference_device | Thiết bị reference | Có |
| reference_type | ECG hoặc PPG | Có |
| reference_start_timestamp | Bắt đầu reference | Có |
| reference_end_timestamp | Kết thúc reference | Có |
| sync_error_ms | Sai lệch đồng bộ | Có |
| reference_hr_bpm | HR tham chiếu | Nếu tính được |
| reference_quality | Chất lượng reference | Có |
| video_quality | Chất lượng video | Có |
| quality_label | PASS/WARNING/REJECT | Có |
| exclusion_reason | Lý do loại | Khi REJECT |
| scenario | Resting/Motion/Low-light | Có |
| notes | Ghi chú | Không |

## 3. Quy tắc
- `sample_id` không trùng.
- Video và reference cùng `subject_id` + `session_id`.
- Thiếu reference hoặc timestamp → không phải reference sample hoàn chỉnh.
- `sync_error_ms > 100` → REJECT.
- Quality label phải được ghi sau kiểm tra.
