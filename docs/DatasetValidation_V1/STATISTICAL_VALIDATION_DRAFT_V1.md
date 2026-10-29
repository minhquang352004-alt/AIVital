# Statistical validation draft V1

Ngày: 2026-10-15. Mục tiêu: estimation, wellness, research/screening support. Status: **draft; pilot inventory snapshot có thể khóa, supervised/clinical validation chưa đủ bằng chứng**. Formal pilot DoD approval chưa ghi nhận.

## 1. Code alignment

Đối chiếu `main@5d9b4ae72955ebc289bc2f70ba6a51ba88f348a5` và working tree: `aivitals_engine/benchmark/metrics.py`; đường dẫn đúng của BP là `aivitals_engine/models/blood_pressure/evaluation.py` (không phải top-level `models/`). Script gọi hai hàm hiện có read-only thay vì chép công thức. SHA256 code/rules thực tế được lưu trong `DATASET_LOCK.json` của mỗi run.

Cho n cặp hợp lệ, reference `y_i`, estimate `p_i`, error `e_i=p_i-y_i`, pair mean `m_i=(p_i+y_i)/2`:

| Metric | Công thức/chi tiết hiện có |
|---|---|
| MAE | `sum(abs(e_i))/n`; bpm hoặc mmHg |
| RMSE | `sqrt(sum(e_i^2)/n)`; cùng đơn vị reference |
| MAPE | `100*mean(abs(e_i)/max(abs(y_i),1e-12))`; %; không phải accuracy %. Ground truth không dương bị QC loại trước |
| Bias / mean error | `mean(e_i)`; dương nghĩa là estimate cao hơn reference |
| Error SD | `sqrt(sum((e_i-bias)^2)/(n-1))` với n>1 (`ddof=1`) |
| Bland–Altman 95% LoA | `bias ±1.96*SD(error)`; trục ngang `m_i`, trục dọc `e_i` khi có plot |
| Pearson r | covariance chuẩn hóa; code dùng `np.corrcoef`; null nếu n<3 hoặc std của một vector <1e-12 |
| Within tolerance | `mean(abs(error)<=tolerance)`; script dùng 5 bpm cho HR, 5 mmHg cho SBP/DBP để mô tả, không phải clinical pass criterion |

`compute_error_metrics`: loại pair có None bằng zip, không tự kiểm độ dài và không lọc NaN/Inf. Script kiểm tra finite, paired cùng dòng, eligibility/provenance trước khi gọi. n=0 trả count=0 và metrics null. n=1, code đặt SD=0, LoA=bias; phải đánh dấu **không diễn giải agreement** cho n<2 dù có output số. Pearson r cao không chứng minh agreement.

`evaluate_blood_pressure`: yêu cầu targets/predictions cùng `(n,2)` với thứ tự SBP,DBP; trả MAE, mean error, sample SD, r và tỷ lệ `<=5/10/15` mmHg, tách hai endpoint. Nó không trả RMSE/MAPE/LoA; script dùng `compute_error_metrics` để bổ sung trên **đúng cùng cohort cặp đủ hai BP**, nên MAE/bias/r khớp. Script không gọi evaluator BP khi n=0 để tránh empty-array NaN.

Code BP có property `meets_aami` (`abs(mean_error)<=5`, `error_sd<=8`) và BHS grade theo các tỷ lệ; đây chỉ là phép so số. Không serialize chúng thành chứng nhận chuẩn/clinical validation; còn yêu cầu population, sampling, reference acquisition và protocol độc lập.

## 2. Statistical analysis plan

Primary: test holdout hoặc out-of-fold predictions chưa thấy subject test, endpoint status OK và reference/pairing đã QC. Báo n người, n observations, attempts, accepted estimates, missing/error reasons và denominators. Cả failures không có estimate phải nằm trong coverage, không biến thành error=0. Không gộp người thật có reference thiếu với dataset external để tạo cặp.

LoA trên đây là mô tả phân bố sai khác, **không phải 95% confidence interval** của bias/LoA và không phải phần trăm dự đoán chính xác. Diễn giải coverage 95% cần kiểm tra phân bố error, outlier, proportional bias và tính độc lập; hiện chưa có cặp để kiểm. Các cửa sổ chồng lấp/repeats cùng người không độc lập. Sau khi đủ dữ liệu, báo thêm per-subject metrics và subject-weighted macro, dùng cluster bootstrap theo subject cho CI hoặc repeated-measures Bland–Altman phù hợp thiết kế. Script V1 chỉ trả row-pooled metrics; CI, macro và repeated-measures LoA chưa triển khai, không được báo là đã chạy.

