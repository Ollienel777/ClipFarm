"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader } from "lucide-react";
import { createClient } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();

    // Supabase puts tokens in the URL hash after OAuth redirect.
    // The client library picks them up automatically via onAuthStateChange,
    // but we need to wait for the session to be established.
    supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
        router.replace("/games");
      }
    });

    // Fallback: if already signed in (hash already consumed)
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        router.replace("/games");
      }
    });
  }, [router]);

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="text-center">
        <Loader size={24} className="mx-auto mb-3 animate-spin text-blue-400" />
        <p className="text-sm text-zinc-400">Signing you in…</p>
      </div>
    </div>
  );
}
