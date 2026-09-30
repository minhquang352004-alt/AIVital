# AIVitals – Reference Quality Labeling V0

## 1. PASS – Đạt
- Đủ metadata.
- Video đọc được.
- Khuôn mặt nhìn rõ.
- FPS và ánh sáng hợp lệ.
- Có reference signal.
- Có timestamp.
- Đồng bộ đạt yêu cầu.
- Không có điều kiện loại nghiêm trọng.

## 2. WARNING – Cảnh báo
Có sai lệch nhỏ nhưng sample vẫn có thể hữu ích cho một phân tích cụ thể. Sai lệch phải ghi trong metadata.

## 3. REJECT – Loại
- VFR.
- Frame drop >5%.
- Video lỗi.
- Thiếu thời lượng/độ phân giải.
- Không detect được mặt.
- ROI che nghiêm trọng >50%.
- Thiếu reference.
- Thiếu timestamp.
- Sync error >100 ms.
- Ánh sáng <5 lux hoặc >700 lux.

## 4. Mã lý do loại
- `SYNC_ERROR`
- `MISSING_REFERENCE`
- `REFERENCE_SIGNAL_POOR`
- `VIDEO_CORRUPTED`
- `FPS_INVALID`
- `FRAME_DROP_GT_5_PERCENT`
- `FACE_NOT_DETECTED`
- `ROI_OCCLUSION_GT_50_PERCENT`
- `INSUFFICIENT_DURATION`
- `INVALID_ILLUMINANCE`

## 5. Quy trình
Kiểm tra video → reference → timestamp → đồng bộ → metadata → gán nhãn → nếu REJECT thì ghi `exclusion_reason`. Không xóa dữ liệu gốc.
