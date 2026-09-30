# AIVitals – Reference Recording Protocol V0

**Week 3:** Reference recordings và dữ liệu tham chiếu  
**Mục tiêu:** Ghi video đồng thời với ECG/PPG reference, đồng bộ thời gian, kiểm tra chất lượng và tạo dữ liệu đầu vào cho Reference Dataset V0.

## 1. Phạm vi
Week 3 tập trung vào dữ liệu tham chiếu. Chưa đánh giá thuật toán rPPG.

## 2. Kế thừa Week 2
- Độ phân giải tối thiểu 320×240; ưu tiên 720p/1080p.
- Camera cố định, ổn định, gần ngang tầm mắt.
- Tối thiểu 30 FPS cho HR/RR; 60 FPS là mục tiêu cho BP/PTT.
- Video dùng tốc độ khung hình cố định (CFR).
- Resting: ngồi ổn định, hướng mặt camera, trung tính, hạn chế chuyển động.
- Resting target: 60 giây.
- Ánh sáng tiêu chuẩn ≥500 lux.
- Ghi đầy đủ metadata và kiểm tra chất lượng.

## 3. Reference recording
Mỗi phiên gồm:
1. Video khuôn mặt.
2. Tín hiệu ECG hoặc PPG tham chiếu.
3. Timestamp video.
4. Timestamp reference.
5. Thiết bị và loại reference.
6. Thông tin đồng bộ.

Tên đề xuất:
- `SUB###_SES##_video.mp4`
- `SUB###_SES##_reference.ext`
- `SUB###_SES##_metadata.csv`

## 4. Quy trình
### Bước 1 – Chuẩn bị người tham gia
Ngồi ổn định, hướng mặt camera, kiểm tra vùng khuôn mặt nhìn rõ.

### Bước 2 – Chuẩn bị camera
Kiểm tra độ phân giải, FPS, ánh sáng; giữ nguyên cấu hình trong phiên; khóa phơi sáng/cân bằng trắng nếu hỗ trợ.

### Bước 3 – Chuẩn bị reference
Kiểm tra ECG/PPG hoạt động, loại thiết bị và timestamp.

### Bước 4 – Đồng bộ
Bắt đầu video và reference trong cùng phiên. Ghi:
- `video_start_timestamp`
- `reference_start_timestamp`
- `video_end_timestamp`
- `reference_end_timestamp`
- `sync_error_ms`

### Bước 5 – Ghi
Ưu tiên resting 60 giây. Có thể ghi thêm motion và low-light theo Protocol V1.

### Bước 6 – Lưu
Video, reference và metadata phải cùng `subject_id` và `session_id`.

### Bước 7 – Kiểm tra
Kiểm tra video, FPS, thời lượng, khuôn mặt, ánh sáng, reference signal, timestamp và đồng bộ.

## 5. Chất lượng
**PASS:** dữ liệu đầy đủ và đạt yêu cầu.  
**WARNING:** có sai lệch nhỏ, vẫn hữu ích cho phân tích cụ thể và phải ghi chú.  
**REJECT:** có điều kiện loại nghiêm trọng.

Các điều kiện loại kế thừa Week 2 gồm VFR, frame drop >5%, video lỗi, thiếu thời lượng/độ phân giải, không detect được mặt, ROI che >50%, thiếu reference/timestamp, sync error >100 ms, ánh sáng <5 hoặc >700 lux.

## 6. Hoàn thành
- [ ] Có video.
- [ ] Có ECG/PPG reference.
- [ ] Có timestamp.
- [ ] Đã kiểm tra đồng bộ.
- [ ] Có HR tham chiếu.
- [ ] Có quality label.
- [ ] Có lý do loại nếu REJECT.
- [ ] Đưa sample hợp lệ vào Reference Dataset V0.
