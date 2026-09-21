import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { authApi, type UserInput, type UserUpdateInput } from "../services/authApi";
import { ApiError } from "../services/apiClient";
import type { Role, User } from "../types/auth";
import styles from "./UsersPage.module.css";

/** RF-01, RF-03: alta, edición y desactivación de usuarios -- solo admin (ver App.tsx AdminRoute). */
function UsersPage() {
  const { token, user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<UserInput>({
    username: "",
    password: "",
    full_name: "",
    role_id: "",
    must_change_password: true,
  });

  const [editing, setEditing] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<UserUpdateInput>({});

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = () => {
    if (!token) return;
    setIsLoading(true);
    Promise.all([authApi.listUsers(token), authApi.listRoles(token)])
      .then(([usersData, rolesData]) => {
        setUsers(usersData);
        setRoles(rolesData);
      })
      .catch(() => setLoadError("No se pudo cargar la lista de usuarios."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [token]);

  const openCreate = () => {
    // Mínimo privilegio: un usuario nuevo parte como operador, salvo que el administrador elija otro rol.
    const defaultRole = roles.find((r) => r.name === "operador") ?? roles[0];
    setCreateForm({ username: "", password: "", full_name: "", role_id: defaultRole?.id ?? "", must_change_password: true });
    setFormError(null);
    setIsCreateOpen(true);
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      await authApi.createUser(token, createForm);
      setIsCreateOpen(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo crear el usuario.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const openEdit = (u: User) => {
    setEditing(u);
    setEditForm({ full_name: u.full_name ?? "", role_id: u.role.id, is_active: u.is_active, password: "" });
    setFormError(null);
  };

  const handleEdit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !editing) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      const payload = { ...editForm };
      if (!payload.password) delete payload.password;
      await authApi.updateUser(token, editing.id, payload);
      setEditing(null);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo actualizar el usuario.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnlock = async (u: User) => {
    if (!token) return;
    try {
      await authApi.unlockUser(token, u.id);
      load();
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "No se pudo desbloquear la cuenta.");
    }
  };

  /** RNF-03: hasta cuándo sigue bloqueada la cuenta por intentos fallidos (null si no lo está). */
  const lockedUntil = (u: User) =>
    u.locked_until && new Date(u.locked_until).getTime() > Date.now() ? new Date(u.locked_until) : null;

  return (
    <AppShell title="Usuarios">
      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <span className={styles.panelTitle}>Usuarios del sistema</span>
          <button type="button" className={styles.newButton} onClick={openCreate} disabled={roles.length === 0}>
            <Plus size={16} />
            Nuevo usuario
          </button>
        </div>

        {loadError && <p className={styles.empty}>{loadError}</p>}

        {users.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Nombre</th>
                <th>Rol</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="mono">{u.username}</td>
                  <td>{u.full_name ?? "—"}</td>
                  <td style={{ textTransform: "capitalize" }}>{u.role.name}</td>
                  <td>
                    <span className={`${styles.badge} ${u.is_active ? styles.badgeActivo : styles.badgeInactivo}`}>
                      {u.is_active ? "Activo" : "Inactivo"}
                    </span>
                    {lockedUntil(u) && (
                      <span className={`${styles.badge} ${styles.badgeBloqueado}`}>
                        Bloqueado hasta {lockedUntil(u)!.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    )}
                    {u.must_change_password && <span className={styles.note}>Debe cambiar su contraseña</span>}
                  </td>
                  <td className={styles.actionsCell}>
                    <button type="button" className={styles.editLink} onClick={() => openEdit(u)}>
                      Editar
                    </button>
                    {lockedUntil(u) && (
                      <button type="button" className={styles.editLink} onClick={() => handleUnlock(u)}>
                        Desbloquear
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isCreateOpen && (
        <Modal title="Nuevo usuario" onClose={() => setIsCreateOpen(false)}>
          <form onSubmit={handleCreate}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.field}>
              <label htmlFor="full_name">Nombre completo</label>
              <input
                id="full_name"
                value={createForm.full_name}
                onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                required
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="username">Usuario</label>
              <input
                id="username"
                value={createForm.username}
                onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                required
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="password">Contraseña</label>
              <input
                id="password"
                type="password"
                value={createForm.password}
                onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                pattern="(?=.*[A-Za-z])(?=.*\d).{8,}"
                title="Mínimo 8 caracteres, con al menos una letra y un número."
                minLength={8}
                required
              />
              <span className={styles.fieldHint}>Mínimo 8 caracteres, con al menos una letra y un número.</span>
            </div>
            <div className={styles.field}>
              <label htmlFor="role_id">Rol</label>
              <select
                id="role_id"
                value={createForm.role_id}
                onChange={(e) => setCreateForm({ ...createForm, role_id: e.target.value })}
                required
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id} style={{ textTransform: "capitalize" }}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>

            <label className={styles.checkRow}>
              <input
                type="checkbox"
                checked={createForm.must_change_password ?? false}
                onChange={(e) => setCreateForm({ ...createForm, must_change_password: e.target.checked })}
              />
              Pedir que cambie esta contraseña en su primer ingreso
            </label>

            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setIsCreateOpen(false)}>
                Cancelar
              </button>
              <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
                {isSubmitting ? "Guardando…" : "Crear usuario"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title={`Editar usuario — ${editing.username}`} onClose={() => setEditing(null)}>
          <form onSubmit={handleEdit}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.field}>
              <label htmlFor="edit_full_name">Nombre completo</label>
              <input
                id="edit_full_name"
                value={editForm.full_name ?? ""}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="edit_role_id">Rol</label>
              <select
                id="edit_role_id"
                value={editForm.role_id ?? ""}
                onChange={(e) => setEditForm({ ...editForm, role_id: e.target.value })}
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id} style={{ textTransform: "capitalize" }}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div className={styles.field}>
              <label htmlFor="edit_is_active">Estado de la cuenta</label>
              <select
                id="edit_is_active"
                value={editForm.is_active ? "activo" : "inactivo"}
                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === "activo" })}
                disabled={editing.id === currentUser?.id}
              >
                <option value="activo">Activo</option>
                <option value="inactivo">Inactivo</option>
              </select>
            </div>
            <div className={styles.field}>
              <label htmlFor="edit_password">Nueva contraseña (opcional)</label>
              <input
                id="edit_password"
                type="password"
                value={editForm.password ?? ""}
                onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                placeholder="Dejar en blanco para no cambiarla"
                pattern="(?=.*[A-Za-z])(?=.*\d).{8,}"
                title="Mínimo 8 caracteres, con al menos una letra y un número."
                minLength={8}
              />
              <span className={styles.fieldHint}>
                Si la cambias: mínimo 8 caracteres, con al menos una letra y un número. El usuario deberá cambiarla en
                su próximo ingreso.
              </span>
            </div>

            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setEditing(null)}>
                Cancelar
              </button>
              <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
                {isSubmitting ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </AppShell>
  );
}

export default UsersPage;
