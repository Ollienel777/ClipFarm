"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { Loader, AlertCircle } from "lucide-react";
import { ClipCard } from "@/components/ClipCard";
import { ClipModal } from "@/components/ClipModal";
import { Badge } from "@/components/ui/Badge";
import { getGame, getClips, getPlayers, type Game, type Clip, type Player, type ActionType, type ClipFilters } from "@/lib/api";

const ACTION_TYPES: ActionType[] = ["spike", "serve", "dig", "set", "block"];

export default function GamePage() {
  const { id } = useParams<{ id: string }>();
  const [game, setGame] = useState<Game | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeClipIndex, setActiveClipIndex] = useState<number | null>(null);
  const [filters, setFilters] = useState<ClipFilters>({ min_confidence: 0 });

  // Poll for status while processing
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    async function fetchGame() {
      try {
        const g = await getGame(id);
        setGame(g);
        if (g.status === "processing" || g.status === "queued") {
          interval = setInterval(async () => {
            const updated = await getGame(id);
            setGame(updated);
            if (updated.status === "ready" || updated.status === "failed") {
              if (interval) clearInterval(interval);
            }
          }, 5000);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load game.");
      }
    }

    fetchGame();
    return () => { if (interval) clearInterval(interval); };
  }, [id]);

  useEffect(() => {
    if (!game || game.status !== "ready") return;
    Promise.all([getClips(id, filters), getPlayers()])
      .then(([c, p]) => { setClips(c); setPlayers(p); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [game, id, filters]);

  const toggleActionFilter = useCallback((action: ActionType) => {
    setFilters((f) => {
      const current = f.action_type ?? [];
      return {
        ...f,
        action_type: current.includes(action)
          ? current.filter((a) => a !== action)
          : [...current, action],
      };
    });
  }, []);

  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-400">
        <AlertCircle size={16} /> {error}
      </div>
    );
  }

  if (!game || loading) {
    return (
      <div className="flex items-center gap-2 text-zinc-400">
        <Loader size={16} className="animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">{game.title}</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {game.clip_count ?? clips.length} clips
          </p>
        </div>
        <GameStatusBadge status={game.status} />
      </div>

      {/* Processing state */}
      {(game.status === "queued" || game.status === "processing") && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 py-16 text-center">
          <Loader size={32} className="mb-4 animate-spin text-blue-400" />
          <p className="font-medium text-zinc-200">
            {game.status === "queued" ? "Queued for processing…" : "Processing your footage…"}
          </p>
          <p className="mt-1 text-sm text-zinc-500">
            We&apos;ll have your highlights ready soon. You can leave this page.
          </p>
        </div>
      )}

      {game.status === "ready" && (
        <>
          {/* Filters */}
          <div className="mb-4 flex flex-wrap gap-2">
            {ACTION_TYPES.map((action) => (
              <button
                key={action}
                onClick={() => toggleActionFilter(action)}
                className="transition-opacity"
                style={{
                  opacity: !filters.action_type?.length || filters.action_type.includes(action) ? 1 : 0.4,
                }}
              >
                <Badge label={action} action={action} />
              </button>
            ))}
            <div className="ml-auto flex items-center gap-2 text-xs text-zinc-500">
              <label htmlFor="conf-slider">Min confidence</label>
              <input
                id="conf-slider"
                type="range"
                min={0}
                max={100}
                value={(filters.min_confidence ?? 0) * 100}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, min_confidence: Number(e.target.value) / 100 }))
                }
                className="w-24 accent-blue-500"
              />
              <span>{Math.round((filters.min_confidence ?? 0) * 100)}%</span>
            </div>
          </div>

          {/* Clip grid */}
          {clips.length === 0 ? (
            <p className="py-16 text-center text-zinc-500">No clips match your filters.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {clips.map((clip, i) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  players={players}
                  onPlay={() => setActiveClipIndex(i)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Modal */}
      {activeClipIndex !== null && clips[activeClipIndex] && (
        <ClipModal
          clip={clips[activeClipIndex]}
          onClose={() => setActiveClipIndex(null)}
          onPrev={activeClipIndex > 0 ? () => setActiveClipIndex((i) => i! - 1) : undefined}
          onNext={activeClipIndex < clips.length - 1 ? () => setActiveClipIndex((i) => i! + 1) : undefined}
        />
      )}
    </div>
  );
}

function GameStatusBadge({ status }: { status: Game["status"] }) {
  const map: Record<Game["status"], { label: string; className: string }> = {
    queued: { label: "Queued", className: "bg-zinc-700 text-zinc-300" },
    processing: { label: "Processing", className: "bg-blue-500/20 text-blue-400" },
    ready: { label: "Ready", className: "bg-green-500/20 text-green-400" },
    failed: { label: "Failed", className: "bg-red-500/20 text-red-400" },
  };
  const { label, className } = map[status];
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}
