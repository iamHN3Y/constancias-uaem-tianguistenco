import { Navigate, Outlet } from "react-router-dom";
import { useSession } from "../hooks/useSession";

export function RequireAuth() {
  const { data, isLoading, isError } = useSession();
  if (isLoading) return null;
  if (isError || !data) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function RequireAdmin() {
  const { data, isLoading, isError } = useSession();
  if (isLoading) return null;
  if (isError || !data) return <Navigate to="/login" replace />;
  if (!data.es_admin) return <Navigate to="/" replace />;
  return <Outlet />;
}
