"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSupabase } from "../../hooks/useSupabase";

const navLinks = [
  { href: "/extract", label: "💾 Extraction", icon: "💾" },
  { href: "/dashboard", label: "📊 Dashboard", icon: "📊" },
  { href: "/gestion", label: "📁 Gestion", icon: "📁" },
];

export const Sidebar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { session, supabase } = useSupabase();

  const logout = async () => {
    await supabase.auth.signOut();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-gray-200 bg-white">
      <div className="flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-6">
          <span className="text-lg font-medium text-gray-900">AYO Boulangerie</span>
          <nav className="flex items-center gap-2">
            {navLinks.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-teal-600 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {item.icon} {item.label.replace(/[^\w\s]/gi, '').trim()}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600">{session?.user.email}</span>
          <button
            onClick={logout}
            className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800"
          >
            Déconnexion
          </button>
        </div>
      </div>
    </header>
  );
};
