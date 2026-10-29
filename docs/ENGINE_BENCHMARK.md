# Báo Cáo Đo Kiểm Hiệu Năng & Độ Bền rPPG Engine (Tuần 6)
**Ngày thực hiện:** 2026-10-27 10:39:54  
**Người phụ trách:** Khang (Coding / AI Signal)  
**Môi trường thử nghiệm:** Python 3.14.7 | Nền tảng: win32  
**Dữ liệu kiểm thử:** `vid.avi`  
**Thời lượng kiểm thử:** Toàn bộ video (Full duration)  
**Bộ phát hiện khuôn mặt:** `Google MediaPipe Face Mesh (478 landmarks, Active)`

---

## 1. So Sánh Hiệu Năng 3 Thuật Toán rPPG Core (POS vs CHROM vs GREEN)

| Thuật toán | Thông lượng (FPS) | Độ trễ Median (ms) | Độ trễ p95 (ms) | CPU (%) | RAM (MB) | SQI Trung bình | Tỷ lệ Accepted |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **POS** | 49.6 FPS | 21.11 ms | 24.27 ms | 105.7% | 2386.1 MB | 0.687 | 69.2% |
| **CHROM** | 64.3 FPS | 14.92 ms | 17.09 ms | 107.2% | 2393.3 MB | 0.637 | 69.2% |
| **GREEN** | 67.0 FPS | 14.2 ms | 16.38 ms | 106.1% | 2395.7 MB | 0.351 | 21.3% |

> **Phân tích kỹ thuật:**
> - **Ngân sách thời gian thực (Budget 33.3 ms @ 30 FPS):** Cả 3 thuật toán đều đáp ứng tốt yêu cầu thời gian thực. Thuật toán POS tiêu tốn median 21.11 ms/frame (đạt thông lượng 49.6 FPS), vượt xa ngưỡng trần 33.3 ms (30 FPS).
> - **Chất lượng sóng (BVP Quality):** POS duy trì chỉ số SQI cao nhất (0.687) cùng tỷ lệ Accepted đạt 69.2%, thể hiện khả năng bù trừ thay đổi pha màu da và chống nhiễu vượt trội so với CHROM và GREEN.
> - **GREEN Method:** Tốc độ xử lý nhanh nhất (67.0 FPS với độ trễ median 14.2 ms/frame), đóng vai trò thuật toán dự phòng tối ưu cho các thiết bị di động/máy yếu.

---

## 2. Đánh Giá Cơ Chế Multi-ROI (Trán vs Trán + 2 Gò Má — Task 3)

| Hạng mục đo lường | Single-ROI (Chỉ Trán) | Multi-ROI (Trán + 2 Má) | Độ lệch (Delta / Overhead) |
|:---|:---:|:---:|:---:|
| **Thời gian trích xuất RGB (Median)** | 0.143 ms | 0.239 ms | +0.096 ms (+67.3%) |
| **Độ trễ toàn bộ Pipeline (Median)** | 20.98 ms | 21.23 ms | +0.25 ms |
| **Chất lượng sóng BVP (Mean SQI)** | 0.643 | 0.687 | $\Delta = +0.044$ |
| **Tương quan Cross-ROI ($r_{mean}$)** | — | **$r = 0.54$** | Đạt chuẩn (r > 0.5) |

> **Kết luận Task 3:**
> - Chi phí tính toán thêm của Multi-ROI là rất nhỏ (+0.096 ms cho khâu trích xuất, và độ trễ toàn pipeline duy trì ổn định quanh mức ~21.23 ms).
> - Chất lượng sóng BVP cải thiện (SQI tăng +0.044). Tương quan tín hiệu giữa trán và 2 má đạt mức đồng bộ tốt ($r = 0.54$), phản ánh đúng đặc tính tưới máu đồng pha trên mặt thật. Cơ chế Multi-ROI là hoàn toàn khả thi và **khuyến nghị bật mặc định** để hỗ trợ Quality Gate.

---

