import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { ApiError } from "../services/apiClient";
import type { Driver, Vehicle } from "../types/fleet";
import {
  FIXED_COST_LABELS,
  PERSONNEL_LABELS,
  type CostPeriod,
  type FixedCost,
  type FixedCostCategory,
  type PersonnelConcept,
  type PersonnelCost,
} from "../types/costs";
import styles from "./CostsPage.module.css";

const currency = new Intl.NumberFormat("es-EC", { style: "currency", currency: "USD" });

const CATEGORY_HINTS: Record<FixedCostCategory, string> = {
  depreciacion: "Depreciación lineal anual = (valor de compra − valor residual) ÷ vida útil en años.",
  capital: "Cuota de leasing o de crédito del vehículo (la parte de intereses y cargos).",
  seguro: "Prima del seguro del vehículo, en el período que cubre.",
  impuestos: "Matrícula, impuesto al rodaje y otros impuestos sobre el activo.",
  otros: "Cualquier otro costo que no depende de los kilómetros recorridos.",
};

type Tab = "fijos" | "personal";

type FixedForm = {
  vehicle_id: string;
  category: FixedCostCategory;
  amount: string;
  period: CostPeriod;
  valid_from: string;
  valid_to: string;
  notes: string;
};

type PersonnelForm = {
  driver_id: string;
  concept: PersonnelConcept;
  amount: string;
  valid_from: string;
  valid_to: string;
  notes: string;
};

const today = () => new Date().toISOString().slice(0, 10);
const EMPTY_FIXED: FixedForm = { vehicle_id: "", category: "depreciacion", amount: "", period: "anual", valid_from: "", valid_to: "", notes: "" };
const EMPTY_PERSONNEL: PersonnelForm = { driver_id: "", concept: "sueldo", amount: "", valid_from: "", valid_to: "", notes: "" };

/** Equivalente anual de un monto (mensual × 12). */
const annual = (amount: string, period: CostPeriod) => Number(amount) * (period === "mensual" ? 12 : 1);

const isActiveToday = (from: string, to: string | null) => from <= today() && (to === null || to >= today());
const validity = (from: string, to: string | null) => (to ? `${from} → ${to}` : `${from} → vigente`);
const isExample = (notes: string | null) => Boolean(notes && notes.toUpperCase().startsWith("EJEMPLO"));

/** Fase 3 (solo admin): costos fijos por vehículo (depreciación, capital, seguro, impuestos, otros) y costos de
 * personal por conductor (sueldo y beneficios). Sin ellos no se puede calcular el costo total Ct = Cv + Cf
 * (Poliak et al., 2025) ni el costo por kilómetro y el margen de la literatura (Zysińska & Menes, 2026). */
function CostsPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState<Tab>("fijos");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [fixed, setFixed] = useState<FixedCost[]>([]);
  const [personnel, setPersonnel] = useState<PersonnelCost[]>([]);
  const [vehicleFilter, setVehicleFilter] = useState("");
  const [driverFilter, setDriverFilter] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [fixedForm, setFixedForm] = useState<FixedForm>(EMPTY_FIXED);
  const [personnelForm, setPersonnelForm] = useState<PersonnelForm>(EMPTY_PERSONNEL);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = () => {
    if (!token) return;
    setIsLoading(true);
    Promise.all([
      fleetApi.listVehicles(token),
      fleetApi.listDrivers(token),
      fleetApi.listFixedCosts(token),
      fleetApi.listPersonnelCosts(token),
    ])
      .then(([v, d, f, p]) => {
        setVehicles(v);
        setDrivers(d);
        setFixed(f);
        setPersonnel(p);
        setLoadError(null);
      })
      .catch(() => setLoadError("No se pudieron cargar los costos."))
      .finally(() => setIsLoading(false));
  };
  useEffect(load, [token]);

  const vehicleMap = useMemo(() => new Map(vehicles.map((v) => [v.id, v])), [vehicles]);
  const driverMap = useMemo(() => new Map(drivers.map((d) => [d.id, d])), [drivers]);
  // Solo conductores con datos vigentes pueden recibir costos de personal.
  const selectableDrivers = drivers.filter((d) => d.anonymized_at === null);

  const fixedRows = fixed.filter((c) => !vehicleFilter || c.vehicle_id === vehicleFilter);
  const personnelRows = personnel.filter((c) => !driverFilter || c.driver_id === driverFilter);
  const fixedAnnual = fixedRows.filter((c) => isActiveToday(c.valid_from, c.valid_to)).reduce((a, c) => a + annual(c.amount, c.period), 0);
  const personnelAnnual = personnelRows.filter((c) => isActiveToday(c.valid_from, c.valid_to)).reduce((a, c) => a + annual(c.amount, "mensual"), 0);
  const hasExamples = fixed.some((c) => isExample(c.notes)) || personnel.some((c) => isExample(c.notes));

  const openCreate = () => {
    setEditingId(null);
    setFormError(null);
    if (tab === "fijos") setFixedForm({ ...EMPTY_FIXED, vehicle_id: vehicleFilter || vehicles[0]?.id || "", valid_from: today() });
    else setPersonnelForm({ ...EMPTY_PERSONNEL, driver_id: driverFilter || selectableDrivers[0]?.id || "", valid_from: today() });
    setIsModalOpen(true);
  };

  const openEditFixed = (c: FixedCost) => {
    setEditingId(c.id);
    setFormError(null);
    setFixedForm({ vehicle_id: c.vehicle_id, category: c.category, amount: c.amount, period: c.period, valid_from: c.valid_from, valid_to: c.valid_to ?? "", notes: c.notes ?? "" });
    setIsModalOpen(true);
  };

  const openEditPersonnel = (c: PersonnelCost) => {
    setEditingId(c.id);
    setFormError(null);
    setPersonnelForm({ driver_id: c.driver_id, concept: c.concept, amount: c.amount, valid_from: c.valid_from, valid_to: c.valid_to ?? "", notes: c.notes ?? "" });
    setIsModalOpen(true);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      if (tab === "fijos") {
        const { vehicle_id, valid_to, notes, amount, ...rest } = fixedForm;
        const payload = { ...rest, amount: Number(amount), valid_to: valid_to || null, notes: notes || undefined };
        if (editingId) await fleetApi.updateFixedCost(token, editingId, payload);
        else await fleetApi.createFixedCost(token, { vehicle_id, ...payload });
      } else {
        const { driver_id, valid_to, notes, amount, ...rest } = personnelForm;
        const payload = { ...rest, amount: Number(amount), valid_to: valid_to || null, notes: notes || undefined };
        if (editingId) await fleetApi.updatePersonnelCost(token, editingId, payload);
        else await fleetApi.createPersonnelCost(token, { driver_id, ...payload });
      }
      setIsModalOpen(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo guardar el costo.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (kind: Tab, id: string) => {
    if (!token || !window.confirm("¿Eliminar este costo? Los indicadores de los períodos que lo incluían se recalculan.")) return;
    try {
      if (kind === "fijos") await fleetApi.deleteFixedCost(token, id);
      else await fleetApi.deletePersonnelCost(token, id);
      load();
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "No se pudo eliminar el costo.");
    }
  };

  return (
    <AppShell title="Costos fijos y de personal">
      <div className={styles.panel}>
        <div className={styles.tabs} role="tablist">
          {(["fijos", "personal"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`}
              onClick={() => setTab(t)}
            >
              {t === "fijos" ? "Costos fijos por vehículo" : "Personal por conductor"}
            </button>
          ))}
        </div>

        <p className={styles.intro}>
          Lo que cuesta tener la flota aunque no ande: depreciación, capital, seguros, impuestos y el personal. Cada monto
          se prorratea por días (365 por año) al calcular un período; el sueldo de cada conductor se reparte entre los
          vehículos que manejó, según sus kilómetros. Solo el administrador ve y edita esta información.
        </p>

        {hasExamples && (
          <p className={styles.notice}>
            <strong>Hay registros marcados como EJEMPLO.</strong> Son valores ilustrativos para probar el cálculo, no datos reales:
            reemplázalos con los valores de la empresa antes de interpretar el costo total o el margen.
          </p>
        )}
        {loadError && <p className={styles.formError}>{loadError}</p>}

        <div className={styles.toolbar}>
          {tab === "fijos" ? (
            <select aria-label="Vehículo" value={vehicleFilter} onChange={(e) => setVehicleFilter(e.target.value)}>
              <option value="">Todos los vehículos</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plate}
                </option>
              ))}
            </select>
          ) : (
            <select aria-label="Conductor" value={driverFilter} onChange={(e) => setDriverFilter(e.target.value)}>
              <option value="">Todos los conductores</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.full_name}
                </option>
              ))}
            </select>
          )}
          <span className={styles.summary}>
            Vigentes hoy, equivalente anual: <strong>{currency.format(tab === "fijos" ? fixedAnnual : personnelAnnual)}</strong>
          </span>
          <button
            type="button"
            className={styles.newButton}
            onClick={openCreate}
            disabled={tab === "fijos" ? vehicles.length === 0 : selectableDrivers.length === 0}
          >
            <Plus size={16} />
            {tab === "fijos" ? "Nuevo costo fijo" : "Nuevo costo de personal"}
          </button>
        </div>

        {tab === "fijos" ? (
          fixedRows.length > 0 ? (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Vehículo</th>
                  <th>Categoría</th>
                  <th>Monto</th>
                  <th>Equivale al año</th>
                  <th>Vigencia</th>
                  <th>Notas</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {fixedRows.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">{vehicleMap.get(c.vehicle_id)?.plate ?? "—"}</td>
                    <td>{FIXED_COST_LABELS[c.category]}</td>
                    <td className="mono">
                      {currency.format(Number(c.amount))} / {c.period === "mensual" ? "mes" : "año"}
                    </td>
                    <td className="mono">{currency.format(annual(c.amount, c.period))}</td>
                    <td className="mono">{validity(c.valid_from, c.valid_to)}</td>
                    <td>{c.notes ?? "—"}</td>
                    <td className={styles.actionsCell}>
                      <button type="button" className={styles.editLink} onClick={() => openEditFixed(c)}>
                        Editar
                      </button>
                      <button type="button" className={styles.editLink} onClick={() => handleDelete("fijos", c.id)}>
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay costos fijos registrados para este filtro."}</p>
          )
        ) : personnelRows.length > 0 ? (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Conductor</th>
                <th>Concepto</th>
                <th>Monto mensual</th>
                <th>Equivale al año</th>
                <th>Vigencia</th>
                <th>Notas</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {personnelRows.map((c) => (
                <tr key={c.id}>
                  <td>{driverMap.get(c.driver_id)?.full_name ?? "—"}</td>
                  <td>{PERSONNEL_LABELS[c.concept]}</td>
                  <td className="mono">{currency.format(Number(c.amount))} / mes</td>
                  <td className="mono">{currency.format(annual(c.amount, "mensual"))}</td>
                  <td className="mono">{validity(c.valid_from, c.valid_to)}</td>
                  <td>{c.notes ?? "—"}</td>
                  <td className={styles.actionsCell}>
                    <button type="button" className={styles.editLink} onClick={() => openEditPersonnel(c)}>
                      Editar
                    </button>
                    <button type="button" className={styles.editLink} onClick={() => handleDelete("personal", c.id)}>
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className={styles.empty}>{isLoading ? "Cargando…" : "Todavía no hay costos de personal registrados para este filtro."}</p>
        )}
      </div>

      {isModalOpen && (
        <Modal
          title={
            tab === "fijos"
              ? editingId ? "Editar costo fijo" : "Nuevo costo fijo"
              : editingId ? "Editar costo de personal" : "Nuevo costo de personal"
          }
          onClose={() => setIsModalOpen(false)}
        >
          <form onSubmit={handleSubmit}>
            {formError && <p className={styles.formError}>{formError}</p>}

            {tab === "fijos" ? (
              <>
                <div className={styles.field}>
                  <label htmlFor="vehicle_id">Vehículo</label>
                  <select
                    id="vehicle_id"
                    value={fixedForm.vehicle_id}
                    disabled={Boolean(editingId)}
                    onChange={(e) => setFixedForm({ ...fixedForm, vehicle_id: e.target.value })}
                    required
                  >
                    {vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.plate} — {v.brand} {v.model}
                      </option>
                    ))}
                  </select>
                </div>
                <div className={styles.field}>
                  <label htmlFor="category">Categoría</label>
                  <select
                    id="category"
                    value={fixedForm.category}
                    onChange={(e) => setFixedForm({ ...fixedForm, category: e.target.value as FixedCostCategory })}
                  >
                    {Object.entries(FIXED_COST_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <span className={styles.hint}>{CATEGORY_HINTS[fixedForm.category]}</span>
                </div>
                <div className={styles.row2}>
                  <div className={styles.field}>
                    <label htmlFor="amount">Monto (USD)</label>
                    <input
                      id="amount"
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={fixedForm.amount}
                      onChange={(e) => setFixedForm({ ...fixedForm, amount: e.target.value })}
                      required
                    />
                  </div>
                  <div className={styles.field}>
                    <label htmlFor="period">Corresponde a</label>
                    <select id="period" value={fixedForm.period} onChange={(e) => setFixedForm({ ...fixedForm, period: e.target.value as CostPeriod })}>
                      <option value="anual">un año</option>
                      <option value="mensual">un mes</option>
                    </select>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className={styles.field}>
                  <label htmlFor="driver_id">Conductor</label>
                  <select
                    id="driver_id"
                    value={personnelForm.driver_id}
                    disabled={Boolean(editingId)}
                    onChange={(e) => setPersonnelForm({ ...personnelForm, driver_id: e.target.value })}
                    required
                  >
                    {(editingId ? drivers : selectableDrivers).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.full_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className={styles.row2}>
                  <div className={styles.field}>
                    <label htmlFor="concept">Concepto</label>
                    <select id="concept" value={personnelForm.concept} onChange={(e) => setPersonnelForm({ ...personnelForm, concept: e.target.value as PersonnelConcept })}>
                      {Object.entries(PERSONNEL_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className={styles.field}>
                    <label htmlFor="amount">Monto mensual (USD)</label>
                    <input
                      id="amount"
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={personnelForm.amount}
                      onChange={(e) => setPersonnelForm({ ...personnelForm, amount: e.target.value })}
                      required
                    />
                  </div>
                </div>
                <span className={styles.hint}>
                  Beneficios sociales: décimos, aporte patronal, vacaciones y fondos de reserva, en su equivalente mensual.
                </span>
              </>
            )}

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="valid_from">Vigente desde</label>
                <input
                  id="valid_from"
                  type="date"
                  value={tab === "fijos" ? fixedForm.valid_from : personnelForm.valid_from}
                  onChange={(e) => (tab === "fijos" ? setFixedForm({ ...fixedForm, valid_from: e.target.value }) : setPersonnelForm({ ...personnelForm, valid_from: e.target.value }))}
                  required
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="valid_to">Hasta (opcional)</label>
                <input
                  id="valid_to"
                  type="date"
                  value={tab === "fijos" ? fixedForm.valid_to : personnelForm.valid_to}
                  onChange={(e) => (tab === "fijos" ? setFixedForm({ ...fixedForm, valid_to: e.target.value }) : setPersonnelForm({ ...personnelForm, valid_to: e.target.value }))}
                />
              </div>
            </div>

            <div className={styles.field}>
              <label htmlFor="notes">Notas (opcional)</label>
              <input
                id="notes"
                maxLength={500}
                value={tab === "fijos" ? fixedForm.notes : personnelForm.notes}
                onChange={(e) => (tab === "fijos" ? setFixedForm({ ...fixedForm, notes: e.target.value }) : setPersonnelForm({ ...personnelForm, notes: e.target.value }))}
              />
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

export default CostsPage;
