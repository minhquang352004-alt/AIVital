import type {
  CreateSessionRequest,
  CreateSessionResponse,
  GetResultResponse,
  HistoryQuery,
  HistoryResponse,
  StartMeasurementRequest,
  StartMeasurementResponse,
  StopMeasurementRequest,
  StopMeasurementResponse
} from "./api-contract";

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;

  constructor(status: number, code: string, message: string, requestId: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export class AIVitalsApiClient {
  constructor(
    private readonly baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v0",
    private readonly fetcher: typeof fetch = fetch
  ) {}

  createSession(payload: CreateSessionRequest): Promise<CreateSessionResponse> {
    return this.request("/sessions", { method: "POST", body: payload });
  }

  startMeasurement(sessionId: string, payload: StartMeasurementRequest): Promise<StartMeasurementResponse> {
    return this.request(`/sessions/${encodeURIComponent(sessionId)}/measurements`, {
      method: "POST",
      body: payload
    });
  }

  stopMeasurement(
    sessionId: string,
    measurementId: string,
    payload: StopMeasurementRequest = {}
  ): Promise<StopMeasurementResponse> {
    return this.request(
      `/sessions/${encodeURIComponent(sessionId)}/measurements/${encodeURIComponent(measurementId)}/stop`,
      { method: "POST", body: payload }
    );
  }

  getResult(sessionId: string, measurementId: string): Promise<GetResultResponse> {
    return this.request(
      `/sessions/${encodeURIComponent(sessionId)}/measurements/${encodeURIComponent(measurementId)}/result`,
      { method: "GET" }
    );
  }

  getHistory(query: HistoryQuery = {}): Promise<HistoryResponse> {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) params.set(key, String(value));
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return this.request(`/history${suffix}`, { method: "GET" });
  }

  private async request<T>(path: string, options: { method: "GET" | "POST"; body?: unknown }): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method: options.method,
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined
    });

    if (response.ok) return (await response.json()) as T;

    let errorBody: { error?: { code?: string; message?: string; request_id?: string } } = {};
    try {
      errorBody = (await response.json()) as typeof errorBody;
    } catch {
      // Preserve the HTTP error when the server did not return JSON.
    }
    throw new ApiClientError(
      response.status,
      errorBody.error?.code ?? "UNKNOWN_ERROR",
      errorBody.error?.message ?? `API request failed with status ${response.status}`,
      errorBody.error?.request_id ?? "unknown"
    );
  }
}

export const apiClient = new AIVitalsApiClient();
