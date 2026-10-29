# AIVitals – Week 3 Review Notes

## 1. Mục tiêu
Tạo Reference Dataset V0 từ video kết hợp ECG/PPG reference.

## 2. Kết quả cần đạt
- Reference recordings.
- Đối chiếu HR với ECG/PPG/reference.
- Gán nhãn chất lượng.
- Loại sample không đạt.
- Hoàn thiện Reference Dataset V0.

## 3. Nhật ký
| Ngày | Công việc | Số sample | Kết quả | Ghi chú |
|---|---|---:|---|---|
| 2026-10-14 | Review video-only và test pipeline | 1 file hiện tại | Decode được; reference chưa có | Phone video, không tính fixture RGB/video của engine là participant reference |
| 2026-10-14 | HR reference validation | 0 paired sample | Chưa thực hiện được | Không có reference HR/timestamp/sync |
| 2026-10-14 | Quality labeling | 1 | REJECT khỏi reference dataset | MISSING_REFERENCE; kết quả rPPG cuối cũng REJECTED |
| 2026-10-14 | Dataset review | 0 accepted reference | Chưa đạt data DoD | Schema/issue docs đã đối chiếu; collection package đã chuẩn bị |
| 2026-10-14 | Agent full automated phone QC | 1 file, 16 updates | Exit 0, final INVALID/REJECTED | 1906 frame; metadata/raw result/summary lưu; không reference |
| 2026-10-14 | Agent full phone02 QC | 1 file mới, 7 updates | Exit 0; raw BAD/frontend READY/POOR | Score 34; reference vẫn thiếu; tổng 2 file |
| 2026-10-14 | Agent full phone03/04 QC | 2 file mới | Exit 0 cả hai; BAD/READY và no result/PENDING | Tổng 4 video-only; 0 accepted reference |
| 2026-10-14 | Official dataset assessment + MPU baseline | 1 public candidate, 2 windows | Run hoàn tất; 0 usable HR estimates | Reference HR 71 bpm; index alignment assumed, sync chưa xác minh; không strict acceptance |

## 4. Tổng hợp
| Chỉ số | Giá trị |
|---|---:|
| Tổng sample đã xác nhận còn file | 4 video-only |
| PASS vào reference dataset | 0 |
| WARNING vào reference dataset | 0 |
| REJECT khỏi reference dataset | 4 |
| Có ECG | 0 |
| Có PPG reference độc lập | 0 |
| Đồng bộ đạt | 0 đã chứng minh |
| Đồng bộ không đạt | Chưa đo; 4 chưa xác định, không thay bằng 0 ms |

## 5. Vấn đề
| ID | Vấn đề | Mức độ | Hướng xử lý | Trạng thái |
|---|---|---|---|---|
| W3-01 | Không có reference độc lập | Chặn validation | Mượn thiết bị/nhận paired dataset đúng protocol | Chưa giải quyết |
| W3-02 | Thiếu capture/reference timestamp và sync evidence | Chặn paired comparison | Thu đồng thời, ghi timebase/marker/uncertainty | Chưa giải quyết |
| W3-03 | Video giải mã mặt nằm ngang; SQI thấp | Ảnh hưởng pipeline | Đã thêm rotate 270; quay có điều kiện ổn định, giữ gates | Hướng được xử lý; chất lượng vẫn hạn chế |

## 6. Definition of Done
- [ ] Có reference recordings.
- [ ] Video và ECG/PPG liên kết đúng session.
- [ ] Đã kiểm tra timestamp.
- [ ] Đã kiểm tra đồng bộ.
- [ ] Đã xác định HR reference.
- [x] Đã gán PASS/WARNING/REJECT cho file video-only hiện có.
- [x] Sample REJECT có lý do.
- [ ] Reference Dataset V0 được tạo.

File metadata/QC và package được tạo không đồng nghĩa có accepted reference dataset. Theo dõi tiếp tại HAO_WEEK3_WEEK4_STATUS.md.
