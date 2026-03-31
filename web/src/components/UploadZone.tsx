"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Film, AlertCircle, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { uploadGame } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACCEPTED = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"];
const MAX_SIZE_GB = 15;

export function UploadZone() {
  const router = useRouter();
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validate = (f: File) => {
    if (!ACCEPTED.includes(f.type)) return "Unsupported file type. Please upload an MP4, MOV, AVI, or WebM file.";
    if (f.size > MAX_SIZE_GB * 1024 ** 3) return `File too large. Maximum size is ${MAX_SIZE_GB} GB.`;
    return null;
  };

  const pickFile = useCallback((f: File) => {
    const err = validate(f);
    if (err) { setError(err); return; }
    setError(null);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  }, [title]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) pickFile(f);
  };

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) pickFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setError(null);
    try {
      const game = await uploadGame(file, title || file.name, (pct) => setProgress(pct));
      router.push(`/games/${game.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
      setProgress(null);
    }
  };

  return (
    <div className="w-full max-w-xl">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-14 text-center transition-all duration-200 cursor-pointer",
          dragging
            ? "border-brand bg-brand/5 scale-[1.01]"
            : file
            ? "border-border-light bg-surface"
            : "border-border bg-surface/50 hover:border-border-light hover:bg-surface"
        )}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={onFileInput}
        />

        {file ? (
          <>
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand/10">
              <Film size={22} className="text-brand" />
            </div>
            <p className="font-medium text-foreground">{file.name}</p>
            <p className="mt-1 text-sm text-muted">{formatBytes(file.size)}</p>
            <p className="mt-3 text-xs text-zinc-600 hover:text-muted transition-colors">Click to change file</p>
          </>
        ) : (
          <>
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-light">
              <Upload size={22} className="text-muted" />
            </div>
            <p className="font-medium text-foreground">Drop your game video here</p>
            <p className="mt-1 text-sm text-muted">
              MP4, MOV, AVI, or WebM &middot; up to {MAX_SIZE_GB} GB
            </p>
          </>
        )}
      </div>

      {/* Title input */}
      {file && (
        <div className="mt-4">
          <label className="block text-xs font-medium text-muted mb-1.5" htmlFor="game-title">
            Game title
          </label>
          <input
            id="game-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Varsity vs Lincoln — March 25"
            className="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-foreground placeholder:text-zinc-600 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/20 transition-colors"
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-2.5 text-sm text-red-400">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Progress bar */}
      {progress !== null && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-muted mb-2">
            <span>Uploading...</span>
            <span className="tabular-nums">{progress}%</span>
          </div>
          <div className="h-1 rounded-full bg-surface-light overflow-hidden">
            <div
              className="h-full rounded-full bg-brand transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Upload button */}
      {file && progress === null && (
        <Button className="mt-5 w-full" size="lg" onClick={handleUpload}>
          Upload &amp; Process
        </Button>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}
