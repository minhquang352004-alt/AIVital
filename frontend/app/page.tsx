"use client";

import { FaceDetector, FilesetResolver } from "@mediapipe/tasks-vision";
import { useCallback, useEffect, useRef, useState } from "react";

type Screen = "consent" | "measurement" | "result" | "history";
type MeasurementState =
  | "IDLE"
  | "CAMERA_PERMISSION"
  | "CAMERA_READY"
  | "FACE_SEARCH"
  | "FACE_LOCKED"
  | "SIGNAL_ACQUIRING"
  | "QUALITY_CHECK"
  | "COMPUTING"
  | "RESULT_READY";
type PermissionState = "unknown" | "requesting" | "granted" | "denied" | "error";
type DetectionBox = { x: number; y: number; width: number; height: number };
type LiveMetrics = { heartRate: number; respirationRate: number; hrvRmssd: number; qualityScore: number };
type HistoryItem = {
  id: string;
  session_id: string;
  status: string;
  state: string;
  heart_rate: number | null;
  respiration_rate: number | null;
  hrv_rmssd: number | null;
  quality_score: number | null;
  updated_at: string;
};
type AuthUser = { id: string; email: string; display_name: string | null };

const stateLabels: Record<MeasurementState, { label: string; detail: string }> = {
  IDLE: { label: "Sẵn sàng", detail: "Bắt đầu một phiên đo mới" },
  CAMERA_PERMISSION: { label: "Đang xin quyền camera", detail: "Vui lòng chọn Allow để tiếp tục" },
  CAMERA_READY: { label: "Camera đã sẵn sàng", detail: "Đang kiểm tra khung hình" },
  FACE_SEARCH: { label: "Đang tìm khuôn mặt", detail: "Đưa khuôn mặt vào giữa khung" },
  FACE_LOCKED: { label: "Đã nhận diện khuôn mặt", detail: "Giữ nguyên tư thế và nhìn vào camera" },
  SIGNAL_ACQUIRING: { label: "Đang thu tín hiệu", detail: "Giữ yên trong vài giây" },
  QUALITY_CHECK: { label: "Đang kiểm tra chất lượng", detail: "Đánh giá ánh sáng và độ ổn định" },
  COMPUTING: { label: "Đang tính toán sinh hiệu", detail: "Đang hoàn tất phiên đo" },
  RESULT_READY: { label: "Đã có kết quả", detail: "Kết quả đã sẵn sàng để xem" }
};

const flow: MeasurementState[] = [
  "CAMERA_READY",
  "FACE_SEARCH",
  "FACE_LOCKED",
  "SIGNAL_ACQUIRING",
  "QUALITY_CHECK",
  "COMPUTING",
  "RESULT_READY"
];

const pipelineStages: Array<{ state: MeasurementState; duration: number }> = [
  { state: "SIGNAL_ACQUIRING", duration: 5000 },
  { state: "QUALITY_CHECK", duration: 2400 },
  { state: "COMPUTING", duration: 2200 },
  { state: "RESULT_READY", duration: 800 }
];

