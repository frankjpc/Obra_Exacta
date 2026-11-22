import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "ObraExacta | Control Determinista para Contratistas",
  description: "Cubicación 2D por voz, auditoría de facturas anti-fraude y libro de obra con Telegram + Gemini 2.5 Flash",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark h-full" suppressHydrationWarning>
      <body 
        className="min-h-full bg-[#070b12] text-zinc-100 antialiased font-sans"
        suppressHydrationWarning
      >
        <Suspense fallback={<div className="min-h-screen bg-[#070b12]" />}>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </Suspense>
      </body>
    </html>
  );
}
