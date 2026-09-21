// Se deriva del host con el que el navegador cargó la pagina (no un
// "localhost" fijo): si el conductor abre el enlace del QR desde la IP de
// red local de la computadora (p. ej. http://192.168.1.23:5173), las
// llamadas a la API deben ir a esa misma IP en el puerto del gateway, no a
// "localhost" -- que en el celular del conductor se refiere al propio
// celular y nunca encontraria el backend.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? `http://${window.location.hostname}:8080/api`;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** El `detail` de una respuesta de error de FastAPI no siempre es un
 * string: en un 422 de validación de Pydantic es un arreglo de objetos
 * `{msg, loc, ...}` — pasarlo tal cual a `Error(message)` lo convierte en
 * el literal "[object Object]" en vez de un mensaje legible. */
function extractErrorMessage(body: unknown, fallback: string): string {
  if (body == null || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        const msg = typeof item === "object" && item !== null ? (item as { msg?: unknown }).msg : undefined;
        const text = typeof msg === "string" ? msg : JSON.stringify(item);
        // Pydantic v2 antepone "Value error, " a los ValueError de un @field_validator.
        return text.replace(/^Value error,\s*/, "");
      })
      .join(" · ");
  }
  return fallback;
}

/** Evento que se emite cuando el servidor rechaza el token de la sesión (venció o la cuenta ya no es
 * válida): AuthContext cierra la sesión y ProtectedRoute lleva a /login. */
export const SESSION_EXPIRED_EVENT = "flotacontrol:session-expired";

// Mensajes con los que los servicios responden 401 por un token inválido. Un 401 de otro tipo (p. ej.
// "La contraseña actual no es correcta.") NO cierra la sesión.
const SESSION_REJECTED_DETAILS = ["Token inválido o expirado.", "Usuario inválido o inactivo."];

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  for (const [name, value] of Object.entries(extraHeaders)) {
    headers.set(name, value);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    if (response.status === 429) {
      // El gateway limita los intentos por minuto (RNF-03, RF-18) y responde sin JSON.
      throw new ApiError(429, "Demasiados intentos seguidos. Espera un minuto e inténtalo de nuevo.");
    }
    try {
      const body = await response.json();
      detail = extractErrorMessage(body, detail);
    } catch {
      // sin cuerpo JSON, se usa el statusText
    }
    if (response.status === 401 && token && SESSION_REJECTED_DETAILS.includes(detail)) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string, token?: string | null, extraHeaders?: Record<string, string>) =>
    request<T>(path, { method: "GET" }, token, extraHeaders),
  post: <T>(path: string, body: unknown, token?: string | null, extraHeaders?: Record<string, string>) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }, token, extraHeaders),
  patch: <T>(path: string, body: unknown, token?: string | null) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }, token),
};
