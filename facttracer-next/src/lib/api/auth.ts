import {
  createApiNotConfiguredError,
  isApiConfigured,
} from "@/lib/api/config";
import { apiFetch } from "@/lib/api/http";
import type {
  AuthSession,
  AuthUser,
  LoginRequest,
  MutationResponse,
  NotificationSettings,
  SignupRequest,
  UserDashboardResponse,
  UserNotificationsResponse,
  UserPreferencesUpdateRequest,
  UserProfileUpdateRequest,
} from "@/lib/api/types";

const defaultNotificationSettings: NotificationSettings = {
  dailyDigest: false,
  numberChanges: true,
  officialSourceChanges: true,
  preferredPerspective: "균형",
  reviewCompleted: true,
  timelineUpdates: true,
};

const emptyUserDashboard = (user: AuthUser): UserDashboardResponse => ({
  savedIssues: [],
  submittedClaims: [],
  user,
  verificationRequests: [],
});

const emptyUserNotifications: UserNotificationsResponse = {
  followedIssues: [],
  notifications: [],
  settings: defaultNotificationSettings,
};

export async function loginUser(payload: LoginRequest): Promise<AuthSession> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<AuthSession>("/v1/auth/login", {
    body: payload,
    method: "POST",
  });
}

export async function signupUser(payload: SignupRequest): Promise<AuthSession> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<AuthSession>("/v1/auth/signup", {
    body: payload,
    method: "POST",
  });
}

export async function fetchCurrentUser(token: string): Promise<AuthUser> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<AuthUser>("/v1/users/me", { token });
}

export async function fetchUserDashboard(
  token: string,
  user?: AuthUser | null,
): Promise<UserDashboardResponse> {
  if (!isApiConfigured()) {
    if (!user) throw createApiNotConfiguredError();
    return emptyUserDashboard(user);
  }

  return apiFetch<UserDashboardResponse>("/v1/users/me/dashboard", { token });
}

export async function updateCurrentUserProfile(
  payload: UserProfileUpdateRequest,
  token: string,
): Promise<AuthUser> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<AuthUser>("/v1/users/me", {
    body: payload,
    method: "PATCH",
    token,
  });
}

export async function fetchUserNotifications(
  token: string,
): Promise<UserNotificationsResponse> {
  if (!isApiConfigured()) return emptyUserNotifications;

  return apiFetch<UserNotificationsResponse>("/v1/users/me/notifications", {
    cache: "no-store",
    token,
  });
}

export async function updateUserPreferences(
  payload: UserPreferencesUpdateRequest,
  token: string,
): Promise<MutationResponse> {
  if (!isApiConfigured()) throw createApiNotConfiguredError();

  return apiFetch<MutationResponse>("/v1/users/me/preferences", {
    body: payload,
    method: "PATCH",
    token,
  });
}
