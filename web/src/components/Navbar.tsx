"use client";

import Link from "next/link";
import { Upload, LogOut, Zap } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/contexts/AuthContext";

export function Navbar() {
  const { user, loading, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-border/50 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10 group-hover:bg-brand/20 transition-colors">
            <Zap size={16} className="text-brand" />
          </div>
          <span className="text-base font-bold tracking-tight text-foreground">
            Clip<span className="text-brand">Farm</span>
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {loading ? (
            <div className="h-8 w-24 shimmer rounded-lg" />
          ) : user ? (
            <>
              <Link
                href="/games"
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted hover:text-foreground hover:bg-surface-light transition-colors"
              >
                My Games
              </Link>
              <Link href="/upload">
                <Button size="sm">
                  <Upload size={14} />
                  Upload
                </Button>
              </Link>
              <div className="ml-1 h-5 w-px bg-border" />
              <button
                onClick={signOut}
                className="ml-1 flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-muted hover:text-foreground hover:bg-surface-light transition-colors"
                title="Sign out"
              >
                <span className="hidden sm:inline max-w-[140px] truncate text-xs">
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
                <Button size="sm">Get started</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
