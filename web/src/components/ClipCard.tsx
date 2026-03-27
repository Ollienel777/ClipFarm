"use client";

import { useState } from "react";
import { Play, User } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { type Clip, type Player, tagClip } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ClipCardProps {
  clip: Clip;
  players: Player[];
  onPlay: (clip: Clip) => void;
}

export function ClipCard({ clip, players, onPlay }: ClipCardProps) {
  const [tagging, setTagging] = useState(false);
  const [localPlayerName, setLocalPlayerName] = useState(clip.player_name);

  async function handleTag(playerId: string) {
    setTagging(false);
    const updated = await tagClip(clip.id, playerId);
    setLocalPlayerName(updated.player_name);
  }

  const confidencePct = Math.round(clip.confidence * 100);

  return (
    <div className="group relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 hover:border-zinc-600 transition-colors">
      {/* Thumbnail */}
      <div
        className="relative aspect-video cursor-pointer bg-zinc-950"
        onClick={() => onPlay(clip)}
      >
        {clip.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={clip.thumbnail_url}
            alt={`${clip.action_type} clip thumbnail`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-zinc-700">
            <Play size={32} />
          </div>
        )}

        {/* Play overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="rounded-full bg-white/20 p-3 backdrop-blur-sm">
            <Play size={24} className="text-white fill-white" />
          </div>
        </div>

        {/* Duration badge */}
        <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
          {formatDuration(clip.end_time - clip.start_time)}
        </span>
      </div>

      {/* Info */}
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            <Badge label={clip.action_type} action={clip.action_type} />
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                confidencePct >= 80
                  ? "text-green-400"
                  : confidencePct >= 60
                  ? "text-yellow-400"
                  : "text-zinc-500"
              )}
            >
              {confidencePct}%
            </span>
          </div>

          {/* Player tag */}
          <div className="relative shrink-0">
            {tagging ? (
              <select
                autoFocus
                className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-100 focus:outline-none"
                onBlur={() => setTagging(false)}
                onChange={(e) => handleTag(e.target.value)}
                defaultValue=""
              >
                <option value="" disabled>
                  Select player
                </option>
                {players.map((p) => (
                  <option key={p.id} value={p.id}>
                    #{p.jersey_number} {p.name}
                  </option>
                ))}
              </select>
            ) : (
              <button
                onClick={() => setTagging(true)}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
              >
                <User size={12} />
                {localPlayerName ?? "Tag player"}
              </button>
            )}
          </div>
        </div>

        <p className="mt-1.5 text-xs text-zinc-500">
          {formatTimestamp(clip.start_time)}
        </p>
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
}
