# Final Validation Report V1 – Research/Data Sign-off Week 8 (Hào)

Cập nhật 30/10/2026 (Asia/Bangkok). Checkout `E:\AIVitals_New`, `main` @ `faffe86` + thay đổi local chưa commit.

## 0. Kết luận

**Đề nghị sign-off Research/Data: CÓ ĐIỀU KIỆN – chỉ cho demo nội bộ / nghiên cứu, KHÔNG cho go-live tới người dùng thật.**

- Phần tài liệu Research/Data cho W7–W8 đã hoàn thành: knowledge package, data dictionary, traceability, disclaimer, limitations, claim review.
- **Validation độ chính xác trên người thật: chưa thực hiện được.** Paired reference = 0, metrics = null. Không có con số độ chính xác nào để công bố.
- **2 blocker P0 ngoài phạm vi Hào** chặn go-live. C01: frontend tạo số đo ngẫu nhiên và lưu như kết quả thật. C02: consent tự ghi `accepted: true`.

Sign-off này chưa được nhóm hay giảng viên xác nhận (xem mục 6).

## 1. Phạm vi và deliverables

| Task (plan W7/W8 của Hào) | Deliverable | Trạng thái |
|---|---|---|
| W7: Health knowledge base / evidence summary | `docs/EvidenceMatrix_BP/health_knowledge_v1/MEDICAL_KNOWLEDGE_PACKAGE_V1.md` §2 | Xong (chờ clinician) |
| W7: finding → interpretation → caution | Như trên §3 + `health_findings_vi.proposed_v0.2.0.json` | Xong, đề xuất; Khoa áp dụng vào engine |
| W7: Review medical wording / prompts | Như trên §4–5 + `GUARD_REDTEAM_RESULTS_V1.json` + `scripts/data_qc/review_health_knowledge_guard.py` | Xong; có kết quả chạy thật |
| W8: Final validation report | Tài liệu này | Xong; validation thật vẫn pending |
| W8: Data dictionary | `DATA_DICTIONARY_V1.md` | Xong |
| W8: Evidence traceability | `EVIDENCE_TRACEABILITY_V1.md` | Xong; 2 điểm lệch (T05, T16) |
| W8: Disclaimer / known limitations / claim review | `DISCLAIMER_LIMITATIONS_CLAIM_REVIEW_V1.md` | Xong; 12 claim, 2 P0 |

## 2. Kết quả validation

| Hạng mục | n | Kết quả | Ghi chú |
|---|---|---|---|
| HR camera vs reference độc lập | **0 cặp** | MAE/RMSE/bias = null | Không có ECG/PPG đồng bộ |
| HRV vs ECG NN | 0 | null | — |
| RR vs reference | 0 | null | — |
| BP vs cuff theo protocol | 0 đạt strict | null | CLBP 5 mẫu thiếu timing/repeats; gate 85/255 fail |
| Phone pilot (video-only) | 1 người / 4 video | 1 INVALID, 2 BAD, 1 không có kết quả; HRV/RR không có | Kiểm tính chạy được, không phải độ chính xác |
| CLBP pilot | 5 người / 5 video | HR 1 OK / 2 BAD / 2 INVALID | Nhãn BP của publisher, không có BP prediction |
| MPU public sample | 2 window | HR INVALID/null | Đồng bộ chỉ theo index |
| Knowledge base (v0.1 & v0.2) | 7 finding | Schema + coverage PASS; nhắc lại qua guard PASS | Chạy 30/10 |
| OutputGuard red-team | 18 câu | 8/18 đúng kỳ vọng; 10/15 câu không an toàn lọt | Chạy 30/10; câu tổng hợp, không phải LLM thật |
| Lock dataset Week 6 | 2 run | Artifact 6/6 SAME; rule engine 3 file CHANGED | Chạy 30/10 |

Kết quả của owner khác chỉ được dẫn lại, chưa xác minh độc lập: latency p95 7,91 ms (Khoa), Signal QA `SIGNED_OFF` (Khang). Cả hai đều dựa trên tín hiệu tổng hợp.

## 3. Điều kiện để nâng thành sign-off đầy đủ

| # | Điều kiện | Owner | Chặn |
|---|---|---|---|
| D1 | Sửa C01: frontend dùng kết quả engine thật, bỏ `Math.random`, không lưu dữ liệu mô phỏng như COMPLETED | Quang | Go-live |
| D2 | Sửa C02: consent thật, xác nhận ≥18 tuổi | Quang | Go-live |
| D3 | Áp dụng knowledge v0.2 + prompt §4 + guard G1–G7; tăng `ENGINE_VERSION` | Khoa | Go-live có tính năng AI explanation |
| D4 | Clinician review wording | Hào/nhóm | Gỡ trạng thái `pending_clinician` |
| D5 | Thu thập paired reference (ECG/PPG cho HR/HRV, đếm nhịp thở hoặc thiết bị cho RR) theo `TIMESTAMP_SYNC_PROTOCOL.md`, nhiều người, consent ký | Hào + nhóm | Mọi claim độ chính xác |
| D6 | Chạy run03 với rule hiện tại và predictions subject-independent của Khoa/Khang | Hào, Khoa/Khang | Bằng chứng gắn với release |
| D7 | Thống nhất disclaimer (§1 của claim review) ở README, frontend, engine | Nhóm | P2 |

## 4. Claim được phép / không được phép (tính đến 30/10/2026)

| Được phép | Không được phép |
|---|---|
| "Ước tính nhịp tim, nhịp thở, HRV từ camera cho mục đích wellness/nghiên cứu" | "Đo chính xác", "độ chính xác X%", "chuẩn y khoa", "thay thế máy đo" |
| "Kết quả chỉ hiển thị khi tín hiệu đạt kiểm tra chất lượng" (sau khi sửa D1) | "Phát hiện / chẩn đoán" bất kỳ bệnh nào; claim nguy cơ tim mạch, đột quỵ |
| "Chưa được kiểm chứng trên người thật so với thiết bị tham chiếu" | Hiển thị huyết áp cho người dùng |
| "Tầng AI chỉ giải thích số đã kiểm tra, có bộ lọc chống chẩn đoán" | "AI không bao giờ sai/không bao giờ chẩn đoán" (guard còn lọt, L9) |

## 5. Kiểm tra đã chạy / chưa chạy

**Đã chạy ngày 30/10:**

- `review_health_knowledge_guard.py`: exit 0, kết quả như trên.
- SHA256 lock của 2 run02.
- Đọc lại counts và metrics của 2 `VALIDATION_REPORT.json`.
- Grep có mục tiêu claim trong frontend/README và đọc ngữ cảnh code liên quan.
- Kiểm 2 nguồn web cho khoảng tham chiếu.

**Chưa chạy:** `pytest` của engine và frontend; gọi OpenAI thật; chạy app hay UI; run03; QC lại video; mọi phép đo độ chính xác. Không có training và không chia sẻ dữ liệu.

## 6. Xác nhận (để trống, chỉ điền khi có xác nhận thật)

| Vai trò | Họ tên | Quyết định | Ngày |
|---|---|---|---|
| Data / Health Research (Hào) | | | |
| AI / Vitals (Khoa) | | | |
| Signal (Khang) | | | |
| Frontend / DB / Deploy (Quang) | | | |
| Giảng viên / người nghiệm thu | | | |
