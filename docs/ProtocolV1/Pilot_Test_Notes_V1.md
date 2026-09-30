# AIVitals – Pilot Test Notes V1

**Project:** AIVitals / rPPG V1  
**Document:** Pilot Test Notes  
**Version:** V1.0  
**Purpose:** Ghi nhận kết quả pilot để kiểm tra và hoàn thiện Measurement Protocol V1 trước khi thu thập dữ liệu chính thức.

---

## 1. Mục tiêu pilot

Pilot được thực hiện để kiểm tra tính khả thi và khả năng tái lập của Measurement Protocol V1, tập trung vào:

- Khoảng cách camera – người tham gia.
- Tư thế và hướng mặt.
- Điều kiện ánh sáng.
- FPS và chất lượng video.
- Thời lượng ghi hình.
- Khả năng ghi nhận đầy đủ metadata.
- Khả năng phát hiện các sample không đạt tiêu chí chất lượng.
- Tính nhất quán khi một thành viên khác thực hiện lại protocol.

> **Lưu ý:** Pilot ở Week 2 chỉ đánh giá quy trình thu thập và chất lượng sample. Không sử dụng pilot này để đánh giá thuật toán rPPG, BVP, HR, HRV, RR hoặc mô hình BP.

---

## 2. Tài liệu tham chiếu

- `research/week1/DATA_COLLECTION_PLAN.md`
- `research/week2/AIVitals_Measurement_Protocol_V1.md`
- `research/week2/Metadata_Dictionary_V1.xlsx`
- `research/week2/Sample_Exclusion_Rules_V1.md`

Các ngưỡng và yêu cầu trong pilot phải được đối chiếu với Measurement Protocol V1 và DATA_COLLECTION_PLAN.md.

---

## 3. Thiết lập pilot

### 3.1 Thông tin chung

| Field | Value |
|---|---|
| Pilot ID | `PILOT_001` |
| Date | YYYY-MM-DD |
| Operator | |
| Reviewer | |
| Camera/device | |
| Video resolution | |
| Configured FPS | |
| Actual FPS | |
| Environment | |
| Notes | |

---

## 4. Kiểm tra khoảng cách camera

Week 1 chưa quy định một khoảng cách camera cố định. Vì vậy, pilot được dùng để quan sát và lựa chọn khoảng cách phù hợp cho protocol chính.

### 4.1 Các khoảng cách thử nghiệm

Có thể thử các mức khoảng cách ứng viên:

- 40 cm
- 50 cm
- 60 cm
- 70 cm
- 80 cm

Các giá trị trên là **candidate distances để pilot**, không phải yêu cầu chính thức của protocol.

### 4.2 Bảng kết quả

| Distance (cm) | Face clearly visible | Face stable | ROI visibility | Image quality | Operator notes |
|---:|---|---|---|---|---|
| 40 | | | | | |
| 50 | | | | | |
| 60 | | | | | |
| 70 | | | | | |
| 80 | | | | | |

### 4.3 Kết luận khoảng cách

**Candidate range selected:** __________________ cm

**Reason:**

____________________________________________________________

____________________________________________________________

**Protocol update required:** Yes / No

---

## 5. Kiểm tra tư thế

### 5.1 Resting pose

Yêu cầu kiểm tra:

- Người tham gia ngồi ổn định.
- Mặt hướng về camera.
- Mắt hướng về camera.
- Biểu cảm trung tính.
- Hạn chế chuyển động đầu.
- Không nói chuyện hoặc nhai trong resting condition.

### 5.2 Kết quả

| Check | Result | Notes |
|---|---|---|
| Seated position | PASS / WARNING / REJECT | |
| Face frontal | PASS / WARNING / REJECT | |
| Eyes toward camera | PASS / WARNING / REJECT | |
| Neutral expression | PASS / WARNING / REJECT | |
| Minimal head movement | PASS / WARNING / REJECT | |
| No talking / chewing | PASS / WARNING / REJECT | |

---

## 6. Kiểm tra ánh sáng

### 6.1 Standard lighting

Theo DATA_COLLECTION_PLAN.md:

- Mức ánh sáng mục tiêu: **≥ 500 lux**.
- Ánh sáng ưu tiên trực diện.
- Tránh bóng đổ trên mặt.
- Tránh backlight.
- Tránh ánh sáng nhấp nháy.
- Nếu camera hỗ trợ, khóa auto-exposure và white balance.

### 6.2 Low-light challenge

Có thể kiểm tra các điều kiện low-light đã được xác định trong Week 1:

- Khoảng **8 lux**.
- Khoảng **42.4 lux**.

