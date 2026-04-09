"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { RequireAuth } from "@/components/RequireAuth";
import { getDeadTimeClips, getDeadTimeRun, type DeadTimeClip, type DeadTimeRun } from "@/lib/api";

export default function DeadTimeRunPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<DeadTimeRun | null>(null);
  const [clips, setClips] = useState<DeadTimeClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let interval: ReturnType<typeof setInterval> | null = null;

    async function load() {
      try {
        const nextRun = await getDeadTimeRun(id);
        if (!active) return;
        setRun(nextRun);

        if (nextRun.status === "ready") {
          const nextClips = await getDeadTimeClips(id);
          if (!active) return;
          setClips(nextClips);
        }

        if (nextRun.status === "queued" || nextRun.status === "processing") {
          interval = setInterval(async () => {
            try {
              const polled = await getDeadTimeRun(id);
              if (!active) return;
              setRun(polled);
              if (polled.status === "ready") {
                const refreshed = await getDeadTimeClips(id);
                if (!active) return;
                setClips(refreshed);
                if (interval) clearInterval(interval);
              }
              if (polled.status === "failed" && interval) {
                clearInterval(interval);
              }
            } catch {
              // ignore transient poll errors
            }
          }, 4000);
        }
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Failed to load run.");
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
      if (interval) clearInterval(interval);
    };
  }, [id]);

  return (
    <RequireAuth>
      <div className="mx-auto max-w-6xl space-y-6">
        <Link href="/deadtime" className="text-sm text-muted hover:text-foreground">
          Back to dead-time runs
        </Link>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {loading || !run ? (
          <p className="text-sm text-muted">Loading run...</p>
        ) : (
          <>
            <div className="rounded-2xl border border-border bg-surface px-5 py-4">
              <h1 className="text-xl font-bold text-foreground">{run.title}</h1>
              <p className="mt-1 text-sm text-muted">
                Status: {run.status} · Clips: {run.clip_count ?? clips.length}
              </p>
            </div>

            {(run.status === "queued" || run.status === "processing") && (
              <p className="text-sm text-muted">Processing video. This page updates automatically.</p>
            )}

            {run.status === "ready" && clips.length === 0 && (
              <p className="text-sm text-muted">No dead-time clips were extracted for this run.</p>
            )}

            {clips.length > 0 && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {clips.map((clip) => (
                  <article key={clip.id} className="rounded-2xl border border-border bg-surface p-3">
                    <video
                      controls
                      preload="metadata"
                      poster={clip.thumbnail_url ?? undefined}
                      src={clip.clip_url}
                      className="aspect-video w-full rounded-xl bg-black"
                    />
                    <div className="mt-2 flex items-center justify-between text-xs text-muted">
                      <span>
                        {fmtTime(clip.start_time)} - {fmtTime(clip.end_time)}
                      </span>
                      <span>score {clip.score.toFixed(2)}</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </RequireAuth>
  );
}

function fmtTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
