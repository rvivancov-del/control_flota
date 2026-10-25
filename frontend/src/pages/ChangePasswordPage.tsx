/**
 * Ruta /cambiar-clave · todos los roles · RNF-02.
 * Cambio de contraseña obligatorio en el primer acceso. API: auth-service (POST /api/auth/change-password).
 */
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../services/authApi";
import { ApiError } from "../services/apiClient";
import styles from "./LoginPage.module.css";

// Misma regla que auth-service (RNF-02): 8 o más caracteres, con al menos una letra y un número.
const COMPLEXITY = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

/** RNF-02: cambio de contraseña. Es obligatorio (no hay menú ni otra salida que cerrar sesión)
 * cuando la cuenta lo tiene pendiente, p. ej. la clave inicial del administrador o una que otro
 * administrador fijó; para el resto de usuarios es voluntario y se abre desde "Mi perfil". */
function ChangePasswordPage() {
  const { token, user, applySession, logout } = useAuth();
  const navigate = useNavigate();
  const forced = Boolean(user?.must_change_password);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!COMPLEXITY.test(next)) {
      setError("La contraseña nueva debe tener al menos 8 caracteres, con letras y números.");
      return;
    }
    if (next !== confirm) {
      setError("La confirmación no coincide con la contraseña nueva.");
      return;
    }
    if (next === current) {
      setError("La contraseña nueva debe ser distinta de la actual.");
      return;
    }
    if (!token) return;
    setIsSubmitting(true);
    try {
      // El servidor devuelve un token nuevo, ya sin la marca de cambio pendiente.
      applySession(await authApi.changePassword(token, current, next));
      navigate(forced ? "/" : "/perfil", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <Logo size={76} tone="inverted" />
        <div className={styles.brandName}>FlotaControl</div>
        <p className={styles.slogan}>{forced ? "Antes de continuar, elige tu propia contraseña." : "Cambiar contraseña"}</p>
      </div>

      <form className={styles.card} onSubmit={handleSubmit}>
        <div className={styles.cardTitle}>{forced ? "Cambio de contraseña obligatorio" : "Cambiar contraseña"}</div>

        <div className={styles.field}>
          <label htmlFor="current_password">Contraseña actual</label>
          <input
            id="current_password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="new_password">Contraseña nueva</label>
          <input
            id="new_password"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="confirm_password">Repetir contraseña nueva</label>
          <input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
          <span style={{ fontSize: "0.78rem", color: "var(--ink-muted)" }}>
            Mínimo 8 caracteres, con al menos una letra y un número.
          </span>
        </div>

        {error && <p className={styles.error}>{error}</p>}

        <button type="submit" className={styles.submit} disabled={isSubmitting}>
          {isSubmitting ? "Guardando…" : "Cambiar contraseña"}
        </button>

        {forced ? (
          <button
            type="button"
            onClick={logout}
            style={{ background: "none", border: "none", color: "var(--ink-muted)", fontSize: "0.85rem", padding: 0 }}
          >
            Cerrar sesión
          </button>
        ) : (
          <Link to="/perfil" style={{ color: "var(--ink-muted)", fontSize: "0.85rem", textAlign: "center" }}>
            Cancelar
          </Link>
        )}
      </form>
    </div>
  );
}

export default ChangePasswordPage;
