# AIVitals – Medical Evidence Matrix V1

Reviewed 2026-10-15 (Asia/Bangkok); engine baseline main@5d9b4ae. Intended use: estimation, wellness, research/screening support; no clinical diagnosis or medical-grade replacement.

## 1. Plan đã chỉnh và phạm vi mức bằng chứng

- Code thực tế: 23 BVP features (morphology 10, amplitude 3, spectral 5, trend 5) + 5 vital inputs + 3 demographics = 31 BP inputs, đúng thứ tự BP_FEATURE_NAMES. Không cố ép thành “15 features”. BVP schema version 1.0; feature-set bp_features_v2+bvp_1.0.
- Tách bằng chứng cho đo feature/chỉ số, hiệu quả feature trong BP prediction và readiness của AIVitals. Cột evidence_level áp dụng claim_scope; tất cả 31 BP inputs hiện bp_inference_evidence=Insufficient cho mô hình AIVitals chưa có measured BP validation. Không chuyển bằng chứng contact PPG sang camera như tương đương.
- Established: có nền tảng/reference methodology vững cho phạm vi ghi rõ; không phải certification của engine. Promising: có proof-of-concept/analogy nhưng phụ thuộc acquisition/reference/validation. Insufficient: chưa có bằng chứng trực tiếp đủ cho claim đó; không khẳng định không có literature. Not Recommended: không sử dụng theo claim lâm sàng/thay thiết bị hiện tại.
- Các mức là đánh giá nghiên cứu của Hào, không một hệ GRADE chính thức hoặc kết quả systematic review đầy đủ. Nguồn là original studies/official statements; chỉ tóm tắt phần đã kiểm tra, không dựa vào lời marketing hoặc code comments như medical proof.
- Physiological rationale là giả thuyết/định nghĩa có thể kiểm thử, không chứng minh feature causal, BP accuracy hay diagnosis. CSV có đủ rationale, noise, limitations, allowed use, validation_required và URL theo từng dòng; UTF-8 BOM để mở Excel.

## 2. Chỉ số và claims

