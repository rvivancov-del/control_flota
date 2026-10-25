/**
 * Ruta /viajes · todos los roles · RF-06, RF-14.
 * Registro y consulta filtrada de viajes. API: fleet-core-service (/api/fleet/trips).
 */
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { ApiError } from "../services/apiClient";
import type { Driver, Vehicle } from "../types/fleet";
import type { ExpenseRow, Trip, TripInput } from "../types/trips";
import styles from "./TripsPage.module.css";

const STATUS_LABELS: Record<string, string> = {
  planificado: "Planificado",
  en_curso: "En curso",
  completado: "Completado",
  anulado: "Anulado",
};

const EXPENSE_TYPE_LABELS: Record<string, string> = {
  combustible: "Combustible",
  peaje: "Peaje",
  alimentacion: "Alimentación",
};

type Tab = "viajes" | "gastos";

/** Máximo de gastos que se piden al servidor por consulta; si llega a este tope se avisa. */
const EXPENSE_LIMIT = 1000;

/** RF-14: filtros de consulta; los vacíos no se envían. */
type Filters = { vehicle_id: string; driver_id: string; status_filter: string; type: string; date_from: string; date_to: string };
const NO_FILTERS: Filters = { vehicle_id: "", driver_id: "", status_filter: "", type: "", date_from: "", date_to: "" };

function badgeClass(status: string) {
  const key = ({ planificado: "Planificado", en_curso: "EnCurso", completado: "Completado", anulado: "Anulado" } as Record<string, string>)[status];
  return `${styles.badge} ${styles[`badge${key ?? "Planificado"}`]}`;
}

function emptyForm(): TripInput {
  return {
    vehicle_id: "",
    driver_id: "",
    origin: "",
    destination: "",
    departure_at: new Date().toISOString().slice(0, 16),
    start_mileage_km: 0,
  };
}

/** RF-06, RF-14: registro de viajes y consulta de viajes y gastos filtrada por
 * vehículo, conductor o rango de fechas (el filtrado lo hace el servidor). El
 * detalle de un viaje (gastos, cierre) está en TripDetailPage. */
