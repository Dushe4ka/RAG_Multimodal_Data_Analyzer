import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  BookMarked,
  Check,
  FolderOpen,
  Globe2,
  Lock,
  Paperclip,
  Plus,
  SendHorizonal,
  Sparkles,
  X,
} from "lucide-react";

import { api } from "../../shared/api/client";
import type { Workspace } from "../../shared/api/types";
import { MarkdownMessage } from "../../shared/ui/MarkdownMessage";
import { dedupeSources } from "../../shared/utils/dedupeSources";
import { makeChatTitle } from "../../shared/utils/makeChatTitle";
import { useUiStore } from "../../shared/store/uiStore";
import type { ChatMessage } from "./chatTypes";
import { MessageSources } from "./MessageSources";
import styles from "./ChatPage.module.css";

function WorkspaceOption({
  workspace,
  isSelected,
  onSelect,
}: {
  workspace: Workspace;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`${styles.workspaceOption} ${isSelected ? styles.workspaceOptionActive : ""}`}
      onClick={onSelect}
    >
      <span className={workspace.is_private ? styles.optionIconPrivate : styles.optionIconPublic}>
        {workspace.is_private ? <Lock size={13} /> : <Globe2 size={13} />}
      </span>
      <span className={styles.workspaceOptionText}>
        <span className={styles.workspaceOptionName}>{workspace.name}</span>
        {workspace.owner_display_name ? (
          <span className={styles.workspaceOptionAuthor}>{workspace.owner_display_name}</span>
        ) : null}
      </span>
      {isSelected ? <Check size={15} className={styles.workspaceOptionCheck} /> : null}
    </button>
  );
}

function TypingIndicator() {
  return (
    <div className={styles.typingBubble} role="status" aria-label="ИИ формирует ответ">
      <span className={styles.typingAvatar} aria-hidden>
        <Sparkles size={14} />
      </span>
      <div className={styles.typingDots} aria-hidden>
        <span className={styles.typingDot} />
        <span className={styles.typingDot} />
        <span className={styles.typingDot} />
      </div>
    </div>
  );
}

