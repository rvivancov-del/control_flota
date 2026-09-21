import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import TruckIcon from "../components/TruckIcon";
import { SESSION_EXPIRED_FLAG, useAuth } from "../context/AuthContext";
import { ApiError } from "../services/apiClient";
import styles from "./LoginPage.module.css";

/** RF-02: formulario de inicio de sesión -- redirige al dashboard si ya hay sesión iniciada. */
function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Aviso de una sola vez cuando se llega aquí porque la sesión venció. Se lee sin efectos
  // secundarios (React puede ejecutar el inicializador dos veces) y se borra tras montar.
  const [sessionExpired] = useState(() => {
    try {
      return sessionStorage.getItem(SESSION_EXPIRED_FLAG) === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      sessionStorage.removeItem(SESSION_EXPIRED_FLAG);
    } catch {
      // nada que borrar
    }
  }, []);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <Logo size={76} tone="inverted" />
        <div className={styles.brandName}>FlotaControl</div>
        <p className={styles.slogan}>Cada kilómetro, bajo control.</p>

        <div className={styles.road}>
          <div className={styles.roadLine} />
          <div className={styles.truckWrap}>
            <TruckIcon size={64} />
          </div>
        </div>
      </div>

      <form className={styles.card} onSubmit={handleSubmit}>
        <div className={styles.cardTitle}>Iniciar sesión</div>

        <div className={styles.field}>
          <label htmlFor="username">Usuario</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {sessionExpired && !error && (
          <p className={styles.error}>Tu sesión venció. Ingresa de nuevo para continuar.</p>
        )}
        {error && <p className={styles.error}>{error}</p>}

        <button type="submit" className={styles.submit} disabled={isSubmitting}>
          {isSubmitting ? "Ingresando…" : "Ingresar"}
        </button>
      </form>

      <p className={styles.footer}>
        Sistema desarrollado por Rosa Margarita Vivanco Velez — Trabajo de titulación, UNEMI
      </p>
    </div>
  );
}

export default LoginPage;
