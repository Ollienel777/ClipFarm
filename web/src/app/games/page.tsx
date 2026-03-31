"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Clock, CheckCircle, AlertCircle, ChevronRight, Plus } from "lucide-react";
import { Volleyball } from "@/components/ui/Volleyball";
import { RequireAuth } from "@/components/RequireAuth";
import { Button } from "@/components/ui/Button";
import { getGames, type Game } from "@/lib/api";

function GameStatusDot({ status }: { status: Game["status"] }) {
  const styles: Record<Game["status"], string> = {
    ready: "bg-emerald-400",
    processing: "bg-blue-400 animate-pulse",
    queued: "bg-zinc-500",
    failed: "bg-red-400",
  };
  return <span className={`inline-block h-2 w-2 rounded-full ${styles[status]}`} />;
}

const STATUS_LABEL: Record<Game["status"], string> = {
  queued: "Queued",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

function GamesContent() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGames()
      .then(setGames)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const hasActive = games.some((g) => g.status === "processing" || g.status === "queued");
    if (!hasActive) return;

    const interval = setInterval(() => {
      getGames().then(setGames).catch(() => {});
    }, 10_000);
    return () => clearInterval(interval);
  }, [games]);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-bold text-foreground">My Games</h1>
          <p className="mt-1 text-sm text-muted">
            {games.length > 0
              ? `${games.length} game${games.length !== 1 ? "s" : ""} uploaded`
              : "Upload your first game to get started"}
          </p>
        </div>
        <Link href="/upload">
          <Button size="sm">
            <Plus size={14} />
            New game
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Volleyball size={28} />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
          <AlertCircle size={16} />
          {error}
        </div>
      ) : games.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-24 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-light">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted">
              <path d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-foreground">No games yet</p>
          <p className="mt-1 text-sm text-muted">
            Upload game footage to start generating highlights.
          </p>
          <Link href="/upload" className="mt-5">
            <Button size="sm">Upload now</Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {games.map((game) => (
            <Link
              key={game.id}
              href={`/games/${game.id}`}
              className="group flex items-center justify-between rounded-xl border border-border bg-surface px-5 py-4 transition-all hover:border-border-light hover:bg-surface-light"
            >
              <div className="min-w-0">
                <h2 className="font-medium text-foreground truncate">{game.title}</h2>
                <div className="mt-1 flex items-center gap-3 text-xs text-muted">
                  <span>
                    {new Date(game.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </span>
                  {game.clip_count != null && game.status === "ready" && (
                    <span>{game.clip_count} clips</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <GameStatusDot status={game.status} />
                  <span className="text-xs text-muted">{STATUS_LABEL[game.status]}</span>
                </div>
                <ChevronRight size={16} className="text-zinc-600 group-hover:text-muted transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function GamesPage() {
  return (
    <RequireAuth>
      <GamesContent />
    </RequireAuth>
  );
}
