import "./globals.css";

import { cookies } from "next/headers";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { createServerComponentClient } from "@supabase/auth-helpers-nextjs";

import { Providers } from "../components/layout/Providers";
import { Database } from "../types/database";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Invoice Analyst",
  description: "Modern invoice intelligence platform",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const supabase = createServerComponentClient<Database>({ cookies });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers initialSession={session}>{children}</Providers>
      </body>
    </html>
  );
}
