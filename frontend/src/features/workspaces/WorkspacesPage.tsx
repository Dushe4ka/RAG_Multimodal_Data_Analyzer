import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  BookMarked,
  FolderOpen,
  Globe2,
  Lock,
  Pencil,
  Plus,
  Search,
  Trash2,
  UserRound,
  X,
} from "lucide-react";

import { api } from "../../shared/api/client";
import type { Workspace } from "../../shared/api/types";
import styles from "./WorkspacesPage.module.css";

type TabId = "mine" | "library" | "catalog";

function formatDate(value?: string): string {
  if (!value) return "";
  return new Date(value).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function WorkspaceCard({
  workspace,
  variant = "mine",
  onRename,
  onDelete,
  onRemoveFromLibrary,
  onToggleVisibility,
  onAddToLibrary,
}: {
  workspace: Workspace;
  variant?: TabId;
  onRename?: (id: string, name: string) => void;
  onDelete?: (id: string) => void;
  onRemoveFromLibrary?: (id: string) => void;
  onToggleVisibility?: (id: string, isPrivate: boolean) => void;
  onAddToLibrary?: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(workspace.name);

  const roleLabel = workspace.is_owner ? "Владелец" : workspace.is_subscribed ? "Добавлено" : "Публичное";

  return (
    <article className={styles.card}>
      <div className={styles.cardTop}>
        <div className={styles.cardIcon}>
          {workspace.is_private ? <Lock size={18} /> : <Globe2 size={18} />}
        </div>
        <div className={styles.cardHead}>
          {editing ? (
            <input
              className={styles.renameInput}
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              autoFocus
            />
          ) : (
            <Link to={`/workspaces/${workspace.workspace_id}`} className={styles.cardTitle}>
              {workspace.name}
            </Link>
          )}
          <div className={styles.cardMeta}>
            <span className={workspace.is_private ? styles.badgePrivate : styles.badgePublic}>
              {workspace.is_private ? "Приватный" : "Публичный"}
            </span>
            <span className={styles.badgeRole}>{roleLabel}</span>
          </div>
        </div>
      </div>

      <div className={styles.ownerRow}>
        <UserRound size={14} />
        <span>
          Автор: <strong>{workspace.owner_display_name || workspace.owner_login || "—"}</strong>
          {workspace.owner_login && workspace.owner_display_name !== workspace.owner_login ? (
            <span className={styles.ownerLogin}> (@{workspace.owner_login})</span>
          ) : null}
        </span>
      </div>

      <p className={styles.cardDate}>Обновлён: {formatDate(workspace.updated_at)}</p>

      <div className={styles.cardActions}>
        <Link to={`/workspaces/${workspace.workspace_id}`} className={styles.openBtn}>
          <FolderOpen size={14} />
          Открыть
        </Link>

        {variant === "catalog" && !workspace.is_owner && workspace.is_subscribed && onRemoveFromLibrary ? (
          <button
            type="button"
            className={styles.catalogSubscribedBtn}
            title="Нажмите, чтобы убрать из добавленных"
            onClick={() => onRemoveFromLibrary(workspace.workspace_id)}
          >
            <span className={styles.catalogBtnDefault}>Уже добавлено</span>
            <span className={styles.catalogBtnHover}>
              <X size={14} />
              Удалить
            </span>
          </button>
        ) : null}

        {variant === "catalog" && !workspace.is_owner && !workspace.is_subscribed && onAddToLibrary ? (
          <button type="button" className={styles.primaryBtn} onClick={() => onAddToLibrary(workspace.workspace_id)}>
            <Plus size={14} />
            Добавить к себе
          </button>
        ) : null}

        {variant === "catalog" && workspace.is_owner ? (
          <span className={styles.ownCatalogBadge}>Ваше пространство</span>
        ) : null}

        {workspace.is_owner && onToggleVisibility ? (
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={() => onToggleVisibility(workspace.workspace_id, !workspace.is_private)}
          >
            {workspace.is_private ? "Сделать публичным" : "Сделать приватным"}
          </button>
        ) : null}

        {workspace.is_owner && onRename ? (
          editing ? (
            <>
              <button
                type="button"
                className={styles.primaryBtn}
                onClick={() => {
                  onRename(workspace.workspace_id, draftName.trim() || workspace.name);
                  setEditing(false);
                }}
              >
                Сохранить
              </button>
              <button type="button" className={styles.ghostBtn} onClick={() => setEditing(false)}>
                Отмена
              </button>
            </>
          ) : (
            <button type="button" className={styles.iconBtn} title="Переименовать" onClick={() => setEditing(true)}>
              <Pencil size={14} />
            </button>
          )
        ) : null}

        {workspace.is_owner && onDelete ? (
          <button
            type="button"
            className={styles.dangerBtn}
            title="Удалить workspace"
            onClick={() => onDelete(workspace.workspace_id)}
          >
            <Trash2 size={14} />
          </button>
        ) : null}

        {workspace.is_subscribed && variant === "library" && onRemoveFromLibrary ? (
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={() => onRemoveFromLibrary(workspace.workspace_id)}
          >
            <X size={14} />
            Убрать из списка
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function WorkspacesPage() {
  const [tab, setTab] = useState<TabId>("mine");
  const [name, setName] = useState("");
  const [isPrivate, setIsPrivate] = useState(true);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const queryClient = useQueryClient();

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["workspaces-my"] }),
      queryClient.invalidateQueries({ queryKey: ["workspaces-library"] }),
      queryClient.invalidateQueries({ queryKey: ["workspaces-catalog"] }),
      queryClient.invalidateQueries({ queryKey: ["workspaces-accessible"] }),
    ]);
  };

  const ownedQuery = useQuery({ queryKey: ["workspaces-my"], queryFn: api.myWorkspaces });
  const libraryQuery = useQuery({ queryKey: ["workspaces-library"], queryFn: api.libraryWorkspaces });
  const catalogQueryResult = useQuery({
    queryKey: ["workspaces-catalog", searchQuery],
    queryFn: () => api.searchPublicWorkspaces(searchQuery),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createWorkspace(name, isPrivate),
    onSuccess: async () => {
      setName("");
      await invalidateAll();
      setTab("mine");
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => api.renameWorkspace(id, value),
    onSuccess: invalidateAll,
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteWorkspace,
    onSuccess: invalidateAll,
  });

  const addMutation = useMutation({
    mutationFn: api.addWorkspaceToLibrary,
    onSuccess: invalidateAll,
  });

  const removeMutation = useMutation({
    mutationFn: api.removeWorkspaceFromLibrary,
    onSuccess: invalidateAll,
  });

  const visibilityMutation = useMutation({
    mutationFn: ({ id, is_private }: { id: string; is_private: boolean }) =>
      api.setWorkspaceVisibility(id, is_private),
    onSuccess: invalidateAll,
  });

  const catalogItems = catalogQueryResult.data ?? [];

  const tabs = useMemo(
    () => [
      { id: "mine" as const, label: "Мои", count: ownedQuery.data?.length ?? 0, icon: FolderOpen },
      { id: "library" as const, label: "Добавленные", count: libraryQuery.data?.length ?? 0, icon: BookMarked },
      { id: "catalog" as const, label: "Каталог", count: catalogItems.length, icon: Globe2 },
    ],
    [ownedQuery.data?.length, libraryQuery.data?.length, catalogItems.length]
  );

  const currentList =
    tab === "mine" ? ownedQuery.data : tab === "library" ? libraryQuery.data : catalogItems;

  const isLoading =
    tab === "mine"
      ? ownedQuery.isLoading
      : tab === "library"
        ? libraryQuery.isLoading
        : catalogQueryResult.isLoading;

  const emptyMessages: Record<TabId, string> = {
    mine: "У вас пока нет собственных workspace. Создайте первый ниже.",
    library: "Вы ещё не добавили чужие workspace. Откройте каталог публичных пространств.",
    catalog: searchQuery
      ? "По запросу ничего не найдено. Попробуйте другое название."
      : "Публичных workspace пока нет. Создайте своё и снимите галочку «Приватный».",
  };

  return (
    <section className={styles.page}>
      <header className={styles.hero}>
        <div>
          <h1>Рабочие пространства</h1>
          <p className={styles.subtitle}>
            Создавайте свои workspace, делитесь публичными и добавляйте чужие в свой список.
          </p>
        </div>
      </header>

      <section className={styles.createPanel}>
        <h2>Новое пространство</h2>
        <div className={styles.createRow}>
          <input
            className={styles.textInput}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Название, например «Диплом 2025»"
          />
          <label className={styles.toggle}>
            <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} />
            <span>Приватный</span>
          </label>
          <button
            type="button"
            className={styles.createBtn}
            onClick={() => createMutation.mutate()}
            disabled={!name.trim() || createMutation.isPending}
          >
            <Plus size={16} />
            Создать
          </button>
        </div>
        <p className={styles.createHint}>
          {isPrivate
            ? "Приватный workspace видите только вы."
            : "Публичный workspace появится в каталоге — другие смогут добавить его к себе."}
        </p>
      </section>

      <nav className={styles.tabs}>
        {tabs.map(({ id, label, count, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`${styles.tab} ${tab === id ? styles.tabActive : ""}`}
            onClick={() => setTab(id)}
          >
            <Icon size={16} />
            {label}
            <span className={styles.tabCount}>{count}</span>
          </button>
        ))}
      </nav>

      {tab === "catalog" ? (
        <div className={styles.searchBar}>
          <Search size={16} />
          <input
            className={styles.searchInput}
            value={catalogQuery}
            onChange={(e) => setCatalogQuery(e.target.value)}
            placeholder="Поиск по названию..."
            onKeyDown={(e) => {
              if (e.key === "Enter") setSearchQuery(catalogQuery.trim());
            }}
          />
          <button type="button" className={styles.searchBtn} onClick={() => setSearchQuery(catalogQuery.trim())}>
            Найти
          </button>
        </div>
      ) : null}

      {isLoading ? <div className={styles.loading}>Загрузка...</div> : null}

      {!isLoading && !currentList?.length ? (
        <div className={styles.empty}>{emptyMessages[tab]}</div>
      ) : null}

      <div className={styles.grid}>
        {currentList?.map((ws) => (
          <WorkspaceCard
            key={ws.workspace_id}
            workspace={ws}
            variant={tab}
            onRename={(id, value) => renameMutation.mutate({ id, value })}
            onDelete={(id) => deleteMutation.mutate(id)}
            onRemoveFromLibrary={(id) => removeMutation.mutate(id)}
            onToggleVisibility={(id, is_private) => visibilityMutation.mutate({ id, is_private })}
            onAddToLibrary={(id) => addMutation.mutate(id)}
          />
        ))}
      </div>
    </section>
  );
}
