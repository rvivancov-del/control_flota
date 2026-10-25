/**
 * Guardas de navegación: exige sesión iniciada (RF-02) y obliga a cambiar la contraseña
 * inicial antes de usar el sistema (RNF-02).
 */
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export const CHANGE_PASSWORD_PATH = "/cambiar-clave";

/** Envuelve una ruta: si no hay sesión iniciada, redirige a /login; si la cuenta debe cambiar su
 * contraseña (RNF-02), a la pantalla de cambio, que es lo único que puede usar hasta hacerlo. */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const { pathname } = useLocation();

  if (isLoading) {
    return null;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (user?.must_change_password && pathname !== CHANGE_PASSWORD_PATH) {
    return <Navigate to={CHANGE_PASSWORD_PATH} replace />;
  }
  return <>{children}</>;
}

export default ProtectedRoute;
