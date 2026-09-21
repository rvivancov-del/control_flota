// Llamadas HTTP a auth-service (vía el gateway): login, sesión actual, y
// gestión de usuarios/roles -- todas pasan por apiClient.ts.
import { apiClient } from "./apiClient";
import type { LoginResponse, Role, User } from "../types/auth";

export type UserInput = {
  username: string;
  password: string;
  full_name: string;
  role_id: string;
  /** El usuario deberá cambiar la contraseña inicial en su primer ingreso. */
  must_change_password?: boolean;
};

export type UserUpdateInput = Partial<{
  full_name: string;
  role_id: string;
  is_active: boolean;
  password: string;
  must_change_password: boolean;
}>;

export const authApi = {
  login: (username: string, password: string) =>
    apiClient.post<LoginResponse>("/auth/login", { username, password }),
  me: (token: string) => apiClient.get<User>("/auth/me", token),
  /** RNF-02: cambia la contraseña del usuario en sesión y devuelve una sesión nueva. */
  changePassword: (token: string, currentPassword: string, newPassword: string) =>
    apiClient.post<LoginResponse>(
      "/auth/change-password",
      { current_password: currentPassword, new_password: newPassword },
      token,
    ),
  /** RNF-03: quita el bloqueo temporal de una cuenta sin esperar a que venza. */
  unlockUser: (token: string, id: string) => apiClient.post<User>(`/auth/users/${id}/unlock`, {}, token),

  listRoles: (token: string) => apiClient.get<Role[]>("/auth/roles", token),
  listUsers: (token: string) => apiClient.get<User[]>("/auth/users", token),
  createUser: (token: string, payload: UserInput) =>
    apiClient.post<User>("/auth/users", payload, token),
  updateUser: (token: string, id: string, payload: UserUpdateInput) =>
    apiClient.patch<User>(`/auth/users/${id}`, payload, token),
};
