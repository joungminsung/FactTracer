const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const publicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const serverApiBaseUrl = process.env.FACTTRACER_API_BASE_URL || publicApiBaseUrl;

export const API_BASE_URL = trimTrailingSlash(
  typeof window === "undefined" ? serverApiBaseUrl : publicApiBaseUrl,
);

export const API_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_API_TIMEOUT_MS || 15000,
);

export function isApiConfigured() {
  return API_BASE_URL.length > 0;
}

export function createApiNotConfiguredError() {
  return new Error("현재 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.");
}

export function buildApiUrl(
  path: string,
  searchParams?: Record<string, boolean | number | string | null | undefined>,
) {
  if (!isApiConfigured()) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${API_BASE_URL}${normalizedPath}`);

  Object.entries(searchParams ?? {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return;
    url.searchParams.set(key, String(value));
  });

  return url.toString();
}
