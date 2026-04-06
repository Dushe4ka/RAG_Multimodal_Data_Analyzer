import { useEffect, useState } from "react";
import { api } from "./api";

export default function App() {
  const [auth, setAuth] = useState({ login: "", password: "" });
  const [user, setUser] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [publicWs, setPublicWs] = useState([]);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [msg, setMsg] = useState("");
  const [messages, setMessages] = useState([]);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [newChatTitle, setNewChatTitle] = useState("");
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const [w, c] = await Promise.all([api.myWorkspaces(), api.listChats()]);
    setWorkspaces(w);
    setChats(c);
  }

  async function handleLogin() {
    setError("");
    setLoading(true);
    try {
      await api.login(auth.login, auth.password);
      const profile = await api.me();
      setUser(profile);
      await refresh();
    } catch (e) {
      setError(`Ошибка входа: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function createWorkspace() {
    if (!newWorkspaceName.trim()) return;
    await api.createWorkspace(newWorkspaceName, false);
    setNewWorkspaceName("");
    await refresh();
  }

  async function createChat() {
    const created = await api.createChat(
      newChatTitle || "Новый чат",
      selectedWorkspaceId ? [selectedWorkspaceId] : []
    );
    setNewChatTitle("");
    setActiveChatId(created.chat_id);
    await refresh();
  }

  async function sendMessage() {
    if (!activeChatId || !msg.trim()) return;
    const text = msg;
    setMsg("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    const resp = await api.sendMessage(activeChatId, text);
    setMessages((prev) => [...prev, { role: "assistant", text: resp.answer, sources: resp.sources }]);
  }

  useEffect(() => {
    if (!user) return;
    api.searchPublic("").then(setPublicWs).catch(() => {});
  }, [user]);

  if (!user) {
    return (
      <main className="container">
        <h1>Вход</h1>
        <input placeholder="Логин" value={auth.login} onChange={(e) => setAuth({ ...auth, login: e.target.value })} />
        <input
          placeholder="Пароль"
          type="password"
          value={auth.password}
          onChange={(e) => setAuth({ ...auth, password: e.target.value })}
        />
        <button onClick={handleLogin}>Войти</button>
        {loading ? <p>Выполняется вход...</p> : null}
        {error ? <p style={{ color: "crimson" }}>{error}</p> : null}
      </main>
    );
  }

  return (
    <main className="container">
      <h1>RAG Workspace Hub</h1>
      <p>Пользователь: {user.login}</p>

      <section>
        <h2>Workspaces</h2>
        <div className="row">
          <input
            placeholder="Название нового workspace"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
          />
          <button onClick={createWorkspace}>Создать workspace</button>
        </div>
        <ul>
          {workspaces.map((w) => (
            <li key={w.workspace_id}>
              {w.name} ({w.is_private ? "private" : "public"}) id={w.workspace_id}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Публичные workspaces</h2>
        <ul>
          {publicWs.map((w) => (
            <li key={w.workspace_id}>
              {w.name} <button onClick={() => api.addPublicWorkspace(w.workspace_id)}>Добавить в библиотеку</button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Чаты</h2>
        <div className="row">
          <input placeholder="Название чата" value={newChatTitle} onChange={(e) => setNewChatTitle(e.target.value)} />
          <select value={selectedWorkspaceId} onChange={(e) => setSelectedWorkspaceId(e.target.value)}>
            <option value="">Без workspace</option>
            {workspaces.map((w) => (
              <option key={w.workspace_id} value={w.workspace_id}>
                {w.name}
              </option>
            ))}
          </select>
          <button onClick={createChat}>Создать чат</button>
        </div>
        <ul>
          {chats.map((c) => (
            <li key={c.chat_id}>
              <button onClick={() => setActiveChatId(c.chat_id)}>{c.title}</button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Диалог</h2>
        <div className="row">
          <input placeholder="Сообщение" value={msg} onChange={(e) => setMsg(e.target.value)} />
          <button onClick={sendMessage}>Отправить</button>
        </div>
        <div className="chatBox">
          {messages.map((m, idx) => (
            <div key={idx} className={m.role}>
              <b>{m.role}:</b> {m.text}
              {m.sources && m.sources.length > 0 && (
                <ul>
                  {m.sources.map((s, i) => (
                    <li key={i}>
                      {s.source} {s.download_url ? <a href={s.download_url}>скачать источник</a> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
