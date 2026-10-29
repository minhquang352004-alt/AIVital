# Subject-independent split specification V1

Đối chiếu 2026-10-15, `main@5d9b4ae`. Mục đích: một người chỉ thuộc một partition/fold test, kể cả nhiều phiên, window, augmentation, video nén hoặc nguồn khác.

## 1. Định danh trước phân hoạch

Hoàn thiện registry subject với nguồn/alias và quyền dùng. Kiểm tra ID không rỗng, sample duy nhất, hash/parent không gán sang nhiều người. Script từ chối biến thể chữ hoa/thường của subject; alias khác thực sự cần người cung cấp dữ liệu xác nhận. Nó không nhận diện người từ khuôn mặt và không phát hiện được một người bị khai thành hai ID không liên hệ.

Nếu CSV đã có `split` hoặc `fold`, script kiểm tra toàn bộ phân hoạch đầu vào trước bất kỳ lọc QC nào. Một subject có nhiều split/fold, phân hoạch một phần, hoặc source/parent khác người đều gây lỗi. Không tự sửa leakage bằng cách xóa dòng lỗi.

## 2. Các chế độ

| Mode | Cách chia | Sử dụng |
|---|---|---|
| `holdout` | Sort unique subject IDs, shuffle `random.Random(seed=42)`, phân bổ theo 70/15/15 bằng floor rồi largest remainder; tie ưu tiên train, val, test | Cohort đủ lớn; tối thiểu 7 người theo policy kỹ thuật để 3 tập có người; 7 không phải ngưỡng bằng chứng thống kê |
| `kfold --folds K` | Shuffle unique subject IDs với seed rồi round-robin vào K fold; mỗi người làm test đúng một lần, K trong [2,N] | Pilot 5 người: K=5 chỉ là thiết kế kiểm kê; chưa có training/prediction |
| `existing` | Audit nguyên `split=train/val/test` hoặc `fold` số nguyên không âm đã supplied; yêu cầu đúng một kiểu, đủ cột, các tập không rỗng | Dùng allocation của Khoa/nhóm, bao gồm GroupKFold đã xuất; không reassign |
| `audit` | Không chia, ghi `unassigned`; không tính test accuracy | Kiểm kê video-only chỉ 1 người hoặc cohort chưa thể phân hoạch |

Tỷ lệ là theo số người, không theo video/window. Báo tỷ lệ thực tế do rounding. K-fold của script cân bằng số người; `evaluation.py` của Khoa dùng `sklearn.model_selection.GroupKFold` theo các dòng/groups và có thể tạo fold khác. Cả hai bảo vệ subject; muốn trùng fold phải dùng `existing` với allocation được export từ đúng lần chạy của Khoa. Không tuyên bố seed của script tái tạo GroupKFold của Khoa.

## 3. Allocation kiểm kê và tập đủ điều kiện

`candidate_split`/`candidate_fold` áp dụng toàn bộ registry đã kiểm tra; `supervised_eligible` và lý do lọc ở từng dòng giữ riêng. Loại QC không được kéo người từ test về train. Báo số người/dòng eligible từng tập; nếu một tập eligible trống thì `usable_supervised_partitions=false`. Phân hoạch kiểm kê vẫn truy vết được nhưng chưa dùng để huấn luyện. Eligibility thay đổi phải tạo dataset version mới, giữ assignment hoặc review rõ lý do thay.

Holdout: fit preprocessing, feature selection, imputer, scaler, calibration và model chỉ bằng train; lựa chọn hyperparameter bằng val; mở test sau khi quyết định đã khóa. Không chọn seed bằng cách thử error test. K-fold: tune bên trong train bằng inner grouped CV; outer test không tham gia tune. Với 5 người, nested validation rất yếu; không suy rộng độ chính xác quần thể. Personal calibration cần nghiên cứu riêng, không gọi subject-independent nếu dùng nhãn của người test để fit.

## 4. Leakage audit và reproducibility

Kiểm tra tất cả cặp train/val/test; K-fold kiểm tra train–test trong mỗi vòng. Ngoài identity, rà features để không chứa target, tên file mã hóa BP, future timestamps/reference hoặc thông tin fit từ test. Script chỉ kiểm tra metadata identity/partition và các xác nhận provenance; không audit được code training hay thiết bị bằng CSV.

`assignment_sha256` = SHA256 của JSON ASCII compact (separators `,` và `:`), danh sách các cặp `(subject_id, candidate_split/fold)` unique, sort. Hash, seed, mode, input/code/rules hash và phiên bản runtime lưu trong run. Prediction phải khai đúng hash và `prediction_holdout` (`test` hoặc số fold); nếu khác, không tính metrics primary. Với k-fold, mỗi prediction phải là out-of-fold của chính người đó. `prediction_subject_independent=true` kèm provenance là xác nhận của producer, không phải script chứng minh model chưa nhìn thấy test.

Lock là checksum snapshot bất biến theo quy trình (không phải filesystem read-only hay chữ ký số); thay đổi bất kỳ dữ liệu/rules/code phải run ID mới và review. Không commit raw hoặc bảng CLBP có nhãn/derived distribution khi quyền chia sẻ chưa rõ. Các `*_run*` trong thư mục này được Git-ignore.
