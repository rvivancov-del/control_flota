// Llamadas HTTP a auth-service (vía el gateway): login, sesión actual, y
// gestión de usuarios/roles -- todas pasan por apiClient.ts.
import { apiClient } from "./apiClient";
import type { LoginResponse, Role, User } from "../types/auth";

export type UserInput = {
  username: string;
  password: string;
  full_name: string;
  role_id: string;
};

export type UserUpdateInput = Partial<{
  full_name: string;
  role_id: string;
  is_active: boolean;
  password: string;
}>;

export const authApi = {
  login: (username: string, password: string) =>
    apiClient.post<LoginResponse>("/auth/login", { username, password }),
  me: (token: string) => apiClient.get<User>("/auth/me", token),

  listRoles: (token: string) => apiClient.get<Role[]>("/auth/roles", token),
  listUsers: (token: string) => apiClient.get<User[]>("/auth/users", token),
  createUser: (token: string, payload: UserInput) =>
    apiClient.post<User>("/auth/users", payload, token),
  updateUser: (token: string, id: string, payload: UserUpdateInput) =>
    apiClient.patch<User>(`/auth/users/${id}`, payload, token),
};
