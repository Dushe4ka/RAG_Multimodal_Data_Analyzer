import { useState } from "react";
import {
  ChevronDown,
  Download,
  FileAudio,
  FileImage,
  FileText,
  FileVideo,
  Library,
} from "lucide-react";

import type { Source } from "../../shared/api/types";
import styles from "./MessageSources.module.css";

type MessageSourcesProps = {
  sources: Source[];
};

function SourceIcon({ mediaType }: { mediaType?: string }) {
  const size = 15;
  switch (mediaType) {
    case "image":
      return <FileImage size={size} />;
    case "audio":
      return <FileAudio size={size} />;
    case "video":
      return <FileVideo size={size} />;
    default:
      return <FileText size={size} />;
  }
}

function mediaLabel(mediaType?: string): string {
  switch (mediaType) {
    case "image":
      return "Изображение";
    case "audio":
      return "Аудио";
    case "video":
      return "Видео";
    default:
      return "Документ";
  }
}

export function MessageSources({ sources }: MessageSourcesProps) {
  const [open, setOpen] = useState(false);

  if (!sources.length) return null;

  return (
    <div className={styles.wrap}>
      <button type="button" className={styles.toggle} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className={styles.toggleIcon}>
          <Library size={15} />
        </span>
        <span className={styles.toggleText}>
          Источники
          <span className={styles.count}>{sources.length}</span>
        </span>
        <ChevronDown size={16} className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`} />
      </button>

      {open ? (
        <ul className={styles.list}>
          {sources.map((source) => {
            const key = source.file_id || source.object_key || source.source || source.download_url;
            const label = source.source || "Источник";
            const preview = source.text?.trim();
            return (
              <li key={key} className={styles.item}>
                <div className={styles.itemTop}>
                  <span className={styles.itemIcon}>
                    <SourceIcon mediaType={source.media_type} />
                  </span>
                  <div className={styles.itemMeta}>
                    <span className={styles.itemName}>{label}</span>
                    <span className={styles.itemType}>{mediaLabel(source.media_type)}</span>
                  </div>
                  {source.download_url ? (
                    <a
                      className={styles.downloadBtn}
                      href={source.download_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      title="Скачать файл"
                    >
                      <Download size={14} />
                    </a>
                  ) : null}
                </div>
                {preview ? <p className={styles.preview}>{preview}</p> : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
