const rawHost = window.location.hostname || "localhost";
const apiHost = rawHost === "0.0.0.0" ? "127.0.0.1" : rawHost;
const API_BASE = `http://${apiHost}:8000`;

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    throw new Error(`Сетевая ошибка: API недоступно по ${API_BASE}. Убедись, что backend запущен на 8000 порту.`);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status} (${path})`);
  }
  return response.json();
}

export const api = {
  login: (login, password) =>
    request("/login", { method: "POST", body: JSON.stringify({ login, password }) }),
  me: () => request("/profile/"),
  createWorkspace: (name, is_private) =>
    request("/workspaces/", { method: "POST", body: JSON.stringify({ name, is_private }) }),
  myWorkspaces: () => request("/workspaces/my"),
  library: () => request("/workspaces/library"),
  searchPublic: (query) =>
    request("/workspaces/search_public", { method: "POST", body: JSON.stringify({ query }) }),
  addPublicWorkspace: (workspaceId) =>
    request(`/workspaces/${workspaceId}/add_to_library`, { method: "POST" }),
  createChat: (title, workspace_ids) =>
    request("/chat/create", { method: "POST", body: JSON.stringify({ title, workspace_ids }) }),
  listChats: () => request("/chat/list"),
  sendMessage: (chatId, message) =>
    request(`/chat/${chatId}/message`, { method: "POST", body: JSON.stringify({ message }) }),
};
