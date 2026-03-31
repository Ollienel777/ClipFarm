"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Volleyball } from "@/components/ui/Volleyball";
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
      <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
        <AlertCircle size={16} /> {error}
      </div>
    );
  }

  if (!game || loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Volleyball size={28} />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/games"
          className="mb-4 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-foreground transition-colors"
        >
          <ArrowLeft size={12} />
          Back to games
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-foreground">{game.title}</h1>
            <p className="mt-1 text-sm text-muted">
              {game.clip_count ?? clips.length} clips
            </p>
          </div>
          <GameStatusBadge status={game.status} />
        </div>
      </div>

      {/* Processing state */}
      {(game.status === "queued" || game.status === "processing") && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-border bg-surface py-20 text-center">
          <div className="mb-5">
            <Volleyball size={36} />
          </div>
          <p className="font-medium text-foreground">
            {game.status === "queued" ? "Queued for processing" : "Analyzing your footage"}
          </p>
          <p className="mt-1.5 text-sm text-muted max-w-xs">
            Detecting actions and generating clips. You can leave this page.
          </p>
        </div>
      )}

      {game.status === "ready" && (
        <>
          {/* Filters */}
          <div className="mb-6 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3">
            <span className="text-xs font-medium text-muted mr-1">Filter</span>
            {ACTION_TYPES.map((action) => {
              const active = !filters.action_type?.length || filters.action_type.includes(action);
              return (
                <button
                  key={action}
                  onClick={() => toggleActionFilter(action)}
                  className={`transition-all duration-150 ${active ? "opacity-100 scale-100" : "opacity-30 scale-95"}`}
                >
                  <Badge label={action} action={action} />
                </button>
              );
            })}
            <div className="ml-auto flex items-center gap-3 text-xs text-muted">
              <span>Confidence</span>
              <input
                type="range"
                min={0}
                max={100}
                value={(filters.min_confidence ?? 0) * 100}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, min_confidence: Number(e.target.value) / 100 }))
                }
                className="w-20"
              />
              <span className="tabular-nums w-7 text-right">{Math.round((filters.min_confidence ?? 0) * 100)}%</span>
            </div>
          </div>

          {/* Clip grid */}
          {clips.length === 0 ? (
            <p className="py-20 text-center text-sm text-muted">No clips match your filters.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {clips.map((clip, i) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  players={players}
                  onPlay={() => setActiveClipIndex(i)}
                  onUpdate={(updated) =>
                    setClips((prev) =>
                      prev.map((c) => (c.id === updated.id ? updated : c))
                    )
                  }
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
    queued: { label: "Queued", className: "bg-zinc-800 text-zinc-400" },
    processing: { label: "Processing", className: "bg-blue-500/10 text-blue-400" },
    ready: { label: "Ready", className: "bg-emerald-500/10 text-emerald-400" },
    failed: { label: "Failed", className: "bg-red-500/10 text-red-400" },
  };
  const { label, className } = map[status];
  return (
    <span className={`rounded-lg px-2.5 py-1 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}
