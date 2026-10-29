# Disclaimer, Known Limitations và Claim Review V1 – Week 8 (Hào)

Cập nhật 30/10/2026, `main` @ `faffe86`. Hào chỉ review và đề xuất. Code thuộc owner (engine: Khoa/Khang; frontend/DB: Quang) không bị sửa.

## 1. Disclaimer chuẩn (dùng thống nhất)

Hiện có ít nhất 4 chuỗi disclaimer khác nhau: README, `frontend/app/page.tsx`, knowledge `disclaimer`, và `DEFAULT_DISCLAIMER` trong `explanation/service.py`. Đề xuất dùng một bản duy nhất.

**Ngắn (màn hình kết quả, báo cáo AI):**

> Kết quả là ước tính từ camera, chỉ để tham khảo cho mục đích theo dõi sức khỏe tổng quát (wellness). Đây không phải chẩn đoán y khoa và không thay thế thiết bị đo hoặc nhân viên y tế. Nếu có triệu chứng bất thường, hãy liên hệ nhân viên y tế.

**Đầy đủ (màn hình consent / trang giới thiệu / README):**

> AIVitals ước tính nhịp tim, nhịp thở và biến thiên nhịp tim từ video khuôn mặt (rPPG). Đây là sản phẩm nghiên cứu cho mục đích wellness và hỗ trợ sàng lọc, **không phải thiết bị y tế**, chưa được cơ quan quản lý nào cấp phép, và **chưa được kiểm chứng độ chính xác trên người thật so với thiết bị tham chiếu**. Kết quả có thể sai do cử động, ánh sáng, camera, màu da hoặc trang điểm. Khoảng tham chiếu chỉ áp dụng cho người trưởng thành khi nghỉ. Không dùng kết quả để tự chẩn đoán, tự dùng thuốc, đổi thuốc hay trì hoãn đi khám. Khi có đau ngực, khó thở nhiều, ngất hoặc lơ mơ, hãy gọi cấp cứu **115** ngay. AIVitals không đo huyết áp cho người dùng.

## 2. Known limitations (đưa vào release notes / báo cáo cuối)

| # | Giới hạn | Bằng chứng |
|---|---|---|
| L1 | **Chưa có validation trên người thật:** 0 mẫu ghép cặp với ECG/PPG/cuff. Không có MAE/RMSE/bias | Traceability T01–T02 |
| L2 | Số liệu benchmark và độ chính xác hiện có đều trên tín hiệu tổng hợp | `RELEASE_NOTES.md`, T15 |
| L3 | Pilot thật chỉ có 1 người (video-only, 4 video: 1 INVALID, 2 BAD, 1 không có kết quả) và 5 mẫu CLBP (1 HR OK). Không đại diện về tuổi, giới, màu da, thiết bị | T03, T06, T07 |
| L4 | RR là gián tiếp (modulation BVP), mức bằng chứng `promising`; HRV từ camera là PRV, mức `insufficient` cho diễn giải cá nhân | Matrix M02–M04 |
| L5 | Khoảng tham chiếu chỉ cho người trưởng thành khi nghỉ. Engine không kiểm tuổi hay trạng thái nghỉ | Knowledge package §3 |
| L6 | BP và health-risk chỉ là research-only, chưa đạt gate 85 người/255 mẫu | Matrix, Week 5–6 |
| L7 | Nhiễu trắng có thể bị nhận là nhịp tim khi SQI đầu vào cao | `RELEASE_NOTES.md`, `QA_HARDENING.md` §4 |
| L8 | SQI/confidence là điểm chất lượng tín hiệu, không phải xác suất đúng | Data dictionary §A |
| L9 | Guard của tầng LLM để lọt 10/15 câu không an toàn trong red-team (số không đơn vị, thuốc, trấn an sai, accuracy %, không dấu…) | Knowledge package §5 |
| L10 | Wording y khoa chưa có clinician duyệt | Knowledge package, `review_status` |
| L11 | Lock dataset Week 6 dựa trên rule trước W7 (SQI 0,3); `ENGINE_VERSION` chưa tăng theo release 0.2.0 | Traceability §3 |
| L12 | Consent pilot là khai báo qua chat, không có chữ ký. Chưa có quyền chia sẻ public hoặc derived data CLBP | `CONSENT_SUBJ_001_CHAT_V1.json`, handoff |

## 3. Claim review

Mức độ: **P0** = chặn go-live hoặc sign-off; **P1** = sửa trước khi demo cho người ngoài; **P2** = nên sửa.

