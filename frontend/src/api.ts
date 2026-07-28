const TOKEN_KEY = "affairs_os_token";
const USER_KEY = "affairs_os_user";

export class ApiError extends Error {
  errors: Record<string, unknown>;

  constructor(message: string, errors: Record<string, unknown> = {}) {
    super(message);
    this.errors = errors;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSession(token: string, user: unknown) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated && getToken()) {
    headers.set("Authorization", `Token ${getToken()}`);
  }

  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401 && authenticated) {
      clearSession();
      window.dispatchEvent(new CustomEvent("session-expired"));
    }
    throw new ApiError(
      payload.message || "操作未完成，请稍后重试。",
      payload.errors || {},
    );
  }
  return payload as T;
}

export async function download(
  path: string,
  options: RequestInit = {},
  fallbackFilename = "download.xlsx",
): Promise<void> {
  const headers = new Headers(options.headers);
  if (getToken()) {
    headers.set("Authorization", `Token ${getToken()}`);
  }

  const response = await fetch(`/api/v1${path}`, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401) {
      clearSession();
      window.dispatchEvent(new CustomEvent("session-expired"));
    }
    throw new Error("下载失败");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;

  const contentDisposition = response.headers.get("Content-Disposition");
  let filename = fallbackFilename;
  if (contentDisposition) {
    const encodedMatch = contentDisposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
    const plainMatch = contentDisposition.match(/filename\s*=\s*"([^"]+)"/i)
      || contentDisposition.match(/filename\s*=\s*([^;\s]+)/i);
    if (encodedMatch?.[1]) {
      try { filename = decodeURIComponent(encodedMatch[1].trim().replace(/^"|"$/g, "")); }
      catch { filename = fallbackFilename; }
    } else if (plainMatch?.[1]) {
      filename = plainMatch[1].trim();
    }
  }

  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
