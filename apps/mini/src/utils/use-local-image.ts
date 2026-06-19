import { useEffect, useMemo, useState } from "react";

import { assetUrl, resolveMiniImageSrc } from "./api";

const LOCAL_IMAGE_RESOLVE_CONCURRENCY = 4;

function uniquePaths(paths: Array<string | null | undefined>): string[] {
  return [...new Set(paths.filter((path): path is string => Boolean(path)))];
}

function compactDependencyKey(path: string | null | undefined): string {
  if (!path) {
    return "";
  }
  if (path.startsWith("data:image/")) {
    return `data-image:${path.length}:${stableTextHash(path)}`;
  }
  return path;
}

function stableTextHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

async function runWithConcurrencyLimit<T>(
  paths: string[],
  worker: (path: string) => Promise<T>,
): Promise<T[]> {
  const results: T[] = new Array(paths.length);
  let nextIndex = 0;

  const workers = Array.from(
    { length: Math.min(LOCAL_IMAGE_RESOLVE_CONCURRENCY, paths.length) },
    async () => {
      while (nextIndex < paths.length) {
        const currentIndex = nextIndex;
        nextIndex += 1;
        results[currentIndex] = await worker(paths[currentIndex]);
      }
    },
  );

  await Promise.all(workers);
  return results;
}

export function useLocalImageMap(paths: Array<string | null | undefined>) {
  const [imageMap, setImageMap] = useState<Record<string, string>>({});
  const dependencyKey = paths.map(compactDependencyKey).join("|");
  const normalizedPaths = useMemo(() => uniquePaths(paths), [dependencyKey]);

  useEffect(() => {
    let cancelled = false;
    const remotePaths = normalizedPaths.filter((path) => {
      const url = assetUrl(path);
      return url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:image/");
    });
    if (remotePaths.length === 0) {
      return;
    }

    void runWithConcurrencyLimit(
      remotePaths,
      async (path) => [path, await resolveMiniImageSrc(path)] as const,
    )
      .then((entries) => {
        if (cancelled) {
          return;
        }
        setImageMap((current) => ({
          ...current,
          ...Object.fromEntries(entries),
        }));
      })
      .catch(() => {
        // Keep the view stable; the UI falls back to an empty src if a temp file cannot be prepared.
      });

    return () => {
      cancelled = true;
    };
  }, [normalizedPaths]);

  return imageMap;
}

export function getLocalImageSrc(
  path: string | null | undefined,
  imageMap: Record<string, string>,
): string {
  if (!path) {
    return "";
  }

  const url = assetUrl(path);
  if (!url.startsWith("http://") && !url.startsWith("https://") && !url.startsWith("data:image/")) {
    return url;
  }

  return imageMap[path] ?? "";
}
