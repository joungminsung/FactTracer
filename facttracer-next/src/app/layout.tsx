import type { Metadata, Viewport } from "next";
import { Suspense, type ReactNode } from "react";
import { AnalyticsTracker } from "@/components/analytics-tracker";
import { AuthProvider } from "@/components/auth/auth-provider";
import { MobileTabNav } from "@/components/mobile/mobile-tab-nav";
import { PodcastPlayerProvider } from "@/components/podcast/podcast-player-provider";
import { PwaRegistration } from "@/components/pwa-registration";
import "./globals.css";

export const metadata: Metadata = {
  applicationName: "FactTracer",
  title: "FactTracer",
  description: "사건 흐름, 쟁점, 근거, 의견 충돌을 한 번에 정리하는 보도 분석 플랫폼",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "FactTracer",
  },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <PodcastPlayerProvider>
            {children}
            <MobileTabNav />
            <Suspense fallback={null}>
              <AnalyticsTracker />
            </Suspense>
            <PwaRegistration />
          </PodcastPlayerProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
