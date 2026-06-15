import type { Source } from "../api/types";

function sourceKey(source: Source): string {
  if (source.file_id) return `file:${source.file_id}`;
  if (source.object_key) return `object:${source.object_key}`;
  if (source.source) return `name:${source.source}`;
  if (source.download_url) return `url:${source.download_url}`;
  return `text:${source.text ?? ""}`;
}

/** Один файл — один источник; при дубликатах оставляем лучший score. */
export function dedupeSources(sources: Source[] | undefined): Source[] {
  if (!sources?.length) return [];
  const best = new Map<string, Source>();
  for (const source of sources) {
    const key = sourceKey(source);
    const prev = best.get(key);
    if (!prev || (source.score ?? 0) > (prev.score ?? 0)) {
      best.set(key, source);
    }
  }
  return Array.from(best.values()).sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
}
