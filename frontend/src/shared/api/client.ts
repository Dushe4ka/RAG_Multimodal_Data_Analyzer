import type {
  Chat,
  ChatMessageResponse,
  FileDoc,
  HistoryMessage,
  UploadResponse,
  UserProfile,
  Workspace,
} from "./types";

const rawHost = window.location.hostname || "localhost";
const apiHost = rawHost === "0.0.0.0" ? "127.0.0.1" : rawHost;
const API_BASE = `http://${apiHost}:8000`;

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(`Сетевая ошибка. API недоступно по ${API_BASE}`);
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const json = await response.json();
      detail = json.detail || json.message || detail;
    } catch {
      const text = await response.text();
      if (text) detail = text;
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  login: (login: string, password: string) =>
    request<{ message: string }>("/login", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    }),
  logout: () => request<{ message: string }>("/logout", { method: "POST" }),
  profile: () => request<UserProfile>("/profile/"),
  chats: () => request<Chat[]>("/chat/list"),
  createChat: (title: string, workspace_ids: string[] = []) =>
    request<Chat>("/chat/create", {
      method: "POST",
      body: JSON.stringify({ title, workspace_ids }),
    }),
  deleteChat: (chatId: string) => request<{ status: string }>(`/chat/${chatId}`, { method: "DELETE" }),
  renameChat: (chatId: string, title: string) =>
    request<{ status: string }>(`/chat/${chatId}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  chatHistory: (chatId: string) => request<HistoryMessage[]>(`/chat/${chatId}/history`),
  attachWorkspaces: (chatId: string, workspaceIds: string[]) =>
    request<{ status: string }>(`/chat/${chatId}/attach_workspaces`, {
      method: "POST",
      body: JSON.stringify({ workspace_ids: workspaceIds }),
    }),
  sendMessage: (chatId: string, message: string) =>
    request<ChatMessageResponse>(`/chat/${chatId}/message`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  myWorkspaces: () => request<Workspace[]>("/workspaces/my"),
  createWorkspace: (name: string, is_private: boolean) =>
    request<Workspace>("/workspaces/", {
      method: "POST",
      body: JSON.stringify({ name, is_private }),
    }),
  renameWorkspace: (workspaceId: string, name: string) =>
    request<{ status: string }>(`/workspaces/${workspaceId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteWorkspace: (workspaceId: string) =>
    request<{ status: string }>(`/workspaces/${workspaceId}`, { method: "DELETE" }),
  filesByWorkspace: (workspaceId: string) => request<FileDoc[]>(`/files/workspace/${workspaceId}`),
  uploadFile: async (workspaceId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>(`/files/upload/${workspaceId}`, { method: "POST", body: form });
  },
};
