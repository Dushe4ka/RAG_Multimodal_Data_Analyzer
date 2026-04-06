import { create } from "zustand";

type UiState = {
  sidebarCollapsed: boolean;
  activeChatId: string | null;
  selectedWorkspaceId: string | null;
  selectedWorkspaceName: string | null;
  setSidebarCollapsed: (value: boolean) => void;
  setActiveChatId: (id: string | null) => void;
  setSelectedWorkspace: (workspaceId: string | null, workspaceName: string | null) => void;
};

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  activeChatId: null,
  selectedWorkspaceId: null,
  selectedWorkspaceName: null,
  setSidebarCollapsed: (value) => set({ sidebarCollapsed: value }),
  setActiveChatId: (id) => set({ activeChatId: id }),
  setSelectedWorkspace: (workspaceId, workspaceName) =>
    set({ selectedWorkspaceId: workspaceId, selectedWorkspaceName: workspaceName }),
}));
