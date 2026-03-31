import Link from "next/link";
import { Upload, Play, SlidersHorizontal, Users, ArrowRight, Zap } from "lucide-react";
import { Button } from "@/components/ui/Button";

const FEATURES = [
  {
    icon: Upload,
    title: "Drop your footage",
    body: "Upload any MP4, MOV, or AVI up to 15 GB. Processing starts immediately.",
  },
  {
    icon: Play,
    title: "AI-powered detection",
    body: "Pose estimation identifies spikes, serves, digs, sets, and blocks in real time.",
  },
  {
    icon: SlidersHorizontal,
    title: "Filter everything",
    body: "Slice your clip feed by action type, player, or confidence threshold.",
  },
  {
    icon: Users,
    title: "Player tagging",
    body: "Jersey-number OCR auto-links clips to player profiles. Manual tag as fallback.",
  },
];

export default function HomePage() {
  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <div className="relative mt-20 max-w-2xl text-center">
        {/* Background glow */}
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 h-64 w-96 bg-brand/8 blur-[100px] rounded-full pointer-events-none" />

        <div className="relative">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand/5 px-4 py-1.5 text-xs font-medium text-brand">
            <Zap size={12} />
            Powered by YOLOv8 pose estimation
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-[1.1] text-foreground">
            Your game footage,
            <br />
            <span className="bg-gradient-to-r from-brand to-orange-300 bg-clip-text text-transparent">
              instant highlights
            </span>
          </h1>

          <p className="mx-auto mt-5 max-w-md text-base text-muted leading-relaxed">
            Upload a full volleyball game. Get a filterable feed of every spike,
            serve, dig, set, and block — automatically tagged by player.
          </p>

          <div className="mt-8 flex justify-center gap-3">
            <Link href="/upload">
              <Button size="lg">
                Upload a game
                <ArrowRight size={14} />
              </Button>
            </Link>
            <Link href="/games">
              <Button size="lg" variant="secondary">
                View my games
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="mt-28 grid w-full max-w-3xl grid-cols-1 gap-3 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="card-noise group rounded-xl border border-border bg-surface p-5 transition-colors hover:border-border-light"
          >
            <div className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand/10 text-brand group-hover:bg-brand/15 transition-colors">
              <Icon size={18} strokeWidth={2} />
            </div>
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
          </div>
        ))}
      </div>

      {/* Footer hint */}
      <p className="mt-20 mb-8 text-xs text-zinc-600">
        Built for volleyball coaches, analysts, and players.
      </p>
    </div>
  );
}
