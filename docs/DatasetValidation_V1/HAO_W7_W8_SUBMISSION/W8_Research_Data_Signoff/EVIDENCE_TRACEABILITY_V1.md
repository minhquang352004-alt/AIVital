# Evidence Traceability V1 – Week 8 (Hào)

Cập nhật 30/10/2026, `main` @ `faffe86` + thay đổi local. Mục đích: mỗi claim hay con số của AIVitals phải truy được về artifact và lần chạy cụ thể. Claim nào không truy được thì không được dùng.

Cột "Kiểm 30/10" chỉ ghi phép kiểm đã thực sự chạy hôm nay. Kết quả các tuần trước là lịch sử, chưa chạy lại.

## 1. Claim → bằng chứng

| ID | Claim / số liệu | Artifact bằng chứng | Run / phép kiểm | Kiểm 30/10 | Trạng thái |
|---|---|---|---|---|---|
| T01 | Số mẫu tham chiếu ghép cặp (HR/BP) = **0** | `clbp_inventory_run02/VALIDATION_REPORT.json`, `phone_inventory_run02/VALIDATION_REPORT.json` | `split_and_validate_dataset.py` (14/10) | Đọc lại: `paired_rows=0`, `eligible.rows=0` cả hai run | Truy được |
| T02 | Không có MAE/RMSE/bias cho người thật | Như T01, `evaluation.metrics.*` = null | Như T01 | Đọc lại: count 0, metrics null | Truy được |
| T03 | Inventory: CLBP 5 người/5 dòng; phone 1 người/4 dòng | Như T01, `input.rows/subjects` | Như T01 | Đọc lại | Truy được |
| T04 | Lock Week 6 toàn vẹn | `*/DATASET_LOCK.json` `artifacts_sha256` | SHA256 | **Chạy lại: 3/3 artifact SAME ở cả hai run** | Truy được |
| T05 | Quy tắc dùng để lock khớp code hiện tại | `DATASET_LOCK.json` `rules_and_code_sha256` | SHA256 | **Chạy lại: `quality/sqi.py`, `config/vitals_config.py`, `validation/rules.py` CHANGED; 8 file còn lại SAME** | **Lệch** (xem §3) |
| T06 | Phone pilot QC: phone01 INVALID, phone02 BAD, phone03 BAD, phone04 không có raw result | `docs/ReferenceDataset/hao_phone*_qc_run*/`, `CollectionPackage_V1/SESSION_METADATA_*.csv` cột 38–39 | QC video 14–15/10 | Chỉ đọc cột engine_status của 2 CSV | Truy được (lịch sử) |
| T07 | CLBP pilot: HR 1 OK / 2 BAD / 2 INVALID; 6/31 feature thiếu mỗi mẫu | `docs/EvidenceMatrix_BP/clbp_pilot_run01/RUN_SUMMARY.json`, `WEEK5_CLBP_PILOT_REPORT_V1.md` (local, Git-ignore) | `prepare_clbp_pilot.py` | Không chạy lại | Truy được (lịch sử, chỉ có ở checkout này) |
| T08 | MPU public benchmark: 2 window, HR INVALID/null | `docs/ReferenceDataset/mpu_public_benchmark_run01/`, `WEEK3_PUBLIC_REFERENCE_BENCHMARK_V1.md` | `benchmark_mpu_public_sample.py` | Không chạy lại | Truy được (lịch sử) |
| T09 | Mức bằng chứng HR/HRV/RR/BP features | `docs/EvidenceMatrix_BP/MEDICAL_EVIDENCE_MATRIX_V1.md/.csv` (42 dòng, nguồn S1–S…) | Review tài liệu Week 5 | Đọc dòng M01–M04 | Truy được |
| T10 | Khoảng HR 60–100, RR 12–20 (người trưởng thành, nghỉ) | `health_knowledge_v1/MEDICAL_KNOWLEDGE_PACKAGE_V1.md` §2 | Tra nguồn web 30/10 | Có (qua kết quả tìm kiếm; chưa mở trang AHA gốc) | Truy được, cần bổ sung nguồn gốc AHA |
| T11 | Knowledge v0.1 và v0.2 hợp lệ schema/coverage | `health_knowledge_v1/GUARD_REDTEAM_RESULTS_V1.json` | `review_health_knowledge_guard.py` | **Chạy: PASS** | Truy được |
| T12 | Guard chặn 8/18 câu red-team; 10 câu không an toàn lọt | Như T11 | Như T11 | **Chạy: 8/18** | Truy được |
| T13 | Latency `VitalsService.compute` p95 7,91 ms | `docs/VitalsEngine/HEALTH_OPENAI_BOUNDARY.md` §6 (Khoa) | Benchmark của Khoa | Không chạy lại | Claim của owner, chưa xác minh độc lập |
| T14 | Signal QA sign-off, thuật toán đóng băng POS/CHROM/GREEN 1.0 | `aivitals_engine/version.py` (`SIGNAL_QA_STATUS="SIGNED_OFF"`), `docs/SIGNAL_QA_SIGNOFF.md` (Khang) | – | Đọc `version.py` | Claim của owner; dựa trên dữ liệu tổng hợp |
| T15 | "Mọi con số độ chính xác hiện tại đều trên tín hiệu tổng hợp" | `docs/VitalsEngine/RELEASE_NOTES.md` – Giới hạn đã biết | – | Đọc | Truy được; khớp T01 |
| T16 | Frontend hiển thị/lưu HR, RR, HRV, SQI từ phép đo thật | – | – | **Đọc code: không đúng.** Xem `DISCLAIMER_LIMITATIONS_CLAIM_REVIEW_V1.md` §3, C01 | **Không truy được – blocker** |
| T17 | Consent của người tham gia SUBJ_001 | `CollectionPackage_V1/CONSENT_SUBJ_001_CHAT_V1.json` | – | Không mở lại | Chỉ là khai báo qua chat, không có chữ ký/chấp nhận đầy đủ |

