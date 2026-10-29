# Dataset cleaning and QC rules V1

Ngày đối chiếu: 2026-10-15, `main@5d9b4ae72955ebc289bc2f70ba6a51ba88f348a5` cùng working tree hiện tại. Phạm vi: estimation, wellness, research/screening support. Quy tắc dataset nằm ngoài engine contract và không thêm BP vào `VitalsResult`.

## 1. Điều chỉnh plan và đơn vị dữ liệu

Week 6 tạo bộ quy tắc, phân hoạch theo người, snapshot kiểm kê có checksum và validation draft. Chỉ công bố **training dataset locked** khi có quyền sử dụng, ground truth và các cổng readiness phù hợp. Snapshot pilot vẫn có thể khóa để truy vết dù số dòng đủ điều kiện bằng 0. Formal approval cho DoD pilot chưa được ghi nhận.

Một dòng là một sample/window đã khai báo; `subject_id` là mã người toàn cục. Dùng registry để hợp nhất alias giữa nguồn nếu cùng người; namespace nguồn chỉ tránh trùng tên, không chứng minh hai người độc lập. `parent_sample_id` giữ liên hệ với video gốc; hash gốc giữ nguyên khi tạo window/biến thể. Không dùng tên file chứa BP/HR, ID, đường dẫn hay trường reference làm predictor.

Giữ raw và nhãn nguồn bất biến. Cleaning là đánh dấu eligibility/lý do, không sửa số đo, điền 0, nội suy nhãn thiếu hay xóa dấu vết. CSV gốc được hash; snapshot mới có ID thư mục mới và không ghi đè. Không suy ra consent, thời gian cuff hoặc skin type từ video/tên file/mtime.

## 2. Ground-truth QC

| Kiểm tra | Xử lý |
|---|---|
| Thiếu/đúp sample hoặc subject; CSV lệch cột; numeric NaN/Inf | Dừng trước khi tạo snapshot; sửa mapping bằng bằng chứng nguồn |
| Thiếu reference HR hoặc HR <=0 | Giữ dòng; loại khỏi cohort HR đủ điều kiện |
| HR dương ngoài [40,180] bpm | Gắn review vì nằm ngoài phạm vi estimator hiện tại; không kết luận nhãn sinh lý sai hoặc cắt về biên |
| Thiếu SBP/DBP hoặc không thỏa SBP > DBP >0 mmHg | Giữ dòng; loại khỏi cohort BP đủ điều kiện, kiểm tra unit/transcription/nguồn |
| BP cao/thấp nhưng thứ tự hợp lệ | Không tự loại theo range dự đoán; kiểm tra nguồn và protocol. Bộ 180/121 mmHg của publisher được giữ |
| Numeric hợp lệ nhưng chưa đối chiếu device/method/unit/repeats/reference support | Chưa đạt `*_reference_qc_pass`; số hợp lý không chứng minh ground truth tốt |
| Reference HR là device/session summary, khoảng lấy trung bình không rõ | `hr_pairing_verified=false`; chưa tính HR agreement cho cửa sổ engine |
| Cuff spot BP thiếu timing/repeats | Giữ nhãn external exploratory; `strict_protocol_accepted=false`, `bp_pairing_verified=false` |

[Protocol BP](../EvidenceMatrix_BP/GROUND_TRUTH_BP_PROTOCOL_V1.md) và [timestamp protocol](../CollectionPackage_V1/TIMESTAMP_SYNC_PROTOCOL.md) quy định kiểm tra gốc. Không tự tạo ngưỡng HR/BP “y khoa” từ phạm vi đầu ra model. Các cờ QC là kết luận cần có hồ sơ review, không phải phép đo do script chứng thực. Với protocol external khác cần một phiên bản quy tắc/ngoại lệ được nhóm duyệt trước khi thay cờ.

## 3. Signal QC: phân biệt mô tả SQI và runtime

Nguồn read-only: `aivitals_engine/quality/sqi.py`, `config/vitals_config.py`, `validation/rules.py`, `contracts/result.py`.

