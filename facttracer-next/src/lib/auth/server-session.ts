import { cookies } from "next/headers";
import { AUTH_TOKEN_COOKIE } from "@/lib/auth/constants";

export async function getServerAccessToken() {
  const cookieStore = await cookies();
  return cookieStore.get(AUTH_TOKEN_COOKIE)?.value ?? null;
}
