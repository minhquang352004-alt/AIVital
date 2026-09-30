# KẾ HOẠCH THU THẬP DỮ LIỆU (rPPG & HEALTH SCREENING)

## 1. Mục tiêu
Thu thập bộ dữ liệu video khuôn mặt chất lượng cao, đồng bộ với thiết bị y tế chuẩn (Ground Truth) để huấn luyện/kiểm thử các thuật toán rPPG (HR, HRV, RR, ước tính xu hướng BP).

## 2. Thiết bị & Môi trường
* **Camera:** Tối thiểu 320 × 240 pixels (ưu tiên 720p hoặc 1080p trên webcam/laptop/điện thoại).
* **FPS:** Khung hình cố định (Constant Frame Rate - CFR) ở mức tối thiểu 30 FPS (đo HR, RR) và 60 FPS (đo BP/PTT).
* **Ánh sáng:** Tối thiểu 500 lux trở lên, chiếu trực diện (ring light), không bị bóng đổ, ngược sáng hay nhấp nháy đèn. Khóa cố định Auto-Exposure/White Balance và cố định độ sáng màn hình.

## 3. Thiết bị Đối chứng Y khoa (Reference Devices)
* **HR/SpO2/ECG:** CMS50E pulse oximeter, Beurer, hoặc hệ thống Biosignalplux / Biopac / GETEMED ECG.
* **Huyết áp (BP):** OMRON-BP 7000, OMRON HEM-1020, OMRON M2, hoặc Biopac NIBP100D. **Không dùng smartwatch.**
* **Timestamping:** Ghi nhận timestamp từ phần mềm cảm biến theo khoảng thời gian đều đặn, đồng bộ chính xác thời điểm bắt đầu/kết thúc giữa video và máy y tế.

## 4. Đặc tả Người tham gia (Tránh AI Bias)
* **Màu da:** Đủ dải màu da Fitzpatrick (Type I–VI), chú trọng đặc biệt da tối màu (Loại V & VI, tối thiểu 35% – 40%) để xử lý vấn đề hấp thụ ánh sáng của Melanin.
* **Che khuất (Occlusion):** Tỷ lệ 15% – 20% người tham gia đeo kính râm/kính cận, có râu, tóc mái che trán, đội khăn trùm đầu hoặc trang điểm nhẹ.

## 5. Kịch bản Thu thập
* **Tĩnh (Resting):** Ngồi yên 60 giây, nhìn thẳng camera.
* **Động (Motion):** Gật/xoay đầu (±30°), đổi biểu cảm, vừa nói chuyện/nhai.
* **Thiếu sáng (Low Light):** Ánh sáng yếu 8 lux hoặc 42.4 lux (màn hình hắt vào).
* **Nhịp tim cao (Elevated HR):** Vận động nhẹ trước khi quay để đẩy HR lên 90 – 140 BPM.

## 6. Tiêu chuẩn Loại bỏ (Data Exclusion)
* Video rớt khung hình > 5% hoặc dùng FPS biến thiên (VFR).
* Tóc/phụ kiện che khuất > 50% vùng trán/ROI chính.
* Thiếu hoặc không đồng bộ được dữ liệu đối chứng y tế (sai lệch timestamp > 100ms).
* Cháy sáng (>700 lux) hoặc quá tối (<5 lux).