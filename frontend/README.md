# AIVitals Frontend

Giao diện Next.js + TypeScript cho flow `Consent -> Measurement -> Result -> History`.

## Chạy local

```powershell
cd frontend
npm install
npm run dev
```

Mở `http://localhost:3000`.

## Kiểm thử camera

- **Allow**: chọn `Đo ngay`, cấp quyền camera; flow sẽ đi qua `CAMERA_READY -> FACE_SEARCH -> FACE_LOCKED -> SIGNAL_ACQUIRING -> QUALITY_CHECK -> COMPUTING -> RESULT_READY`.
- **Deny**: từ chối quyền trên prompt trình duyệt; UI hiển thị trạng thái bị từ chối và nút thử lại.
- **Camera Error**: chạy trong môi trường không có `getUserMedia`, hoặc khi camera đang bị ứng dụng khác sử dụng; UI hiển thị lỗi thiết bị và cho phép thử lại.

Frontend đã dùng PostgreSQL runtime qua `pg` và `DATABASE_URL`: session, consent, camera, measurement, vital result và audit log được ghi trong transaction. Chạy migration `../db/001_week2_camera_demo.sql` rồi `../db/002_engine_metadata.sql` trước khi gọi API.

### Chạy PostgreSQL runtime

1. Tạo database PostgreSQL `aivitals`.
2. Chạy lần lượt hai file SQL trong thư mục `../db/`.
3. Sao chép `.env.example` thành `.env.local` và sửa `DATABASE_URL`.
4. Chạy `npm run dev` hoặc `npm run start`.

API sẽ báo lỗi rõ ràng nếu thiếu `DATABASE_URL`; không còn fallback in-memory.

## API Contract V0

Contract và TypeScript client nằm ở:

- `API_CONTRACT_V0.md`: endpoint, request/response JSON và mã lỗi.
- `lib/api-contract.ts`: type/schema dùng chung.
- `lib/api-client.ts`: HTTP client cho create session, start/stop measurement, result và history.

Client mặc định gọi `/api/v0`. Khi backend chạy ở host khác, đặt `NEXT_PUBLIC_API_BASE_URL`.

## Week 2 camera demo E2E

Luồng demo hiện tại:

1. Consent -> `getUserMedia`.
2. Hiển thị camera live và xử lý `Allow`, `Deny`, camera error.
3. MediaPipe nhận diện khuôn mặt trong video.
4. Vẽ face box và 3 ROI theo cùng tỷ lệ với engine: trán, má trái, má phải.
5. Chỉ chuyển `FACE_SEARCH -> FACE_LOCKED` khi khuôn mặt đủ lớn, nằm giữa khung và ổn định 5 frame.
6. Chạy `SIGNAL_ACQUIRING -> QUALITY_CHECK -> COMPUTING -> RESULT_READY`.
7. Thoát phiên sẽ stop camera tracks và dispose detector.

Kịch bản kiểm thử thủ công:

- Chọn **Bắt đầu đo** và chọn **Allow**: thấy `● LIVE`, face box/ROI và state flow.
- Chọn **Block/Deny**: thấy trạng thái từ chối và nút thử lại.
- Tắt camera hoặc dùng môi trường không hỗ trợ `getUserMedia`: thấy camera error.

Schema persistence tuần 2 nằm ở `../db/001_week2_camera_demo.sql`, gồm users, sessions, cameras, measurements, face_quality, vital_measurements và measurement_quality; không lưu raw video frames.

## Phạm vi MVP đã hoàn thành

- Camera permission/error flow, live preview, face box và ROI trán/má.
- State machine từ `CAMERA_READY` đến `RESULT_READY`.
- BVP/HR/SQI realtime dạng demo trong lúc pipeline chạy; kết quả được PATCH về measurement API.
- API route `POST /api/v0/sessions`, `POST /api/v0/sessions/{id}/measurements`,
  `GET/PATCH /api/v0/sessions/{id}/measurements/{measurementId}`.
- Health check PostgreSQL: `GET /api/health/db`.

## Chưa hoàn thành cho production

- Chưa có WebSocket server thật; realtime hiện là client-side demo timer, cần thay bằng stream BVP từ signal engine.
- PostgreSQL runtime đã kết nối qua `pg`; Redis, authentication và WebSocket production vẫn là phần tiếp theo.
- Chưa ghi được raw RGB/ROI samples từ browser sang engine; schema chỉ là migration contract.
- Chưa có E2E automation trong CI; camera allow/deny vẫn cần chạy thủ công trên browser có thiết bị camera.
