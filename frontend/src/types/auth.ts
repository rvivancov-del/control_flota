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
  created_at: string | null;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};
