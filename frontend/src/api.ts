// Appels aux API JSON de Pimmich (même origine : la session et la protection CSRF du navigateur suffisent).

export class ApiError extends Error {
  constructor(message: string, public status: number, public data: Record<string, unknown> = {}) {
    super(message);
  }
}

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { credentials: "same-origin", ...init });
  } catch {
    throw new ApiError("Erreur de communication avec le serveur.", 0);
  }
  if (response.status === 401 || (response.redirected && response.url.includes("/login"))) {
    window.location.href = "/login";
    throw new ApiError("Authentification requise.", 401);
  }
  const type = response.headers.get("Content-Type") || "";
  const data = type.includes("application/json") ? await response.json() : {};
  if (!response.ok || data.success === false) {
    throw new ApiError(String(data.message || response.statusText || "Erreur"), response.status, data);
  }
  return data as T;
}

export function get<T = Record<string, unknown>>(url: string): Promise<T> {
  return request<T>(url);
}

export function post<T = { success: boolean; message?: string }>(url: string, body?: unknown, method = "POST"): Promise<T> {
  return request<T>(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}
