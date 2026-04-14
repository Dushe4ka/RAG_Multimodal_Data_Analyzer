import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "./app/AppLayout";
import { ProtectedRoute } from "./app/ProtectedRoute";
import { LoginPage } from "./features/auth/LoginPage";
import { ChatPage } from "./features/chat/ChatPage";
import { WorkspaceDetailPage } from "./features/files/WorkspaceDetailPage";
import { WorkspacesPage } from "./features/workspaces/WorkspacesPage";
import { AdminUsersPage } from "./features/admin/AdminUsersPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { ErrorBoundary } from "./shared/ui/ErrorBoundary";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <ErrorBoundary>
        <LoginPage />
      </ErrorBoundary>
    ),
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: (
          <ErrorBoundary>
            <AppLayout />
          </ErrorBoundary>
        ),
        children: [
          { index: true, element: <ChatPage /> },
          { path: "workspaces", element: <WorkspacesPage /> },
          { path: "workspaces/:workspaceId", element: <WorkspaceDetailPage /> },
          { path: "admin", element: <AdminUsersPage /> },
          { path: "profile", element: <ProfilePage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
