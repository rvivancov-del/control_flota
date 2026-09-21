// Tipos que reflejan los esquemas de auth-service (Pydantic -> TS a mano).
export type Role = {
  id: string;
  name: "admin" | "operador" | string;
};

export type User = {
  id: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  role: Role;
  /** RNF-03: fin del bloqueo temporal por intentos fallidos; null si la cuenta no está bloqueada. */
  locked_until: string | null;
  /** RNF-02: debe cambiar su contraseña antes de usar el sistema. */
  must_change_password: boolean;
  created_at: string | null;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};
