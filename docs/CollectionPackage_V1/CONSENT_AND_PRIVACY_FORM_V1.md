# AIVitals – Đồng ý tham gia và quyền riêng tư V1

Dự thảo cho estimation, wellness, research/screening support. Người phụ trách phải điền `[USER_FILL_REQUIRED]` và giải thích trước thu thập. Mẫu không tự chứng nhận tuân thủ pháp luật hay thay thế xét duyệt của đơn vị.

## Thông tin nghiên cứu

- Đơn vị / người phụ trách: `[USER_FILL_REQUIRED]` (stream: Trương Vỹ Hào).
- Liên hệ hỏi đáp / rút đồng ý: `[USER_FILL_REQUIRED]`.
- Mục đích cụ thể, quy trình, thời lượng và thiết bị: `[USER_FILL_REQUIRED]`.
- Chi phí / hỗ trợ / bồi hoàn nếu có: `[USER_FILL_REQUIRED]`.
- Phiên bản: V1; ngày giải thích: `[USER_FILL_REQUIRED]`.
- subject_id: `[USER_FILL_REQUIRED]`; consent_record_id: `[USER_FILL_REQUIRED]`.

## Dữ liệu và rủi ro

Thu video mặt và timestamp; ECG/PPG nếu hỗ trợ; HR smartwatch hoặc số đo cuff BP nếu có; metadata camera/thiết bị, điều kiện ghi và QC. Chỉ thu dữ liệu đã giải thích và được chọn bên dưới. Không mặc định thu âm hoặc hồ sơ bệnh án.
Video mặt có thể nhận diện cá nhân; subject_id giả danh không làm video trở thành ẩn danh. Có rủi ro lộ hình ảnh/sinh hiệu. Ghi ECG/PPG hoặc đo cuff có thể gây khó chịu; người tham gia có thể yêu cầu dừng khi không thoải mái. Không hứa lợi ích sức khỏe trực tiếp.

## Giới hạn kết quả

Kết quả camera là **estimation** cho **wellness** và **research/screening support**. Không dùng chẩn đoán, quyết định điều trị, thay thế thiết bị y tế hoặc đánh giá chuyên môn. Tham gia không tạo dịch vụ chăm sóc y tế; không đảm bảo độ chính xác hay phát hiện bệnh.

## Quyền riêng tư và vòng đời dữ liệu

- Kho lưu được phê duyệt, mã hóa, người được truy cập: `[USER_FILL_REQUIRED]`.
- Thời hạn giữ, mốc bắt đầu, lịch xóa: `[USER_FILL_REQUIRED]`.
- Consent có tên/chữ ký và bảng liên kết danh tính lưu riêng khỏi video/metadata, chỉ người được phân quyền truy cập.
- Không đưa video mặt, tín hiệu người thật, consent có chữ ký hoặc khóa liên kết lên GitHub. Repo chỉ lưu mẫu trống, quy trình và dữ liệu được phép chia sẻ.
- Cách yêu cầu truy cập/sửa/xóa/rút đồng ý, thời gian phản hồi, giới hạn với dữ liệu đã tổng hợp/chia sẻ: `[USER_FILL_REQUIRED]`.
- Bên nhận dữ liệu, mục đích, vị trí lưu/chuyển giao nếu có: `[USER_FILL_REQUIRED]`. Không mặc định cho phép công khai, thương mại hoặc tái nhận diện.

## Lựa chọn tự nguyện

Đánh dấu Có/Không từng mục; trống nghĩa là chưa đồng ý. Chia sẻ/tái sử dụng tùy chọn không là điều kiện tham gia cơ bản.

| Nội dung | Có | Không |
|---|---|---|
| Tham gia và ghi video mặt cho mục đích đã nêu | [ ] | [ ] |
| Ghi ECG/PPG hoặc HR smartwatch đã giải thích | [ ] | [ ] |
| Ghi số đo máy huyết áp đã giải thích | [ ] | [ ] |
| Sử dụng nội bộ cho nghiên cứu/validation đã nêu | [ ] | [ ] |
| Chia sẻ cho bên nhận cụ thể ghi ở trên | [ ] | [ ] |
| Tái sử dụng cho nghiên cứu tương lai mô tả riêng: `[USER_FILL_REQUIRED]` | [ ] | [ ] |

Tôi đã được giải thích và có cơ hội hỏi. Tôi hiểu từ chối/dừng tham gia không bị phạt hoặc mất quyền lợi vốn có. Tôi có thể rút đồng ý qua liên hệ trên; dữ liệu đã thu được xử lý theo chính sách đã giải thích, không hứa xóa dữ liệu không còn liên kết hoặc thu hồi được. Tôi được nhận một bản đã hoàn tất.

- Người tham gia / chữ ký / ngày: `[USER_FILL_REQUIRED]`.
- Người giải thích / chữ ký / ngày: `[USER_FILL_REQUIRED]`.
- Trạng thái đồng ý, phiên bản và session áp dụng: `[USER_FILL_REQUIRED]`.

Không thu khi chưa điền mục bắt buộc hoặc chưa có đồng ý hợp lệ. Đối tượng cần cơ chế đồng ý đặc biệt phải có quy trình được chốt trước.

Trạng thái hồ sơ 2026-10-14: người tham gia xác nhận qua chat video quay chính mình, OPPO A16 camera trước và đồng ý dùng cho nghiên cứu nội bộ. Đã gán SUBJ_001 và ghi riêng CONSENT_SUBJ_001_CHAT_V1.json, liên kết HAO_PHONE_001. Không tự điền chữ ký hoặc exact accepted_at; chưa có chính sách access/retention/contact hoàn chỉnh. Bản này vẫn là template đầy đủ, không đánh đồng xác nhận qua chat với việc đã chấp nhận mọi điều khoản chưa điền; không có quyền công khai/tái sử dụng được xác nhận.

Tham khảo về tự nguyện và rút tham gia: [HHS OHRP – Withdrawal guidance](https://www.hhs.gov/ohrp/regulations-and-policy/guidance/guidance-on-withdrawal-of-subject/index.html). Nguồn hỗ trợ thiết kế biểu mẫu, không xác nhận luật áp dụng tại nơi thu thập.