## 3. Ma Trận Khảo Sát Tình Huống Biên & Độ Bền (Failure Cases — Task 4)

| Tình huống lỗi (Scenario) | Điều kiện kích hoạt | Hành vi & Cơ chế xử lý | Trạng thái |
|:---|:---|:---|:---:|
| **1. Mất mặt (Face Loss)** | Bbox = None trong 30 frames | Bật cờ `FACE_LOST`, tạm dừng push buffer, tự phục hồi khi thấy lại mặt | ✅ PASS |
| **2. Thiếu sáng cực hạn** | Độ sáng pixel mean < 25 | SQI tự động tụt, Quality Gate chuyển sang `REJECTED`, không văng lỗi | ✅ PASS |
| **3. Chói lóa bão hòa (Flash)** | Pixel mean > 235 (Saturation) | Kích hoạt bộ phát hiện đột biến `ARTIFACT`, chặn frame nhiễu | ✅ PASS |
| **4. Rung lắc đầu (Motion)** | Độ dịch chuyển khuôn mặt đột ngột | Bộ lọc `Motion SQI` phát hiện và hạ độ tin cậy của cửa sổ xuống thấp | ✅ PASS |
| **5. Rớt FPS Camera (Jitter)** | Khoảng cách timestamp không đều (15-30 Hz) | Module `resample_to_fixed_fps` nội suy mượt mà về tần số chuẩn 30.0 Hz | ✅ PASS |

---

## 4. Biên Bản Nghiệm Thu & Bàn Giao Kỹ Thuật (DoD Sign-off — Task 5)

### 4.1 Bàn giao cho Quang (Frontend & API Integration)
- **Thuật toán mặc định:** Khuyến nghị đặt **`POS` làm mặc định** cho Web MVP vì cân bằng tối ưu giữa độ ổn định và độ trễ (21.11 ms, đạt 49.6 FPS).
- **Cấu hình Web Camera đề xuất:**
  - Độ phân giải khuyến nghị: $640 \times 480$ (vừa nhẹ CPU, vừa đủ diện tích pixel cho ROI).
  - Tần số khung hình mục tiêu: $30.0\text{ FPS}$ (tối thiểu không được dưới $20\text{ FPS}$).
  - Cửa sổ phân tích: Giữ buffer **$8.0\text{ giây}$**, bắt đầu hiển thị sơ bộ khi nạp đủ $3.0\text{ giây}$.
- **Mã lỗi & Cảnh báo UI:** Khi nhận status từ Engine, hiển thị hướng dẫn trực quan:
  - `FACE_LOST` $\to$ *"Vui lòng đưa khuôn mặt vào giữa khung hình"*.
  - `ARTIFACT` $\to$ *"Phát hiện rung lắc hoặc ánh sáng thay đổi, vui lòng ngồi yên"*.
  - `LOW_QUALITY` $\to$ *"Tín hiệu yếu, hãy tăng cường ánh sáng phòng"*.

### 4.2 Bàn giao cho Khoa (AI Application & Validation)
- **Ngưỡng lọc dữ liệu (Quality Thresholds):** Đề xuất Khoa sử dụng các ngưỡng cắt sau trong `vital_validator.py`:
  - Ngưỡng từ chối chất lượng: **`SQI < 0.40`** $\to$ Gán cờ `REJECTED`, không tính nhịp tim/huyết áp.
  - Ngưỡng tương quan chéo: **`r_mean < 0.35`** $\to$ Cảnh báo không nhất quán giữa trán và má.
  - Bộ đặc trưng BVP (`BVPFeatures` 23 chiều) hoạt động đồng bộ với tốc độ trích xuất $< 3\text{ ms}$.

### 4.3 Bàn giao cho Hào (Data & Protocol)
- Đưa vào quy trình thu thập dữ liệu (*Measurement Protocol*): Bắt buộc người đo ngồi cách camera $0.5 - 0.8\text{ m}$, tránh ngồi ngay dưới bóng đèn tuýp nhấp nháy 50Hz, và giữ yên tư thế trong 10 giây đầu tiên.