export function ChatPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [isSmartSearchEnabled, setIsSmartSearchEnabled] = useState(false);
  const [messagesByChat, setMessagesByChat] = useState<Record<string, ChatMessage[]>>({});
  const [showWorkspacePicker, setShowWorkspacePicker] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);
  const {
    activeChatId,
    setActiveChatId,
    selectedWorkspaceId,
    selectedWorkspaceName,
    setSelectedWorkspace,
  } = useUiStore();

  const workspaceQuery = useQuery({
    queryKey: ["workspaces-accessible"],
    queryFn: async () => {
      const [mine, library] = await Promise.all([api.myWorkspaces(), api.libraryWorkspaces()]);
      return { mine, library };
    },
  });

  const accessibleWorkspaces = useMemo(() => {
    const data = workspaceQuery.data;
    if (!data) return [];
    const map = new Map<string, Workspace>();
    [...data.mine, ...data.library].forEach((ws) => map.set(ws.workspace_id, ws));
    return Array.from(map.values());
  }, [workspaceQuery.data]);

  const selectedWorkspace = useMemo(
    () => accessibleWorkspaces.find((ws) => ws.workspace_id === selectedWorkspaceId) ?? null,
    [accessibleWorkspaces, selectedWorkspaceId]
  );

  const chatsQuery = useQuery({ queryKey: ["chats"], queryFn: api.chats });
  const historyQuery = useQuery({
    queryKey: ["chat-history", activeChatId],
    queryFn: () => api.chatHistory(activeChatId!),
    enabled: Boolean(activeChatId),
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatMessages = useMemo(
    () => (activeChatId ? messagesByChat[activeChatId] || [] : []),
    [activeChatId, messagesByChat]
  );

  const sendMutation = useMutation({
    mutationFn: async ({
      chatId,
      message,
      smartSearch,
    }: {
      chatId: string;
      message: string;
      smartSearch: boolean;
    }) =>
      api.sendMessage(chatId, message, {
        smart_search: smartSearch,
        smart_iterations: 3,
        smart_extra_queries: 2,
      }),
  });

  const attachMutation = useMutation({
    mutationFn: async ({ workspaceId, workspaceName }: { workspaceId: string; workspaceName: string }) => {
      if (activeChatId) {
        await api.attachWorkspaces(activeChatId, [workspaceId]);
      }
      setSelectedWorkspace(workspaceId, workspaceName);
      return activeChatId;
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages.length, sendMutation.isPending]);

  useEffect(() => {
    if (!activeChatId || !historyQuery.data) return;
    const normalized: ChatMessage[] = historyQuery.data.map((msg, idx) => ({
      id: `${activeChatId}-${idx}-${msg.created_at || ""}`,
      role: msg.role,
      content: msg.content,
      sources: dedupeSources(msg.sources),
    }));
    setMessagesByChat((prev) => ({ ...prev, [activeChatId]: normalized }));
  }, [activeChatId, historyQuery.data]);

  useEffect(() => {
    if (!selectedWorkspaceId || !accessibleWorkspaces.length) return;
    const selectedExists = accessibleWorkspaces.some((w) => w.workspace_id === selectedWorkspaceId);
    if (!selectedExists) setSelectedWorkspace(null, null);
  }, [selectedWorkspaceId, accessibleWorkspaces, setSelectedWorkspace]);

  useEffect(() => {
    if (!activeChatId || !chatsQuery.data) return;
    const chat = chatsQuery.data.find((item) => item.chat_id === activeChatId);
    const wsId = chat?.workspace_ids?.[0] ?? null;
    if (!wsId) {
      setSelectedWorkspace(null, null);
      return;
    }
    const wsName = accessibleWorkspaces.find((w) => w.workspace_id === wsId)?.name ?? null;
    setSelectedWorkspace(wsId, wsName);
  }, [activeChatId, chatsQuery.data, accessibleWorkspaces, setSelectedWorkspace]);

  useEffect(() => {
    if (!showWorkspacePicker) return;
    const onPointerDown = (event: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(event.target as Node)) {
        setShowWorkspacePicker(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [showWorkspacePicker]);

  const onSend = async () => {
    const message = draft.trim();
    if (!message || sendMutation.isPending) return;
    setDraft("");
    let chatId = activeChatId;
    if (!chatId) {
      const created = await api.createChat(makeChatTitle(message), selectedWorkspaceId ? [selectedWorkspaceId] : []);
      chatId = created.chat_id;
      setActiveChatId(chatId);
      await queryClient.invalidateQueries({ queryKey: ["chats"] });
    }
    const optimisticMessage: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: message,
    };
    setMessagesByChat((prev) => ({
      ...prev,
      [chatId!]: [...(prev[chatId!] || []), optimisticMessage],
    }));
    try {
      const finalResponse = await sendMutation.mutateAsync({
        chatId: chatId!,
        message,
        smartSearch: isSmartSearchEnabled,
      });
      const assistantMessage: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: finalResponse.answer,
        sources: dedupeSources(finalResponse.sources),
      };
      setMessagesByChat((prev) => ({
        ...prev,
        [finalResponse.chat_id]: [...(prev[finalResponse.chat_id] || []), assistantMessage],
      }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["chat-history", chatId] }),
        queryClient.invalidateQueries({ queryKey: ["chats"] }),
      ]);
    } catch {
      // error rendered below
    }
  };

  const detachWorkspace = async () => {
    if (activeChatId) {
      await api.attachWorkspaces(activeChatId, []);
    }
    setSelectedWorkspace(null, null);
  };

  const mineWorkspaces = workspaceQuery.data?.mine ?? [];
  const libraryWorkspaces = workspaceQuery.data?.library ?? [];
  const hasWorkspaces = mineWorkspaces.length > 0 || libraryWorkspaces.length > 0;

  return (
    <section className={styles.page}>
      <header className={styles.header}>RAG assistant</header>
      <div className={styles.messages}>
        {!chatMessages.length ? (
          <div className={styles.emptyState}>
            <h2>Начните диалог</h2>
            <p>Если чат не выбран, он будет создан автоматически при отправке первого сообщения.</p>
          </div>
        ) : (
          chatMessages.map((message) => (
            <article
              key={message.id}
              className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}
            >
              {message.role === "assistant" ? (
                <MarkdownMessage content={message.content} />
              ) : (
                <p className={styles.userText}>{message.content}</p>
              )}
              {message.role === "assistant" && message.sources?.length ? (
                <MessageSources sources={message.sources} />
              ) : null}
            </article>
          ))
        )}
        {sendMutation.isPending ? <TypingIndicator /> : null}
        <div ref={messagesEndRef} />
      </div>

      <footer className={styles.composer}>
        <div className={styles.composerCard}>
          {selectedWorkspaceName ? (
            <div className={styles.composerMeta}>
              <span className={styles.workspaceChip}>
                <span className={selectedWorkspace?.is_subscribed ? styles.chipIconLibrary : styles.chipIconMine}>
                  {selectedWorkspace?.is_subscribed ? <BookMarked size={12} /> : <FolderOpen size={12} />}
                </span>
                <span className={styles.workspaceChipLabel}>
                  {selectedWorkspace?.is_subscribed ? "Добавлено:" : "Моё:"}
                </span>
                <strong className={styles.workspaceChipName}>{selectedWorkspaceName}</strong>
                <button
                  type="button"
                  className={styles.workspaceChipRemove}
                  onClick={detachWorkspace}
                  title="Открепить workspace"
                >
                  <X size={12} />
                </button>
              </span>
              {isSmartSearchEnabled ? (
                <span className={styles.smartSearchHint}>
                  <Sparkles size={12} />
                  Умный поиск включён
                </span>
              ) : null}
            </div>
          ) : null}

          <textarea
            className={styles.composerInput}
            value={draft}
            placeholder="Введите сообщение..."
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            rows={2}
          />

          <div className={styles.composerActions}>
            <div className={styles.composerActionsLeft}>
              <button
                type="button"
                className={`${styles.smartSearchBtn} ${isSmartSearchEnabled ? styles.smartSearchBtnActive : ""}`}
                onClick={() => setIsSmartSearchEnabled((v) => !v)}
                title="Умный поиск — несколько итераций RAG"
              >
                <Sparkles size={15} />
                Умный поиск
              </button>

              <div className={styles.workspacePickerWrap} ref={pickerRef}>
                <button
                  type="button"
                  className={`${styles.workspacePickerBtn} ${selectedWorkspaceName ? styles.workspacePickerBtnActive : ""}`}
                  onClick={() => setShowWorkspacePicker((v) => !v)}
                  title="Выбрать workspace для поиска по файлам"
                >
                  <Paperclip size={15} />
                  <span>{selectedWorkspaceName ?? "Workspace"}</span>
                </button>

                {showWorkspacePicker ? (
                  <div className={styles.workspacePopover}>
                    <div className={styles.popoverHeader}>
                      <h3>Источник данных</h3>
                      <p>Выберите пространство — ответы будут с опорой на его файлы</p>
                    </div>

                    <Link
                      to="/workspaces"
                      className={styles.createWorkspaceRow}
                      onClick={() => setShowWorkspacePicker(false)}
                    >
                      <Plus size={15} />
                      Создать workspace
                    </Link>

                    {workspaceQuery.isLoading ? (
                      <div className={styles.popoverEmpty}>Загрузка...</div>
                    ) : !hasWorkspaces ? (
                      <div className={styles.popoverEmpty}>
                        Нет доступных пространств. Создайте своё или добавьте из каталога.
                      </div>
                    ) : (
                      <div className={styles.popoverSections}>
                        {mineWorkspaces.length > 0 ? (
                          <section className={styles.popoverSection}>
                            <div className={styles.popoverSectionLabel}>
                              <FolderOpen size={14} />
                              Мои пространства
                              <span className={styles.sectionCount}>{mineWorkspaces.length}</span>
                            </div>
                            <div className={styles.workspaceList}>
                              {mineWorkspaces.map((workspace) => (
                                <WorkspaceOption
                                  key={workspace.workspace_id}
                                  workspace={workspace}
                                  isSelected={workspace.workspace_id === selectedWorkspaceId}
                                  onSelect={() => {
                                    attachMutation.mutate({
                                      workspaceId: workspace.workspace_id,
                                      workspaceName: workspace.name,
                                    });
                                    setShowWorkspacePicker(false);
                                  }}
                                />
                              ))}
                            </div>
                          </section>
                        ) : null}

                        {libraryWorkspaces.length > 0 ? (
                          <section className={styles.popoverSection}>
                            <div className={`${styles.popoverSectionLabel} ${styles.popoverSectionLabelLibrary}`}>
                              <BookMarked size={14} />
                              Добавленные
                              <span className={styles.sectionCount}>{libraryWorkspaces.length}</span>
                            </div>
                            <div className={styles.workspaceList}>
                              {libraryWorkspaces.map((workspace) => (
                                <WorkspaceOption
                                  key={workspace.workspace_id}
                                  workspace={workspace}
                                  isSelected={workspace.workspace_id === selectedWorkspaceId}
                                  onSelect={() => {
                                    attachMutation.mutate({
                                      workspaceId: workspace.workspace_id,
                                      workspaceName: workspace.name,
                                    });
                                    setShowWorkspacePicker(false);
                                  }}
                                />
                              ))}
                            </div>
                          </section>
                        ) : null}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </div>

            <button
              type="button"
              className={styles.sendBtn}
              onClick={onSend}
              disabled={sendMutation.isPending || !draft.trim()}
              title="Отправить"
            >
              <SendHorizonal size={17} />
            </button>
          </div>
        </div>
      </footer>

      {sendMutation.error ? <div className={styles.error}>{(sendMutation.error as Error).message}</div> : null}
    </section>
  );
}