`calculate_bvp_quality` tính `round(clip((SNR-(-5))/(10-(-5)),0,1),2)` với default, tạo SQI trong [0,1]. Docstring mô tả <0,4 / 0,4–0,7 / >=0,7; đây không phải ngưỡng status của validator. `calculate_periodicity_sqi` và cross-ROI SQI là chỉ số khác, không được thay thế trường SQI này mà giữ nguyên ý nghĩa.

| SQI mặc định runtime | `SignalQualityRule` khi có candidate value và quality | Lọc primary dataset |
|---|---|---|
| <0,3 | ERROR `SIGNAL_QUALITY_UNUSABLE` | Không đủ điều kiện |
| [0,3;0,6) | WARNING `SIGNAL_QUALITY_LOW` | Không đủ điều kiện primary; giữ exploratory |
| >=0,6 | Không phát issue SQI | Cần thêm `signal_status=OK`, reference và quyền dùng |
| Missing | Rule không phát issue SQI; computation/status do các rule khác quyết định | Chưa đủ điều kiện primary |

Script đọc `ValidationConfig` hiện tại, không dùng 0,7 thay cho 0,6. Nếu run dùng override thì cần ghi cấu hình run và phiên bản rules tương ứng; báo cáo hiện tại chỉ áp dụng default. Status còn phụ thuộc duration, missing ratio, confidence, physiological range, temporal/cross-ROI và computation. Ví dụ SQI 0,6 không cứu một vital `INVALID`. Script tiêu thụ status đã QC; không thay engine tính lại tín hiệu. CSV collection cũ thiếu SQI/cờ reference được báo thiếu, không tự đọc video để bổ sung.

## 4. Eligibility và denominators

Với endpoint `--target hr|bp`, `supervised_eligible=true` chỉ là screening theo metadata: nhãn hợp lệ, `usage_authorized`, `strict_protocol_accepted`, `*_reference_qc_pass`, `*_pairing_verified` đều true, SQI >=0,6 và `signal_status=OK`. Missing/blank flag mặc định false. Đây chưa kiểm tra đầy đủ feature schema, missing-feature gate, reference waveform hoặc tính đúng đắn của giấy phép; `training_dataset_ready` trong lock vẫn false.

Accuracy còn cần prediction không thiếu, endpoint status `OK`, provenance độc lập theo subject, đúng allocation hash/fold/test. BAD/INVALID không được dùng trong primary; nếu sau này nghiên cứu exploratory BAD cần báo một cohort riêng có quy tắc phiên bản. Không loại theo độ lớn error để làm đẹp MAE. Loại trừ được đếm theo lý do không loại trừ nhau; tổng lý do có thể vượt số dòng.

Report tách kiểm kê gốc, eligible, từng partition và denominators: số dòng, số người, missingness. Demographic tính theo người; xung đột sex/age/Fitzpatrick trong cùng người phải review (dataset longitudinal có tuổi thay đổi cần schema mở rộng). Reference vitals có cả thống kê theo dòng và subject mean; bảng kiểm kê có thể chứa nhãn cần review, không được coi là phân bố cohort sạch. Mean subject trong report descriptive vẫn có thể bị số window lặp chi phối; BP gate chỉ có ý nghĩa khi đầu vào là independent spot observations, không nhân dòng theo window.

## 5. BP sufficiency và trạng thái hiện tại

Giữ nguyên `aivitals_engine/models/blood_pressure/gate.py`: >=85 người, >=255 mẫu; tính phân bố trên subject means với SBP <=100: >=5%, SBP >=160: >=5%, SBP >=140: >=20%; DBP <=60: >=5%, DBP >=100: >=5%, DBP >=85: >=20%. Gate được gọi nguyên bản, riêng cohort nhãn và cohort eligible. Script không suy luận một window là một lần cuff mới; Hào phải chuẩn bị một observation ID/aggregation đúng trước khi dùng gate cho readiness.

Pilot CLBP: 5 nhãn publisher, strict accepted=0; phone: 4 video/1 người, thiếu reference; MPU: 2 windows, 0 HR estimates, pairing/sync còn giới hạn. Các nguồn không bù nhãn cho nhau. Không có training, publishing hay clinical validation trong workflow này.
