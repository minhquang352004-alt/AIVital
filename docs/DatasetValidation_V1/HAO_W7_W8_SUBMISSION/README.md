# Hồ sơ nộp W7–W8 – Hào (Data / Health Research)

AIVitals, cập nhật 30/10/2026. Checkout `main` @ `faffe86`.

**Trạng thái:** đã hoàn thành deliverables tài liệu của Hào cho W7–W8. Sign-off Research/Data là **có điều kiện, chỉ cho demo nội bộ**. Validation trên người thật và nghiệm thu chính thức vẫn pending.

Thư mục này là **bản sao để nộp**. Bản gốc (nguồn chuẩn khi cần sửa) nằm ở đường dẫn ghi trong cột cuối. Nếu sửa bản gốc thì copy lại vào đây.

## Thứ tự đọc đề xuất

1. `W8_Research_Data_Signoff/WEEK8_FINAL_VALIDATION_REPORT_V1.md`: kết luận, kết quả, điều kiện, bảng xác nhận
2. `W7_Medical_Knowledge_Package/MEDICAL_KNOWLEDGE_PACKAGE_V1.md`
3. Các file còn lại theo bảng dưới

## W7 – Health Assessment + OpenAI (Medical knowledge package)

| Task trong plan | File | Bản gốc |
|---|---|---|
| Knowledge base / evidence summary | `MEDICAL_KNOWLEDGE_PACKAGE_V1.md` §2 | `docs/EvidenceMatrix_BP/health_knowledge_v1/` |
| finding → interpretation → caution | `MEDICAL_KNOWLEDGE_PACKAGE_V1.md` §3, `health_findings_vi.proposed_v0.2.0.json` | như trên |
| Review medical wording / prompts | `MEDICAL_KNOWLEDGE_PACKAGE_V1.md` §4–5, `GUARD_REDTEAM_RESULTS_V1.json` | như trên |
| Script tái lập kết quả | `review_health_knowledge_guard.py` | `scripts/data_qc/` (chạy từ bản gốc, vì đường dẫn repo tính theo vị trí đó) |

## W8 – QA + Hardening (Research/Data sign-off)

| Task trong plan | File | Bản gốc |
|---|---|---|
| Final validation report | `WEEK8_FINAL_VALIDATION_REPORT_V1.md` | `docs/DatasetValidation_V1/` |
| Data dictionary | `DATA_DICTIONARY_V1.md` | như trên |
| Evidence traceability | `EVIDENCE_TRACEABILITY_V1.md` | như trên |
| Disclaimer / known limitations / claim review | `DISCLAIMER_LIMITATIONS_CLAIM_REVIEW_V1.md` | như trên |

## Lưu ý khi nộp

- Không ghi "đã nghiệm thu" hay "đã validate độ chính xác": paired reference = 0, metrics = null.
- Còn 2 blocker P0 thuộc Quang (C01 số đo random trên frontend, C02 consent tự động). Knowledge v0.2 và sửa guard chờ Khoa áp dụng vào engine.
- Đường dẫn trong các tài liệu (ví dụ `docs/...`, `aivitals_engine/...`) tính từ gốc repo, không tính từ thư mục này.
- Artifact dữ liệu Week 3–6 (run folders, video) không nằm trong thư mục này vì bị Git-ignore hoặc là dữ liệu hạn chế; chỉ được dẫn chiếu.
