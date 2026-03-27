import Link from "next/link";
import { Film, Clock, CheckCircle, AlertCircle, Loader } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

// This page fetches games server-side in production.
// For now it renders a placeholder that links to the upload flow.
export default function GamesPage() {
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

      {/* Empty state */}
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
    </div>
  );
}

export function GameStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "ready": return <CheckCircle size={14} className="text-green-400" />;
    case "processing": return <Loader size={14} className="text-blue-400 animate-spin" />;
    case "queued": return <Clock size={14} className="text-zinc-400" />;
    case "failed": return <AlertCircle size={14} className="text-red-400" />;
    default: return null;
  }
}
