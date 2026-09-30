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
| S001 | ECG/PPG | [thực tế] | [thực tế] | PASS/WARNING/REJECT | |
| S002 | ECG/PPG | [thực tế] | [thực tế] | PASS/WARNING/REJECT | |
| S003 | ECG/PPG | [thực tế] | [thực tế] | PASS/WARNING/REJECT | |

**Không tự điền HR nếu reference signal không đủ chất lượng.**
