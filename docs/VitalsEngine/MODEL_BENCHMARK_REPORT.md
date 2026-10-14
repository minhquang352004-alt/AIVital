# Model Benchmark Report – Tuần 6 (Khoa)

- Thời điểm: 2026-10-14T11:52:17.251549+00:00
- Engine version: 0.1.0
- **Toàn bộ số liệu dưới đây chạy trên dữ liệu mô phỏng**, chỉ để kiểm tra pipeline và so sánh tương đối giữa các thuật toán; chưa phản ánh độ chính xác trên người thật.

## 1. Sai số nhịp tim (GREEN / CHROM / POS của Khang)

| Method | Cửa sổ | Bị từ chối | MAE (bpm) | RMSE | Bias | LoA Bland-Altman | Pearson r | ±5 bpm |
|---|---|---|---|---|---|---|---|---|
| CHROM | 90 | 2 | 0.54 | 0.78 | 0.05 | -1.49 → 1.59 | 0.999 | 1.00 |
| GREEN | 90 | 0 | 0.46 | 0.64 | 0.06 | -1.20 → 1.31 | 1.000 | 1.00 |
| POS | 90 | 0 | 0.60 | 0.84 | 0.14 | -1.50 → 1.78 | 0.999 | 1.00 |

### CHROM theo kịch bản / trạng thái / mức confidence

| Nhóm | Cửa sổ | MAE (bpm) | ±5 bpm |
|---|---|---|---|
| high_heart_rate | 15 | 0.71 | 1.00 |
| low_heart_rate | 15 | 0.25 | 1.00 |
| low_light_noise | 15 | 1.08 | 1.00 |
| missing_frames | 15 | 0.46 | 1.00 |
| motion_artifacts | 15 | 0.40 | 1.00 |
| rest_good_light | 15 | 0.39 | 1.00 |
| BAD | 22 | 0.74 | 1.00 |
| INVALID | 2 | – | – |
| OK | 66 | 0.47 | 1.00 |
| 0.0–0.3 | 2 | – | – |
| 0.3–0.6 | 2 | 1.10 | 1.00 |
| 0.6–0.8 | 9 | 0.74 | 1.00 |
| 0.8–1.0 | 77 | 0.50 | 1.00 |

Cửa sổ sai nhiều nhất:

| Kịch bản | t (s) | Tham chiếu | Ước lượng | Sai số | Trạng thái | Confidence | Issue |
|---|---|---|---|---|---|---|---|
| low_light_noise | 36.0 | 72.1 | 67.9 | -4.2 | BAD | 0.78 | CROSS_ROI_INCONSISTENT |
| high_heart_rate | 50.0 | 117.6 | 119.6 | 2.0 | OK | 0.816 | – |
| high_heart_rate | 52.0 | 117.0 | 118.8 | 1.8 | OK | 0.848 | – |
| high_heart_rate | 44.0 | 118.3 | 119.9 | 1.6 | OK | 0.879 | – |
| low_light_noise | 32.0 | 72.3 | 70.8 | -1.5 | BAD | 0.879 | CROSS_ROI_INCONSISTENT |

### GREEN theo kịch bản / trạng thái / mức confidence

| Nhóm | Cửa sổ | MAE (bpm) | ±5 bpm |
|---|---|---|---|
| high_heart_rate | 15 | 0.78 | 1.00 |
| low_heart_rate | 15 | 0.21 | 1.00 |
| low_light_noise | 15 | 0.61 | 1.00 |
| missing_frames | 15 | 0.34 | 1.00 |
| motion_artifacts | 15 | 0.44 | 1.00 |
| rest_good_light | 15 | 0.40 | 1.00 |
| BAD | 15 | 0.34 | 1.00 |
| OK | 75 | 0.49 | 1.00 |
| 0.0–0.3 | 0 | – | – |
| 0.3–0.6 | 0 | – | – |
| 0.6–0.8 | 8 | 0.24 | 1.00 |
| 0.8–1.0 | 82 | 0.48 | 1.00 |

Cửa sổ sai nhiều nhất:

| Kịch bản | t (s) | Tham chiếu | Ước lượng | Sai số | Trạng thái | Confidence | Issue |
|---|---|---|---|---|---|---|---|
| high_heart_rate | 44.0 | 118.3 | 120.5 | 2.2 | OK | 0.883 | – |
| high_heart_rate | 50.0 | 117.6 | 119.7 | 2.1 | OK | 0.823 | – |
| high_heart_rate | 52.0 | 117.0 | 118.7 | 1.7 | OK | 0.899 | – |
| high_heart_rate | 38.0 | 120.5 | 121.8 | 1.3 | OK | 0.867 | – |
| low_light_noise | 30.0 | 72.5 | 71.3 | -1.2 | OK | 0.912 | – |

