"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Film, AlertCircle } from "lucide-react";
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
          "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center transition-colors cursor-pointer",
          dragging
            ? "border-blue-500 bg-blue-500/10"
            : file
            ? "border-zinc-600 bg-zinc-900"
            : "border-zinc-700 bg-zinc-900/50 hover:border-zinc-500 hover:bg-zinc-900"
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
            <Film size={40} className="mb-3 text-blue-400" />
            <p className="font-medium text-zinc-100">{file.name}</p>
            <p className="mt-1 text-sm text-zinc-500">{formatBytes(file.size)}</p>
            <p className="mt-2 text-xs text-zinc-600">Click to change file</p>
          </>
        ) : (
          <>
            <Upload size={40} className="mb-3 text-zinc-500" />
            <p className="font-medium text-zinc-200">Drop your game video here</p>
            <p className="mt-1 text-sm text-zinc-500">
              MP4, MOV, AVI, or WebM · up to {MAX_SIZE_GB} GB
            </p>
          </>
        )}
      </div>

      {/* Title input */}
      {file && (
        <div className="mt-4">
          <label className="block text-sm text-zinc-400 mb-1.5" htmlFor="game-title">
            Game title
          </label>
          <input
            id="game-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Varsity vs Lincoln — March 25"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-500 focus:outline-none"
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-400">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Progress bar */}
      {progress !== null && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-zinc-500 mb-1">
            <span>Uploading…</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Upload button */}
      {file && progress === null && (
        <Button className="mt-4 w-full" size="lg" onClick={handleUpload}>
          <Upload size={16} />
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
