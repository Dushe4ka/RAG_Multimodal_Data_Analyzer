import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { LoaderCircle, RotateCcw, Upload, X } from "lucide-react";

import { api } from "../../shared/api/client";
import styles from "./WorkspaceDetailPage.module.css";

type UploadItem = {
  id: string;
  file: File;
  name: string;
  status: "pending" | "indexed" | "error";
  message?: string;
};

export function WorkspaceDetailPage() {
  const { workspaceId = "" } = useParams();
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<UploadItem[]>([]);

  const filesQuery = useQuery({
    queryKey: ["workspace-files", workspaceId],
    queryFn: () => api.filesByWorkspace(workspaceId),
    enabled: Boolean(workspaceId),
  });

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      for (const file of files) {
        const id = `${file.name}-${Date.now()}-${Math.random()}`;
        setUploads((prev) => [...prev, { id, file, name: file.name, status: "pending" }]);
        try {
          const response = await api.uploadFile(workspaceId, file);
          setUploads((prev) =>
            prev.map((item) =>
              item.id === id
                ? {
                    ...item,
                    status: response.extraction_status === "indexed" ? "indexed" : "error",
                    message: response.message,
                  }
                : item
            )
          );
        } catch (error) {
          setUploads((prev) =>
            prev.map((item) =>
              item.id === id
                ? { ...item, status: "error", message: (error as Error).message }
                : item
            )
          );
        }
      }
      await queryClient.invalidateQueries({ queryKey: ["workspace-files", workspaceId] });
    },
  });

  const mergedFiles = useMemo(() => {
    const backend = filesQuery.data ?? [];
    const inProgress = uploads.map((u) => ({
      _upload_id: u.id,
      filename: u.name,
      extraction_status: u.status,
      _temp_message: u.message,
    }));
    return [...inProgress, ...backend];
  }, [filesQuery.data, uploads]);

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <h1>Файлы workspace</h1>
        <label className={styles.uploadButton}>
          <Upload size={16} /> Загрузить
          <input
            type="file"
            multiple
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              if (files.length) uploadMutation.mutate(files);
            }}
            hidden
          />
        </label>
      </header>

      {!mergedFiles.length ? <div className={styles.empty}>Файлы пока не загружены.</div> : null}
      <ul className={styles.fileList}>
        {mergedFiles.map((file, idx) => (
          <li key={`${file.filename}-${idx}`} className={styles.fileItem}>
            <span>{file.filename}</span>
            {file.extraction_status === "pending" ? (
              <span className={styles.pending}>
                <LoaderCircle size={14} className={styles.spin} /> indexing
              </span>
            ) : null}
            {file.extraction_status === "indexed" ? <span className={styles.indexed}>indexed</span> : null}
            {file.extraction_status !== "pending" && file.extraction_status !== "indexed" ? (
              <span className={styles.error}>
                error
                {"_upload_id" in file ? (
                  <>
                    <button
                      className={styles.inlineAction}
                      title="Повторить"
                      onClick={() => {
                        const upload = uploads.find((u) => u.id === file._upload_id);
                        if (!upload) return;
                        uploadMutation.mutate([upload.file]);
                        setUploads((prev) => prev.filter((u) => u.id !== upload.id));
                      }}
                    >
                      <RotateCcw size={12} />
                    </button>
                    <button
                      className={styles.inlineAction}
                      title="Убрать из списка"
                      onClick={() => setUploads((prev) => prev.filter((u) => u.id !== file._upload_id))}
                    >
                      <X size={12} />
                    </button>
                  </>
                ) : null}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
