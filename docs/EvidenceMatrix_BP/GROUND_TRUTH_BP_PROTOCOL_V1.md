# AIVitals – Ground Truth BP Protocol V1

Ngày kiểm tra: 2026-10-15, Asia/Bangkok; read-only engine main@5d9b4ae.
Mục đích: nhãn SBP/DBP đo độc lập cho estimation, wellness, research/screening support. Protocol chuẩn hóa thu thập theo nguồn chuyên môn; không tự chứng nhận medical-grade, ISO compliance hoặc clinical diagnosis cho AIVitals.

## 1. Điều chỉnh plan và trạng thái hiện tại

- Prompt cũ nhầm gate dữ liệu với kỹ thuật đo: gate.py kiểm tra cohort/count/distribution, không chứa quy tắc nghỉ 5 phút, cuff hoặc loại repeat chênh >10 mmHg.
- Chênh >10 mmHg là lý do đo bổ sung/kiểm tra kỹ thuật, không tự động xóa mọi số đo. Chính sách QC nội bộ bên dưới chỉ nhận nhãn ổn định sau repeats và giữ raw values.
- Nhóm hiện không có máy đo bắp tay/reference BP tự thu. Bốn phone videos và public PPG/HR sample không cung cấp SBP/DBP labels. External CLBP sample đã có 5 nhãn BP do tác giả cung cấp và đối chiếu workbook; không coi nhãn external là cuff repeats do nhóm đo. Không điền giá trị ước đoán, dùng model output làm target hoặc đánh dấu Dataset v1 BP đầy đủ.
- Áp dụng thu BP khi có thiết bị đã được xác minh validation và người vận hành biết kỹ thuật đo. Chốt consent, policy/storage và protocol version trước phiên; đối tượng/thiết bị ngoài population đã validation cần quy trình riêng.

## 2. Thiết bị và chuẩn bị

Chọn máy đo oscillometric bắp tay đã validation cho population dùng; ghi model, serial nếu được phép, firmware, lịch kiểm tra/calibration và cỡ cuff theo arm circumference/nhà sản xuất. Không coi mọi máy ghi “medical” hoặc smartphone app là reference được validation.

