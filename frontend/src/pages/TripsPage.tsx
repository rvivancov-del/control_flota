import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { ApiError } from "../services/apiClient";
import type { Driver, Vehicle } from "../types/fleet";
import type { Trip, TripInput } from "../types/trips";
import styles from "./TripsPage.module.css";

const STATUS_LABELS: Record<string, string> = {
  planificado: "Planificado",
  en_curso: "En curso",
  completado: "Completado",
  anulado: "Anulado",
};

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

/** RF-06, RF-14: registro de viajes y su consulta/filtrado por vehículo,
 * conductor o rango de fechas. El detalle (gastos, cierre) está en TripDetailPage. */
function TripsPage() {
  const { token } = useAuth();
  const [trips, setTrips] = useState<Trip[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState("");
  const [vehicleFilter, setVehicleFilter] = useState("");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form, setForm] = useState<TripInput>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = () => {
    if (!token) return;
    setIsLoading(true);
    Promise.all([fleetApi.listTrips(token), fleetApi.listVehicles(token), fleetApi.listDrivers(token)])
      .then(([tripsData, vehiclesData, driversData]) => {
        setTrips(tripsData);
        setVehicles(vehiclesData);
        setDrivers(driversData);
      })
      .catch(() => setLoadError("No se pudo cargar la lista de viajes."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [token]);

  const vehicleMap = useMemo(() => new Map(vehicles.map((v) => [v.id, v])), [vehicles]);
  const driverMap = useMemo(() => new Map(drivers.map((d) => [d.id, d])), [drivers]);

  const filteredTrips = trips.filter((t) => {
    if (statusFilter && t.status !== statusFilter) return false;
    if (vehicleFilter && t.vehicle_id !== vehicleFilter) return false;
    return true;
  });

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

        <div className={styles.filters}>
          <select value={vehicleFilter} onChange={(e) => setVehicleFilter(e.target.value)}>
            <option value="">Todos los vehículos</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plate}
              </option>
            ))}
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Todos los estados</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {loadError && <p className={styles.empty}>{loadError}</p>}
        {!isLoading && filteredTrips.length === 0 && !loadError && (
          <p className={styles.empty}>No hay viajes que coincidan con el filtro.</p>
        )}

        {filteredTrips.length > 0 && (
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
              {filteredTrips.map((t) => (
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