Các điều kiện này dùng để đánh giá challenge condition và không thay thế standard lighting.

### 6.3 Bảng kết quả

| Condition | Illuminance (lux) | Front lighting | Backlight | Shadow | Flicker | Result | Notes |
|---|---:|---|---|---|---|---|---|
| Standard | | | | | | | |
| Low light 1 | ~8 | | | | | | |
| Low light 2 | ~42.4 | | | | | | |

---

## 7. Kiểm tra camera và FPS

### 7.1 Camera

Kiểm tra:

- Camera cố định, không rung.
- Độ phân giải tối thiểu: **320 × 240**.
- Khuyến nghị: **720p hoặc 1080p**.
- Video có FPS ổn định.
- Không xảy ra VFR nếu protocol yêu cầu CFR.
- Exposure / white balance được khóa nếu camera hỗ trợ.

### 7.2 FPS

Theo Week 1:

- **≥30 FPS** cho HR/RR.
- **60 FPS** là mục tiêu cho BP/PTT.

### 7.3 Bảng kiểm tra

| Parameter | Expected | Actual | Result | Notes |
|---|---|---|---|---|
| Resolution | ≥320×240 | | PASS / REJECT | |
| Preferred resolution | 720p/1080p | | PASS / WARNING | |
| Configured FPS | ≥30 FPS | | PASS / REJECT | |
| Actual FPS | Stable | | PASS / WARNING / REJECT | |
| CFR | Required | | PASS / REJECT | |
| Frame drop | ≤5% | | PASS / REJECT | |
| Camera stability | Fixed | | PASS / WARNING | |
| Auto exposure | Locked if possible | | PASS / WARNING | |
| White balance | Locked if possible | | PASS / WARNING | |

---

## 8. Kiểm tra thời lượng ghi hình

### Resting condition

- Thời lượng mục tiêu: **60 giây**.

| Sample | Target duration | Actual duration | Result | Notes |
|---|---:|---:|---|---|
| Sample 01 | 60 sec | | PASS / REJECT | |
| Sample 02 | 60 sec | | PASS / REJECT | |
| Sample 03 | 60 sec | | PASS / REJECT | |

---

## 9. Kiểm tra metadata

Sau mỗi recording, kiểm tra Metadata Dictionary V1 có thể ghi nhận đầy đủ các thông tin cần thiết.

### Checklist

- [ ] `subject_id`
- [ ] `session_id`
- [ ] `recording_date`
- [ ] `video_filename`
- [ ] `width_px`
- [ ] `height_px`
- [ ] `fps_configured`
- [ ] `fps_actual`
- [ ] `frame_count`
- [ ] `duration_sec`
- [ ] `codec`
- [ ] `pose`
- [ ] `head_orientation`
- [ ] `camera_distance_cm`
- [ ] `lighting_condition`
- [ ] `illuminance_lux`
- [ ] `light_source`
- [ ] `backlight`
- [ ] `movement_level`
- [ ] `face_detected`
- [ ] `face_visibility`
- [ ] `occlusion`
- [ ] `occlusion_type`
- [ ] `occlusion_ratio`
- [ ] `reference_device`
- [ ] `reference_type`
- [ ] `gt_start_timestamp`
- [ ] `gt_end_timestamp`
- [ ] `sync_error_ms`
- [ ] `quality_label`
- [ ] `exclusion_reason`

### Metadata completeness

**Missing fields:** ___________________________________________

**Additional fields needed:** _________________________________

---

## 10. Kiểm tra sample quality

Mỗi sample được gán một trong ba nhãn:

- **PASS:** Sample đáp ứng các yêu cầu cần thiết.
- **WARNING:** Sample có vấn đề nhẹ nhưng chưa nhất thiết phải loại.
- **REJECT:** Sample vi phạm tiêu chí loại.

### Quality review

| Sample | Quality label | Reason / observation | Reviewer |
|---|---|---|---|
| Sample 01 | PASS / WARNING / REJECT | | |
| Sample 02 | PASS / WARNING / REJECT | | |
| Sample 03 | PASS / WARNING / REJECT | | |
| Sample 04 | PASS / WARNING / REJECT | | |
| Sample 05 | PASS / WARNING / REJECT | | |

---

## 11. Kiểm tra tiêu chí loại sample

Pilot cần kiểm tra khả năng nhận diện các trường hợp sau:

