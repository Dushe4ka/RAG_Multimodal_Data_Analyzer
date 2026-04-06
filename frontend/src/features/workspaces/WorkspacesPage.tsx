import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";

import { api } from "../../shared/api/client";
import styles from "./WorkspacesPage.module.css";

export function WorkspacesPage() {
  const [name, setName] = useState("");
  const [isPrivate, setIsPrivate] = useState(true);
  const [renameMap, setRenameMap] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();

  const workspaces = useQuery({ queryKey: ["workspaces-my"], queryFn: api.myWorkspaces });
  const createMutation = useMutation({
    mutationFn: () => api.createWorkspace(name, isPrivate),
    onSuccess: async () => {
      setName("");
      await queryClient.invalidateQueries({ queryKey: ["workspaces-my"] });
    },
  });
  const renameMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => api.renameWorkspace(id, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces-my"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: api.deleteWorkspace,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspaces-my"] }),
  });

  return (
    <section className={styles.page}>
      <header>
        <h1>Рабочие пространства</h1>
      </header>
      <section className={styles.createCard}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название workspace" />
        <label>
          <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} />
          Приватный
        </label>
        <button onClick={() => createMutation.mutate()} disabled={!name.trim() || createMutation.isPending}>
          Создать
        </button>
      </section>

      {workspaces.isLoading ? <div>Загрузка...</div> : null}
      {workspaces.error ? <div className={styles.error}>Ошибка: {(workspaces.error as Error).message}</div> : null}
      {!workspaces.data?.length && !workspaces.isLoading ? <div className={styles.empty}>У вас пока нет workspace.</div> : null}

      <div className={styles.grid}>
        {workspaces.data?.map((ws) => (
          <article key={ws.workspace_id} className={styles.card}>
            <div className={styles.row}>
              <Link to={`/workspaces/${ws.workspace_id}`}>{ws.name}</Link>
              <span className={styles.badge}>{ws.is_private ? "private" : "public"}</span>
            </div>
            <div className={styles.row}>
              <input
                placeholder="Новое имя"
                value={renameMap[ws.workspace_id] ?? ""}
                onChange={(e) => setRenameMap((prev) => ({ ...prev, [ws.workspace_id]: e.target.value }))}
              />
              <button
                onClick={() => renameMutation.mutate({ id: ws.workspace_id, value: renameMap[ws.workspace_id] || ws.name })}
                title="Переименовать"
              >
                <Pencil size={14} />
              </button>
              <button onClick={() => deleteMutation.mutate(ws.workspace_id)} title="Удалить">
                <Trash2 size={14} />
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
