"use client";

import type { AuthSession } from "@/lib/api/types";
import { AUTH_TOKEN_COOKIE } from "@/lib/auth/constants";

const SESSION_STORAGE_KEY = "facttracer.session.v1";

export function readStoredSession(): AuthSession | null {
  const rawSession = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!rawSession) return null;

  try {
    const session = JSON.parse(rawSession) as AuthSession;
    if (!process.env.NEXT_PUBLIC_API_BASE_URL) {
      clearStoredSession();
      return null;
    }
    return session;
  } catch {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

export function writeStoredSession(session: AuthSession) {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  document.cookie = `${AUTH_TOKEN_COOKIE}=${encodeURIComponent(
    session.accessToken,
  )}; path=/; max-age=86400; SameSite=Lax`;
}

export function clearStoredSession() {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  document.cookie = `${AUTH_TOKEN_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}
