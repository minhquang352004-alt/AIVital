/**
 * AIVitals API Contract V0
 *
 * This file is the frontend source of truth for request/response shapes.
 * It intentionally contains no backend implementation.
 */

export const API_CONTRACT_VERSION = "v0";

export type SessionStatus = "CREATED" | "ACTIVE" | "COMPLETED" | "CANCELLED" | "EXPIRED";
export type MeasurementStatus = "CREATED" | "RUNNING" | "STOPPED" | "COMPLETED" | "FAILED";
export type MeasurementState =
  | "IDLE"
  | "CAMERA_PERMISSION"
  | "CAMERA_READY"
  | "FACE_SEARCH"
  | "FACE_LOCKED"
  | "SIGNAL_ACQUIRING"
  | "QUALITY_CHECK"
  | "COMPUTING"
  | "RESULT_READY";
export type ResultQuality = "GOOD" | "FAIR" | "POOR" | "REJECTED";

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, string | number | boolean | null>;
  request_id: string;
}

export interface ApiErrorResponse {
  error: ApiError;
}

export interface CreateSessionRequest {
  client_version?: string;
  timezone?: string;
  consent: {
    accepted: boolean;
    policy_version: string;
  };
}

export interface Session {
  id: string;
  status: SessionStatus;
  created_at: string;
  expires_at: string;
  client_version?: string;
  timezone?: string;
}

export interface CreateSessionResponse {
  session: Session;
}

export interface StartMeasurementRequest {
  device: {
    user_agent?: string;
    platform?: string;
    camera_facing: "user" | "environment";
  };
  capture: {
    fps?: number;
    width?: number;
    height?: number;
  };
}

export interface Measurement {
  id: string;
  session_id: string;
  status: MeasurementStatus;
  state: MeasurementState;
  started_at: string;
  stopped_at?: string;
  completed_at?: string;
}

export interface StartMeasurementResponse {
  measurement: Measurement;
}

export interface StopMeasurementRequest {
  reason?: "USER_STOPPED" | "CAMERA_ERROR" | "QUALITY_REJECTED" | "TIMEOUT";
}

export interface StopMeasurementResponse {
  measurement: Measurement;
}

export interface VitalMetric {
  value: number;
  unit: "bpm" | "ms" | "breaths_per_minute" | "percent";
  confidence?: number;
}

export interface MeasurementResult {
  measurement_id: string;
  status: "PENDING" | "READY" | "REJECTED";
  quality: ResultQuality;
  quality_score?: number;
  measured_at: string;
  metrics?: {
    heart_rate?: VitalMetric;
    hrv_rmssd?: VitalMetric;
    respiration_rate?: VitalMetric;
  };
  algorithm_version?: string;
  disclaimer: string;
}

export interface GetResultResponse {
  result: MeasurementResult;
}

export interface HistoryItem {
  measurement_id: string;
  measured_at: string;
  status: MeasurementResult["status"];
  quality: ResultQuality;
  heart_rate?: VitalMetric;
  hrv_rmssd?: VitalMetric;
  respiration_rate?: VitalMetric;
}

export interface HistoryResponse {
  items: HistoryItem[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
}

export interface HistoryQuery {
  page?: number;
  page_size?: number;
  from?: string;
  to?: string;
}
