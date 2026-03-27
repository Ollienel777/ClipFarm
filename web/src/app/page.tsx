import Link from "next/link";
import { Upload, Play, Filter, Users } from "lucide-react";
import { Button } from "@/components/ui/Button";

const FEATURES = [
  {
    icon: Upload,
    title: "Upload game footage",
    body: "Drop any MP4, MOV, or AVI file up to 15 GB. We handle the rest.",
  },
  {
    icon: Play,
    title: "Auto-generated highlights",
    body: "YOLOv8 detects spikes, serves, digs, sets, and blocks automatically.",
  },
  {
    icon: Filter,
    title: "Filter by action & player",
    body: "Instantly filter your clip feed by action type, player, or confidence score.",
  },
  {
    icon: Users,
    title: "Player profiles",
    body: "Jersey-number OCR links clips to players. Tag manually as a fallback.",
  },
];

export default function HomePage() {
  return (
    <div className="flex flex-col items-center text-center">
      {/* Hero */}
      <div className="mt-16 max-w-2xl">
        <h1 className="text-5xl font-bold tracking-tight text-zinc-50">
          Volleyball highlights,{" "}
          <span className="text-blue-400">automatically</span>
        </h1>
        <p className="mt-4 text-lg text-zinc-400">
          Upload a full game. Get a filterable feed of every spike, serve, dig,
          set, and block — tagged by player.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/upload">
            <Button size="lg">
              <Upload size={16} />
              Upload a game
            </Button>
          </Link>
          <Link href="/games">
            <Button size="lg" variant="secondary">
              View my games
            </Button>
          </Link>
        </div>
      </div>

      {/* Features */}
      <div className="mt-24 grid w-full max-w-4xl grid-cols-1 gap-6 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 text-left"
          >
            <div className="mb-3 inline-flex rounded-lg border border-blue-500/20 bg-blue-500/10 p-2.5">
              <Icon size={20} className="text-blue-400" />
            </div>
            <h3 className="font-semibold text-zinc-100">{title}</h3>
            <p className="mt-1.5 text-sm text-zinc-400">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
