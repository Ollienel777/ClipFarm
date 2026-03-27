import { cn } from "@/lib/utils";
import { type ActionType } from "@/lib/api";

const ACTION_COLORS: Record<ActionType, string> = {
  spike: "bg-red-500/20 text-red-400 border-red-500/30",
  serve: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  dig: "bg-green-500/20 text-green-400 border-green-500/30",
  set: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  block: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

interface BadgeProps {
  label: string;
  variant?: "action" | "status" | "default";
  action?: ActionType;
  className?: string;
}

export function Badge({ label, action, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
        action ? ACTION_COLORS[action] : "bg-zinc-700 text-zinc-300 border-zinc-600",
        className
      )}
    >
      {label}
    </span>
  );
}