Ngồi nghỉ yên ít nhất 5 phút, lưng tựa, bàn chân đặt phẳng, không bắt chéo chân/nói chuyện; tránh caffeine, hút thuốc và vận động trong 30 phút trước đo, bàng quang trống. Cuff trên bắp tay trần, đúng cỡ; tay được đỡ, cuff ngang tim, theo hướng dẫn thiết bị. [AHA scientific statement](https://pubmed.ncbi.nlm.nih.gov/30827125/).

Ghi posture, arm, cuff size, rest duration, time since exercise/caffeine/smoking nếu có; chưa biết ghi missing. Giữ cách đo nhất quán giữa các phiên; không thay thuốc/tạo BP cực trị để lấp nhóm phân bố của gate. Dừng khi người tham gia khó chịu hoặc rút đồng ý; việc xử lý bất thường theo người phụ trách chuyên môn, không theo camera/model.

## 3. Repeated measurements và nhãn reference

Mặc định nghiên cứu lấy 3 readings, cách nhau 1–2 phút; thiết bị có chế độ auto-multiple dùng theo hướng dẫn đã validation và ghi đúng mode. Cơ sở: ESC mô tả repeated measurement, đo thêm khi chênh >10 mmHg và dùng trung bình hai readings cuối; khác biệt auscultatory/AOBP được nêu trong guideline, không áp nhãn “manual standard” cho mọi thiết bị tự động. [ESC 2024](https://academic.oup.com/eurheartj/article/45/38/3912/7741010).

**Quyết định QC nội bộ đã định nghĩa trước (không phải rule trong engine):**

1. Lưu từng SBP/DBP, device HR nếu có, error flags và bắt đầu/kết thúc cuff interval; không sửa readings để hợp nhau.
2. Kiểm tra hai readings cuối: nếu |ΔSBP| >10 hoặc |ΔDBP| >10 mmHg, kiểm tra cuff/tư thế/nói chuyện/thiết bị rồi lấy reading tiếp sau nghỉ phù hợp. Đúng 10 không kích hoạt rule này.
3. Giới hạn mặc định tối đa 5 readings trong series là lựa chọn nghiên cứu nội bộ nhằm tránh lặp vô hạn; trường hợp cần thêm do người phụ trách quyết định và ghi lý do, không tự ép đo.
4. Khi hai readings cuối đạt |ΔSBP| <=10 và |ΔDBP| <=10, không error và kỹ thuật đạt, target SBP/DBP là arithmetic mean riêng của đúng hai readings đó. Lưu IDs của readings dùng; không chọn cặp đẹp nhất trong lịch sử sau khi xem model.
5. Nếu vẫn không ổn định, có artifact/device error hoặc support interval không phù hợp, không nhận paired BP label; đặt dataset QC REJECT/needs review với lý do mô tả. Giữ raw readings, không tạo issue code engine mới hoặc gán 0 cho nhãn thiếu.

Không bình quân giữa hai arms/positions hoặc các trạng thái khác nhau như một target. Không loại nhãn đo hợp lệ chỉ vì nằm ngoài range dự đoán của baseline; kiểm tra chuyên môn/thiết bị và ghi cohort applicability riêng. Đây là quality/reference process, không chẩn đoán tăng/hạ huyết áp.

## 4. Đồng bộ với video và hỗ trợ thời gian của cuff

- Dùng session ID/clock origins thống nhất, ISO 8601 có offset; giữ raw PTS/capture logs và nguồn clock. Marker/clock uncertainty theo ../CollectionPackage_V1/TIMESTAMP_SYNC_PROTOCOL.md.
- Cuff là số đo interval/spot, không beat-by-beat BP và không ground truth từng frame. Timestamp “result displayed” khác interval thực khi cuff thu; ghi cả measurement start/end/completion.
- Nên quay video liên tục bao phủ series và khoảng nghỉ để biết posture/điều kiện; không nhét ba cuff readings cách nhau 1–2 phút vào một video 60 s. Nếu chỉ có clip 60 s, ghi rõ phép gán label là adjacent resting-interval assumption, không chứng minh simultaneous continuous BP.
- Đánh dấu cuff inflation, di chuyển tay/mặt, device errors và site ECG/PPG nếu có; không giả định PPG cùng tay vẫn không bị ảnh hưởng. Mask/loại segment theo rule đã chốt trước, giữ audit.
- Reference target pair hỗ trợ interval của hai readings dùng. Không kéo giá trị này ra mọi frame/phiên hoặc suy PTT từ cuff HR/video đơn lẻ. Capture UTC/offset/drift/sync_error chưa biết giữ missing; không lấy ±8 ms của một public paper gán cho phone sessions.
- Nếu video trước/sau có BP conditions không ổn định, ghi nonstationary và không nhận resting paired label. Một policy before/during/after phải lưu actual measurement intervals và so sánh theo support; không tự interpolate BP.

## 5. Record schema cho BP dataset (research sidecar, không engine migration)

| Field | Yêu cầu / ý nghĩa |
|---|---|
| subject_id, session_id, sample_id | Mã nghiên cứu giả danh; subject grouping nhất quán |
| consent_record_id, consent_version | Hồ sơ quyền dùng đúng phiên; không tự ký/xác nhận thay |
| reference_device, reference_type | Model thực, BP_CUFF; validation source/population, firmware/cuff/arm trong sidecar |
| reference_sbp_mmhg, reference_dbp_mmhg | Nhãn mean của cặp readings đã chốt, number hữu hạn, mmHg; không impute target |
| bp_measurement_start_timestamp/end_timestamp | Khoảng support reference pair; readings chi tiết giữ interval riêng |
| readings | List research records: reading_id, start/end/completion, sbp_mmhg, dbp_mmhg, arm, cuff size, posture, errors |
| selected_reading_ids, aggregation_method | IDs cụ thể và mean_of_last_two_accepted; raw không overwrite |
| video_start/end, video_timebase | Actual/logged source + precision, không run/init date |
| sync_method/offset/drift/error | Có bằng chứng hoặc null; support-policy/uncertainty ghi rõ |
| reference_quality, quality_label, exclusion_reason | Dataset QC, không tự map thành engine issues/status |
| age/height/weight/sex nếu dùng | Dữ liệu được consent và cung cấp/đo thực; không suy từ mặt |
| feature_set_version, processing_config, source_hashes | bp_features_v2+bvp_1.0 hiện tại, provenance và reproducibility |

Metadata template hiện có reference/BP timestamps; repeated readings/validation_source/cuff và selection đặt trong **research sidecar riêng** trong vùng Hào, không thêm vào vital_result JSON hoặc sửa DB. sex_male trong code là 0/1 representation có giới hạn, không giả định phản ánh đầy đủ sex/gender; missing vẫn được ghi missing.

## 6. Data sufficiency gate: mapping chính xác code

Nguồn duy nhất cho bảng này: aivitals_engine/models/blood_pressure/gate.py, DataSufficiencyCriteria. targets shape (n,2) theo thứ tự [SBP,DBP], subject_ids cùng số dòng; kiểm tra finite/valid labels và linkage trước gọi, vì gate không thay mọi input QC.

| Trường / nhóm | Điều kiện code mặc định |
|---|---|
| min_subjects | unique subject count >=85 |
| min_samples | target rows >=255 |
| systolic_low | tỷ lệ subject means SBP <=100 mmHg >=0.05 |
| systolic_high | tỷ lệ subject means SBP >=160 mmHg >=0.05 |
| systolic_elevated | tỷ lệ subject means SBP >=140 mmHg >=0.20 |
| diastolic_low | tỷ lệ subject means DBP <=60 mmHg >=0.05 |
| diastolic_high | tỷ lệ subject means DBP >=100 mmHg >=0.05 |
| diastolic_elevated | tỷ lệ subject means DBP >=85 mmHg >=0.20 |

pressure_distribution tính **mean BP của từng subject trước**, rồi tỷ lệ trên subjects; không tính trên toàn sample rows. Biên <=/>= là inclusive; nhóm elevated/high có thể overlap. Gate fail khi count nhỏ hơn hoặc ratio nhỏ hơn minimum. Không đổi defaults/oversample/copy labels để ép pass.

Ba cuff readings được average thành một target session không tự tạo ba mẫu paired độc lập. Sliding windows từ một recording không làm tăng subject count; giữ subject trong cùng split, fit imputer/scaler trên training only. Một người/bốn video không đạt gate; số BP labels thật hiện tại là 0. Gate 85/255 có hình thức quen thuộc nhưng không chứng minh đầy đủ AAMI/ESH/ISO hoặc validation cuffless. [ESH validation recommendations](https://pubmed.ncbi.nlm.nih.gov/37303198/).

## 7. Inference guards: không nhầm với QC đo BP

Nguồn: models/blood_pressure/baseline.py/features.py; không phải gate.py.

| Guard | Hành vi hiện tại |
|---|---|
| BP_FEATURE_NAMES | 31 fields: 5 vitals +23 BVP +3 demographics, giữ thứ tự |
| Vital feature extraction | Chỉ OK; BAD/INVALID không cung cấp accepted value |
| Missing input ratio >0.3 | ERROR MISSING_FEATURES; predicted BP INVALID/null |
| Có missing nhưng ratio <=0.3 | WARNING MISSING_FEATURES; model có imputer; không chứng minh dữ liệu đo thật |
| Feature ngoài training min/max | Clip + WARNING FEATURES_OUT_OF_TRAINING_RANGE; không validation generalization |
| Predicted SBP | ERROR OUT_OF_PHYSIOLOGICAL_RANGE nếu ngoài inclusive [70,220] mmHg |
| Predicted DBP | ERROR OUT_OF_PHYSIOLOGICAL_RANGE nếu ngoài inclusive [40,130] mmHg |
| Predicted SBP−DBP <10 | ERROR PULSE_PRESSURE_INVALID; đúng 10 không trigger |
| Ridge.fit minimum | 10 samples để fit về mặt code, không gate cohort 85/255 |
| Intended use | product_enabled=False mặc định → RESEARCH_ONLY; không bật product để vượt bằng chứng |

“10 mmHg” ở pulse-pressure guard là **chênh SBP−DBP trong prediction**, khác hoàn toàn “>10 mmHg” giữa hai cuff repeats. Range của prediction không là tiêu chí cắt ground truth cohort. Confidence dựa residual/missingness của model, không xác suất clinical accuracy. BP nằm trong BloodPressureEstimate riêng, không thêm SBP/DBP vào VitalCode hiện tại.

## 8. Acceptance và Week 5 DoD

- [ ] Device validation/population/cuff và consent/điều kiện ghi đủ.
- [ ] Raw repeated BP đo thật, support/timestamps, selection và QC đầy đủ.
- [ ] Video/features paired theo protocol, thiếu/invalid không bị impute thành ground truth.
- [ ] Subject-independent split và data-sufficiency report với counts/subject means/ratios thực.
- [ ] Independent/external/time/calibration validation phù hợp intended use; không chỉ fit error.
- [x] Evidence Matrix MD/CSV + protocol/mapping code prepared; documentation checks riêng.

Deliverables tài liệu hoàn thành; external Dataset v1 BP pilot dùng 5 nhãn CLBP được chuẩn bị riêng trong [Week 5 CLBP pilot report](WEEK5_CLBP_PILOT_REPORT_V1.md). Bộ external thiếu timestamp cuff/repeats/per-subject device model nên không thể xác nhận tuân thủ protocol prospective ở trên; giữ branch exploratory, cần nhóm duyệt giới hạn và quyền sử dụng trước training/sharing. Dataset đầy đủ/gate readiness và clinical validation chưa hoàn thành. Không biến PPG/HR-only dataset thành SBP/DBP. Các nghiên cứu rPPG/BP là estimation/research support; [ESC 2026](https://esc365.escardio.org/journal/92047) không khuyến nghị cuffless BP cho quyết định lâm sàng khi validation chưa đủ.
