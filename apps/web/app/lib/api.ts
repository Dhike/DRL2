export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "drl2_access_token";

export type User = {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  email_verified_at: string | null;
  created_at: string;
};

export type InstrumentInfo = { symbol: string; market: string };

export type Catalog = {
  provider: string;
  instruments: InstrumentInfo[];
  timeframes: string[];
};

export type CandleData = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
};

export type CandlesResponse = {
  provider: string;
  symbol: string;
  timeframe: string;
  candles: CandleData[];
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: nothing to clear */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (res.status === 422) {
        message = "Please check the details you entered and try again.";
      }
    } catch {
      /* response had no JSON body: keep the default message */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export function register(email: string, password: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<void> {
  const result = await request<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(result.access_token);
}

export async function verifyEmail(email: string, code: string): Promise<void> {
  const result = await request<{ access_token: string }>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
  setToken(result.access_token);
}

export async function resendCode(email: string): Promise<void> {
  await request<{ detail: string }>("/auth/resend-code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function forgotPassword(email: string): Promise<void> {
  await request<{ detail: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  email: string,
  code: string,
  newPassword: string,
): Promise<void> {
  await request<{ detail: string }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ email, code, new_password: newPassword }),
  });
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const result = await request<{ access_token: string }>(
    "/auth/change-password",
    {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    },
  );
  setToken(result.access_token);
}

export function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

export function getCatalog(): Promise<Catalog> {
  return request<Catalog>("/market/instruments");
}

export function getCandles(
  symbol: string,
  timeframe: string,
  limit = 300,
): Promise<CandlesResponse> {
  const query = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
  return request<CandlesResponse>(`/market/candles?${query.toString()}`);
}

export type ScannerSignal = {
  market: string;
  symbol: string;
  timeframe: string;
  strategy: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number | null;
  score: number;
  reason: string;
  structure_scope: string;
};

export type ScannerScanResult = {
  status: string;
  signals: ScannerSignal[];
};

export function scanMarket(
  symbol: string,
  timeframe: string,
  strategies: string[],
  scope?: string,
): Promise<ScannerScanResult> {
  return request<ScannerScanResult>("/scanner/scan", {
    method: "POST",
    body: JSON.stringify({
      symbol,
      timeframe,
      strategies,
      scope: scope ?? null,
    }),
  });
}

export type ScannerTransition = {
  previous_state: string;
  reason: string;
  new_state: string;
};

export type ScannerLiveState = {
  symbol: string;
  timeframe: string;
  strategy: string;
  state: string;
  history: ScannerTransition[];
};

export async function getLiveState(
  symbol: string,
  timeframe: string,
  strategy: string,
): Promise<ScannerLiveState | null> {
  const query = new URLSearchParams({ symbol, timeframe, strategy });
  try {
    return await request<ScannerLiveState>(`/scanner/live?${query.toString()}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
