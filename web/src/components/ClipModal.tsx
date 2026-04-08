"use client";

import { useEffect, useRef } from "react";
import { X, ChevronLeft, ChevronRight, Share2, Link2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { type Clip, getClipShareUrl } from "@/lib/api";
import { useAuthedMedia } from "@/lib/useAuthedMedia";

interface ClipModalProps {
  clip: Clip;
  onClose: () => void;
  onPrev?: () => void;
  onNext?: () => void;
}

export function ClipModal({ clip, onClose, onPrev, onNext }: ClipModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoSrc = useAuthedMedia(clip.clip_url);

  useEffect(() => {
    videoRef.current?.play();
  }, [clip.id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onPrev?.();
      if (e.key === "ArrowRight") onNext?.();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, onPrev, onNext]);

  async function handleShare() {
    try {
      const { url } = await getClipShareUrl(clip.id);
      await navigator.clipboard.writeText(url);
      alert("Share link copied to clipboard!");
    } catch {
      alert("Could not generate share link.");
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="relative w-full max-w-4xl rounded-2xl bg-background border border-border overflow-hidden shadow-2xl shadow-black/50">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <Badge label={clip.action_type} action={clip.action_type} />
            {clip.player_name && (
              <span className="text-sm font-medium text-foreground">{clip.player_name}</span>
            )}
            <span className="text-xs text-zinc-600 tabular-nums">
              {Math.round(clip.confidence * 100)}% confidence
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleShare}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted hover:text-foreground hover:bg-surface-light transition-colors"
            >
              <Link2 size={13} />
              Copy link
            </button>
            <button
              onClick={onClose}
              className="flex items-center justify-center rounded-lg h-8 w-8 text-muted hover:text-foreground hover:bg-surface-light transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Video */}
        <div className="relative bg-black">
          <video
            ref={videoRef}
            src={videoSrc}
            controls
            className="w-full max-h-[75vh] object-contain"
            preload="auto"
          />

          {/* Prev / Next */}
          {onPrev && (
            <button
              onClick={onPrev}
              className="absolute left-3 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-black/60 text-white/80 hover:bg-black/80 hover:text-white backdrop-blur-sm transition-all"
            >
              <ChevronLeft size={20} />
            </button>
          )}
          {onNext && (
            <button
              onClick={onNext}
              className="absolute right-3 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-black/60 text-white/80 hover:bg-black/80 hover:text-white backdrop-blur-sm transition-all"
            >
              <ChevronRight size={20} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
