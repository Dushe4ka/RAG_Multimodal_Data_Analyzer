import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Paperclip, SendHorizonal, X } from "lucide-react";

import { api } from "../../shared/api/client";
import { useUiStore } from "../../shared/store/uiStore";
import type { ChatMessage } from "./chatTypes";
import styles from "./ChatPage.module.css";

function makeTitle(message: string) {
  const trimmed = message.trim();
  return trimmed.slice(0, 40) || "Новый чат";
}

export function ChatPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [messagesByChat, setMessagesByChat] = useState<Record<string, ChatMessage[]>>({});
  const [showWorkspacePicker, setShowWorkspacePicker] = useState(false);
  const {
    activeChatId,
    setActiveChatId,
    selectedWorkspaceId,
    selectedWorkspaceName,
    setSelectedWorkspace,
  } = useUiStore();
  const workspaceQuery = useQuery({ queryKey: ["workspaces-my"], queryFn: api.myWorkspaces });
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
    mutationFn: async ({ chatId, message }: { chatId: string; message: string }) => api.sendMessage(chatId, message),
  });

  const attachMutation = useMutation({
    mutationFn: async ({ workspaceId, workspaceName }: { workspaceId: string; workspaceName: string }) => {
      let chatId = activeChatId;
      if (!chatId) {
        const created = await api.createChat("Новый чат", [workspaceId]);
        chatId = created.chat_id;
        setActiveChatId(chatId);
        await queryClient.invalidateQueries({ queryKey: ["chats"] });
      } else {
        await api.attachWorkspaces(chatId, [workspaceId]);
      }
      setSelectedWorkspace(workspaceId, workspaceName);
      return chatId;
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
      sources: msg.sources ?? [],
    }));
    setMessagesByChat((prev) => ({ ...prev, [activeChatId]: normalized }));
  }, [activeChatId, historyQuery.data]);

  useEffect(() => {
    if (!selectedWorkspaceId || !workspaceQuery.data) return;
    const selectedExists = workspaceQuery.data.some((w) => w.workspace_id === selectedWorkspaceId);
    if (!selectedExists) setSelectedWorkspace(null, null);
  }, [selectedWorkspaceId, workspaceQuery.data, setSelectedWorkspace]);

  useEffect(() => {
    if (!activeChatId || !chatsQuery.data) return;
    const chat = chatsQuery.data.find((item) => item.chat_id === activeChatId);
    const wsId = chat?.workspace_ids?.[0] ?? null;
    if (!wsId) {
      setSelectedWorkspace(null, null);
      return;
    }
    const wsName = workspaceQuery.data?.find((w) => w.workspace_id === wsId)?.name ?? null;
    setSelectedWorkspace(wsId, wsName);
  }, [activeChatId, chatsQuery.data, workspaceQuery.data, setSelectedWorkspace]);

  const onSend = async () => {
    const message = draft.trim();
    if (!message || sendMutation.isPending) return;
    setDraft("");
    let chatId = activeChatId;
    if (!chatId) {
      const created = await api.createChat(makeTitle(message), selectedWorkspaceId ? [selectedWorkspaceId] : []);
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
      const response = await sendMutation.mutateAsync({ chatId: chatId!, message });
      const assistantMessage: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      };
      setMessagesByChat((prev) => ({
        ...prev,
        [response.chat_id]: [...(prev[response.chat_id] || []), assistantMessage],
      }));
      await queryClient.invalidateQueries({ queryKey: ["chat-history", chatId] });
    } catch {
      // error rendered below
    }
  };

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
              <p>{message.content}</p>
              {message.role === "assistant" && message.sources?.length ? (
                <details className={styles.sources}>
                  <summary>Источники</summary>
                  <ul>
                    {message.sources.map((source, idx) => (
                      <li key={`${source.file_id || source.source}-${idx}`}>
                        {source.source || "Источник"}{" "}
                        {source.download_url ? (
                          <a href={source.download_url} target="_blank" rel="noreferrer">
                            скачать
                          </a>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </article>
          ))
        )}
        {sendMutation.isPending && <div className={styles.assistantMessage}>ИИ печатает...</div>}
        <div ref={messagesEndRef} />
      </div>
      <footer className={styles.composer}>
        <div className={styles.attachWrap}>
          <button className={styles.attachBtn} onClick={() => setShowWorkspacePicker((v) => !v)} title="Выбрать workspace">
            <Paperclip size={18} />
          </button>
          {selectedWorkspaceName ? (
            <span className={styles.workspaceChip}>
              {selectedWorkspaceName}
              <button
                className={styles.workspaceChipRemove}
                onClick={async () => {
                  if (activeChatId) {
                    await api.attachWorkspaces(activeChatId, []);
                  }
                  setSelectedWorkspace(null, null);
                }}
                title="Открепить workspace"
              >
                <X size={12} />
              </button>
            </span>
          ) : null}
          {showWorkspacePicker ? (
            <div className={styles.workspacePopover}>
              <Link to="/workspaces" className={styles.createWorkspaceRow} onClick={() => setShowWorkspacePicker(false)}>
                + Создать workspace
              </Link>
              <div className={styles.workspaceList}>
                {workspaceQuery.data?.map((workspace) => (
                  <button
                    key={workspace.workspace_id}
                    onClick={() => {
                      attachMutation.mutate({
                        workspaceId: workspace.workspace_id,
                        workspaceName: workspace.name,
                      });
                      setShowWorkspacePicker(false);
                    }}
                  >
                    {workspace.name}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <textarea
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
        <button className={styles.sendBtn} onClick={onSend} disabled={sendMutation.isPending || !draft.trim()}>
          <SendHorizonal size={16} />
        </button>
      </footer>
      {sendMutation.error ? <div className={styles.error}>{(sendMutation.error as Error).message}</div> : null}
    </section>
  );
}
