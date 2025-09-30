"use client";

import { usePathname } from "next/navigation";

const titles: Record<string, string> = {
  "/extract": "Extraction assistée",
  "/dashboard": "Tableau de bord",
  "/gestion": "Gestion des données",
};

export const TopBar = () => {
  const pathname = usePathname();
  const title = Object.entries(titles).find(([key]) => pathname.startsWith(key))?.[1] ?? "Invoice Analyst";

  return (
    <section className="border-b border-slate-100 px-8 py-6">
      <h1 className="text-2xl font-semibold text-slate-800">{title}</h1>
      <p className="text-sm text-slate-500">Gardez une vision claire de vos achats.</p>
    </section>
  );
};
