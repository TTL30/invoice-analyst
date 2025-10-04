import { createBrowserSupabaseClient } from "@supabase/auth-helpers-nextjs";

import { SUPABASE_ANON_KEY, SUPABASE_URL } from "./env";

export const createClient = () => {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error("Supabase environment variables are missing");
  }
  return createBrowserSupabaseClient({
    supabaseUrl: SUPABASE_URL,
    supabaseKey: SUPABASE_ANON_KEY,
  });
};