| ID | Mức | Vị trí | Hiện trạng | Vấn đề | Đề xuất | Owner |
|---|---|---|---|---|---|---|
| C01 | **P0** | `frontend/app/page.tsx` dòng 75–76, 142–153, 165–177, 288 | Khi đo, HR/RR/HRV/SQI khởi tạo 72/16/42/96 rồi đổi ngẫu nhiên ±1 mỗi 800 ms (`Math.random`, kẹp trong 60–100, 12–22, 25–70, 82–99). Dòng 414 hiển thị kèm nhãn "● LIVE". Khi `RESULT_READY`, các số này được `PATCH` vào measurement với `status: "COMPLETED"` | **Số đo bị tạo giả rồi được lưu và hiển thị như kết quả thật.** Vì bị kẹp trong 60–100, HR luôn rơi vào "khoảng thường gặp", tức là trấn an sai một cách có hệ thống | Gọi engine `/api/v1/vitals/compute` và chỉ hiển thị/lưu `VitalValue` có status OK, kèm `result_id`/`engine_version`. Nếu còn giữ chế độ demo thì gắn nhãn "DỮ LIỆU MÔ PHỎNG", không lưu DB như COMPLETED, không gọi là LIVE | Quang |
| C02 | **P0** | `page.tsx` dòng 297 | `consent: { accepted: true, policy_version: "2026-09-01" }` được gửi khi bấm "Bắt đầu đo". Màn hình chỉ nói về quyền camera | Ghi nhận đã đồng ý trong khi người dùng chưa thấy nội dung consent hay chính sách dữ liệu | Thêm bước consent rõ ràng (nội dung theo `CONSENT_AND_PRIVACY_FORM_V1.md`, xác nhận ≥18 tuổi), chỉ gửi `accepted: true` sau khi người dùng tick | Quang |
| C03 | P1 | `frontend/app/api/v0/.../result/route.ts` dòng 17 | `quality_score >= 80` → `"GOOD"` | Thang và ngưỡng tự đặt, không khớp engine (SQI 0–1, 0,4/0,6, status OK/BAD/INVALID) | Dùng `status` và `quality` của engine; không quy SQI ra % | Quang |
| C04 | P1 | `page.tsx` dòng 414 | `SQI {qualityScore}%` | Hiển thị SQI dạng % dễ bị hiểu là độ chính xác | Hiển thị nhãn chất lượng (Tốt / Kém / Không dùng được) theo status | Quang |
| C05 | P1 | `explanation/guard.py` | Xem L9 | LLM có thể nói về thuốc, accuracy, trấn an sai | G1–G7 trong knowledge package | Khoa |
| C06 | P1 | `health/knowledge/health_findings_vi.json` | v0.1: RR `established`, thiếu red flag 115, không có "ước tính" | Mức bằng chứng cao hơn matrix; thiếu hướng xử trí khẩn cấp | Áp dụng v0.2 đề xuất | Khoa |
| C07 | P2 | `page.tsx` dòng 421 | "…không thay thế chẩn đoán y khoa." | Đúng hướng nhưng thiếu "ước tính", "chưa kiểm chứng độ chính xác", 115 | Dùng disclaimer ngắn §1 | Quang |
| C08 | P2 | `page.tsx` dòng 395 | "Đo các chỉ số sinh hiệu cơ bản bằng camera trong vài giây." | "Đo" và "vài giây" chưa đúng: HRV/RR cần cửa sổ ≥30 s, và đây là ước tính | "Ước tính một số chỉ số sinh hiệu bằng camera trong khoảng 30–60 giây." | Quang |
| C09 | P2 | `page.tsx` dòng 421 (gợi ý hôm nay) | "…để theo dõi xu hướng chính xác hơn." | Ngụ ý hệ thống có độ chính xác đã biết | "…để so sánh các lần đo với nhau tốt hơn." | Quang |
| C10 | P2 | `README.md` dòng 115 | "KHÔNG mặc định được sử dụng làm chẩn đoán y khoa độc lập" | Chữ "mặc định" và "độc lập" làm câu yếu đi, có thể hiểu là trong một số trường hợp vẫn dùng để chẩn đoán được | "Không được dùng để chẩn đoán y khoa…" và bổ sung L1 | Nhóm |
| C11 | P2 | `README.md` dòng 17 | Định hướng BP "dựa trên dữ liệu đối chuẩn y tế có ground-truth" | Hiện chưa có ground truth BP đạt protocol | Thêm "(chưa có; đang thu thập)" | Nhóm |
| C12 | OK | `page.tsx` dòng 395 | "không lưu hình ảnh khuôn mặt" | Không thấy code upload frame trong `page.tsx` (chỉ kiểm sơ bộ, chưa kiểm network/backend) | Giữ; Quang xác nhận ở backend | Quang |

Phương pháp: grep có mục tiêu các từ khóa claim (chẩn đoán, chính xác, y tế, medical, accuracy, huyết áp, clinical, thay thế, `Math.random`, `mmHg`, `SpO2`) trong `frontend/app`, `README.md` và tầng explanation của engine, sau đó đọc ngữ cảnh. Chưa chạy app, chưa kiểm UI thực tế, chưa rà toàn bộ text frontend.
