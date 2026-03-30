"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader size={24} className="animate-spin text-zinc-500" />
      </div>
    );
  }

  if (!user) return null;

  return <>{children}</>;
}
