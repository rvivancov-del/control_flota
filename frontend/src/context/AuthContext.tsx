// Sesión del usuario (token JWT + datos básicos), persistida en localStorage
// para sobrevivir un refresh de página -- expuesta a toda la app vía useAuth().
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi } from "../services/authApi";
import { SESSION_EXPIRED_EVENT } from "../services/apiClient";
import type { LoginResponse, User } from "../types/auth";

const STORAGE_KEY = "flotacontrol.session";
/** Marca (por pestaña) para que la pantalla de ingreso avise una vez que la sesión venció. */
export const SESSION_EXPIRED_FLAG = "flotacontrol.session-expired";

type StoredSession = {
  token: string;
  user: User;
};

type AuthContextValue = {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  /** RF-03: solo el rol admin administra catálogo (vehículos, conductores, QR) y exporta reportes. */
  isAdmin: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  /** Reemplaza la sesión (token y usuario), p. ej. tras cambiar la contraseña. */
  applySession: (response: LoginResponse) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Recupera la sesión guardada en localStorage; null si no hay o está corrupta. */
function readStoredSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = readStoredSession();
    if (stored) {
      setToken(stored.token);
      setUser(stored.user);
    }
    setIsLoading(false);
  }, []);

  const applySession = (response: LoginResponse) => {
    setToken(response.access_token);
    setUser(response.user);
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ token: response.access_token, user: response.user }),
    );
  };

  const login = async (username: string, password: string) => {
    applySession(await authApi.login(username, password));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  // El servidor rechazó el token (venció o la cuenta ya no es válida): se cierra la sesión y se
  // vuelve al ingreso, en vez de dejar pantallas con errores de carga.
  useEffect(() => {
    const expireSession = () => {
      // Varias peticiones en vuelo pueden recibir el mismo 401: solo la primera encuentra sesión guardada.
      if (!localStorage.getItem(STORAGE_KEY)) return;
      try {
        sessionStorage.setItem(SESSION_EXPIRED_FLAG, "1");
      } catch {
        // sin almacenamiento: solo se pierde el aviso en la pantalla de ingreso
      }
      logout();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
    // logout solo usa setters estables y localStorage
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      isAdmin: user?.role.name === "admin",
      isLoading,
      login,
      applySession,
      logout,
    }),
    [token, user, isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Hook para leer sesión/token y llamar login/logout desde cualquier componente. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  }
  return ctx;
}