function TripsPage() {
  const { token } = useAuth();
  const [trips, setTrips] = useState<Trip[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>("viajes");
  const [expenses, setExpenses] = useState<ExpenseRow[]>([]);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const setFilter = (name: keyof Filters, value: string) => setFilters((f) => ({ ...f, [name]: value }));

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form, setForm] = useState<TripInput>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!token) return;
    Promise.all([fleetApi.listVehicles(token), fleetApi.listDrivers(token)])
      .then(([vehiclesData, driversData]) => {
        setVehicles(vehiclesData);
        setDrivers(driversData);
      })
      .catch(() => setLoadError("No se pudo cargar el catálogo de vehículos y conductores."));
  }, [token]);

  const load = () => {
    if (!token) return;
    setIsLoading(true);
    setLoadError(null);
    const { vehicle_id, driver_id, status_filter, type, date_from, date_to } = filters;
    const request =
      tab === "viajes"
        ? fleetApi.listTrips(token, { vehicle_id, driver_id, status_filter, date_from, date_to }).then(setTrips)
        : fleetApi
            .queryExpenses(token, { vehicle_id, driver_id, type, date_from, date_to, limit: String(EXPENSE_LIMIT) })
            .then(setExpenses);
    request
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "No se pudo cargar la consulta."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [token, tab, filters]);

  const vehicleMap = useMemo(() => new Map(vehicles.map((v) => [v.id, v])), [vehicles]);
  const driverMap = useMemo(() => new Map(drivers.map((d) => [d.id, d])), [drivers]);

  const openCreate = () => {
    setForm(emptyForm());
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      await fleetApi.createTrip(token, {
        ...form,
        departure_at: new Date(form.departure_at).toISOString(),
      });
      setIsModalOpen(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo registrar el viaje.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell title="Viajes">
      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <span className={styles.panelTitle}>Viajes</span>
          <button type="button" className={styles.newButton} onClick={openCreate} disabled={vehicles.length === 0 || drivers.length === 0}>
            <Plus size={16} />
            Nuevo viaje
          </button>
        </div>

        {vehicles.length === 0 || drivers.length === 0 ? (
          <p className={styles.empty}>
            Registra al menos un vehículo y un conductor antes de crear un viaje.
          </p>
        ) : null}

        <div className={styles.tabs} role="tablist">
          {(["viajes", "gastos"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`}
              onClick={() => setTab(t)}
            >
              {t === "viajes" ? "Viajes" : "Gastos"}
            </button>
          ))}
        </div>

        <div className={styles.filters}>
          <select aria-label="Vehículo" value={filters.vehicle_id} onChange={(e) => setFilter("vehicle_id", e.target.value)}>
            <option value="">Todos los vehículos</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plate}
              </option>
            ))}
          </select>
          <select aria-label="Conductor" value={filters.driver_id} onChange={(e) => setFilter("driver_id", e.target.value)}>
            <option value="">Todos los conductores</option>
            {drivers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name}
              </option>
            ))}
          </select>
          {tab === "viajes" ? (
            <select aria-label="Estado" value={filters.status_filter} onChange={(e) => setFilter("status_filter", e.target.value)}>
              <option value="">Todos los estados</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          ) : (
            <select aria-label="Tipo de gasto" value={filters.type} onChange={(e) => setFilter("type", e.target.value)}>
              <option value="">Todos los tipos</option>
              {Object.entries(EXPENSE_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          )}
          <label className={styles.dateFilter}>
            Desde
            <input type="date" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} />
          </label>
          <label className={styles.dateFilter}>
            Hasta
            <input type="date" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} />
          </label>
          <button type="button" className={styles.clearFilters} onClick={() => setFilters(NO_FILTERS)}>
            Limpiar
          </button>
        </div>

        {loadError && <p className={styles.empty}>{loadError}</p>}
        {!isLoading && !loadError && (tab === "viajes" ? trips : expenses).length === 0 && (
          <p className={styles.empty}>
            {tab === "viajes" ? "No hay viajes que coincidan con el filtro." : "No hay gastos que coincidan con el filtro."}
          </p>
        )}

        {tab === "gastos" && expenses.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Monto</th>
                <th>Litros</th>
                <th>Ubicación</th>
                <th>Vehículo</th>
                <th>Conductor</th>
                <th>Viaje</th>
              </tr>
            </thead>
            <tbody>
              {expenses.map((e) => (
                <tr key={e.id}>
                  <td className="mono">{e.expense_date}</td>
                  <td>{EXPENSE_TYPE_LABELS[e.type] ?? e.type}</td>
                  <td className="mono">
                    {e.currency} {Number(e.amount).toFixed(2)}
                  </td>
                  <td className="mono">{e.liters != null ? Number(e.liters).toFixed(2) : "—"}</td>
                  <td>{e.location ?? "—"}</td>
                  <td className="mono">{vehicleMap.get(e.vehicle_id)?.plate ?? "—"}</td>
                  <td>{driverMap.get(e.driver_id)?.full_name ?? "—"}</td>
                  <td>
                    <Link to={`/viajes/${e.trip_id}`} className={styles.rowLink}>
                      {e.origin} → {e.destination}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "gastos" && expenses.length >= EXPENSE_LIMIT && (
          <p className={styles.empty}>
            Se muestran los {EXPENSE_LIMIT} gastos más recientes. Acote la consulta con fechas o filtros para ver otros.
          </p>
        )}

        {tab === "viajes" && trips.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Ruta</th>
                <th>Vehículo</th>
                <th>Conductor</th>
                <th>Salida</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {trips.map((t) => (
                <tr key={t.id}>
                  <td>
                    {t.origin} → {t.destination}
                  </td>
                  <td className="mono">{vehicleMap.get(t.vehicle_id)?.plate ?? "—"}</td>
                  <td>{driverMap.get(t.driver_id)?.full_name ?? "—"}</td>
                  <td className="mono">{new Date(t.departure_at).toLocaleString("es-EC")}</td>
                  <td>
                    <span className={badgeClass(t.status)}>{STATUS_LABELS[t.status] ?? t.status}</span>
                  </td>
                  <td>
                    <Link to={`/viajes/${t.id}`} className={styles.rowLink}>
                      Ver
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isModalOpen && (
        <Modal title="Nuevo viaje" onClose={() => setIsModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="vehicle_id">Vehículo</label>
                <select
                  id="vehicle_id"
                  value={form.vehicle_id}
                  onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}
                  required
                >
                  <option value="" disabled>
                    Selecciona…
                  </option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.plate}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.field}>
                <label htmlFor="driver_id">Conductor</label>
                <select
                  id="driver_id"
                  value={form.driver_id}
                  onChange={(e) => setForm({ ...form, driver_id: e.target.value })}
                  required
                >
                  <option value="" disabled>
                    Selecciona…
                  </option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="origin">Origen</label>
                <input
                  id="origin"
                  value={form.origin}
                  onChange={(e) => setForm({ ...form, origin: e.target.value })}
                  required
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="destination">Destino</label>
                <input
                  id="destination"
                  value={form.destination}
                  onChange={(e) => setForm({ ...form, destination: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="departure_at">Fecha y hora de salida</label>
                <input
                  id="departure_at"
                  type="datetime-local"
                  value={form.departure_at}
                  onChange={(e) => setForm({ ...form, departure_at: e.target.value })}
                  required
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="start_mileage_km">Km inicial</label>
                <input
                  id="start_mileage_km"
                  type="number"
                  min={0}
                  value={form.start_mileage_km}
                  onChange={(e) => setForm({ ...form, start_mileage_km: Number(e.target.value) })}
                  required
                />
              </div>
            </div>

            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setIsModalOpen(false)}>
                Cancelar
              </button>
              <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
                {isSubmitting ? "Guardando…" : "Registrar viaje"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </AppShell>
  );
}

export default TripsPage;
