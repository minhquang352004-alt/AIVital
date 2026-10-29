# Hướng dẫn chạy validation metadata V1

Chạy tại `E:\AIVitals_New` bằng môi trường đã có. Script không train, không decode video; dependencies engine dùng môi trường `E:\AIVitals_HAO_venv`. Mọi output phải là thư mục mới `*_run*` dưới `docs/DatasetValidation_V1`; không ghi đè. `--dry-run` kiểm tra và tính report trong bộ nhớ, không tạo output. CSV UTF-8 có/không BOM đều đọc được.

Hai lệnh dưới đã được thực hiện cho bản cuối `run02`; `run01` giữ nguyên lịch sử trước khi bổ sung kiểm tra header CSV optional. Để kiểm tra lại input hiện tại, chọn `run03` kèm `--dry-run`; để tạo phiên bản mới bỏ `--dry-run`. Không cần Hào chạy lại bước metadata này để điền accuracy: hiện chưa có paired predictions/reference đủ điều kiện.

## 1. CLBP pilot hiện có

```powershell
& 'E:\AIVitals_HAO_venv\Scripts\python.exe' -B scripts/data_qc/split_and_validate_dataset.py --clbp-run docs/EvidenceMatrix_BP/clbp_pilot_run01 --output-dir docs/DatasetValidation_V1/clbp_inventory_run02 --mode kfold --folds 5 --target bp --seed 42
```

Adapter chỉ đọc cached manifest + 5 `*_qc_features.json`, giữ source label/hash/demographics/SQI/status; cờ quyền dùng/reference/pairing/independent prediction chưa xác nhận đều false. Input này không có BP predictions. Muốn run lại chọn `run03`; không sửa run cũ. Derived records/distributions trong run được Git-ignore theo giới hạn chia sẻ CLBP.

## 2. Bốn CSV collection của Hào

```powershell
& 'E:\AIVitals_HAO_venv\Scripts\python.exe' -B scripts/data_qc/split_and_validate_dataset.py --input-csv docs/CollectionPackage_V1/SESSION_METADATA_ACTUAL_V1.csv docs/CollectionPackage_V1/SESSION_METADATA_HAO_PHONE_002.csv docs/CollectionPackage_V1/SESSION_METADATA_HAO_PHONE_003.csv docs/CollectionPackage_V1/SESSION_METADATA_HAO_PHONE_004.csv --output-dir docs/DatasetValidation_V1/phone_inventory_run02 --mode audit --target hr
```

`audit` kiểm kê và gán `candidate_split=unassigned` vì chỉ có 1 subject; chưa thể tạo train/val/test hoặc 2-fold. Không thêm split khác nhau cho các video của người này. Số dòng từ phone được kiểm kê riêng, không trộn vào train/test CLBP để đủ số người.

## 3. Schema CSV chuẩn cho cohort tương lai

Bắt buộc `sample_id,subject_id`. Numeric tùy có: `age_years,hr_reference_bpm,hr_estimated_bpm,sbp_reference_mmhg,dbp_reference_mmhg,sbp_estimated_mmhg,dbp_estimated_mmhg,sqi`; thiếu để ô trống. Thêm `sex,fitzpatrick,source_dataset,parent_sample_id,video_sha256` nếu có nguồn. Header collection cũ được alias: `reference_hr_bpm`, `reference_sbp_mmhg`, `reference_dbp_mmhg`, `subject_age_years`, `subject_sex`, `fitzpatrick_type`, `engine_status`.

Flags (blank=false; nhận true/false/1/0): `usage_authorized,strict_protocol_accepted,hr_reference_qc_pass,bp_reference_qc_pass,hr_pairing_verified,bp_pairing_verified,prediction_subject_independent`. Chỉ điền true khi có bằng chứng review tương ứng. Status `signal_status,hr_status,bp_status` nhận OK/BAD/INVALID hoặc blank; BP status là metadata đánh giá riêng, không thêm field vào engine `VitalsResult`.

CSV allocation cũ dùng đúng một cột `split` (train/val/test) hoặc `fold` (số nguyên >=0), chạy `--mode existing`. Chưa có allocation: >=7 người có thể `--mode holdout`; pilot 2–6 người chọn `--mode kfold --folds K` phù hợp. Tạo partition trước fit preprocessing/model. Script không chọn hyperparameters.

CSV prediction bổ sung `prediction_provenance` (run/model/preprocessing/calibration/source evidence), `prediction_holdout` (`test` hoặc fold của row), `prediction_assignment_sha256` từ report đã khóa và `prediction_subject_independent=true`. Producer phải xác nhận model/preprocessing không dùng người test; script không kiểm training history. Export `candidate_split/fold` thành `split/fold` rồi dùng `existing` để kiểm lại chính allocation đó. Không bỏ ID/hash để tạo lại split khác sau khi xem metrics.

## 4. Output và kiểm tra

`DATASET_SNAPSHOT.csv`: mọi dòng + allocation/eligibility/reasons; `ELIGIBLE_ROWS.csv`: subset đủ metadata QC, có header kể cả rỗng; `VALIDATION_REPORT.json`: phân bố input/eligible/từng partition, gate và paired metrics; `DATASET_LOCK.json`: source/artifact/rules/code SHA256, runtime và arguments. Thư mục run giữ local; không upload khi chưa rõ quyền chia sẻ.

Exit 0 nghĩa là kiểm kê chạy được, có thể eligible=0/metrics=null/gate fail. Exit 2 là lỗi input/identity/leakage/output scope/existing path; sửa nguyên nhân từ nguồn rồi tạo run mới. Snapshot checksum không xác minh quyền dùng hay ground truth tự động. Một input alias của cùng người không có registry/hash liên hệ vẫn có thể lọt kiểm tra và cần review thủ công.