## 2. Chuỗi provenance của một kết quả hiển thị cho người dùng

```
Camera frame → ROI/RGB (Khang) → BVPWindow → VitalsService (VitalsResult, status/issues)
  → HealthAssessmentService (findings, knowledge_version, review_status)
  → ExplanationService (source_result_ids, guard_passed, violations, llm_model)
  → API /api/v1 → frontend / DB (Quang)
```

Mỗi bước phải giữ lại các ID và version sau để truy ngược: `result_id`, `engine_version`, `algorithm.name/version`, `source.rppg_method_version`, `knowledge_version`, `review_status`, `ruleset.version`, `source_result_ids`, `llm_model`.

**Đứt chuỗi hiện tại:** frontend `/api/v0` không gọi engine `/api/v1`. Không tìm thấy tham chiếu `api/v1`, `health-assessments` hay `explanations` trong `frontend/app`. Giá trị lưu DB vì vậy không có `result_id` hay `engine_version` để truy về engine (C01).

## 3. Lệch version / ngưỡng sau merge W7–W8

| Mục | Khi lock Week 6 (14/10) | Hiện tại (`faffe86`) | Ảnh hưởng |
|---|---|---|---|
| Ngưỡng SQI invalid | 0,3 (ghi trong `DATASET_CLEANING_AND_QC_RULES.md`) | **0,4** (`ValidationConfig.signal_quality_invalid`) | Script Week 6 đọc config động, nên run mới sẽ dùng 0,4. Kết luận không đổi vì eligible = 0 do thiếu reference, không phải do SQI |
| `sqi.py`, `rules.py` | SHA trong lock | CHANGED | Run02 phản ánh rule trước W7. Muốn dùng làm bằng chứng cho bản release phải chạy run03 với output mới (metadata-only, không cần QC lại video) |
| `ENGINE_VERSION` | 0.1.0 | vẫn 0.1.0 | `RELEASE_NOTES.md` ghi 0.2.0 cho tuần 8 nhưng `version.py` chưa tăng. Kết quả đo mới vẫn mang 0.1.0 nên không phân biệt được trước/sau W8. **Báo Khoa** |
| Knowledge | v0.1.0-draft, `pending_medical_review` | Đề xuất v0.2.0-hao-review | Khoa áp dụng thì phải cập nhật golden/example |

**Addendum cho `DATASET_CLEANING_AND_QC_RULES.md`:** không sửa trực tiếp file này vì SHA256 của nó nằm trong lock run02. Từ `faffe86`, bảng SQI đọc là `<0,4` ERROR / `[0,4;0,6)` WARNING / `>=0,6` không phát issue. Khi tạo run03 thì phát hành rules V2 cùng lúc.

Việc cần làm cho Hào: chạy run03 (theo `RUN_GUIDE.md`, output mới, không ghi đè run02) khi nhóm cần bằng chứng gắn với bản release.
