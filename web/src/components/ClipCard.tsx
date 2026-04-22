"use client";

import { useState } from "react";
import { Play, User, ChevronLeft, ChevronRight, Tag, Check } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { type Clip, type Player, type ActionType, tagClip, updateClipLabels, trimClip } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABEL_OPTIONS = ["spike", "serve", "dig", "set", "block", "not_an_action"];

interface ClipCardProps {
  clip: Clip;
  players: Player[];
  onPlay: (clip: Clip) => void;
  onUpdate?: (clip: Clip) => void;
  selected?: boolean;
  onToggleSelect?: (clipId: string) => void;
}

export function ClipCard({ clip, players, onPlay, onUpdate, selected, onToggleSelect }: ClipCardProps) {
  const [tagging, setTagging] = useState(false);
  const [labeling, setLabeling] = useState(false);
  const [trimming, setTrimming] = useState(false);
  const [localPlayerName, setLocalPlayerName] = useState(clip.player_name);
  const [localAction, setLocalAction] = useState(clip.action_type);
  const [localConfidence, setLocalConfidence] = useState(clip.confidence);
  const [localLabels, setLocalLabels] = useState<string[]>(clip.labels ?? []);
  const [localStart, setLocalStart] = useState(clip.start_time);
  const [localEnd, setLocalEnd] = useState(clip.end_time);
  const [trimLoading, setTrimLoading] = useState(false);
  const [labelLoading, setLabelLoading] = useState(false);

  async function handleTag(playerId: string) {
    setTagging(false);
    const updated = await tagClip(clip.id, playerId);
    setLocalPlayerName(updated.player_name);
  }

  async function handleToggleLabel(label: string) {
    if (labelLoading) return;

    let next: string[];
    if (label === "not_an_action") {
      next = ["not_an_action"];
    } else {
      const without = localLabels.filter((l) => l !== "not_an_action");
      if (without.includes(label)) {
        next = without.filter((l) => l !== label);
      } else if (without.length >= 2) {
        next = [without[1], label];
      } else {
        next = [...without, label];
      }
    }
    if (next.length === 0) {
      next = ["not_an_action"];
    }

    const prev = localLabels;
    setLocalLabels(next);
    setLabelLoading(true);
    try {
      const updated = await updateClipLabels(clip.id, next);
      setLocalLabels(updated.labels);
      setLocalAction(updated.action_type);
      setLocalConfidence(updated.confidence);
      onUpdate?.(updated);
    } catch (err) {
      console.error("Label update failed:", err);
      setLocalLabels(prev);
    } finally {
      setLabelLoading(false);
    }
  }

  async function handleTrim(startDelta: number, endDelta: number) {
    setTrimLoading(true);
    try {
      const updated = await trimClip(clip.id, startDelta, endDelta);
      setLocalStart(updated.start_time);
      setLocalEnd(updated.end_time);
      onUpdate?.(updated);
    } catch (err) {
      console.error("Trim failed:", err);
    } finally {
      setTrimLoading(false);
    }
  }

  const confidencePct = Math.round(localConfidence * 100);
  const isDiscarded = localLabels.includes("not_an_action") || (localAction === "unknown" && localConfidence === 0);
  const duration = localEnd - localStart;
  const displayLabels = localLabels.filter((l) => l !== "not_an_action");

  return (
    <div className={cn(
      "group card-noise overflow-hidden rounded-xl border bg-surface transition-all duration-200 hover:shadow-lg hover:shadow-black/20",
      selected ? "border-brand ring-2 ring-brand/40" : "border-border hover:border-border-light",
      isDiscarded && "opacity-40"
    )}>
      {/* Thumbnail */}
      <div
        className="relative aspect-video cursor-pointer bg-black overflow-hidden"
        onClick={() => {
          if (onToggleSelect) onToggleSelect(clip.id);
          else onPlay(clip);
        }}
      >
        {/* Selection checkbox (only shown when parent provides handler) */}
        {onToggleSelect && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleSelect(clip.id);
            }}
            className={cn(
              "absolute top-2 right-2 z-10 flex h-6 w-6 items-center justify-center rounded-md border-2 backdrop-blur-sm transition-all",
              selected
                ? "bg-brand border-brand text-white"
                : "bg-black/40 border-white/60 text-transparent hover:border-white"
            )}
            aria-label={selected ? "Deselect clip" : "Select clip"}
          >
            <Check size={14} strokeWidth={3} />
          </button>
        )}
        {clip.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={clip.thumbnail_url}
            loading="lazy"
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
          {formatDuration(duration)}
        </span>

        {/* Badges */}
        <div className="absolute top-2 left-2 flex flex-wrap gap-1">
          {isDiscarded ? (
            <Badge label="removed" action="unknown" />
          ) : displayLabels.length > 0 ? (
            displayLabels.map((l) => (
              <Badge key={l} label={l} action={l as ActionType} />
            ))
          ) : (
            <Badge label={localAction} action={localAction as ActionType} />
          )}
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
              {formatTimestamp(localStart)}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* Labels toggle */}
            <button
              onClick={() => {
                if (!labeling) {
                  // Seed labels with current action when opening panel
                  // but not if already explicitly labeled or marked as not_an_action
                  if (localLabels.length === 0 && localAction !== "unknown") {
                    setLocalLabels([localAction]);
                  }
                }
                setLabeling(!labeling);
                setTrimming(false);
              }}
              className={cn(
                "flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] transition-colors",
                labeling ? "bg-brand/10 text-brand" : "text-zinc-500 hover:bg-surface-light hover:text-brand"
              )}
              title="Classify actions"
            >
              <Tag size={10} />
              Label
            </button>

            {/* Trim toggle */}
            <button
              onClick={() => { setTrimming(!trimming); setLabeling(false); }}
              className={cn(
                "flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] transition-colors",
                trimming ? "bg-brand/10 text-brand" : "text-zinc-500 hover:bg-surface-light hover:text-brand"
              )}
              title="Trim clip"
            >
              <ChevronLeft size={10} /><ChevronRight size={10} className="-ml-1.5" />
              Trim
            </button>

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

        {/* Labels panel */}
        {labeling && (
          <div className="mt-2 flex flex-wrap gap-1.5 pt-2 border-t border-border">
            {LABEL_OPTIONS.map((label) => {
              const isNotAction = label === "not_an_action";
              const active = isNotAction
                ? localLabels.includes("not_an_action") || isDiscarded
                : localLabels.includes(label);
              return (
                <button
                  key={label}
                  disabled={labelLoading}
                  onClick={() => handleToggleLabel(label)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[11px] font-medium capitalize transition-all disabled:opacity-50",
                    active && isNotAction
                      ? "bg-red-500/20 text-red-400 ring-1 ring-red-500/40"
                      : active
                      ? "bg-brand/20 text-brand ring-1 ring-brand/40"
                      : "bg-surface-light text-zinc-500 hover:text-foreground"
                  )}
                >
                  {isNotAction ? "Not an action" : label}
                </button>
              );
            })}
          </div>
        )}

        {/* Trim panel */}
        {trimming && (
          <div className="mt-2 pt-2 border-t border-border">
            <div className="flex items-center justify-between gap-2">
              <div className="flex flex-col items-center gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Start</span>
                <div className="flex items-center gap-1">
                  <button
                    disabled={trimLoading}
                    onClick={() => handleTrim(-2, 0)}
                    className="rounded-md bg-surface-light px-2 py-1 text-[11px] font-medium text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors disabled:opacity-50"
                    title="Extend start 2s earlier"
                  >
                    -2s
                  </button>
                  <span className="text-[11px] text-zinc-500 tabular-nums w-10 text-center">
                    {formatTimestamp(localStart)}
                  </span>
                  <button
                    disabled={trimLoading}
                    onClick={() => handleTrim(2, 0)}
                    className="rounded-md bg-surface-light px-2 py-1 text-[11px] font-medium text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                    title="Shrink start 2s later"
                  >
                    +2s
                  </button>
                </div>
              </div>
              <div className="text-[10px] text-zinc-600 tabular-nums">
                {formatDuration(duration)}
              </div>
              <div className="flex flex-col items-center gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider">End</span>
                <div className="flex items-center gap-1">
                  <button
                    disabled={trimLoading}
                    onClick={() => handleTrim(0, -2)}
                    className="rounded-md bg-surface-light px-2 py-1 text-[11px] font-medium text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                    title="Shrink end 2s earlier"
                  >
                    -2s
                  </button>
                  <span className="text-[11px] text-zinc-500 tabular-nums w-10 text-center">
                    {formatTimestamp(localEnd)}
                  </span>
                  <button
                    disabled={trimLoading}
                    onClick={() => handleTrim(0, 2)}
                    className="rounded-md bg-surface-light px-2 py-1 text-[11px] font-medium text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors disabled:opacity-50"
                    title="Extend end 2s later"
                  >
                    +2s
                  </button>
                </div>
              </div>
            </div>
            {trimLoading && (
              <p className="mt-1.5 text-center text-[10px] text-brand animate-pulse">Re-cutting clip...</p>
            )}
          </div>
        )}
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
