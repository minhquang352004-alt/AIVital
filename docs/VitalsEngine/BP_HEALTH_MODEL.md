# BP / Health Model – Tuần 5 (Khoa)

Khung mô hình ước tính huyết áp và rủi ro sức khỏe **chỉ phục vụ nghiên cứu**. Mọi kết quả mang `intended_use = research_only`, rủi ro mang `is_diagnosis = false` và `evidence_level = insufficient`. Không có module nào trong phần này gọi OpenAI hay dịch vụ ngoài (có test kiểm tra import).

## 1. Luồng dữ liệu

```
FrameResult (Khang) → RealtimeVitalsEngine → VitalsResult (HR/HRV/RR)
                                           → BVPFeatureExtractor (Khang, 23 đặc trưng)
Demographics (tuổi, giới, chiều cao, cân nặng)
        ↓ build_bp_features()
31 đặc trưng → RidgeBloodPressureModel → BloodPressureEstimate (SBP/DBP)
                                        → BloodPressureRiskModel → HealthRiskOutput
```

- `RealtimeVitalsEngine` tính `BVPFeatures` trên cùng cửa sổ dài với HRV/RR và trả trong `RealtimeVitalsUpdate.bvp_features`.
- `BloodPressureService` (`integration/bp_service.py`) ghép tất cả; khi chưa có model đã huấn luyện thì trả `None` (không hiển thị huyết áp).

## 2. Bộ đặc trưng `bp_features_v2+bvp_1.0` (31 cột)

| Nhóm | Số cột | Nguồn |
|---|---|---|
| Chỉ số sinh tồn: `heart_rate_bpm`, `hrv_rmssd_ms`, `hrv_sdnn_ms`, `mean_ibi_ms`, `respiratory_rate_brpm` | 5 | `VitalsResult` của Khoa, chỉ lấy chỉ số trạng thái OK |
| Hình thái, biên độ, phổ, xu hướng sóng BVP | 23 | `BVPFeatures.feature_names()` của Khang (`docs/FEATURE_CONTRACT.md`) |
| `age_years`, `sex_male`, `bmi` | 3 | `Demographics` do người dùng nhập |

Thứ tự cột cố định theo `BP_FEATURE_NAMES`. Giá trị NaN của Khang được đổi thành thiếu và điền trung vị khi dự đoán. Khang thêm đặc trưng mới (append + tăng version) thì phiên bản bộ đặc trưng đổi theo.

## 3. Mô hình cơ sở `bp_ridge_baseline`

- `SimpleImputer(median)` → `StandardScaler` → `Ridge`, dự đoán cùng lúc SBP và DBP.
- Rào chắn khi dự đoán:
  - Thiếu > 30% đặc trưng → `INVALID` (`MISSING_FEATURES`); thiếu ít hơn → `BAD`.
  - Đặc trưng nằm ngoài khoảng dữ liệu huấn luyện → giới hạn lại về khoảng đó và cảnh báo `FEATURES_OUT_OF_TRAINING_RANGE` (`BAD`), tránh mô hình tuyến tính ngoại suy.
  - SBP ngoài 70–220 hoặc DBP ngoài 40–130 mmHg → `INVALID`.
  - Hiệu áp < 10 mmHg → `INVALID` (`PULSE_PRESSURE_INVALID`).
- Lưu / nạp bằng joblib; `load(path, checksum_sha256)` tính lại SHA-256 và **từ chối nạp** nếu không khớp.

## 4. Rủi ro sức khỏe `bp_category_risk`

| Mức | Điều kiện trên huyết áp ước tính |
|---|---|
| `low` | SBP < 120 và DBP < 80 |
| `moderate` | SBP 120–139 hoặc DBP 80–89 |
| `elevated` | SBP ≥ 140 hoặc DBP ≥ 90 |

`score` (0–1) chỉ dùng để sắp xếp, không phải xác suất bệnh. Huyết áp ước tính `INVALID` thì rủi ro cũng `INVALID`, không có `score` / `category`.

## 5. Benchmark và điều kiện đủ dữ liệu

```bash
python aivitals_engine/scripts/run_bp_baseline.py                 # dữ liệu mô phỏng
python aivitals_engine/scripts/run_bp_baseline.py --csv data.csv --save-model
```

- File CSV: `subject_id`, `sbp_mmhg`, `dbp_mmhg` + các cột trong `BP_FEATURE_NAMES` (thiếu cột thì coi là NaN).
- Đánh giá chia theo người đo (GroupKFold), tự báo lỗi nếu một người xuất hiện ở cả train và test.
- Chỉ số: MAE, sai số trung bình ± độ lệch chuẩn (AAMI: |ME| ≤ 5, SD ≤ 8 mmHg), xếp hạng BHS A–D, Pearson, tỷ lệ sai số ≤ 5 / 10 / 15 mmHg.
- Cổng dữ liệu: ≥ 85 người, ≥ 255 mẫu và đủ tỷ lệ người ở nhóm huyết áp thấp / cao. Chưa đạt thì không được bật mô hình trong sản phẩm. Ngưỡng cần Hào đối chiếu lại với bản chính thức của ISO 81060-2.
- Báo cáo ghi ra `aivitals_engine/outputs/bp/bp_baseline_report.json`.

**Dữ liệu mô phỏng chỉ để kiểm tra pipeline chạy đúng**: quan hệ giữa đặc trưng và huyết áp do bộ sinh tự đặt ra, nên các con số MAE / AAMI trên dữ liệu này không nói gì về độ chính xác thật.

## 6. Việc cần phối hợp

- Hào: dataset có huyết áp tham chiếu (máy đo cuff) theo cùng `subject_id` với video, kèm tuổi / giới / chiều cao / cân nặng.
- Khang: giữ thứ tự 23 đặc trưng cố định, báo khi tăng `_FEATURE_VECTOR_VERSION`.
- Quang: nếu hiển thị huyết áp thì luôn kèm nhãn "chỉ phục vụ nghiên cứu", không lưu chung bảng `vital_measurements`.
