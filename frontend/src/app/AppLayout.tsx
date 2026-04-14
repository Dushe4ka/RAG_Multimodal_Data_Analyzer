import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, LogOut, MessageSquarePlus, PanelsLeftBottom, Pencil, Shield, Trash2, UserCircle2 } from "lucide-react";
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

  return (
    <div className={styles.layout}>
      <aside className={`${styles.sidebar} ${sidebarCollapsed ? styles.collapsed : ""}`}>
        <div className={styles.topActions}>
          <button className={styles.iconButton} onClick={() => setSidebarCollapsed(!sidebarCollapsed)}>
            {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
          {!sidebarCollapsed && (
            <>
              <button
                className={styles.actionButton}
                onClick={() => {
                  setActiveChatId(null);
                  setSelectedWorkspace(null, null);
                  navigate("/");
                }}
              >
                <MessageSquarePlus size={16} />
                Новый чат
              </button>
              <NavLink className={styles.actionButton} to="/workspaces">
                <PanelsLeftBottom size={16} />
                Рабочие пространства
              </NavLink>
              {session.data?.admin ? (
                <NavLink className={styles.actionButton} to="/admin">
                  <Shield size={16} />
                  Админ панель
                </NavLink>
              ) : null}
            </>
          )}
        </div>
        <div className={styles.divider} />
        {!sidebarCollapsed && (
          <div className={styles.chatList}>
            {chatsQuery.data?.length ? (
              chatsQuery.data.map((chat) => (
                <div key={chat.chat_id} className={`${styles.chatItem} ${activeChatId === chat.chat_id ? styles.activeChat : ""}`}>
                  <button
                    className={styles.chatOpenButton}
                    onClick={() => {
                      setActiveChatId(chat.chat_id);
                      const firstWs = chat.workspace_ids?.[0] ?? null;
                      setSelectedWorkspace(firstWs, null);
                      navigate("/");
                    }}
                  >
                    {chat.title}
                  </button>
                  <div className={styles.chatActions}>
                    <button
                      className={styles.chatActionBtn}
                      onClick={() => {
                        setRenameId(chat.chat_id);
                        setRenameValue(chat.title);
                      }}
                      title="Переименовать чат"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      className={styles.chatActionBtn}
                      onClick={() => deleteChatMutation.mutate(chat.chat_id)}
                      title="Удалить чат"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  {renameId === chat.chat_id ? (
                    <div className={styles.renameRow}>
                      <input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} />
                      <button
                        onClick={() => renameChatMutation.mutate({ chatId: chat.chat_id, title: renameValue || chat.title })}
                      >
                        OK
                      </button>
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <div className={styles.empty}>Пока нет чатов</div>
            )}
          </div>
        )}
        <div className={styles.bottom}>
          {!sidebarCollapsed && <Link to="/">RAG Multimodal</Link>}
          <div className={styles.bottomActions}>
            <NavLink className={`${styles.iconButton} ${styles.profileButton}`} to="/profile" title="Профиль">
              <UserCircle2 size={18} />
            </NavLink>
            <button className={styles.iconButton} onClick={() => logoutMutation.mutate()} title="Выйти">
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
