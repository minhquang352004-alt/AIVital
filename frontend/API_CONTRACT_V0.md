# AIVitals API Contract V0

Base URL: `/api/v0` (configurable with `NEXT_PUBLIC_API_BASE_URL`).

All timestamps use ISO-8601 UTC strings. IDs are opaque strings. JSON fields use `snake_case`.

## Common errors

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session was not found",
    "details": {},
    "request_id": "req_01H..."
  }
}
```

Recommended status codes:

| Status | Meaning |
| --- | --- |
| `400` | Invalid request |
| `404` | Session or measurement not found |
| `409` | Invalid state transition |
| `422` | Consent or measurement rejected |
| `500` | Unexpected server error |

## 1. Create session

`POST /sessions`

Request:

```json
{
  "client_version": "0.1.0",
  "timezone": "Asia/Ho_Chi_Minh",
  "consent": {
    "accepted": true,
    "policy_version": "2026-09-01"
  }
}
```

Response `201`:

```json
{
  "session": {
    "id": "ses_01H...",
    "status": "CREATED",
    "created_at": "2026-09-13T16:00:00Z",
    "expires_at": "2026-09-13T16:30:00Z",
    "client_version": "0.1.0",
    "timezone": "Asia/Ho_Chi_Minh"
  }
}
```

## 2. Start measurement

`POST /sessions/{session_id}/measurements`

Request:

```json
{
  "device": {
    "user_agent": "...",
    "platform": "Windows",
    "camera_facing": "user"
  },
  "capture": {
    "fps": 30,
    "width": 1280,
    "height": 720
  }
}
```

Response `201`:

```json
{
  "measurement": {
    "id": "mea_01H...",
    "session_id": "ses_01H...",
    "status": "RUNNING",
    "state": "CAMERA_READY",
    "started_at": "2026-09-13T16:00:05Z"
  }
}
```

The frontend owns camera permission and face-lock UI. The backend receives the measurement lifecycle and may update `state` as signal data is processed.

## 3. Stop measurement

`POST /sessions/{session_id}/measurements/{measurement_id}/stop`

Request:

```json
{
  "reason": "USER_STOPPED"
}
```

Response `200` returns the updated `measurement`.

## 4. Get result

`GET /sessions/{session_id}/measurements/{measurement_id}`

Response `200`:

```json
{
  "result": {
    "measurement_id": "mea_01H...",
    "status": "READY",
    "quality": "GOOD",
    "quality_score": 96,
    "measured_at": "2026-09-13T16:00:18Z",
    "metrics": {
      "heart_rate": { "value": 72, "unit": "bpm", "confidence": 0.96 },
      "hrv_rmssd": { "value": 42, "unit": "ms", "confidence": 0.91 },
      "respiration_rate": { "value": 16, "unit": "breaths_per_minute", "confidence": 0.93 }
    },
    "algorithm_version": "rppg-v1",
    "disclaimer": "Kết quả chỉ mang tính tham khảo..."
  }
}
```

`status: PENDING` means the result is still being computed. `status: REJECTED` means the quality gate did not accept the signal. The MVP route also accepts `PATCH` on this resource for state/result updates from the realtime pipeline.

`GET /sessions/{session_id}/measurements/{measurement_id}/result` returns the result envelope above, or `status: PENDING`.

`POST /sessions/{session_id}/measurements/{measurement_id}/stop` stops an active measurement.

## 5. Get history

`GET /history?page=1&page_size=20&from=2026-09-01T00:00:00Z&to=2026-09-13T23:59:59Z`

Response `200`:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "has_next": false
}
```

## Frontend usage

```ts
import { apiClient } from "./lib/api-client";

const { session } = await apiClient.createSession({
  consent: { accepted: true, policy_version: "2026-09-01" }
});
```

The current Next.js MVP implements session/measurement lifecycle routes with an in-memory store. PostgreSQL persistence is defined by `../db/001_week2_camera_demo.sql`; authentication, streamed frames, and a real WebSocket transport remain production work.
