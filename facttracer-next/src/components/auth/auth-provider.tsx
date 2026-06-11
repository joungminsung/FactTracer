"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { fetchCurrentUser, loginUser, signupUser } from "@/lib/api/auth";
import type {
  AuthSession,
  AuthUser,
  LoginRequest,
  SignupRequest,
} from "@/lib/api/types";
import {
  clearStoredSession,
  readStoredSession,
  writeStoredSession,
} from "@/lib/auth/session-storage";

type AuthContextValue = {
  session: AuthSession | null;
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginRequest) => Promise<AuthSession>;
  signup: (payload: SignupRequest) => Promise<AuthSession>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    queueMicrotask(() => {
      if (!isMounted) return;
      setSession(readStoredSession());
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const persistSession = useCallback((nextSession: AuthSession) => {
    setSession(nextSession);
    writeStoredSession(nextSession);
  }, []);

  const login = useCallback(
    async (payload: LoginRequest) => {
      const nextSession = await loginUser(payload);
      persistSession(nextSession);
      return nextSession;
    },
    [persistSession],
  );

  const signup = useCallback(
    async (payload: SignupRequest) => {
      const nextSession = await signupUser(payload);
      persistSession(nextSession);
      return nextSession;
    },
    [persistSession],
  );

  const logout = useCallback(() => {
    setSession(null);
    clearStoredSession();
  }, []);

  const refreshUser = useCallback(async () => {
    if (!session?.accessToken) return;
    const user = await fetchCurrentUser(session.accessToken);
    persistSession({ ...session, user });
  }, [persistSession, session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      token: session?.accessToken ?? null,
      isAuthenticated: Boolean(session?.accessToken),
      isLoading,
      login,
      signup,
      logout,
      refreshUser,
    }),
    [isLoading, login, logout, refreshUser, session, signup],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