| ID | Chỉ số/phạm vi | Engine mapping | Level | Điều kiện/giới hạn | Nguồn |
|---|---|---|---|---|---|
| M01 | HR camera ở điều kiện kiểm soát | heart_rate | Established | Established là nguyên lý/literature, không phải AIVitals đã validated; HR BAD không ground truth | [S1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/), [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/), [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/) |
| M02 | RMSSD camera-derived PRV | hrv_rmssd | Promising | 30 s minimum compute không bảo đảm HRV reference equivalence; cần duration thống nhất | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/), [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/) |
| M03 | SDNN camera-derived PRV | hrv_sdnn | Promising | Không so SDNN 30–60 s với ECG 5 min/24 h như cùng chỉ số chuẩn | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/), [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/) |
| M04 | RR từ modulation BVP | respiratory_rate | Promising | Không phải đo trực tiếp luồng khí; RR không tính được giữ null | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/) |
| M05 | SBP camera/BVP model | sbp_mmhg | Insufficient | Có 5 nhãn BP external CLBP do tác giả cung cấp; chưa có BP accuracy validation; không chuyển bằng chứng contact sang camera | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/), [S9](https://pubmed.ncbi.nlm.nih.gov/37303198/), [S10](https://esc365.escardio.org/journal/92047) |
| M06 | DBP camera/BVP model | dbp_mmhg | Insufficient | Không infer DBP từ HR hoặc mean amplitude | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/), [S9](https://pubmed.ncbi.nlm.nih.gov/37303198/), [S10](https://esc365.escardio.org/journal/92047) |
| M07 | Facial pulsatility/BVP tương đối | none;mean_pulse_amplitude | Promising | Không gọi đây là blood flow tuyệt đối hoặc chỉ số bệnh; không có dedicated flow field | [S1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/), [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/) |
| M08 | Facial blood flow tuyệt đối | none | Insufficient | Không chuyển a.u. thành mL/min hoặc perfusion diagnosis | [S1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/), [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/) |
| M09 | Dùng camera BP để chẩn đoán/điều trị/thay máy đo | none | Not Recommended | Không dùng kết quả nhóm để quyết định điều trị hoặc medical-grade replacement | [S9](https://pubmed.ncbi.nlm.nih.gov/37303198/), [S10](https://esc365.escardio.org/journal/92047) |
| M10 | SBP/DBP từ máy đo bắp tay đã validation | reference_sbp_mmhg;reference_dbp_mmhg | Established | Tên/model cụ thể vẫn phải được kiểm tra validation; cuff không phải waveform liên tục | [S7](https://pubmed.ncbi.nlm.nih.gov/30827125/), [S8](https://academic.oup.com/eurheartj/article/45/38/3912/7741010) |
| M11 | RMSSD/SDNN theo ECG NN chuẩn hóa | none | Established | Không gán Established này cho camera PRV hoặc feature ibi_std_ms | [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/) |

HRV camera nên gọi PRV/HRV estimation có điều kiện. ECG NN là reference; recording chuẩn ngắn hạn thường dùng 5 phút, không suy compute minimum 30 s thành clinical equivalence. RR cần reference respiration riêng. Pulsatility quang học không phải flow tuyệt đối; SBP/DBP model output không thuộc VitalCode của vital_result schema hiện tại.

## 3. Mapping đầy đủ vector BP (không reorder)

| Pos | Field / unit | Level cho feature | Rationale (liên hệ, không causal proof) | Giới hạn code/noise | Nguồn / phạm vi |
|---:|---|---|---|---|---|
| 1 | heart_rate_bpm (bpm) | Established | Pulse frequency proxy cho HR; BP hiệu quả riêng chưa chứng minh | Chỉ VitalValue OK được BP adapter lấy; BAD bị thiếu | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/), [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/); indirect/definition, chưa validate BP AIVitals |
| 2 | hrv_rmssd_ms (ms) | Promising | Biến thiên xung liên tiếp; autonomic proxy phụ thuộc điều kiện | Pulse PRV không ECG NN-HRV; frame jitter khuếch đại sai số | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/), [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/); indirect/definition, chưa validate BP AIVitals |
| 3 | hrv_sdnn_ms (ms) | Promising | Biến thiên xung toàn cửa sổ; duration dependence | Không so các duration khác nhau như tương đương; chỉ OK được lấy | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/), [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/); indirect/definition, chưa validate BP AIVitals |
| 4 | mean_ibi_ms (ms) | Promising | Khoảng xung trung bình liên quan inverse pulse rate | VITAL_FEATURE_NAMES maps hrv_mean_ibi; không gọi ECG RR trực tiếp | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/), [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/); indirect/definition, chưa validate BP AIVitals |
| 5 | respiratory_rate_brpm (brpm) | Promising | Modulation liên quan respiration có điều kiện | Chỉ OK; chưa chứng minh RR là predictor BP đủ mạnh | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/); indirect/definition, chưa validate BP AIVitals |
| 6 | mean_rise_time_ms (ms) | Insufficient | Thời gian onset→peak, descriptor contour; BP inference là giả thuyết | Không phải PEP/PTT hoặc ejection time; chỉ contact analogy | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 7 | mean_decay_time_ms (ms) | Insufficient | Peak→onset tiếp theo mô tả descending contour | Ảnh hưởng peripheral tone/filter/segmentation; không DBP trực tiếp | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 8 | std_rise_time_ms (ms) | Insufficient | Độ dao động vị trí peak/onset qua các nhịp | Có thể chủ yếu đo noise; không bằng chứng ổn định co cơ tim | [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/), [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 9 | mean_systolic_ratio (ratio) | Insufficient | Rise/(rise+decay) là tỷ lệ timing nội bộ code | Tên systolic không chứng minh pha co tim hay arterial stiffness calibrated | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 10 | mean_pw25_ms (ms) | Insufficient | Độ rộng xung ở 25% normalized peak; contour descriptor | Ngưỡng crossing nhạy baseline/filter; không biomarker BP đã xác thực | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 11 | mean_pw50_ms (ms) | Insufficient | Độ rộng xung ở 50% normalized peak; contour descriptor | Pulse width không xác định duy nhất compliance hoặc BP | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 12 | mean_pw75_ms (ms) | Insufficient | Độ rộng xung ở 75% normalized peak; contour descriptor | Vùng gần peak rất nhạy sampling/plateau | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 13 | mean_area_ratio (ratio) | Insufficient | Tỷ lệ area onset→peak / peak→end trên beat chuẩn hóa | Không phải stroke volume, contractility hay SBP/DBP trực tiếp | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/); indirect/definition, chưa validate BP AIVitals |
| 14 | aix_proxy (ratio) | Insufficient | Code (P2-P1)/P1 từ secondary local peak | Không AIx áp lực chuẩn; peak thứ hai không được xác minh là reflected wave | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/), [S6](https://pubmed.ncbi.nlm.nih.gov/9719069/); indirect/definition, chưa validate BP AIVitals |
| 15 | apg_aging_index (ratio) | Insufficient | Code (b-c-d-e)/a trên đạo hàm bậc 2 | Lấy 5 extrema đầu không chứng minh a–e sinh lý; không vascular age camera | [S6](https://pubmed.ncbi.nlm.nih.gov/9719069/); indirect/definition, chưa validate BP AIVitals |
| 16 | mean_pulse_amplitude (a.u.) | Insufficient | Raw peak-onset BVP amplitude; optical volume proxy | Exposure/normalization/ROI thay scale; không flow hoặc mmHg | [S1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/), [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 17 | pulse_amp_cv (ratio) | Insufficient | SD/mean amplitude; độ biến thiên tương đối | Breathing/motion/light đều ảnh hưởng; không autonomic/BP diagnosis | [S1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/), [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/); indirect/definition, chưa validate BP AIVitals |
| 18 | notch_relative_amp (ratio) | Insufficient | Code first post-peak trough / peak trên normalized beat | Local trough không đảm bảo dicrotic notch; không phải pressure augmentation | [S5](https://pubmed.ncbi.nlm.nih.gov/12241535/), [S6](https://pubmed.ncbi.nlm.nih.gov/9719069/); indirect/definition, chưa validate BP AIVitals |
| 19 | fundamental_freq_hz (Hz) | Established | Peak phổ dải pulse là proxy tần số HR nếu signal hợp lệ | Feature band 0.75–2.5 Hz khác HR validator 40–180 bpm; có harmonic ambiguity | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 20 | harmonic_ratio_h2 (ratio) | Insufficient | Power quanh 2f0 / power quanh f0 mô tả shape/spectral content | Filter/bandwidth/ROI làm thay ratio; không stiffness/BP trực tiếp | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 21 | harmonic_ratio_h3 (ratio) | Insufficient | Power quanh 3f0 / power quanh f0 | Hài cao có thể bị bandpass xóa; thiếu thông tin không phải zero physiology | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 22 | spectral_entropy (unitless) | Insufficient | Entropy chuẩn hóa mô tả độ phân tán phổ trong dải | Chỉ mathematical descriptor/QC candidate; không chứng minh BP causality | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 23 | in_band_power_ratio (ratio) | Insufficient | Power 0.75–2.5 Hz / total Nyquist power | Pre-filtering có thể làm ratio cao; không SQI/accuracy độc lập | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 24 | baseline_drift_slope (a.u./s) | Insufficient | Linear slope của BVP đã xử lý | Detrend/bandpass có thể xóa baseline; không respiration hoặc BP drift thật | [S1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/), [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/); indirect/definition, chưa validate BP AIVitals |
| 25 | bvp_skewness (unitless) | Insufficient | Moment bậc 3 chuẩn hóa mô tả phân bố amplitude | Biến đổi waveform hoặc motion làm đổi; không pressure distribution | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 26 | bvp_kurtosis (unitless) | Insufficient | Excess kurtosis: m4/m2^2 - 3 trong code | Spikes/artifacts ảnh hưởng; không bằng chứng bệnh/pressure | [S2](https://pubmed.ncbi.nlm.nih.gov/28113245/); indirect/definition, chưa validate BP AIVitals |
| 27 | ibi_std_ms (ms) | Promising | SD np.std của duration onset→onset beat; PRV descriptor | Không mặc định SDNN ECG; population SD/beat selection khác vital estimator | [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/); indirect/definition, chưa validate BP AIVitals |
| 28 | ibi_mean_ms (ms) | Promising | Mean onset→onset duration; pulse interval proxy | Không đồng nhất trường mean_ibi_ms của vitals adapter; pipeline definitions khác | [S3](https://pubmed.ncbi.nlm.nih.gov/20952328/), [S4](https://pubmed.ncbi.nlm.nih.gov/8598068/); indirect/definition, chưa validate BP AIVitals |
| 29 | age_years (years) | Insufficient | Covariate/confounder cho BP model, không waveform feature | Không suy tuổi từ mặt; demographic shortcut có thể làm benchmark đẹp giả | [S9](https://pubmed.ncbi.nlm.nih.gov/37303198/); indirect/definition, chưa validate BP AIVitals |
| 30 | sex_male (0/1) | Insufficient | Binary covariate theo representation hiện tại của code | Không infer từ ảnh; binary encoding không đại diện đầy đủ sex/gender | [S9](https://pubmed.ncbi.nlm.nih.gov/37303198/); indirect/definition, chưa validate BP AIVitals |
| 31 | bmi (kg/m^2) | Insufficient | weight_kg / (height_cm/100)^2 trong adapter | Có thể confound/covariate, không BP hoặc vascular metric; không đoán từ mặt | [S9](https://pubmed.ncbi.nlm.nih.gov/37303198/); indirect/definition, chưa validate BP AIVitals |

## 4. Audit code quan trọng

- Nguồn read-only: features/schema.py, models/blood_pressure/features.py/gate.py/baseline.py; morphology/amplitude/spectral/trend/segmentation/config trong features.
- valid_beat_count, window_duration_s, fs là 3 metadata, không trong vector 23 features. _schema_version là thông tin export JSON, không BP feature.
- extract_vital_features chỉ lấy accepted_vitals (OK), không lấy BAD dù frontend có READY. NaN → missing; imputation trong model không làm sinh ra physiological evidence. Không impute BP ground-truth labels.
- Một frame tại 30 Hz cách nhau ~33.3 ms; ở 60 Hz ~16.7 ms. Nội suy/FFT zero padding không tạo thêm fiducial timing information. Filter/normalization thay morphology/amplitude; phải ghi pipeline version và thông số khi đánh giá.
- aix_proxy không pressure AIx chuẩn; apg_aging_index lấy 5 extrema đầu, chưa chứng minh a–e đúng sinh lý. ibi_std_ms dùng np.std trên beat duration, không mặc định đồng nghĩa SDNN vital/ECG. bvp_kurtosis là excess kurtosis. fundamental band 0.75–2.5 Hz là code feature, không toàn HR physiological range.
- baseline_drift_slope đo signal đã xử lý; bandpass/detrend có thể loại chính baseline/respiration cần nghiên cứu. Không diễn giải slope thành BP drift.

## 5. Nguồn và giới hạn chuyển giao

- [S1 – Verkruysse et al. 2008 – ambient-light rPPG (primary optical experiment)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717852/): Cho thấy pulsatility quang học; calibration biên độ còn hạn chế, không xác nhận flow tuyệt đối.
- [S2 – Wang et al. 2017 – Algorithmic Principles of Remote PPG (primary POS study)](https://pubmed.ncbi.nlm.nih.gov/28113245/): Mô hình quang học và benchmark pulse extraction; không validation BP của AIVitals.
- [S3 – Poh et al. 2011 – webcam multiparameter proof of concept](https://pubmed.ncbi.nlm.nih.gov/20952328/): HR/variability/respiration trong điều kiện thử nghiệm; không chứng minh camera HRV thay ECG ở mọi điều kiện.
- [S4 – ESC/NASPE Task Force 1996 – HRV measurement standards](https://pubmed.ncbi.nlm.nih.gov/8598068/): Chuẩn ECG NN và duration; ngưỡng compute 30 s của engine không tự tương đương recording chuẩn.
- [S5 – Millasseau et al. 2002 – contact digital pulse contour and stiffness](https://pubmed.ncbi.nlm.nih.gov/12241535/): Bằng chứng contact DVP; chỉ hỗ trợ analog sinh lý, không xác thực morphology rPPG/BP.
- [S6 – Takazawa et al. 1998 – second-derivative contact PPG](https://pubmed.ncbi.nlm.nih.gov/9719069/): 600 subjects trong phần aging; extrema sinh lý của contact PPG không mặc định bằng extrema đầu tiên của code.
- [S7 – AHA/Muntner et al. 2019 – BP measurement statement](https://pubmed.ncbi.nlm.nih.gov/30827125/): Kỹ thuật đo BP chuẩn hóa; không chứng nhận thiết bị hay thuật toán của nhóm.
- [S8 – ESC 2024 hypertension guideline – measurement technique](https://academic.oup.com/eurheartj/article/45/38/3912/7741010): Đo bổ sung khi chênh >10 mmHg; không phải quy tắc loại ngay toàn phiên.
- [S9 – ESH/Stergiou et al. 2023 – cuffless validation recommendations](https://pubmed.ncbi.nlm.nih.gov/37303198/): Validation phù hợp thiết bị/calibration, nhiều điều kiện; gate số lượng không thay các thử nghiệm đó.
- [S10 – ESC cuffless BP scientific statement – 25 February 2026](https://esc365.escardio.org/journal/92047): Không khuyến nghị cuffless cho quyết định lâm sàng do validation accuracy chưa đủ.

Bằng chứng morphology từ S5/S6 là contact peripheral PPG, không thử nghiệm 23 features rPPG của engine. S9/S10 là framework/cảnh báo validation, không paper xác nhận từng feature. Muốn nâng một dòng phải có dataset/ablation subject-independent, reference phù hợp, sample counts, effect/error/uncertainty và external/time validation; lưu study ID/version và lý do reclassification.

## 6. DoD Week 5 và tình trạng dữ liệu

- Ma trận + CSV, mapping 31 inputs và protocol BP reference: deliverables tài liệu có thể hoàn tất.
- Dataset v1 có BP ground truth không được tạo từ 4 phone videos hoặc public PPG/HR-only sample. Đã đối chiếu 5 nhãn BP độc lập do tác giả CLBP cung cấp cho 5 video local; xem [Week 5 CLBP pilot](WEEK5_CLBP_PILOT_REPORT_V1.md). Chưa có cuff timing/repeats/model validation theo protocol nhóm hoặc BP prediction accuracy. Không nâng evidence level hoặc bật product_enabled chỉ vì đã có nhãn.
- Ground-truth acquisition/gate readiness: GROUND_TRUTH_BP_PROTOCOL_V1.md. Ghi measured labels riêng, subject-level split, holdout calibration/external evaluation; gate 85/255 chỉ cần thiết theo code, không đủ chứng nhận.

## 7. Verification thực hiện

CSV 42 dòng =11 metric/claim +31 BP input; engine_field/order/positions khớp BP_FEATURE_NAMES, đủ 23 BVP fields và 4 evidence levels. Tất cả BP-input rows giữ bp_inference_evidence=Insufficient, có limitations/validation/source URLs; MD bao phủ toàn field. git diff --check pass. Gate smoke read-only bằng fixture tổng hợp trong bộ nhớ xác nhận biên/subject grouping (85 subjects/255 rows pass, 84 subjects hoặc 255 rows một subject fail); không lưu synthetic BP như dữ liệu thật và không train model. Không chạy clinical/device validation hoặc xác nhận Dataset v1 BP.
