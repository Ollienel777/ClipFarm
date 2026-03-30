"use client";

import Link from "next/link";
import { Upload, Film, LogOut } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/contexts/AuthContext";

export function Navbar() {
  const { user, loading, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-zinc-100">
          <Film size={20} className="text-blue-400" />
          ClipFarm
        </Link>

        <nav className="flex items-center gap-2">
          {loading ? (
            <div className="h-8 w-20 animate-pulse rounded bg-zinc-800" />
          ) : user ? (
            <>
              <Link
                href="/games"
                className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors px-3"
              >
                My Games
              </Link>
              <Link href="/upload">
                <Button size="sm">
                  <Upload size={14} />
                  Upload
                </Button>
              </Link>
              <button
                onClick={signOut}
                className="ml-2 flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                title={user.email ?? "Sign out"}
              >
                <span className="hidden sm:inline max-w-[120px] truncate text-xs text-zinc-500">
                  {user.email}
                </span>
                <LogOut size={14} />
              </button>
            </>
          ) : (
            <>
              <Link href="/login">
                <Button size="sm" variant="ghost">
                  Log in
                </Button>
              </Link>
              <Link href="/signup">
                <Button size="sm">Sign up</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
