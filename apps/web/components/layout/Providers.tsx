"use client";

import { Session } from "@supabase/supabase-js";
import { Toaster } from "react-hot-toast";

import { SupabaseProvider } from "../../hooks/useSupabase";

interface ProvidersProps {
  children: React.ReactNode;
  initialSession: Session | null;
}

export const Providers = ({ children, initialSession }: ProvidersProps) => {
  return (
    <SupabaseProvider initialSession={initialSession}>
      <Toaster position="top-right" />
      {children}
    </SupabaseProvider>
  );
};
