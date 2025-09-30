import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createServerComponentClient } from "@supabase/auth-helpers-nextjs";

import { LoginForm } from "../../../components/forms/LoginForm";
import { Database } from "../../../types/database";

export default async function LoginPage() {
  const supabase = createServerComponentClient<Database>({ cookies });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (session) {
    redirect("/extract");
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <h1 className="text-3xl font-bold text-gray-900">InvoSight</h1>
          <p className="mt-3 text-sm text-gray-600">
            Analysez, structurez et gérez vos factures grâce à une interface moderne propulsée par l&apos;IA.
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
