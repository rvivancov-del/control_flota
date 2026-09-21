import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { ApiError } from "../services/apiClient";
import type { Vehicle, VehicleInput } from "../types/fleet";
import styles from "./VehiclesPage.module.css";

const STATUS_OPTIONS = ["activo", "mantenimiento", "inactivo"];

const EMPTY_FORM: VehicleInput = {
  plate: "",
  brand: "",
  model: "",
  year: new Date().getFullYear(),
  current_mileage_km: 0,
  status: "activo",
};

function badgeClass(status: string) {
  if (status === "activo") return `${styles.badge} ${styles.badgeActivo}`;
  if (status === "mantenimiento") return `${styles.badge} ${styles.badgeMantenimiento}`;
  return `${styles.badge} ${styles.badgeInactivo}`;
}

/** RF-04: alta, edición y consulta de vehículos de la flota. RF-03: solo el
 * administrador da de alta y edita; el operador consulta. */
function VehiclesPage() {
  const { token, isAdmin } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editing, setEditing] = useState<Vehicle | null>(null);
  const [form, setForm] = useState<VehicleInput>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadVehicles = () => {
    if (!token) return;
    setIsLoading(true);
    fleetApi
      .listVehicles(token)
      .then(setVehicles)
      .catch(() => setLoadError("No se pudo cargar la lista de vehículos."))
      .finally(() => setIsLoading(false));
  };

  useEffect(loadVehicles, [token]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEdit = (vehicle: Vehicle) => {
    setEditing(vehicle);
    setForm({
      plate: vehicle.plate,
      brand: vehicle.brand,
      model: vehicle.model,
      year: vehicle.year,
      current_mileage_km: vehicle.current_mileage_km,
      status: vehicle.status,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      if (editing) {
        await fleetApi.updateVehicle(token, editing.id, form);
      } else {
        await fleetApi.createVehicle(token, form);
      }
      setIsModalOpen(false);
      loadVehicles();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo guardar el vehículo.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell title="Vehículos">
      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <span className={styles.panelTitle}>Flota registrada</span>
          {isAdmin && (
            <button type="button" className={styles.newButton} onClick={openCreate}>
              <Plus size={16} />
              Nuevo vehículo
            </button>
          )}
        </div>

        {loadError && <p className={styles.empty}>{loadError}</p>}

        {!isLoading && vehicles.length === 0 && !loadError && (
          <p className={styles.empty}>Todavía no hay vehículos registrados.</p>
        )}

        {vehicles.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Placa</th>
                <th>Marca / modelo</th>
                <th>Año</th>
                <th>Km actual</th>
                <th>Estado</th>
                {isAdmin && <th></th>}
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.id}>
                  <td className="mono">{v.plate}</td>
                  <td>
                    {v.brand} {v.model}
                  </td>
                  <td className="mono">{v.year}</td>
                  <td className="mono">{v.current_mileage_km.toLocaleString("es-EC")}</td>
                  <td>
                    <span className={badgeClass(v.status)}>{v.status}</span>
                  </td>
                  {isAdmin && (
                    <td>
                      <button type="button" className={styles.editLink} onClick={() => openEdit(v)}>
                        Editar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isModalOpen && (
        <Modal title={editing ? "Editar vehículo" : "Nuevo vehículo"} onClose={() => setIsModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.field}>
              <label htmlFor="plate">Placa</label>
              <input
                id="plate"
                value={form.plate}
                disabled={Boolean(editing)}
                onChange={(e) => setForm({ ...form, plate: e.target.value.toUpperCase() })}
                required
              />
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="brand">Marca</label>
                <input
                  id="brand"
                  value={form.brand}
                  onChange={(e) => setForm({ ...form, brand: e.target.value })}
                  required
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="model">Modelo</label>
                <input
                  id="model"
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="year">Año</label>
                <input
                  id="year"
                  type="number"
                  value={form.year}
                  onChange={(e) => setForm({ ...form, year: Number(e.target.value) })}
                  required
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="mileage">Kilometraje actual</label>
                <input
                  id="mileage"
                  type="number"
                  min={0}
                  value={form.current_mileage_km}
                  onChange={(e) => setForm({ ...form, current_mileage_km: Number(e.target.value) })}
                  required
                />
              </div>
            </div>

            <div className={styles.field}>
              <label htmlFor="status">Estado</label>
              <select
                id="status"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setIsModalOpen(false)}>
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

export default VehiclesPage;