Phân tầng descriptive theo tuổi/sex/skin type/device/illumination khi metadata có nguồn và đủ người; báo missing và n từng nhóm. Không suy skin type từ mặt, không tính subgroup accuracy khi chưa có paired estimates. Kiểm tra subgroup/external-dataset robustness cần nằm trong plan trước khi mở test. Ngưỡng sufficiency BP giữ đúng `gate.py`; gate pass không tự chứng minh clinical readiness.

## 3. Thực thi Week 6 từ bằng chứng đã có

Các run metadata dùng lại CSV/JSON Week 4/5; không giải mã lại video, train model hoặc chạy signal benchmark. Script và fixtures có 8 kiểm thử pass; dry-run đã xác nhận các counts dưới đây, sau đó xuất snapshot và kiểm checksum. Fixtures chỉ kiểm phần mềm, không phải clinical/reference evidence.

| Cohort | Người / dòng | Eligible / paired | MAE / RMSE / MAPE / r / LoA |
|---|---|---|---|
| CLBP publisher pilot | 5 / 5 | 0 / 0 (BP) | null cho toàn bộ SBP/DBP metrics; HR agreement cũng chưa có interval reference phù hợp |
| Phone video-only | 1 / 4 | 0 / 0 (HR) | null; không có independent reference |
| MPU đã có (Week 3) | 1 candidate source pair / 2 windows; identity chưa xác minh | 0 usable HR estimates; strict acceptance false | unavailable theo report cũ; không chạy lại |

Nguồn MPU: `docs/ReferenceDataset/mpu_public_benchmark_run01/BENCHMARK_SUMMARY.json`, `WEEK3_PUBLIC_REFERENCE_BENCHMARK_V1.md`. Count/FPS index alignment là giả định, sync_error chưa xác minh. Không nhận MPU là một subject registry đủ bằng chứng để trộn với CLBP/phone.

Runs local cuối: `clbp_inventory_run02/` (5 candidate outer folds, mỗi fold 1 người test/4 người train, 0 eligible trong mọi fold) và `phone_inventory_run02/` (`audit`, 1 người unassigned, không thể chia độc lập). Run01 giữ nguyên lịch sử; run02 bổ sung bảo đảm header eligible nhất quán khi nhiều CSV có cột optional khác nhau, không thay counts/allocation/metrics. Audit theo ID/hash/parent không phát hiện leakage; registry alias chưa được xác minh độc lập. BP gate cohort nhãn CLBP vẫn fail counts 85/255 và low-pressure coverage; eligible cohort=0. Không loại BP cao để tăng chất lượng giả tạo.

Mỗi run chứa `DATASET_SNAPSHOT.csv`, `ELIGIBLE_ROWS.csv` chỉ header khi rỗng, `VALIDATION_REPORT.json`, `DATASET_LOCK.json`. Status lock **INVENTORY_SNAPSHOT_LOCKED**, `training_dataset_ready=false`, `usable_supervised_partitions=false`. Các bảng phân bố demographics/vitals có missingness và denominators nằm trong run Git-ignored; giới hạn license/derived-sharing của CLBP được giữ. Khóa này chỉ đóng băng input/rules/allocation cho việc review, chưa hoàn thành DoD training dataset locked.

## 4. Evidence sufficiency / DoD

- Rules, split spec, công thức đồng bộ code và script: hoàn thành, 8 kiểm thử pass.
- Snapshot kiểm kê + allocation với source/output/code hashes: hai run metadata đã xuất; chỉ khóa phạm vi pilot inventory.
- Training dataset locked, full 85/255 BP readiness, MAE/RMSE thực và statistical validation đủ bằng chứng: còn phụ thuộc authorized reference cohort và independent predictions.
- DoD pilot cần nhóm/giảng viên chấp nhận scope. Tài liệu draft không thay quyết định đó.

## 5. Hào action #4

Xem [RUN_GUIDE.md](RUN_GUIDE.md). Việc chạy metadata trên dữ liệu hiện có sẽ do Codex thực hiện trong task này. Hào không cần chạy lại video chỉ để lấy MAE. Phần cần Hào/nhóm bổ sung là quyền dùng dữ liệu, hồ sơ reference/sync/repeats còn thiếu, và nhờ owner Khoa/Khang cung cấp predictions holdout/OOF cùng provenance theo allocation đã khóa. Chưa có các đầu vào đó thì giữ metrics null. Không chỉ chạy benchmark synthetic rồi dùng số đó làm accuracy người thật.
