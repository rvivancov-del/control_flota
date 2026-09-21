import { useEffect, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { describeUrgency } from "../utils/maintenanceAlert";
import { reportsApi } from "../services/reportsApi";
import { ApiError } from "../services/apiClient";
import type { Vehicle } from "../types/fleet";
import type { MaintenanceInput, MaintenanceRecord } from "../types/maintenance";
import type { MaintenancePriorityResponse } from "../types/reports";
import { ivaBreakdown, IVA_RATE_LABELS } from "../utils/tax";
import styles from "./MaintenancePage.module.css";

const TYPE_LABELS: Record<string, string> = {
  aceite: "Aceite",
  filtros: "Filtros",
  llantas: "Llantas",
  frenos: "Frenos",
  bocines: "Bocines",
  otro: "Otro",
};

const CATEGORY_LABELS: Record<string, string> = {
  preventivo: "Preventivo",
  correctivo: "Correctivo",
  programado_km: "Programado por km",
};

const STATUS_LABELS: Record<string, string> = {
  pendiente: "Pendiente",
  en_proceso: "En proceso",
  completado: "Completado",
};

function badgeClass(status: string) {
  const key = ({ pendiente: "Pendiente", en_proceso: "EnProceso", completado: "Completado" } as Record<string, string>)[status];
  return `${styles.badge} ${styles[`badge${key ?? "Pendiente"}`]}`;
}

type RecordWithPlate = MaintenanceRecord & { plate: string };

/** RF-11 a RF-13, RF-20: registros de mantenimiento por vehículo, alertas
 * por kilometraje vencido y el ranking de prioridad por AHP de 3 criterios. */
function MaintenancePage() {
  const { token } = useAuth();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [records, setRecords] = useState<RecordWithPlate[]>([]);
  const [alerts, setAlerts] = useState<RecordWithPlate[]>([]);
  const [priority, setPriority] = useState<MaintenancePriorityResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [vehicleFilter, setVehicleFilter] = useState("");

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<{ vehicle_id: string } & MaintenanceInput>({
    vehicle_id: "",
    maintenance_type: "aceite",
    category: "preventivo",
    scheduled_mileage_km: null,
  });

  const [completing, setCompleting] = useState<RecordWithPlate | null>(null);
  const [completeForm, setCompleteForm] = useState({
    performed_mileage_km: 0,
    performed_at: new Date().toISOString().slice(0, 10),
    cost: 0,
  });

  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = () => {
    if (!token) return;
    setIsLoading(true);
    fleetApi
      .listVehicles(token)
      .then(async (vehiclesData) => {
        setVehicles(vehiclesData);
        const perVehicle = await Promise.all(
          vehiclesData.map((v) =>
            fleetApi.listVehicleMaintenance(token, v.id).then((list) => list.map((r) => ({ ...r, plate: v.plate }))),
          ),
        );
        setRecords(perVehicle.flat());
        const alertsData = await fleetApi.listMaintenanceAlerts(token);
        setAlerts(
          alertsData.map((a) => ({ ...a, plate: vehiclesData.find((v) => v.id === a.vehicle_id)?.plate ?? "—" })),
        );
        setPriority(await reportsApi.maintenancePriority(token));
      })
      .catch(() => setLoadError("No se pudo cargar el mantenimiento."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [token]);

  const filteredRecords = records.filter((r) => !vehicleFilter || r.vehicle_id === vehicleFilter);

  const openCreate = () => {
    setCreateForm({ vehicle_id: vehicles[0]?.id ?? "", maintenance_type: "aceite", category: "preventivo", scheduled_mileage_km: null });
    setFormError(null);
    setIsCreateOpen(true);
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      const { vehicle_id, ...payload } = createForm;
      await fleetApi.createMaintenance(token, vehicle_id, payload);
      setIsCreateOpen(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo registrar el mantenimiento.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const openComplete = (record: RecordWithPlate) => {
    setCompleting(record);
    setCompleteForm({
      performed_mileage_km: record.scheduled_mileage_km ?? 0,
      performed_at: new Date().toISOString().slice(0, 10),
      cost: 0,
    });
    setFormError(null);
  };

  const handleComplete = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !completing) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      await fleetApi.completeMaintenance(token, completing.id, completeForm);
      setCompleting(null);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo completar el mantenimiento.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell title="Mantenimiento">
      {alerts.length > 0 && (
        <div className={styles.alertBanner}>
          <div className={styles.alertTitle}>⚠ Mantenimientos vencidos o próximos por kilometraje</div>
          {alerts.map((a) => (
            <div key={a.id} className={styles.alertItem}>
              {a.plate} — {TYPE_LABELS[a.maintenance_type] ?? a.maintenance_type} (programado a{" "}
              {a.scheduled_mileage_km?.toLocaleString("es-EC")} km) — {describeUrgency(a.urgency, a.km_remaining)}
            </div>
          ))}
        </div>
      )}

      {priority && priority.items.length > 0 && (
        <div className={styles.panel} style={{ marginBottom: "1.5rem" }}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Qué reparar primero</span>
          </div>
          <p className={styles.taxHint} style={{ marginBottom: "0.75rem" }}>
            Se combina la seguridad ({(priority.weights.seguridad * 100).toFixed(0)}%), la urgencia (
            {(priority.weights.urgencia * 100).toFixed(0)}%) y el costo ({(priority.weights.costo * 100).toFixed(0)}%)
            de cada vehículo para ordenar qué taller conviene atender primero.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Vehículo</th>
                <th>Tipo</th>
                <th>Km restante</th>
                <th>Seguridad</th>
                <th>Urgencia</th>
                <th>Costo</th>
                <th>Prioridad</th>
              </tr>
            </thead>
            <tbody>
              {priority.items.slice(0, 8).map((item, idx) => (
                <tr key={`${item.vehicle_id}-${item.maintenance_type}-${idx}`}>
                  <td className="mono">{item.vehicle_plate}</td>
                  <td>{TYPE_LABELS[item.maintenance_type] ?? item.maintenance_type}</td>
                  <td className="mono">{item.km_remaining ?? "—"}</td>
                  <td className="mono">{item.seguridad_score.toFixed(2)}</td>
                  <td className="mono">{item.urgencia_score.toFixed(2)}</td>
                  <td className="mono">{item.costo_score.toFixed(2)}</td>
                  <td className="mono" style={{ fontWeight: 700 }}>
                    {item.priority_score.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <span className={styles.panelTitle}>Registros de mantenimiento</span>
          <button type="button" className={styles.newButton} onClick={openCreate} disabled={vehicles.length === 0}>
            <Plus size={16} />
            Nuevo mantenimiento
          </button>
        </div>

        {vehicles.length === 0 && <p className={styles.empty}>Registra al menos un vehículo primero.</p>}

        {vehicles.length > 0 && (
          <div className={styles.filters}>
            <select value={vehicleFilter} onChange={(e) => setVehicleFilter(e.target.value)}>
              <option value="">Todos los vehículos</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plate}
                </option>
              ))}
            </select>
          </div>
        )}

        {loadError && <p className={styles.empty}>{loadError}</p>}
        {!isLoading && filteredRecords.length === 0 && !loadError && (
          <p className={styles.empty}>No hay registros de mantenimiento.</p>
        )}

        {filteredRecords.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Vehículo</th>
                <th>Tipo</th>
                <th>Categoría</th>
                <th>Km programado</th>
                <th>Costo (base + IVA)</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((r) => {
                const cost = r.cost != null ? Number(r.cost) : null;
                const breakdown = cost != null ? ivaBreakdown(cost, "mantenimiento") : null;
                return (
                  <tr key={r.id}>
                    <td className="mono">{r.plate}</td>
                    <td>{TYPE_LABELS[r.maintenance_type] ?? r.maintenance_type}</td>
                    <td>{CATEGORY_LABELS[r.category] ?? r.category}</td>
                    <td className="mono">{r.scheduled_mileage_km?.toLocaleString("es-EC") ?? "—"}</td>
                    <td className="mono">
                      {breakdown
                        ? `${breakdown.subtotal.toFixed(2)} + ${breakdown.iva.toFixed(2)} = ${breakdown.total.toFixed(2)}`
                        : "—"}
                    </td>
                    <td>
                      <span className={badgeClass(r.status)}>{STATUS_LABELS[r.status] ?? r.status}</span>
                    </td>
                    <td>
                      {r.status !== "completado" && (
                        <button type="button" className={styles.completeLink} onClick={() => openComplete(r)}>
                          Completar
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {isCreateOpen && (
        <Modal title="Nuevo mantenimiento" onClose={() => setIsCreateOpen(false)}>
          <form onSubmit={handleCreate}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.field}>
              <label htmlFor="vehicle_id">Vehículo</label>
              <select
                id="vehicle_id"
                value={createForm.vehicle_id}
                onChange={(e) => setCreateForm({ ...createForm, vehicle_id: e.target.value })}
                required
              >
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="maintenance_type">Tipo</label>
                <select
                  id="maintenance_type"
                  value={createForm.maintenance_type}
                  onChange={(e) => setCreateForm({ ...createForm, maintenance_type: e.target.value })}
                >
                  {Object.entries(TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.field}>
                <label htmlFor="category">Categoría</label>
                <select
                  id="category"
                  value={createForm.category}
                  onChange={(e) => setCreateForm({ ...createForm, category: e.target.value })}
                >
                  {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className={styles.field}>
              <label htmlFor="scheduled_mileage_km">Kilometraje programado (opcional)</label>
              <input
                id="scheduled_mileage_km"
                type="number"
                min={0}
                value={createForm.scheduled_mileage_km ?? ""}
                onChange={(e) =>
                  setCreateForm({
                    ...createForm,
                    scheduled_mileage_km: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </div>

            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setIsCreateOpen(false)}>
                Cancelar
              </button>
              <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
                {isSubmitting ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {completing && (
        <Modal title={`Completar mantenimiento — ${completing.plate}`} onClose={() => setCompleting(null)}>
          <form onSubmit={handleComplete}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.field}>
              <label htmlFor="performed_mileage_km">Kilometraje al momento del mantenimiento</label>
              <input
                id="performed_mileage_km"
                type="number"
                min={0}
                value={completeForm.performed_mileage_km}
                onChange={(e) => setCompleteForm({ ...completeForm, performed_mileage_km: Number(e.target.value) })}
                required
              />
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="performed_at">Fecha</label>
                <input
                  id="performed_at"
                  type="date"
                  value={completeForm.performed_at}
                  onChange={(e) => setCompleteForm({ ...completeForm, performed_at: e.target.value })}
                  required
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="cost">Costo (USD)</label>
                <input
                  id="cost"
                  type="number"
                  min={0}
                  step="0.01"
                  value={completeForm.cost}
                  onChange={(e) => setCompleteForm({ ...completeForm, cost: Number(e.target.value) })}
                  required
                />
                {completeForm.cost > 0 && (
                  <span className={styles.taxHint}>
                    {(() => {
                      const b = ivaBreakdown(completeForm.cost, "mantenimiento");
                      return `Base imponible USD ${b.subtotal.toFixed(2)} + IVA (${IVA_RATE_LABELS.mantenimiento}) USD ${b.iva.toFixed(2)}`;
                    })()}
                  </span>
                )}
              </div>
            </div>

            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setCompleting(null)}>
                Cancelar
              </button>
              <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
                {isSubmitting ? "Guardando…" : "Marcar completado"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </AppShell>
  );
}

export default MaintenancePage;
