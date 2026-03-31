"use client";

import { UploadZone } from "@/components/UploadZone";
import { RequireAuth } from "@/components/RequireAuth";

export default function UploadPage() {
  return (
    <RequireAuth>
      <div className="flex flex-col items-center">
        <div className="text-center mb-8">
          <h1 className="text-xl font-bold text-foreground">Upload a game</h1>
          <p className="mt-1.5 text-sm text-muted">
            Drop your footage and we&apos;ll generate a highlight reel automatically.
          </p>
        </div>
        <UploadZone />
      </div>
    </RequireAuth>
  );
}
