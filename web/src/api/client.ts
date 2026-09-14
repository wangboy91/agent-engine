import type { PrincipalProfile } from "../config";

const TOKEN_KEY = "ae_access_token";
const PRINCIPAL_KEY = "ae_principal";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function saveSession(token: string, principal: Record<string, unknown>) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(PRINCIPAL_KEY, JSON.stringify(principal));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(PRINCIPAL_KEY);
}

export function loadToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function loadStoredPrincipal(): Record<string, unknown> | null {
  const raw = localStorage.getItem(PRINCIPAL_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Header principal fallback for dev role switcher (no login). */
export function principalHeaders(p: PrincipalProfile): Record<string, string> {
  return {
    "X-Tenant-Id": p.tenantId,
    "X-Principal-Id": p.principalId,
    "X-Principal-Type": "user",
    "X-Workspace-Roles": p.workspaceRoles.join(","),
    "X-Group-Ids": p.groupIds.join(","),
  };
}

function authHeaders(p?: PrincipalProfile): Record<string, string> {
  const token = loadToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  if (p) return principalHeaders(p);
  return {};
}

async function request<T>(
  path: string,
  principal: PrincipalProfile | undefined,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...authHeaders(principal),
      ...(init?.headers || {}),
    },
  });
  if (res.status === 401) {
    clearSession();
    throw new ApiError(401, "UNAUTHORIZED", "未登录或会话已过期");
  }
  if (res.status === 404) {
    throw new ApiError(404, "NOT_FOUND", "资源不存在或无权访问");
  }
  if (res.status === 403) {
    throw new ApiError(403, "FORBIDDEN", "没有权限执行该操作");
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : String(detail);
    throw new ApiError(res.status, "HTTP_ERROR", message || res.statusText);
  }
  return (await res.json()) as T;
}

/** Account service (login / users). Paths are proxied under /account. */
export const accountApi = {
  login: (username: string, password: string) =>
    request<{
      access_token: string;
      principal: Record<string, unknown>;
      profile: Record<string, unknown>;
    }>("/account/auth/login", undefined, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () =>
    request<Record<string, unknown>>("/account/auth/me", undefined, {}),
};

/** Agent engine API. */
export const api = {
  get: <T>(path: string, p: PrincipalProfile) => request<T>(path, p),
  post: <T>(path: string, p: PrincipalProfile, body?: unknown) =>
    request<T>(path, p, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};
