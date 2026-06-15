import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Download, FolderOpen, Globe2, LoaderCircle, Lock, RotateCcw, Upload, UserRound, X } from "lucide-react";

import { api } from "../../shared/api/client";
import type { FileDoc } from "../../shared/api/types";
import styles from "./WorkspaceDetailPage.module.css";

type UploadItem = {
  id: string;
  file: File;
  name: string;
  status: "pending" | "indexed" | "error";
  message?: string;
};

type MergedFile = FileDoc | {
  _upload_id: string;
  filename: string;
  extraction_status: string;
  _temp_message?: string;
};

const STAGE_LABELS: Record<string, string> = {
  indexing: "индексация",
  extraction: "извлечение текста",
  full: "полная обработка",
  storage: "хранилище",
};

function formatSize(bytes?: number): string {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFailedStage(file: FileDoc): string | undefined {
  const meta = file.metadata || {};
  const explicit = meta.failed_stage as string | undefined;
  if (explicit) return explicit;
  if (meta.extracted_text) return "indexing";
  if (meta.error === "empty_text_after_extraction") return "extraction";
  return "full";
}

function retryTitle(file: FileDoc): string {
  const stage = getFailedStage(file);
  const hasCachedText = Boolean(file.metadata?.extracted_text);
  if (stage === "indexing" && hasCachedText) {
    return "Повторить только индексацию (текст уже извлечён)";
  }
  if (stage === "extraction") {
    return "Повторить извлечение текста и индексацию";
  }
  return "Повторить полную обработку файла из хранилища";
}

function statusLabel(file: MergedFile): { text: string; className: string; hint?: string } {
  const status = file.extraction_status;
  const metaError =
    "metadata" in file && file.metadata && typeof file.metadata === "object"
      ? (file.metadata as { error?: string }).error
      : undefined;
  const tempMessage = "_temp_message" in file ? file._temp_message : undefined;

  if (status === "pending") {
    const stage =
      "metadata" in file && file.metadata?.reprocess_stage
        ? STAGE_LABELS[String(file.metadata.reprocess_stage)] || String(file.metadata.reprocess_stage)
        : "обработка";
    return { text: `${stage}…`, className: styles.pending };
  }
  if (status === "indexed") {
    return { text: "готов к поиску", className: styles.indexed };
  }
  if (status === "stub") {
    return {
      text: "загружен, текст пустой",
      className: styles.stub,
      hint: "Файл сохранён, но извлечь текст для поиска не удалось.",
    };
  }
  if (status === "error" && "file_id" in file) {
    const stage = getFailedStage(file);
    const stageText = stage ? STAGE_LABELS[stage] || stage : "обработка";
    return {
      text: `загружен, сбой: ${stageText}`,
      className: styles.error,
      hint: metaError || `Этап «${stageText}» не завершился. Нажмите ↻ для повтора.`,
    };
  }
  return {
    text: "ошибка загрузки",
    className: styles.error,
    hint: tempMessage,
  };
}

export function WorkspaceDetailPage() {
  const { workspaceId = "" } = useParams();
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [reprocessingIds, setReprocessingIds] = useState<Set<string>>(new Set());

  const filesQuery = useQuery({
    queryKey: ["workspace-files", workspaceId],
    queryFn: () => api.filesByWorkspace(workspaceId),
    enabled: Boolean(workspaceId),
  });

  const workspaceQuery = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => api.getWorkspace(workspaceId),
    enabled: Boolean(workspaceId),
  });

  const canUpload = Boolean(workspaceQuery.data?.is_owner || workspaceQuery.data?.is_subscribed);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      for (const file of files) {
        const id = `${file.name}-${Date.now()}-${Math.random()}`;
        setUploads((prev) => [...prev, { id, file, name: file.name, status: "pending" }]);
        try {
          await api.uploadFile(workspaceId, file);
          setUploads((prev) => prev.filter((item) => item.id !== id && item.name !== file.name));
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

  const reprocessMutation = useMutation({
    mutationFn: (fileId: string) => api.reprocessFile(fileId),
    onMutate: (fileId) => {
      setReprocessingIds((prev) => new Set(prev).add(fileId));
    },
    onSettled: async (_data, _error, fileId) => {
      setReprocessingIds((prev) => {
        const next = new Set(prev);
        next.delete(fileId);
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["workspace-files", workspaceId] });
    },
  });

  const downloadMutation = useMutation({
    mutationFn: async (file: FileDoc) => {
      const { url } = await api.fileDownloadLink(file.file_id);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.filename;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    },
  });

  const mergedFiles = useMemo(() => {
    const backend = (filesQuery.data ?? []).map((file) => {
      if (reprocessingIds.has(file.file_id)) {
        return {
          ...file,
          extraction_status: "pending",
          metadata: { ...file.metadata, reprocess_stage: getFailedStage(file) },
        };
      }
      return file;
    });
    const backendNames = new Set(backend.map((f) => f.filename));
    const inProgress = uploads
      .filter((u) => !backendNames.has(u.name) || u.status === "pending")
      .map((u) => ({
        _upload_id: u.id,
        filename: u.name,
        extraction_status: u.status,
        _temp_message: u.message,
      }));
    return [...inProgress, ...backend];
  }, [filesQuery.data, uploads, reprocessingIds]);

  const canReprocess = (file: MergedFile): file is FileDoc =>
    canUpload &&
    "file_id" in file &&
    (file.extraction_status === "error" || file.extraction_status === "stub") &&
    !reprocessingIds.has(file.file_id);

  const canDownload = (file: MergedFile): file is FileDoc =>
    "file_id" in file && file.extraction_status !== "pending";

  return (
    <section className={styles.page}>
      <Link to="/workspaces" className={styles.backLink}>
        <ArrowLeft size={16} />
        К рабочим пространствам
      </Link>

      <header className={styles.hero}>
        <div className={styles.heroIcon}>
          {workspaceQuery.data?.is_private ? <Lock size={22} /> : <Globe2 size={22} />}
        </div>
        <div className={styles.heroText}>
          <h1>{workspaceQuery.data?.name || "Workspace"}</h1>
          {workspaceQuery.data ? (
            <div className={styles.heroMeta}>
              <span className={workspaceQuery.data.is_private ? styles.badgePrivate : styles.badgePublic}>
                {workspaceQuery.data.is_private ? "Приватный" : "Публичный"}
              </span>
              <span className={styles.owner}>
                <UserRound size={14} />
                Автор: {workspaceQuery.data.owner_display_name || workspaceQuery.data.owner_login || "—"}
              </span>
              {workspaceQuery.data.is_owner ? (
                <span className={styles.roleBadge}>Вы владелец</span>
              ) : workspaceQuery.data.is_subscribed ? (
                <span className={styles.roleBadge}>Добавлено вами</span>
              ) : (
                <span className={styles.roleBadgeMuted}>Только просмотр</span>
              )}
            </div>
          ) : null}
        </div>
        {canUpload ? (
          <label className={styles.uploadButton}>
            <Upload size={16} /> Загрузить файлы
            <input
              type="file"
              multiple
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                if (files.length) uploadMutation.mutate(files);
                e.target.value = "";
              }}
              hidden
            />
          </label>
        ) : null}
      </header>

      {!canUpload && workspaceQuery.data && !workspaceQuery.data.is_private ? (
        <p className={styles.readOnlyHint}>
          Вы просматриваете публичное пространство. Чтобы загружать файлы, добавьте его к себе в разделе «Каталог».
        </p>
      ) : null}

      {filesQuery.isLoading || workspaceQuery.isLoading ? (
        <div className={styles.loading}>Загрузка файлов...</div>
      ) : null}
      {filesQuery.error ? (
        <div className={styles.error}>Ошибка: {(filesQuery.error as Error).message}</div>
      ) : null}

      {!filesQuery.isLoading && !filesQuery.error && !mergedFiles.length ? (
        <div className={styles.emptyState}>
          <FolderOpen size={32} />
          <p>Файлы пока не загружены.</p>
          {canUpload ? <span>Нажмите «Загрузить файлы», чтобы добавить первый документ.</span> : null}
        </div>
      ) : null}

      <ul className={styles.fileList}>
        {mergedFiles.map((file, idx) => {
          const label = statusLabel(file);
          const size = "size_bytes" in file ? formatSize(file.size_bytes) : undefined;
          return (
            <li
              key={"file_id" in file && file.file_id ? file.file_id : `${file.filename}-${idx}`}
              className={styles.fileItem}
            >
              <div className={styles.fileMeta}>
                <span>{file.filename}</span>
                {size ? <span className={styles.fileSize}>{size}</span> : null}
              </div>
              <div className={styles.fileActions}>
                <span className={label.className} title={label.hint}>
                  {file.extraction_status === "pending" ? (
                    <LoaderCircle size={14} className={styles.spin} />
                  ) : null}
                  {label.text}
                </span>
                {canDownload(file) ? (
                  <button
                    type="button"
                    className={styles.downloadBtn}
                    title="Скачать файл"
                    disabled={downloadMutation.isPending}
                    onClick={() => downloadMutation.mutate(file)}
                  >
                    <Download size={14} />
                    Скачать
                  </button>
                ) : null}
                {canReprocess(file) ? (
                  <button
                    type="button"
                    className={styles.inlineAction}
                    title={retryTitle(file)}
                    disabled={reprocessMutation.isPending}
                    onClick={() => reprocessMutation.mutate(file.file_id)}
                  >
                    <RotateCcw size={12} />
                  </button>
                ) : null}
                {file.extraction_status === "error" && "_upload_id" in file ? (
                  <>
                    <button
                      type="button"
                      className={styles.inlineAction}
                      title="Повторить загрузку"
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
                      type="button"
                      className={styles.inlineAction}
                      title="Убрать из списка"
                      onClick={() => setUploads((prev) => prev.filter((u) => u.id !== file._upload_id))}
                    >
                      <X size={12} />
                    </button>
                  </>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
