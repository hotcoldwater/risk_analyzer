import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Risk Analyzer",
  description: "DART 기반 재무제표 이상징후 및 감사위험 탐지 서비스"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