### POS theo kịch bản / trạng thái / mức confidence

| Nhóm | Cửa sổ | MAE (bpm) | ±5 bpm |
|---|---|---|---|
| high_heart_rate | 15 | 0.72 | 1.00 |
| low_heart_rate | 15 | 0.29 | 1.00 |
| low_light_noise | 15 | 1.29 | 1.00 |
| missing_frames | 15 | 0.49 | 1.00 |
| motion_artifacts | 15 | 0.40 | 1.00 |
| rest_good_light | 15 | 0.40 | 1.00 |
| BAD | 24 | 0.79 | 1.00 |
| OK | 66 | 0.53 | 1.00 |
| 0.0–0.3 | 0 | – | – |
| 0.3–0.6 | 4 | 1.35 | 1.00 |
| 0.6–0.8 | 12 | 0.76 | 1.00 |
| 0.8–1.0 | 74 | 0.53 | 1.00 |

Cửa sổ sai nhiều nhất:

| Kịch bản | t (s) | Tham chiếu | Ước lượng | Sai số | Trạng thái | Confidence | Issue |
|---|---|---|---|---|---|---|---|
| low_light_noise | 56.0 | 72.6 | 75.4 | 2.8 | BAD | 0.637 | CROSS_ROI_INCONSISTENT |
| low_light_noise | 50.0 | 71.5 | 74.3 | 2.8 | BAD | 0.595 | LOW_CONFIDENCE |
| low_light_noise | 30.0 | 72.5 | 70.2 | -2.3 | OK | 0.803 | – |
| low_light_noise | 32.0 | 72.3 | 70.3 | -2.0 | BAD | 0.842 | CROSS_ROI_INCONSISTENT |
| high_heart_rate | 50.0 | 117.6 | 119.5 | 1.9 | OK | 0.815 | – |

## 2. Hiệu chỉnh confidence (isotonic)

- Huấn luyện trên 269 cửa sổ (seed 7), kiểm tra trên 268 cửa sổ (seed 8).
- Đúng = sai số ≤ 5.0 bpm. ECE trước: 0.1124, sau: 0.0.
- Tỷ lệ cửa sổ đúng trên tập kiểm tra: 1.0.
- Tất cả cửa sổ đều đúng nên isotonic chỉ học được hằng số 1; ECE sau hiệu chỉnh không có ý nghĩa, cần dữ liệu thật có cửa sổ sai.
- Registry: {"name": "hr_confidence_calibrator", "version": "0.1.0", "registered": true, "status": "experimental", "checksum_sha256": "b4df4af8100412491043c983b63eca6578a0b668d69f38d6cf1c184e3296aebb"}

## 3. Baseline huyết áp

- Dữ liệu: synthetic – 400 mẫu, 100 người.
- SBP: MAE 6.12 mmHg, ME 0.13 ± 7.71, AAMI đạt, BHS C.
- DBP: MAE 3.96 mmHg, ME 0.11 ± 4.99, AAMI đạt, BHS A.
- Gate dữ liệu: chưa đạt. Registry: {"registered": false, "reason": "Chưa đủ dữ liệu theo gate, không huấn luyện bản đăng ký"}
  - Phân bố huyết áp nhóm systolic_low là 0.03, cần tối thiểu 0.05
  - Phân bố huyết áp nhóm systolic_high là 0.00, cần tối thiểu 0.05
  - Phân bố huyết áp nhóm systolic_elevated là 0.11, cần tối thiểu 0.20
  - Phân bố huyết áp nhóm diastolic_low là 0.02, cần tối thiểu 0.05
  - Phân bố huyết áp nhóm diastolic_high là 0.00, cần tối thiểu 0.05
  - Phân bố huyết áp nhóm diastolic_elevated là 0.05, cần tối thiểu 0.20

## 4. Deep model

| Ưu tiên | Model | Phân loại | Chunk | Cửa sổ (s) | Tiền xử lý (ms) | Trọng số | Độ chính xác |
|---|---|---|---|---|---|---|---|
| 1 | tscan | realtime_candidate | 180 | 6.0 | 67.84 | chưa có | Chưa đo – chưa có trọng số pretrained |
| 2 | efficientphys | realtime_candidate | 180 | 6.0 | 25.8 | chưa có | Chưa đo – chưa có trọng số pretrained |
| 3 | deepphys | benchmark_only | 180 | 6.0 | 67.61 | chưa có | Chưa đo – chưa có trọng số pretrained |
| 4 | physnet | benchmark_only | 128 | 4.3 | 25.28 | chưa có | Chưa đo – chưa có trọng số pretrained |
