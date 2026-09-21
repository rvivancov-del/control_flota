import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { describeUrgency } from "../utils/maintenanceAlert";
import { ApiError } from "../services/apiClient";
import type { Driver, Vehicle } from "../types/fleet";
import type { Expense, ExpenseInput, MaintenanceAlertBrief, Trip } from "../types/trips";
import { ivaBreakdown, IVA_RATE_LABELS, type TaxableCategory } from "../utils/tax";
import styles from "./TripDetailPage.module.css";

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

function badgeClass(status: string) {
  const key = ({ planificado: "Planificado", en_curso: "EnCurso", completado: "Completado", anulado: "Anulado" } as Record<string, string>)[status];
  return `${styles.badge} ${styles[`badge${key ?? "Planificado"}`]}`;
}

/** RF-07 a RF-10: detalle de un viaje -- iniciar/anular, registrar gastos
 * (combustible, peaje, alimentación) y cerrar con kilometraje final. */
function TripDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();

  const [trip, setTrip] = useState<Trip | null>(null);
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [driver, setDriver] = useState<Driver | null>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<MaintenanceAlertBrief[]>([]);

  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);
  const [closeForm, setCloseForm] = useState({ end_mileage_km: 0, arrival_at: "", revenue: "" });
  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);
  const [expenseForm, setExpenseForm] = useState<Omit<ExpenseInput, "liters"> & { liters: number | "" }>({
    type: "combustible",
    amount: 0,
    liters: "",
    currency: "USD",
    expense_date: new Date().toISOString().slice(0, 10),
    notes: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = () => {
    if (!token || !id) return;
    setIsLoading(true);
    Promise.all([
      fleetApi.getTrip(token, id),
      fleetApi.listExpenses(token, id),
      fleetApi.listVehicles(token),
      fleetApi.listDrivers(token),
    ])
      .then(([tripData, expensesData, vehicles, drivers]) => {
        setTrip(tripData);
        setExpenses(expensesData);
        setVehicle(vehicles.find((v) => v.id === tripData.vehicle_id) ?? null);
        setDriver(drivers.find((d) => d.id === tripData.driver_id) ?? null);
        setCloseForm({
          end_mileage_km: tripData.start_mileage_km,
          arrival_at: new Date().toISOString().slice(0, 16),
          revenue: "",
        });
      })
      .catch(() => setError("No se pudo cargar el viaje."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [token, id]);

  const handleStart = async () => {
    if (!token || !trip) return;
    setActionError(null);
    try {
      const updated = await fleetApi.startTrip(token, trip.id);
      setTrip(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "No se pudo iniciar el viaje.");
    }
  };

  const handleCancel = async () => {
    if (!token || !trip) return;
    setActionError(null);
    try {
      const updated = await fleetApi.cancelTrip(token, trip.id);
      setTrip(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "No se pudo anular el viaje.");
    }
  };

  const handleClose = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !trip) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      const result = await fleetApi.closeTrip(token, trip.id, {
        end_mileage_km: closeForm.end_mileage_km,
        arrival_at: new Date(closeForm.arrival_at).toISOString(),
        ...(closeForm.revenue !== "" ? { revenue: Number(closeForm.revenue) } : {}),
      });
      setTrip(result.trip);
      setAlerts(result.maintenance_alerts);
      setIsCloseModalOpen(false);
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "No se pudo cerrar el viaje.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddExpense = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || !trip) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      await fleetApi.createExpense(token, trip.id, {
        ...expenseForm,
        liters: expenseForm.liters === "" ? undefined : expenseForm.liters,
      });
      setIsExpenseModalOpen(false);
      setExpenseForm({ type: "combustible", amount: 0, liters: "", currency: "USD", expense_date: new Date().toISOString().slice(0, 10), notes: "" });
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "No se pudo registrar el gasto.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading || !trip) {
    return (
      <AppShell title="Viaje">
        <p className={styles.empty}>{error ?? "Cargando…"}</p>
      </AppShell>
    );
  }

  return (
    <AppShell title="Detalle de viaje">
      <div className={styles.grid}>
        <Link to="/viajes" className={styles.backLink}>
          ← Volver a viajes
        </Link>

        {alerts.length > 0 && (
          <div className={styles.alertBanner}>
            <div className={styles.alertTitle}>⚠ Mantenimiento vencido o próximo por kilometraje</div>
            {alerts.map((a) => (
              <div key={a.id} className={styles.alertItem}>
                {a.maintenance_type} — programado a {a.scheduled_mileage_km?.toLocaleString("es-EC")} km — {describeUrgency(a.urgency, a.km_remaining)}
              </div>
            ))}
          </div>
        )}

        <div className={styles.panel}>
          <div className={styles.headRow}>
            <span className={styles.route}>
              {trip.origin} → {trip.destination}
            </span>
            <span className={badgeClass(trip.status)}>{STATUS_LABELS[trip.status] ?? trip.status}</span>
          </div>

          {actionError && <p className={styles.formError}>{actionError}</p>}

          <div className={styles.infoGrid}>
            <div>
              <div className={styles.infoLabel}>Vehículo</div>
              <div className={styles.infoValue}>{vehicle?.plate ?? "—"}</div>
            </div>
            <div>
              <div className={styles.infoLabel}>Conductor</div>
              <div className={styles.infoValue}>{driver?.full_name ?? "—"}</div>
            </div>
            <div>
              <div className={styles.infoLabel}>Salida</div>
              <div className={styles.infoValue}>{new Date(trip.departure_at).toLocaleString("es-EC")}</div>
            </div>
            <div>
              <div className={styles.infoLabel}>Llegada</div>
              <div className={styles.infoValue}>
                {trip.arrival_at ? new Date(trip.arrival_at).toLocaleString("es-EC") : "—"}
              </div>
            </div>
            <div>
              <div className={styles.infoLabel}>Km inicial</div>
              <div className={styles.infoValue}>{trip.start_mileage_km.toLocaleString("es-EC")}</div>
            </div>
            <div>
              <div className={styles.infoLabel}>Km final</div>
              <div className={styles.infoValue}>
                {trip.end_mileage_km != null ? trip.end_mileage_km.toLocaleString("es-EC") : "—"}
              </div>
            </div>
            <div>
              <div className={styles.infoLabel}>Km recorridos</div>
              <div className={styles.infoValue}>
                {trip.km_recorridos != null ? trip.km_recorridos.toLocaleString("es-EC") : "—"}
              </div>
            </div>
            <div>
              <div className={styles.infoLabel}>Ingreso del viaje</div>
              <div className={styles.infoValue}>
                {trip.revenue != null ? `$${Number(trip.revenue).toFixed(2)}` : "—"}
              </div>
            </div>
          </div>

          <div className={styles.actions}>
            {trip.status === "planificado" && (
              <>
                <button type="button" className={styles.actionPrimary} onClick={handleStart}>
                  Iniciar viaje
                </button>
                <button type="button" className={styles.actionDanger} onClick={handleCancel}>
                  Anular
                </button>
              </>
            )}
            {trip.status === "en_curso" && (
              <>
                <button type="button" className={styles.actionPrimary} onClick={() => setIsCloseModalOpen(true)}>
                  Cerrar viaje
                </button>
                <button type="button" className={styles.actionDanger} onClick={handleCancel}>
                  Anular
                </button>
              </>
            )}
          </div>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Gastos del viaje</span>
            <button type="button" className={styles.newButton} onClick={() => setIsExpenseModalOpen(true)}>
              <Plus size={15} />
              Agregar gasto
            </button>
          </div>

          {expenses.length === 0 ? (
            <p className={styles.empty}>Todavía no hay gastos registrados para este viaje.</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Monto</th>
                  <th>Base + IVA</th>
                  <th>Litros</th>
                  <th>Fecha</th>
                  <th>Notas</th>
                </tr>
              </thead>
              <tbody>
                {expenses.map((e) => {
                  const category = e.type as TaxableCategory;
                  const breakdown = ivaBreakdown(Number(e.amount), category);
                  return (
                    <tr key={e.id}>
                      <td>{EXPENSE_TYPE_LABELS[e.type] ?? e.type}</td>
                      <td className="mono">
                        {e.currency} {Number(e.amount).toFixed(2)}
                      </td>
                      <td className="mono">
                        {breakdown.rate === 0
                          ? IVA_RATE_LABELS[category]
                          : `${breakdown.subtotal.toFixed(2)} + ${breakdown.iva.toFixed(2)}`}
                      </td>
                      <td className="mono">{e.liters != null ? Number(e.liters).toFixed(2) : "—"}</td>
                      <td className="mono">{e.expense_date}</td>
                      <td>{e.notes ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {isCloseModalOpen && (
        <Modal title="Cerrar viaje" onClose={() => setIsCloseModalOpen(false)}>
          <form onSubmit={handleClose}>
            <div className={styles.field}>
              <label htmlFor="end_mileage_km">Kilometraje final</label>
              <input
                id="end_mileage_km"
                type="number"
                min={trip.start_mileage_km}
                value={closeForm.end_mileage_km}
                onChange={(e) => setCloseForm({ ...closeForm, end_mileage_km: Number(e.target.value) })}
                required
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="arrival_at">Fecha y hora de llegada</label>
              <input
                id="arrival_at"
                type="datetime-local"
                value={closeForm.arrival_at}
                onChange={(e) => setCloseForm({ ...closeForm, arrival_at: e.target.value })}
                required
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="revenue">Ingreso del viaje — flete cobrado (USD, opcional)</label>
              <input
                id="revenue"
                type="number"
                min={0}
                step="0.01"
                placeholder="Se puede completar después"
                value={closeForm.revenue}
                onChange={(e) => setCloseForm({ ...closeForm, revenue: e.target.value })}
              />
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setIsCloseModalOpen(false)}>
                Cancelar
              </button>
              <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
                {isSubmitting ? "Cerrando…" : "Cerrar viaje"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {isExpenseModalOpen && (
        <Modal title="Nuevo gasto" onClose={() => setIsExpenseModalOpen(false)}>
          <form onSubmit={handleAddExpense}>
            <div className={styles.field}>
              <label htmlFor="type">Tipo de gasto</label>
              <select
                id="type"
                value={expenseForm.type}
                onChange={(e) => setExpenseForm({ ...expenseForm, type: e.target.value as ExpenseInput["type"] })}
              >
                <option value="combustible">Combustible</option>
                <option value="peaje">Peaje</option>
                <option value="alimentacion">Alimentación</option>
              </select>
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="amount">Monto (USD)</label>
                <input
                  id="amount"
                  type="number"
                  min={0}
                  step="0.01"
                  value={expenseForm.amount}
                  onChange={(e) => setExpenseForm({ ...expenseForm, amount: Number(e.target.value) })}
                  required
                />
                {expenseForm.amount > 0 && (
                  <span className={styles.taxHint}>
                    {(() => {
                      const category = expenseForm.type as TaxableCategory;
                      const b = ivaBreakdown(expenseForm.amount, category);
                      return b.rate === 0
                        ? `IVA: ${IVA_RATE_LABELS[category]} — base imponible USD ${b.subtotal.toFixed(2)}`
                        : `Base imponible USD ${b.subtotal.toFixed(2)} + IVA (${IVA_RATE_LABELS[category]}) USD ${b.iva.toFixed(2)}`;
                    })()}
                  </span>
                )}
              </div>
              <div className={styles.field}>
                <label htmlFor="expense_date">Fecha</label>
                <input
                  id="expense_date"
                  type="date"
                  value={expenseForm.expense_date}
                  onChange={(e) => setExpenseForm({ ...expenseForm, expense_date: e.target.value })}
                  required
                />
              </div>
            </div>
            {expenseForm.type === "combustible" && (
              <div className={styles.field}>
                <label htmlFor="liters">Litros cargados (opcional)</label>
                <input
                  id="liters"
                  type="number"
                  min={0}
                  step="0.01"
                  placeholder="Permite calcular consumo (L/100km)"
                  value={expenseForm.liters}
                  onChange={(e) => setExpenseForm({ ...expenseForm, liters: e.target.value === "" ? "" : Number(e.target.value) })}
                />
              </div>
            )}
            <div className={styles.field}>
              <label htmlFor="notes">Notas (opcional)</label>
              <input
                id="notes"
                value={expenseForm.notes}
                onChange={(e) => setExpenseForm({ ...expenseForm, notes: e.target.value })}
              />
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setIsExpenseModalOpen(false)}>
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

export default TripDetailPage;
