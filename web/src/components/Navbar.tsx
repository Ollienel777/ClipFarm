import Link from "next/link";
import { Upload, Film } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-zinc-100">
          <Film size={20} className="text-blue-400" />
          ClipFarm
        </Link>
        <nav className="flex items-center gap-2">
          <Link href="/games" className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors px-3">
            My Games
          </Link>
          <Link href="/upload">
            <Button size="sm">
              <Upload size={14} />
              Upload
            </Button>
          </Link>
        </nav>
      </div>
    </header>
  );
}