- [ ] VFR / FPS không ổn định.
- [ ] Frame drop >5%.
- [ ] Video bị corrupted.
- [ ] Thời lượng không đủ.
- [ ] Độ phân giải không đạt.
- [ ] Không phát hiện được mặt.
- [ ] Face/ROI bị che nghiêm trọng (>50%).
- [ ] Thiếu reference data.
- [ ] Reference data không đồng bộ.
- [ ] Sync error >100 ms.
- [ ] Illuminance <5 lux.
- [ ] Illuminance >700 lux.

### Kết quả

**Các tiêu chí phát hiện rõ ràng:** 

____________________________________________________________

**Các tiêu chí còn khó đánh giá:** 

____________________________________________________________

**Cần sửa Sample_Exclusion_Rules_V1.md:** Yes / No

---

## 12. Kiểm tra synchronization

Nếu pilot có reference device, kiểm tra:

- Thời điểm bắt đầu video.
- Thời điểm bắt đầu reference recording.
- Thời điểm kết thúc.
- Chênh lệch timestamp.
- Khả năng ghi nhận `gt_start_timestamp`, `gt_end_timestamp`.
- `sync_error_ms`.

| Sample | Video start | GT start | Sync error (ms) | Result |
|---|---|---|---:|---|
| Sample 01 | | | | PASS / REJECT |
| Sample 02 | | | | PASS / REJECT |
| Sample 03 | | | | PASS / REJECT |

**Synchronization issue:**

____________________________________________________________

---

## 13. Reproducibility test

Một thành viên khác trong team thực hiện lại cùng protocol mà không được hướng dẫn thêm ngoài tài liệu V1.

### Operator A

**Name:** __________________

**Result:** ________________________________________________

### Operator B

**Name:** __________________

**Result:** ________________________________________________

### So sánh

| Item | Operator A | Operator B | Consistent? |
|---|---|---|---|
| Camera setup | | | Yes / No |
| Distance | | | Yes / No |
| Pose | | | Yes / No |
| Lighting | | | Yes / No |
| FPS | | | Yes / No |
| Recording duration | | | Yes / No |
| Metadata | | | Yes / No |
| Quality labeling | | | Yes / No |

**Các điểm chưa nhất quán:**

____________________________________________________________

____________________________________________________________

---

## 14. Vấn đề phát hiện trong pilot

| ID | Issue | Severity | Affected section | Proposed action | Status |
|---|---|---|---|---|---|
| P01 | | Low / Medium / High | | | Open / Resolved |
| P02 | | Low / Medium / High | | | Open / Resolved |
| P03 | | Low / Medium / High | | | Open / Resolved |

---

## 15. Đề xuất chỉnh sửa Protocol V1

Chỉ ghi những thay đổi thực sự được phát hiện từ pilot.

### 15.1 Camera

____________________________________________________________

### 15.2 FPS

____________________________________________________________

### 15.3 Pose

____________________________________________________________

### 15.4 Distance

____________________________________________________________

### 15.5 Lighting

____________________________________________________________

### 15.6 Recording procedure

____________________________________________________________

### 15.7 Metadata

____________________________________________________________

### 15.8 Exclusion criteria

____________________________________________________________

---

## 16. Kết luận pilot

### Pilot status

- [ ] PASS – Có thể sử dụng Protocol V1 cho data collection.
- [ ] CONDITIONAL – Cần sửa một số điểm trước khi data collection.
- [ ] FAIL – Cần thực hiện lại pilot.

### Summary

____________________________________________________________

____________________________________________________________

____________________________________________________________

---

## 17. Definition of Done – Week 2

Pilot được xem là hoàn thành khi:

- [ ] Đã thử nghiệm các khoảng cách camera candidate.
- [ ] Đã kiểm tra tư thế.
- [ ] Đã kiểm tra standard lighting.
- [ ] Đã kiểm tra low-light condition.
- [ ] Đã kiểm tra resolution.
- [ ] Đã kiểm tra configured FPS và actual FPS.
- [ ] Đã kiểm tra frame drop / CFR.
- [ ] Đã kiểm tra thời lượng recording.
- [ ] Đã kiểm tra metadata dictionary.
- [ ] Đã kiểm tra sample exclusion criteria.
- [ ] Đã kiểm tra synchronization nếu có reference device.
- [ ] Đã thực hiện reproducibility test.
- [ ] Đã ghi lại các issue.
- [ ] Đã cập nhật Protocol V1 nếu cần.
- [ ] Đã xác nhận version cuối cùng trước khi thu thập dữ liệu chính thức.

---

## 18. Version History

| Version | Date | Author | Changes |
|---|---|---|---|
| V0.1 | YYYY-MM-DD | | Initial pilot notes |
| V1.0 | YYYY-MM-DD | | Finalized after pilot |

