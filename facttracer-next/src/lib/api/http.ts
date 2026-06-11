import { API_TIMEOUT_MS, buildApiUrl } from "@/lib/api/config";
import { getHttpStatusMessage } from "@/lib/api/messages";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

type ApiFetchOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  token?: string | null;
  searchParams?: Record<string, boolean | number | string | null | undefined>;
};

export async function apiFetch<T>(
  path: string,
  { body, headers, token, searchParams, ...init }: ApiFetchOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  const requestHeaders = new Headers(headers);
  const isFormData =
    typeof FormData !== "undefined" && body instanceof FormData;

  if (body !== undefined && !isFormData && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (!requestHeaders.has("Accept")) {
    requestHeaders.set("Accept", "application/json");
  }

  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  try {
    const response = await fetch(buildApiUrl(path, searchParams), {
      ...init,
      body:
        body === undefined || isFormData
          ? (body as BodyInit | undefined)
          : JSON.stringify(body),
      headers: requestHeaders,
      signal: controller.signal,
    });

    const contentType = response.headers.get("Content-Type") ?? "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      throw new ApiError(
        getHttpStatusMessage(response.status),
        response.status,
        payload,
      );
    }

    return payload as T;
  } finally {
    clearTimeout(timeoutId);
  }
}
