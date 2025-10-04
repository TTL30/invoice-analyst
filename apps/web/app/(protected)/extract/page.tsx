import { cookies } from "next/headers";
import { createServerComponentClient } from "@supabase/auth-helpers-nextjs";

import { ExtractionWorkspace } from "../../../components/extraction/ExtractionWorkspace";
import { Database } from "../../../types/database";

export default async function ExtractPage() {
  const supabase = createServerComponentClient<Database>({ cookies });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const userId = session?.user.id;

  const [categoriesData, marquesData, fournisseursData] = await Promise.all([
    userId
      ? supabase
          .from("categories")
          .select("nom")
          .eq("user_id", userId)
          .order("nom")
      : Promise.resolve({ data: [] as { nom: string }[] }),
    userId
      ? supabase
          .from("marques")
          .select("nom")
          .eq("user_id", userId)
          .order("nom")
      : Promise.resolve({ data: [] as { nom: string }[] }),
    userId
      ? supabase
          .from("fournisseurs")
          .select("nom")
          .eq("user_id", userId)
          .order("nom")
      : Promise.resolve({ data: [] as { nom: string }[] }),
  ]);

  return (
    <ExtractionWorkspace
      categories={(categoriesData.data ?? []).map((item) => item.nom)}
      marques={(marquesData.data ?? []).map((item) => item.nom)}
      fournisseurs={(fournisseursData.data ?? []).map((item) => item.nom)}
    />
  );
}
