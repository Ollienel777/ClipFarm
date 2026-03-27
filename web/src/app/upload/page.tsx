import { UploadZone } from "@/components/UploadZone";

export default function UploadPage() {
  return (
    <div className="flex flex-col items-center">
      <h1 className="text-2xl font-bold text-zinc-100">Upload a game</h1>
      <p className="mt-2 text-sm text-zinc-400">
        We&apos;ll process your footage and generate a highlight clip feed in ~5–10 minutes per hour of footage.
      </p>
      <div className="mt-8 w-full max-w-xl">
        <UploadZone />
      </div>
    </div>
  );
}
