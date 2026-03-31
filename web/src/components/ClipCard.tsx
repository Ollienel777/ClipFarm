"use client";

import { useState } from "react";
import { Play, User, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { type Clip, type Player, type ActionType, tagClip, fixClipAction } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACTION_OPTIONS: { value: string; label: string }[] = [
  { value: "spike", label: "Spike" },
  { value: "serve", label: "Serve" },
  { value: "dig", label: "Dig" },
  { value: "set", label: "Set" },
  { value: "block", label: "Block" },
  { value: "not_an_action", label: "Not an action" },
];

interface ClipCardProps {
  clip: Clip;
  players: Player[];
  onPlay: (clip: Clip) => void;
  onUpdate?: (clip: Clip) => void;
}

export function ClipCard({ clip, players, onPlay, onUpdate }: ClipCardProps) {
  const [tagging, setTagging] = useState(false);
  const [fixing, setFixing] = useState(false);
  const [localPlayerName, setLocalPlayerName] = useState(clip.player_name);
  const [localAction, setLocalAction] = useState(clip.action_type);
  const [localConfidence, setLocalConfidence] = useState(clip.confidence);

  async function handleTag(playerId: string) {
    setTagging(false);
    const updated = await tagClip(clip.id, playerId);
    setLocalPlayerName(updated.player_name);
  }

  async function handleFixAction(action: string) {
    setFixing(false);
    if (action === localAction) return;
    try {
      const updated = await fixClipAction(clip.id, action);
      setLocalAction(updated.action_type);
      setLocalConfidence(updated.confidence);
      onUpdate?.(updated);
    } catch (err) {
      console.error("Fix action failed:", err);
    }
  }

  const confidencePct = Math.round(localConfidence * 100);
  const isDiscarded = localAction === "unknown" && localConfidence === 0;

  return (
    <div className={cn(
      "group card-noise overflow-hidden rounded-xl border border-border bg-surface transition-all duration-200 hover:border-border-light hover:shadow-lg hover:shadow-black/20",
      isDiscarded && "opacity-40"
    )}>
      {/* Thumbnail */}
      <div
        className="relative aspect-video cursor-pointer bg-black overflow-hidden"
        onClick={() => onPlay(clip)}
      >
        {clip.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={clip.thumbnail_url}
            alt={`${localAction} clip thumbnail`}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full items-center justify-center bg-surface">
            <Play size={28} className="text-zinc-700" />
          </div>
        )}

        {/* Play overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/40 transition-all duration-200">
          <div className="scale-75 opacity-0 group-hover:scale-100 group-hover:opacity-100 transition-all duration-200 rounded-full bg-white/15 p-3 backdrop-blur-sm">
            <Play size={20} className="text-white fill-white" />
          </div>
        </div>

        {/* Duration */}
        <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-white tabular-nums backdrop-blur-sm">
          {formatDuration(clip.end_time - clip.start_time)}
        </span>

        {/* Action badge */}
        <div className="absolute top-2 left-2">
          <Badge label={isDiscarded ? "removed" : localAction} action={isDiscarded ? "unknown" : localAction as ActionType} />
        </div>
      </div>

      {/* Info */}
      <div className="px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-xs font-semibold tabular-nums",
                confidencePct >= 80
                  ? "text-emerald-400"
                  : confidencePct >= 60
                  ? "text-amber-400"
                  : "text-zinc-500"
              )}
            >
              {confidencePct}%
            </span>
            <span className="text-[11px] text-zinc-600">
              {formatTimestamp(clip.start_time)}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* Fix action */}
            {fixing ? (
              <select
                autoFocus
                className="rounded-md border border-border bg-surface-light px-2 py-1 text-xs text-foreground focus:outline-none focus:border-brand"
                onBlur={() => setFixing(false)}
                onChange={(e) => handleFixAction(e.target.value)}
                defaultValue=""
              >
                <option value="" disabled>
                  Fix action
                </option>
                {ACTION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.value === localAction ? `${opt.label} (current)` : opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <button
                onClick={() => setFixing(true)}
                className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-zinc-500 hover:bg-surface-light hover:text-brand transition-colors"
                title="Fix action type"
              >
                <Pencil size={10} />
                Fix
              </button>
            )}

            {/* Player tag */}
            {tagging ? (
              <select
                autoFocus
                className="rounded-md border border-border bg-surface-light px-2 py-1 text-xs text-foreground focus:outline-none focus:border-brand"
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
                className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-zinc-500 hover:bg-surface-light hover:text-foreground transition-colors"
              >
                <User size={11} />
                {localPlayerName ?? "Tag"}
              </button>
            )}
          </div>
        </div>
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
