# AIVitals – Timestamp synchronization V1

Ghép video với reference độc lập cho estimation, wellness, research/screening support. Đồng bộ không chứng minh medical-grade accuracy.

## 0. Chế độ hiện tại: nhóm không có thiết bị reference

Protocol hoàn thiện phần vận hành theo hai nhánh, không thay DoD hoặc gate đã chốt:

| Nhánh | Dữ liệu / mục đích | Có thể chốt |
|---|---|---|
| video_only (hiện dùng) | Video OPPO A16, timeline frame, điều kiện quay và signal QC | Collection thử nghiệm và kiểm tra timing nội bộ video; không paired-reference validation |
| paired_reference (khi có dữ liệu phù hợp) | Video + ECG/PPG hoặc HR summary độc lập với timebase/uncertainty rõ | Đối chiếu theo mức dữ liệu reference thực hỗ trợ |

Nhóm xác nhận không có thiết bị: không bịa reference, không dùng camera trước/sau hay POS/CHROM/GREEN của cùng video làm ground truth độc lập. PTT, clock drift camera–sensor và sync_error_ms không xác định ở nhánh video-only, để null/trống. Kiểm tra độ đều timestamp video không đồng nghĩa đồng bộ sensor.

### A. Thu 3–4 phiên video-only ngay bây giờ

1. Người tham gia SUBJ_001, OPPO A16 camera trước; đồng ý nghiên cứu nội bộ đã ghi riêng. Quyền xem: nhóm dự án; người tham gia phụ trách xóa. Retention 90 ngày vẫn là đề xuất chưa xác nhận. Không công khai raw/metadata phiên khi chưa có quyền chia sẻ.
2. Đặt điện thoại chắc chắn, mặt thẳng/đủ lớn trong khung, ánh sáng đều phía trước; tắt làm đẹp/filter. Chọn 720p/1080p, 30 FPS nếu có. Không giả định lựa chọn 30 FPS bảo đảm CFR hoặc số frame capture.
3. Bật tự động ngày/giờ trên điện thoại và laptop. Ghi ngày, múi giờ UTC+07, thời gian bắt đầu/kết thúc đến giây nếu có; ghi nguồn (tự ghi/clock overlay/container metadata) và độ chính xác biết được. Không dùng mtime copy hoặc measured_at của engine làm capture start.
4. Nếu có thể, quay đồng hồ laptop có giây trong vài giây đầu/cuối rồi quay mặt ổn định. Đó chỉ là anchor thô giữa video và đồng hồ hiển thị; latency hiển thị/camera chưa biết, không chứng minh <=100 ms. Không bắt buộc nếu làm thay đổi ánh sáng/khung hình; thiếu anchor thì ghi unknown.
5. Quay 3–4 file riêng, mỗi phiên 60 giây mặt ổn định (marker ngoài đoạn phân tích nếu dùng); nghỉ/đặt lại máy giữa các phiên. Đầu tiên gửi đường dẫn 1 phiên để QC trước, rồi mới thu các phiên còn lại nếu điều kiện đã cải thiện. Không cố tạo motion/low-light chỉ để đủ số mẫu.
6. Tên file: phone_session01.mp4 ... phone_session04.mp4; giữ file gốc, chuyển USB, không cắt/nén/ghi đè. Raw nằm E:\HAO_Recordings, không trong Git. Đi kèm ghi chú start/end/timezone, camera/facing, scenario và điều kiện sáng. Không biết lux thì để null.

### B. QC timestamp và giới hạn runner

- Giữ nguyên raw, hash và provenance. Ưu tiên đọc PTS từng frame; kiểm tra thứ tự tăng, delta, gaps và duration, lưu video timebase. PTS không tự cung cấp UTC capture hoặc chứng minh không drop frame lúc ghi.
- Nếu có ffprobe, dùng lệnh read-only sau (không tự cài trong task này):

```powershell
ffprobe -v error -select_streams v:0 -show_frames -show_entries frame=pts_time,best_effort_timestamp_time -of json 'E:\HAO_Recordings\phone_session01.mp4'
```

- Hiện chưa tìm thấy ffprobe trên PATH của workspace. OpenCV POS_MSEC có thể hỗ trợ xem timeline decoder nhưng phải ghi nguồn/giới hạn; chưa đủ thì timing_verified=false. Không tự chứng nhận CFR từ một FPS trung bình.
- Runner/QC hiện dùng frame index / reported FPS. Với VFR hoặc PTS không đều, kết quả chỉ exploratory cho video-only; không coi việc chuyển CFR là khôi phục timestamp hay frame bị mất. Reference Dataset V0 vẫn giữ gate loại VFR; muốn thay phải chốt protocol riêng.
- Kiểm tra hướng mặt bằng decoder; phone01 cần rotate 270, không tự áp hướng đó cho mọi file mới. QC phải giữ chất lượng/issue nguyên trạng, không chọn đoạn/phương pháp để che kết quả loại.
- Trong video_only: reference_filename/device/type, reference_hr_bpm, BP, reference timestamps, sync_offset_ms, sync_drift_ppm và sync_error_ms giữ null. quality_label cho reference dataset vẫn REJECT/MISSING_REFERENCE; signal QC có báo cáo riêng và có thể đạt/không đạt độc lập.

### C. Hoàn tất nghiên cứu khi không có phần cứng

Week 3 có thể dùng một dataset công khai đã có video/reference paired, sau khi xác minh nguồn, quyền dùng, file thực, timing và chất lượng. Không tạo paired ground truth từ chính các video mới quay. Week 4 đạt phần video-only pilot khi đủ phiên/metadata/QC; DoD collection có reference của Plan hiện tại vẫn chưa đạt. Nhóm cần chốt thay đổi DoD hoặc cung cấp paired/reference phù hợp; số lượng video không thay thế yêu cầu này.

