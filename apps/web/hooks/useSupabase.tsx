"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Session, SupabaseClient } from "@supabase/supabase-js";

import { createClient } from "../lib/supabaseClient";

interface SupabaseContextValue {
  supabase: SupabaseClient;
  session: Session | null;
  setSession: (session: Session | null) => void;
}

const SupabaseContext = createContext<SupabaseContextValue | undefined>(undefined);

export const SupabaseProvider = ({ children, initialSession }: { children: React.ReactNode; initialSession: Session | null; }) => {
  const [session, setSession] = useState<Session | null>(initialSession);
  const [supabase] = useState(() => createClient());

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => {
      data.subscription.unsubscribe();
    };
  }, [supabase]);

  const value = useMemo(() => ({ supabase, session, setSession }), [session, supabase]);

  return <SupabaseContext.Provider value={value}>{children}</SupabaseContext.Provider>;
};

export const useSupabase = () => {
  const context = useContext(SupabaseContext);
  if (!context) {
    throw new Error("useSupabase must be used inside SupabaseProvider");
  }
  return context;
};