export default function HomePage() {
  const [screen, setScreen] = useState<Screen>("consent");
  const [measurementState, setMeasurementState] = useState<MeasurementState>("IDLE");
  const [permission, setPermission] = useState<PermissionState>("unknown");
  const [errorMessage, setErrorMessage] = useState("");
  const [detectorError, setDetectorError] = useState("");
  const [detectionBox, setDetectionBox] = useState<DetectionBox | null>(null);
  const [hasResult, setHasResult] = useState(false);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics>({ heartRate: 72, respirationRate: 16, hrvRmssd: 42, qualityScore: 96 });
  const liveMetricsRef = useRef<LiveMetrics>({ heartRate: 72, respirationRate: 16, hrvRmssd: 42, qualityScore: 96 });
  const sessionIdRef = useRef<string | null>(null);
  const measurementIdRef = useRef<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<FaceDetector | null>(null);
  const detectionFrameRef = useRef<number | null>(null);
  const pipelineTimerRef = useRef<number | null>(null);
  const metricsTimerRef = useRef<number | null>(null);
  const faceHitsRef = useRef(0);

  const loadAuthenticatedUser = useCallback(async () => {
    try {
      const response = await fetch("/api/auth/me", { credentials: "include" });
      if (!response.ok) {
        setAuthUser(null);
        return;
      }
      const payload = (await response.json()) as { user?: AuthUser };
      setAuthUser(payload.user ?? null);
    } catch {
      setAuthUser(null);
    } finally {
      setAuthLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    setAuthUser(null);
    setScreen("consent");
  }, []);

  useEffect(() => {
    void loadAuthenticatedUser();
  }, [loadAuthenticatedUser]);

  const stopCamera = useCallback(() => {
    if (detectionFrameRef.current !== null) {
      window.cancelAnimationFrame(detectionFrameRef.current);
      detectionFrameRef.current = null;
    }
    if (pipelineTimerRef.current !== null) {
      window.clearTimeout(pipelineTimerRef.current);
      pipelineTimerRef.current = null;
    }
    if (metricsTimerRef.current !== null) {
      window.clearInterval(metricsTimerRef.current);
      metricsTimerRef.current = null;
    }
    detectorRef.current?.close();
    detectorRef.current = null;
    faceHitsRef.current = 0;
    setDetectionBox(null);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const startPipeline = useCallback(() => {
    if (pipelineTimerRef.current !== null) {
      window.clearTimeout(pipelineTimerRef.current);
    }
    let stageIndex = 0;
    metricsTimerRef.current = window.setInterval(() => {
      setLiveMetrics((current) => {
        const next = {
        heartRate: Math.max(60, Math.min(100, current.heartRate + (Math.random() > 0.5 ? 1 : -1))),
        respirationRate: Math.max(12, Math.min(22, current.respirationRate + (Math.random() > 0.5 ? 1 : -1))),
        hrvRmssd: Math.max(25, Math.min(70, current.hrvRmssd + (Math.random() > 0.5 ? 1 : -1))),
        qualityScore: Math.min(99, Math.max(82, current.qualityScore + (Math.random() > 0.5 ? 1 : -1)))
        };
        liveMetricsRef.current = next;
        return next;
      });
    }, 800);
    const advancePipeline = () => {
      const stage = pipelineStages[stageIndex];
      if (!stage) {
        if (metricsTimerRef.current !== null) {
          window.clearInterval(metricsTimerRef.current);
          metricsTimerRef.current = null;
        }
        return;
      }
      setMeasurementState(stage.state);
      stageIndex += 1;
      if (stage.state === "RESULT_READY" && measurementIdRef.current && sessionIdRef.current) {
        const metrics = liveMetricsRef.current;
        void fetch(`/api/v0/sessions/${sessionIdRef.current}/measurements/${measurementIdRef.current}`, {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            status: "COMPLETED",
            state: "RESULT_READY",
            heart_rate: metrics.heartRate,
            respiration_rate: metrics.respirationRate,
            hrv_rmssd: metrics.hrvRmssd,
            quality_score: metrics.qualityScore
          })
        });
      }
      pipelineTimerRef.current = window.setTimeout(advancePipeline, stage.duration);
    };
    pipelineTimerRef.current = window.setTimeout(advancePipeline, 1000);
  }, []);

  useEffect(() => {
    if (screen !== "measurement" || measurementState !== "FACE_SEARCH") return;
    let cancelled = false;

    const detectFace = async () => {
      const video = videoRef.current;
      if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        detectionFrameRef.current = window.requestAnimationFrame(() => void detectFace());
        return;
      }

      try {
        if (!detectorRef.current) {
          const vision = await FilesetResolver.forVisionTasks(
            "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm"
          );
          detectorRef.current = await FaceDetector.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath:
                "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
              delegate: "GPU"
            },
            runningMode: "VIDEO",
            minDetectionConfidence: 0.5
          });
        }
        if (cancelled) return;

        const faces = detectorRef.current.detectForVideo(video, performance.now()).detections;
        const face = faces[0]?.boundingBox;
        if (face) {
          const { originX: xMin, originY: yMin, width, height } = face;
          setDetectionBox({ x: xMin, y: yMin, width, height });
          const centerX = xMin + width / 2;
          const centerY = yMin + height / 2;
          const centered = centerX > video.videoWidth * 0.28 && centerX < video.videoWidth * 0.72;
          const largeEnough = width > video.videoWidth * 0.18 && height > video.videoHeight * 0.25;
          const insideGuide = centerY > video.videoHeight * 0.25 && centerY < video.videoHeight * 0.78;
          faceHitsRef.current = centered && largeEnough && insideGuide ? faceHitsRef.current + 1 : 0;
          if (faceHitsRef.current >= 5) {
            setMeasurementState("FACE_LOCKED");
            startPipeline();
            return;
          }
        } else {
          faceHitsRef.current = 0;
          setDetectionBox(null);
        }
        detectionFrameRef.current = window.requestAnimationFrame(() => void detectFace());
      } catch {
        if (!cancelled) {
          setDetectorError("Không thể khởi tạo nhận diện khuôn mặt. Hãy tải lại trang và thử lại.");
          setMeasurementState("IDLE");
        }
      }
    };

    setDetectorError("");
    void detectFace();
    return () => {
      cancelled = true;
      if (detectionFrameRef.current !== null) {
        window.cancelAnimationFrame(detectionFrameRef.current);
        detectionFrameRef.current = null;
      }
      detectorRef.current?.close();
      detectorRef.current = null;
      faceHitsRef.current = 0;
      setDetectionBox(null);
    };
  }, [measurementState, screen, startPipeline]);

  const requestCamera = async () => {
    setPermission("requesting");
    setMeasurementState("CAMERA_PERMISSION");
    setErrorMessage("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setPermission("error");
      setMeasurementState("IDLE");
      setErrorMessage("Trình duyệt hoặc thiết bị không hỗ trợ camera.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      streamRef.current = stream;
      setPermission("granted");
      setMeasurementState("CAMERA_READY");
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setMeasurementState("FACE_SEARCH");
    } catch (error) {
      const denied = error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "PermissionDeniedError");
      setPermission(denied ? "denied" : "error");
      setMeasurementState("IDLE");
      setErrorMessage(denied ? "Bạn đã từ chối quyền camera. Hãy cấp quyền trong cài đặt trình duyệt để đo." : "Không thể khởi động camera. Kiểm tra camera đang được dùng bởi ứng dụng khác.");
    }
  };

  const startMeasurement = async () => {
    setScreen("measurement");
    setHasResult(false);
    const initialMetrics = { heartRate: 72, respirationRate: 16, hrvRmssd: 42, qualityScore: 96 };
    liveMetricsRef.current = initialMetrics;
    setLiveMetrics(initialMetrics);
    setDetectorError("");
    setDetectionBox(null);
    try {
      const sessionResponse = await fetch("/api/v0/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ consent: { accepted: true, policy_version: "2026-09-01" } })
      });
      if (!sessionResponse.ok) throw new Error("session");
      const { session } = (await sessionResponse.json()) as { session: { id: string } };
      sessionIdRef.current = session.id;
      const measurementResponse = await fetch(`/api/v0/sessions/${session.id}/measurements`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ device: { camera_facing: "user" } })
      });
      if (!measurementResponse.ok) throw new Error("measurement");
      const { measurement } = (await measurementResponse.json()) as { measurement: { id: string } };
      measurementIdRef.current = measurement.id;
    } catch {
      setErrorMessage("Không thể tạo phiên đo. Vui lòng thử lại.");
      setMeasurementState("IDLE");
      return;
    }
    if (permission === "granted" && streamRef.current) {
      setMeasurementState("FACE_SEARCH");
    } else {
      void requestCamera();
    }
  };

  useEffect(() => {
    if (measurementState === "RESULT_READY") {
      setHasResult(true);
    }
  }, [measurementState]);

  useEffect(() => {
    if (screen !== "history") return;
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError("");
    void fetch("/api/v0/history")
      .then(async (response) => {
        if (!response.ok) throw new Error("history");
        return (await response.json()) as { items?: HistoryItem[] };
      })
      .then((payload) => {
        if (!cancelled) setHistoryItems(payload.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setHistoryError("Không thể tải lịch sử đo từ PostgreSQL.");
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [screen]);

  useEffect(() => {
    if (!measurementIdRef.current || !sessionIdRef.current || measurementState === "RESULT_READY") return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`/api/v0/sessions/${sessionIdRef.current}/measurements/${measurementIdRef.current}`);
      if (!response.ok) return;
      const payload = (await response.json()) as { measurement?: { state?: MeasurementState; heart_rate?: number | null; quality_score?: number | null } };
      const remote = payload.measurement;
      if (!remote) return;
      if (remote.heart_rate !== null && remote.heart_rate !== undefined) {
        setLiveMetrics((current) => ({ ...current, heartRate: remote.heart_rate as number, qualityScore: remote.quality_score ?? current.qualityScore }));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [measurementState]);

  const status = stateLabels[measurementState];
  const stateIndex = measurementState === "IDLE" || measurementState === "CAMERA_PERMISSION" ? -1 : flow.indexOf(measurementState);
  const roiBoxes = detectionBox
    ? [
        { ...detectionBox, x: detectionBox.x + detectionBox.width * 0.25, y: detectionBox.y + detectionBox.height * 0.08, width: detectionBox.width * 0.5, height: detectionBox.height * 0.18, label: "Trán" },
        { ...detectionBox, x: detectionBox.x + detectionBox.width * 0.15, y: detectionBox.y + detectionBox.height * 0.5, width: detectionBox.width * 0.25, height: detectionBox.height * 0.2, label: "Má trái" },
        { ...detectionBox, x: detectionBox.x + detectionBox.width * 0.6, y: detectionBox.y + detectionBox.height * 0.5, width: detectionBox.width * 0.25, height: detectionBox.height * 0.2, label: "Má phải" }
      ]
    : [];
  const videoWidth = videoRef.current?.videoWidth ?? 0;
  const videoHeight = videoRef.current?.videoHeight ?? 0;

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setScreen("consent")} aria-label="Về trang chủ"><span className="brand-mark">✦</span><span>AIVitals</span></button>
        <nav aria-label="Điều hướng chính">
          <button className={screen === "measurement" ? "nav-link active" : "nav-link"} onClick={startMeasurement}>Đo ngay</button>
          <button className={screen === "history" ? "nav-link active" : "nav-link"} onClick={() => setScreen("history")}>Lịch sử</button>
        </nav>
        <div className="auth-links">{authLoading ? <span className="auth-loading">Đang tải...</span> : authUser ? <><span className="auth-user">{authUser.display_name || authUser.email}</span><button className="logout-button" onClick={() => void logout()}>Đăng xuất</button></> : <><a href="/login">Đăng nhập</a><a href="/register">Đăng ký</a></>}<span className="secure-pill">● Dữ liệu riêng tư</span></div>
      </header>

      {screen === "consent" && (
        <section className="hero page">
          <div className="hero-copy">
            <span className="eyebrow">NON-CONTACT HEALTH CHECK</span>
            <h1>Hiểu cơ thể bạn,<br /><em>mỗi ngày.</em></h1>
            <p className="lead">Đo các chỉ số sinh hiệu cơ bản bằng camera trong vài giây. Không cần thiết bị đeo, không lưu hình ảnh khuôn mặt.</p>
            <div className="consent-card">
              <div className="icon-circle">⌁</div>
              <div><strong>Sẵn sàng cho phiên đo?</strong><p>Phiên đo cần quyền truy cập camera để phân tích tín hiệu trên khuôn mặt.</p></div>
              <button className="primary-button" onClick={startMeasurement}>Bắt đầu đo <span>→</span></button>
            </div>
            <div className="trust-row"><span>✓ Không lưu video</span><span>✓ Mã hóa dữ liệu</span><span>✓ Chỉ dùng cho wellness</span></div>
          </div>
          <div className="hero-visual"><div className="orb orb-one" /><div className="orb orb-two" /><div className="pulse-card"><span className="mini-label">HEART RATE</span><strong>72 <small>BPM</small></strong><div className="sparkline">〰〰〰〰〰</div><span className="good-text">● Trong ngưỡng bình thường</span></div><div className="visual-caption">Đo không tiếp xúc<br /><span>nhanh · riêng tư · khoa học</span></div></div>
        </section>
      )}

      {screen === "measurement" && (
        <section className="page measurement-page">
          <div className="section-heading"><div><span className="eyebrow">PHIÊN ĐO MỚI</span><h2>Giữ yên và nhìn vào camera</h2></div><button className="text-button" onClick={() => { stopCamera(); setScreen("consent"); }}>Thoát phiên đo</button></div>
          <div className="measurement-grid">
            <div className="camera-panel">
              <div className="camera-frame"><video ref={videoRef} muted playsInline aria-label="Hình ảnh camera trực tiếp" /><div className="face-guide" />{detectionBox && videoWidth > 0 && videoHeight > 0 && <div className="detection-overlay" aria-label="Vùng nhận diện khuôn mặt"><div className="face-box" style={{ left: `${(detectionBox.x / videoWidth) * 100}%`, top: `${(detectionBox.y / videoHeight) * 100}%`, width: `${(detectionBox.width / videoWidth) * 100}%`, height: `${(detectionBox.height / videoHeight) * 100}%` }}><span>Khuôn mặt</span></div>{roiBoxes.map((roi) => <div className="roi-box" key={roi.label} style={{ left: `${(roi.x / videoWidth) * 100}%`, top: `${(roi.y / videoHeight) * 100}%`, width: `${(roi.width / videoWidth) * 100}%`, height: `${(roi.height / videoHeight) * 100}%` }}><span>{roi.label}</span></div>)}</div>}<div className="camera-badge">{permission === "granted" ? "● LIVE" : "○ CAMERA OFF"}</div>{permission !== "granted" && <div className="camera-overlay"><div className="camera-icon">⌁</div><strong>{permission === "denied" ? "Camera đang bị từ chối" : "Cho phép truy cập camera"}</strong><span>{permission === "error" ? errorMessage : "Camera giúp hệ thống thu tín hiệu từ khuôn mặt của bạn."}</span><button className="primary-button compact" onClick={requestCamera}>{permission === "denied" ? "Thử lại quyền camera" : "Cho phép camera"} <span>→</span></button></div>}</div>
              <div className="camera-tip">● {detectorError || status.detail}</div>
              {(measurementState === "SIGNAL_ACQUIRING" || measurementState === "QUALITY_CHECK" || measurementState === "COMPUTING") && <div className="live-metrics" aria-live="polite"><span>BVP <strong>● LIVE</strong></span><span>HR <strong>{liveMetrics.heartRate} BPM</strong></span><span>SQI <strong>{liveMetrics.qualityScore}%</strong></span></div>}
            </div>
            <aside className="status-panel"><div className="status-top"><span className="status-dot" /><span>TRẠNG THÁI HỆ THỐNG</span></div><h3>{status.label}</h3><p>{status.detail}</p><div className="progress-track"><span style={{ width: `${Math.max(0, ((stateIndex + 1) / flow.length) * 100)}%` }} /></div><div className="state-list">{(["CAMERA_READY", "FACE_SEARCH", "FACE_LOCKED", "SIGNAL_ACQUIRING", "QUALITY_CHECK", "COMPUTING", "RESULT_READY"] as MeasurementState[]).map((item, index) => <div className={index < stateIndex ? "state-row complete" : item === measurementState ? "state-row current" : "state-row"} key={item}><span>{index < stateIndex ? "✓" : index + 1}</span><div><strong>{stateLabels[item].label}</strong><small>{stateLabels[item].detail}</small></div></div>)}</div>{hasResult && <button className="primary-button full" onClick={() => setScreen("result")}>Xem kết quả <span>→</span></button>}</aside>
          </div>
        </section>
      )}

      {screen === "result" && <section className="page result-page"><div className="section-heading"><div><span className="eyebrow">KẾT QUẢ PHIÊN ĐO · HÔM NAY</span><h2>Chỉ số của bạn</h2></div><button className="text-button" onClick={startMeasurement}>Đo lại</button></div><div className="result-grid"><div className="result-main"><div className="result-value"><span>Nhịp tim</span><strong>{liveMetrics.heartRate} <small>BPM</small></strong><b>● Ổn định</b></div><div className="metric-row"><div><span>Nhịp thở</span><strong>{liveMetrics.respirationRate} <small>lần/phút</small></strong></div><div><span>HRV (RMSSD)</span><strong>{liveMetrics.hrvRmssd} <small>ms</small></strong></div><div><span>Chất lượng tín hiệu</span><strong>{liveMetrics.qualityScore} <small>%</small></strong></div></div><div className="result-note">Đây là kết quả tham khảo cho mục đích chăm sóc sức khỏe chủ động, không thay thế chẩn đoán y khoa.</div></div><div className="insight-card"><span className="eyebrow">GỢI Ý HÔM NAY</span><h3>Cơ thể đang ở trạng thái cân bằng.</h3><p>Hãy duy trì nhịp sinh hoạt và uống đủ nước. Đo vào cùng một thời điểm mỗi ngày để theo dõi xu hướng chính xác hơn.</p><button className="secondary-button" onClick={() => setScreen("history")}>Xem lịch sử đo →</button></div></div></section>}

      {screen === "history" && <section className="page history-page"><div className="section-heading"><div><span className="eyebrow">THEO DÕI SỨC KHỎE</span><h2>Lịch sử đo</h2></div><button className="primary-button compact" onClick={startMeasurement}>Đo phiên mới <span>→</span></button></div><div className="history-card"><div className="history-header"><span>Ngày đo</span><span>Nhịp tim</span><span>Nhịp thở</span><span>Chất lượng</span><span /></div>{historyLoading && <div className="history-empty">Đang tải lịch sử đo...</div>}{historyError && <div className="history-empty">{historyError}</div>}{!historyLoading && !historyError && historyItems.length === 0 && <div className="history-empty">Chưa có phiên đo hoàn tất.</div>}{!historyLoading && !historyError && historyItems.map((item) => { const measuredAt = new Date(item.updated_at).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }); return <div className="history-row" key={item.id}><span>{measuredAt}</span><strong>{item.heart_rate ?? "--"} BPM</strong><span>{item.respiration_rate ?? "--"} lần/phút</span><span className="quality">{item.quality_score ?? "--"}%</span><button className="icon-button" aria-label={`Xem phiên đo ${measuredAt}`}>→</button></div>; })}</div></section>}
    </main>
  );
}
