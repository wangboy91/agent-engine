import type { PrincipalProfile } from "../config";

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

export function principalHeaders(p: PrincipalProfile): Record<string, string> {
  return {
    "X-Tenant-Id": p.tenantId,
    "X-Principal-Id": p.principalId,
    "X-Principal-Type": "user",
    "X-Workspace-Roles": p.workspaceRoles.join(","),
    "X-Group-Ids": p.groupIds.join(","),
  };
}

async function request<T>(
  path: string,
  principal: PrincipalProfile,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...principalHeaders(principal),
      ...(init?.headers || {}),
    },
  });
  if (res.status === 401) {
    throw new ApiError(401, "UNAUTHORIZED", "缺少 Principal，请重新登录");
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

export const api = {
  get: <T>(path: string, p: PrincipalProfile) => request<T>(path, p),
  post: <T>(path: string, p: PrincipalProfile, body?: unknown) =>
    request<T>(path, p, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  del: <T>(path: string, p: PrincipalProfile) =>
    request<T>(path, p, { method: "DELETE" }),
};
