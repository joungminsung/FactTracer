"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { PageIntro } from "@/components/common/design-system";
import { getUserActionMessage } from "@/lib/api/messages";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const { login, signup } = useAuth();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSignup = mode === "signup";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (isSignup) {
        await signup({ email, name, password });
      } else {
        await login({ email, password });
      }
      router.push("/account");
    } catch (authError) {
      setError(
        getUserActionMessage(authError, "인증 요청을 처리하지 못했습니다."),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 sm:py-8">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_420px]">
        <PageIntro
          eyebrow="계정별 FactTracer"
          title={
            isSignup
              ? "내 검증 요청과 제출 주장을 계정별로 관리합니다"
              : "저장한 이슈와 제출한 주장을 이어서 확인합니다"
          }
          description="로그인 이후 기사 검증 요청, 구조화된 주장 제출, 저장한 이슈, 관리자 권한 여부를 계정별로 확인할 수 있습니다."
        >
          <div className="mt-7 divide-y divide-gray-100 border-y border-gray-200">
            {[
              "계정별 저장 이슈와 검증 요청 이력",
              "주장 제출 시 작성자와 근거 링크 연결",
              "관리자·검토자 권한에 따른 운영 메뉴",
            ].map((item) => (
              <div key={item} className="flex items-center gap-3 py-4">
                <ShieldCheck
                  className="size-4 shrink-0 text-blue-600"
                  aria-hidden="true"
                />
                <span className="text-sm font-semibold text-gray-700">
                  {item}
                </span>
              </div>
            ))}
          </div>
        </PageIntro>

        <form
          onSubmit={handleSubmit}
          className="border border-gray-300 bg-white px-5 py-6 sm:px-6"
        >
          <h2 className="text-2xl font-bold text-gray-900">
            {isSignup ? "회원가입" : "로그인"}
          </h2>

          {isSignup ? (
            <label className="mt-6 block text-sm font-semibold text-gray-700">
              이름
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                className="mt-2 h-11 w-full rounded-md border border-gray-200 px-3 text-sm outline-none"
                placeholder="홍길동"
              />
            </label>
          ) : null}

          <label className="mt-5 block text-sm font-semibold text-gray-700">
            이메일
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="mt-2 h-11 w-full rounded-md border border-gray-200 px-3 text-sm outline-none"
              placeholder="you@example.com"
            />
          </label>

          <label className="mt-5 block text-sm font-semibold text-gray-700">
            비밀번호
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
              className="mt-2 h-11 w-full rounded-md border border-gray-200 px-3 text-sm outline-none"
              placeholder="8자 이상"
            />
          </label>

          {error ? (
            <p className="mt-4 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm font-semibold text-red-600">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-blue-600 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "처리 중" : isSignup ? "계정 만들기" : "로그인"}
            <ArrowRight className="size-4" aria-hidden="true" />
          </button>

          <p className="mt-5 text-sm text-gray-500">
            {isSignup ? "이미 계정이 있나요?" : "계정이 없나요?"}{" "}
            <Link
              href={isSignup ? "/login" : "/signup"}
              className="font-bold text-blue-600"
            >
              {isSignup ? "로그인" : "회원가입"}
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
