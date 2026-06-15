import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  LogOut,
  MessageSquare,
  MessageSquarePlus,
  PanelsLeftBottom,
  Pencil,
  Shield,
  Trash2,
  UserCircle2,
  X,
} from "lucide-react";
import { useState } from "react";

import { api } from "../shared/api/client";
import { useSession } from "../features/auth/useSession";
import { useUiStore } from "../shared/store/uiStore";
import styles from "./AppLayout.module.css";

export function AppLayout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const chatsQuery = useQuery({ queryKey: ["chats"], queryFn: api.chats });
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const { sidebarCollapsed, setSidebarCollapsed, setActiveChatId, activeChatId, setSelectedWorkspace } = useUiStore();
  const session = useSession();

  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSuccess: async () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
  const deleteChatMutation = useMutation({
    mutationFn: api.deleteChat,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["chats"] });
      setActiveChatId(null);
      setSelectedWorkspace(null, null);
      navigate("/");
    },
  });
  const renameChatMutation = useMutation({
    mutationFn: ({ chatId, title }: { chatId: string; title: string }) => api.renameChat(chatId, title),
    onSuccess: async () => {
      setRenameId(null);
      setRenameValue("");
      await queryClient.invalidateQueries({ queryKey: ["chats"] });
    },
  });

  const cancelRename = () => {
    setRenameId(null);
    setRenameValue("");
  };

  return (
    <div className={styles.layout}>
      <aside className={`${styles.sidebar} ${sidebarCollapsed ? styles.collapsed : ""}`}>
        <div className={styles.sidebarHeader}>
          <button
            type="button"
            className={styles.collapseBtn}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? "Развернуть панель" : "Свернуть панель"}
          >
            {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
          {!sidebarCollapsed ? (
            <div className={styles.brand}>
              <span className={styles.brandMark}>RAG</span>
              <span className={styles.brandText}>Multimodal</span>
            </div>
          ) : null}
        </div>

        {!sidebarCollapsed ? (
          <div className={styles.topActions}>
            <button
              type="button"
              className={`${styles.actionButton} ${styles.actionButtonPrimary}`}
              onClick={() => {
                setActiveChatId(null);
                setSelectedWorkspace(null, null);
                navigate("/");
              }}
            >
              <MessageSquarePlus size={16} />
              Новый чат
            </button>
            <NavLink className={({ isActive }) => `${styles.actionButton} ${isActive ? styles.actionButtonActive : ""}`} to="/workspaces">
              <PanelsLeftBottom size={16} />
              Рабочие пространства
            </NavLink>
            {session.data?.admin ? (
              <NavLink className={({ isActive }) => `${styles.actionButton} ${isActive ? styles.actionButtonActive : ""}`} to="/admin">
                <Shield size={16} />
                Админ панель
              </NavLink>
            ) : null}
          </div>
        ) : null}

        {!sidebarCollapsed ? (
          <>
            <div className={styles.sectionLabel}>
              История чатов
              {chatsQuery.data?.length ? <span className={styles.sectionCount}>{chatsQuery.data.length}</span> : null}
            </div>
            <div className={styles.chatList}>
              {chatsQuery.data?.length ? (
                chatsQuery.data.map((chat) => {
                  const isActive = activeChatId === chat.chat_id;
                  const isRenaming = renameId === chat.chat_id;
                  return (
                    <div key={chat.chat_id} className={`${styles.chatItem} ${isActive ? styles.activeChat : ""}`}>
                      {isRenaming ? (
                        <div className={styles.renameRow}>
                          <input
                            className={styles.renameInput}
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                renameChatMutation.mutate({ chatId: chat.chat_id, title: renameValue || chat.title });
                              }
                              if (e.key === "Escape") cancelRename();
                            }}
                            autoFocus
                          />
                          <button
                            type="button"
                            className={styles.renameConfirm}
                            onClick={() => renameChatMutation.mutate({ chatId: chat.chat_id, title: renameValue || chat.title })}
                            title="Сохранить"
                          >
                            <Check size={14} />
                          </button>
                          <button type="button" className={styles.renameCancel} onClick={cancelRename} title="Отмена">
                            <X size={14} />
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className={styles.chatOpenButton}
                            onClick={() => {
                              setActiveChatId(chat.chat_id);
                              const firstWs = chat.workspace_ids?.[0] ?? null;
                              setSelectedWorkspace(firstWs, null);
                              navigate("/");
                            }}
                          >
                            <span className={styles.chatIcon}>
                              <MessageSquare size={15} />
                            </span>
                            <span className={styles.chatTitle}>{chat.title}</span>
                          </button>
                          <div className={styles.chatActions}>
                            <button
                              type="button"
                              className={styles.chatActionBtn}
                              onClick={() => {
                                setRenameId(chat.chat_id);
                                setRenameValue(chat.title);
                              }}
                              title="Переименовать"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              type="button"
                              className={`${styles.chatActionBtn} ${styles.chatActionBtnDanger}`}
                              onClick={() => deleteChatMutation.mutate(chat.chat_id)}
                              title="Удалить чат"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className={styles.empty}>Пока нет чатов — начните новый диалог</div>
              )}
            </div>
          </>
        ) : null}

        <div className={styles.bottom}>
          {!sidebarCollapsed && session.data?.login ? (
            <div className={styles.userBlock}>
              <span className={styles.userAvatar}>{session.data.login.slice(0, 1).toUpperCase()}</span>
              <div className={styles.userMeta}>
                <span className={styles.userName}>
                  {[session.data.name, session.data.surname].filter(Boolean).join(" ") || session.data.login}
                </span>
                <span className={styles.userLogin}>@{session.data.login}</span>
              </div>
            </div>
          ) : null}
          <div className={styles.bottomActions}>
            <NavLink className={styles.bottomIconBtn} to="/profile" title="Профиль">
              <UserCircle2 size={18} />
            </NavLink>
            <button type="button" className={styles.bottomIconBtn} onClick={() => logoutMutation.mutate()} title="Выйти">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
