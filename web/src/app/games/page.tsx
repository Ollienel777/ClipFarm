"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Film, Clock, CheckCircle, AlertCircle, Loader } from "lucide-react";
import { RequireAuth } from "@/components/RequireAuth";
import { getGames, type Game } from "@/lib/api";

function GameStatusIcon({ status }: { status: Game["status"] }) {
  switch (status) {
    case "ready":
      return <CheckCircle size={14} className="text-green-400" />;
    case "processing":
      return <Loader size={14} className="text-blue-400 animate-spin" />;
    case "queued":
      return <Clock size={14} className="text-zinc-400" />;
    case "failed":
      return <AlertCircle size={14} className="text-red-400" />;
    default:
      return null;
  }
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

  // Poll for status updates every 10s if any game is processing/queued
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">My Games</h1>
        <Link
          href="/upload"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          + Upload game
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader size={24} className="animate-spin text-zinc-500" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-lg border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-400">
          <AlertCircle size={16} />
          {error}
        </div>
      ) : games.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 py-24 text-center">
          <Film size={40} className="mb-4 text-zinc-600" />
          <p className="text-zinc-400 font-medium">No games yet</p>
          <p className="mt-1 text-sm text-zinc-600">
            Upload your first game to start generating highlights.
          </p>
          <Link
            href="/upload"
            className="mt-4 rounded-lg bg-zinc-800 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-700 transition-colors"
          >
            Upload now
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {games.map((game) => (
            <Link
              key={game.id}
              href={`/games/${game.id}`}
              className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-4 hover:border-zinc-600 transition-colors"
            >
              <div>
                <h2 className="font-medium text-zinc-100">{game.title}</h2>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {new Date(game.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                  {game.clip_count != null && game.status === "ready" && (
                    <> · {game.clip_count} clips</>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <GameStatusIcon status={game.status} />
                <span className="text-xs text-zinc-500">
                  {STATUS_LABEL[game.status]}
                </span>
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