Nguồn công cụ/benchmark: [ffprobe official documentation](https://ffmpeg.org/ffprobe.html), [rPPG-Toolbox datasets/evaluation](https://github.com/ubicomplab/rPPG-Toolbox). Nguồn thứ hai là điểm tìm dataset, không bằng chứng file/reference/sync của sample hiện tại.

## 1. Chuẩn bị clock và thiết bị

1. Chốt consent, subject_id, session_id, sample_id; ghi model thiết bị và loại reference.
2. Lưu thời gian tuyệt đối ISO 8601 có offset, ưu tiên UTC Z. Giữ timestamp tương đối và mô tả clock/đơn vị/gốc trong video_timebase/reference_timebase. Không suy đoán múi giờ của log không có offset.
3. Video: ưu tiên timestamp/PTS từng frame, log monotonic capture, FPS thực và frame drop/VFR. `frame_index/fps` chỉ xấp xỉ CFR, không chứng minh sai số <=100 ms. VFR bị loại khỏi dataset V0 hiện tại; thay gate cần quyết định protocol riêng.
4. ECG/PPG: waveform gốc, sampling rate, clock, sample-index-to-time và gaps. Smartwatch chỉ xuất HR summary ghi device_hr_summary cùng averaging window và latency nếu biết.
5. BP cuff: ghi bp_spot, SBP/DBP thật, khoảng bắt đầu–kết thúc đo và thời điểm hoàn tất. Không tạo waveform hoặc HRV từ hai số BP.

## 2. Offset và drift

Ưu tiên shared hardware clock/trigger. Nếu không có, dùng sự kiện chung mà **cả hai luồng thực sự ghi nhận** (hardware marker hoặc acquisition log clock chung); ghi cách nhận diện, độ phân giải và latency. Clap chỉ có trong video không đồng bộ ECG nếu ECG không ghi marker đó. NTP chỉ hỗ trợ khởi đầu, không tự chứng minh độ chính xác.

- Ghi marker đầu/cuối và giữa phiên nếu có; lưu thời gian trong cả hai timebase và bất định marker.
- Đổi timebase sang giây rồi fit `t_reference = a * t_video + b`.
- `sync_offset_ms = 1000 * b`; offset dương nghĩa timestamp reference lớn hơn video ở cùng sự kiện.
- `sync_drift_ppm = (a - 1) * 1e6`. Một marker chỉ xác định offset; không xác nhận drift, để trống drift và ghi giới hạn.
- Kiểm tra residual bằng marker độc lập chưa dùng fit nếu có. sync_error_ms là cận sai số bảo thủ: residual lớn nhất cộng bất định marker/timestamp/latency chưa hiệu chỉnh; không phải offset trước hiệu chỉnh.
- Thiếu marker hoặc chưa biết latency/clock: không điền 0, để trống và ghi chưa xác định. Không dùng cross-correlation ECG/PPG để xóa offset mà bỏ qua trễ sinh lý.

## 3. Ghép cửa sổ và gate

- Hiệu chỉnh trên bản dẫn xuất, giữ raw và phép biến đổi.
- Chỉ ghép khoảng video/reference chồng lấp sau hiệu chỉnh; ghi start/end hỗ trợ số đo, không kéo dài reference ra ngoài khoảng đó.
- Gate V0: sync_error_ms >100 → REJECT cho đối chiếu đồng bộ; <=100 chỉ vượt gate thời gian, chưa đủ PASS toàn sample. Unknown chưa đủ PASS. Đây là tiêu chí nội bộ, không ngưỡng engine/y khoa.
- Check duration từng vital: mặc định HR >=6 s; HRV/RR >=30 s. Không tự thay reference window bằng engine window.
- Smartwatch thiếu waveform/clock chính xác: chỉ so summary theo cửa sổ biết rõ, không làm beat-to-beat/HRV reference hoặc tuyên bố sync <=100 ms.
- BP cuff: đối chiếu interval/spot theo protocol đã chốt; ghi posture/arm/device trong notes và đánh dấu đoạn cuff có thể ảnh hưởng tín hiệu. Không coi SBP/DBP là giá trị liên tục mọi frame. Engine hiện không có VitalCode BP.

## 4. Checklist

- [ ] Consent, thiết bị rõ; không có tên thật trong CSV.
- [ ] Timebase/timezone và timestamp raw truy nguyên được.
- [ ] Offset/drift/residual/bất định có bằng chứng; unknown không thay bằng 0.
- [ ] Overlap/reference độc lập đủ cho phân tích dự định.
- [ ] QC dataset tách engine status/issues; estimation không làm reference.
- [ ] Raw/derived lưu đúng kho được cấp quyền; không upload dữ liệu người thật lên repo.

Checklist trên dùng cho paired_reference. Với video_only, thay các mục sensor/sync bằng “không áp dụng cho pilot, thiếu để đạt reference DoD”; không đánh dấu đã kiểm tra đồng bộ độc lập.

Header và kiểu: SESSION_METADATA_TEMPLATE.csv và ../ReferenceDataset/Reference_Dataset_Schema_V0.md.

Trạng thái phone01.mp4 (2026-10-14): decoder có timeline tương đối ~64.37 s nhưng không có clock capture/reference/marker. Chưa tính được offset, drift, sync_error hoặc Pulse Transit Time. Các trường này để null/trống trong metadata, không lấy timestamp run thay thế. Xem DB_MAPPING_AND_USAGE_V1.md để khởi tạo/QC tự động.
