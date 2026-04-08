"use client";

import { useEffect, useState } from "react";
import { fetchAuthedBlobUrl } from "@/lib/api";

/**
 * Loads an authenticated media URL (e.g. /media/clips/abc.mp4) as a blob URL
 * so it can be used in <video src=...> or <img src=...>.
 *
 * Pass an absolute URL or a path beginning with `/`. If the input is empty/undefined,
 * the hook returns an empty string.
 */
export function useAuthedMedia(url: string | null | undefined): string {
  const [blobUrl, setBlobUrl] = useState<string>("");

  useEffect(() => {
    if (!url) {
      setBlobUrl("");
      return;
    }

    let cancelled = false;
    let createdUrl = "";

    // Strip the API origin if present so we hit our own fetcher.
    const path = url.replace(/^https?:\/\/[^/]+/, "");

    fetchAuthedBlobUrl(path)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u);
        } else {
          createdUrl = u;
          setBlobUrl(u);
        }
      })
      .catch(() => {
        if (!cancelled) setBlobUrl("");
      });

    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [url]);

  return blobUrl;
}
