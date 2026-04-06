import { Navigate, Outlet, useLocation } from "react-router-dom";

import { isUnauthorized, useSession } from "../features/auth/useSession";

export function ProtectedRoute() {
  const location = useLocation();
  const session = useSession();

  if (session.isLoading) return <div style={{ padding: 24 }}>Загрузка сессии...</div>;
  if (session.error && isUnauthorized(session.error)) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (session.error) return <div style={{ padding: 24 }}>Ошибка: {(session.error as Error).message}</div>;

  return <Outlet />;
}
