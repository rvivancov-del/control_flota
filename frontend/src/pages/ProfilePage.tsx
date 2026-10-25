/**
 * Ruta /perfil · todos los roles. Datos del usuario en sesión (GET /api/auth/me).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "../components/AppShell";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../services/authApi";
import type { User } from "../types/auth";
import styles from "./ProfilePage.module.css";

/** Datos de solo lectura del usuario en sesión (GET /auth/me). */
function ProfilePage() {
  const { token, user: cachedUser } = useAuth();
  const [user, setUser] = useState<User | null>(cachedUser);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    authApi
      .me(token)
      .then(setUser)
      .catch(() => setUser(cachedUser))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <AppShell title="Mi perfil">
      <div className={styles.panel}>
        {isLoading && !user ? (
          <p className={styles.value}>Cargando…</p>
        ) : (
          <>
            <div className={styles.row}>
              <span className={styles.label}>Usuario</span>
              <span className={styles.value}>{user?.username}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Nombre completo</span>
              <span className={styles.value}>{user?.full_name ?? "—"}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Rol</span>
              <span className={styles.value} style={{ textTransform: "capitalize" }}>
                {user?.role.name}
              </span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Estado de la cuenta</span>
              <span className={styles.value}>{user?.is_active ? "Activa" : "Inactiva"}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Contraseña</span>
              <Link to="/cambiar-clave" className={styles.value}>
                Cambiar contraseña
              </Link>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}

export default ProfilePage;
