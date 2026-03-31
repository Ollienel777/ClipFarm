import { cn } from "@/lib/utils";
import { type ActionType } from "@/lib/api";

const ACTION_STYLES: Record<ActionType, { bg: string; text: string; dot: string }> = {
  spike:   { bg: "bg-red-500/10",    text: "text-red-400",    dot: "bg-red-400" },
  serve:   { bg: "bg-blue-500/10",   text: "text-blue-400",   dot: "bg-blue-400" },
  dig:     { bg: "bg-emerald-500/10", text: "text-emerald-400", dot: "bg-emerald-400" },
  set:     { bg: "bg-violet-500/10", text: "text-violet-400", dot: "bg-violet-400" },
  block:   { bg: "bg-orange-500/10", text: "text-orange-400", dot: "bg-orange-400" },
  unknown: { bg: "bg-zinc-500/10",   text: "text-zinc-400",   dot: "bg-zinc-400" },
};

interface BadgeProps {
  label: string;
  variant?: "action" | "status" | "default";
  action?: ActionType;
  className?: string;
}

export function Badge({ label, action, className }: BadgeProps) {
  const style = action ? ACTION_STYLES[action] : null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider",
        style
          ? `${style.bg} ${style.text}`
          : "bg-zinc-800 text-zinc-400",
        className
      )}
    >
      {style && <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />}
      {label}
    </span>
  );
}
