import { useEffect, useState, type FormEvent } from "react";
import { Plus, QrCode, RefreshCw } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import AppShell from "../components/AppShell";
import Modal from "../components/Modal";
import { useAuth } from "../context/AuthContext";
import { fleetApi } from "../services/fleetApi";
import { ApiError } from "../services/apiClient";
import type { Driver, DriverInput, Vehicle } from "../types/fleet";
import styles from "./DriversPage.module.css";

const EMPTY_FORM: DriverInput & { status: string } = {
  full_name: "",
  license_number: "",
  license_type: "",
  phone: "",
  assigned_vehicle_id: "",
  status: "activo",
};

function despachoUrl(driver: Driver): string {
  const params = new URLSearchParams({ driverId: driver.id, token: driver.qr_token ?? "" });
  return `${window.location.origin}/despacho?${params.toString()}`;
}

/** RF-05: alta, edición y consulta de conductores, incluida la gestión de
 * su token de código QR para el portal de despacho (RF-18). */
function DriversPage() {
  const { token } = useAuth();
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editing, setEditing] = useState<Driver | null>(null);
  const [form, setForm] = useState<DriverInput & { status: string }>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [qrDriver, setQrDriver] = useState<Driver | null>(null);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const vehicleLabel = (id: string | null) => {
    const v = vehicles.find((vehicle) => vehicle.id === id);
    return v ? `${v.plate} — ${v.brand} ${v.model}` : "—";
  };

  const load = () => {
    if (!token) return;
    setIsLoading(true);
    Promise.all([fleetApi.listDrivers(token), fleetApi.listVehicles(token)])
      .then(([driversData, vehiclesData]) => {
        setDrivers(driversData);
        setVehicles(vehiclesData);
      })
      .catch(() => setLoadError("No se pudo cargar la lista de conductores."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [token]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEdit = (driver: Driver) => {
    setEditing(driver);
    setForm({
      full_name: driver.full_name,
      license_number: driver.license_number,
      license_type: driver.license_type ?? "",
      phone: driver.phone ?? "",
      assigned_vehicle_id: driver.assigned_vehicle_id ?? "",
      status: driver.status,
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
      const payload = { ...form, assigned_vehicle_id: form.assigned_vehicle_id || undefined };
      if (editing) {
        const { license_number: _license, ...updatable } = payload;
        await fleetApi.updateDriver(token, editing.id, updatable);
      } else {
        await fleetApi.createDriver(token, payload);
      }
      setIsModalOpen(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "No se pudo guardar el conductor.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegenerateQr = async () => {
    if (!token || !qrDriver) return;
    setIsRegenerating(true);
    try {
      const updated = await fleetApi.regenerateDriverQr(token, qrDriver.id);
      setQrDriver(updated);
      setDrivers((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
    } catch {
      // el modal sigue mostrando el código anterior si falla
    } finally {
      setIsRegenerating(false);
    }
  };

  const handlePrintCard = () => {
    window.print();
  };

  return (
    <AppShell title="Conductores">
      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <span className={styles.panelTitle}>Conductores registrados</span>
          <button type="button" className={styles.newButton} onClick={openCreate}>
            <Plus size={16} />
            Nuevo conductor
          </button>
        </div>

        {loadError && <p className={styles.empty}>{loadError}</p>}
        {!isLoading && drivers.length === 0 && !loadError && (
          <p className={styles.empty}>Todavía no hay conductores registrados.</p>
        )}

        {drivers.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Licencia</th>
                <th>Tipo</th>
                <th>Teléfono</th>
                <th>Estado</th>
                <th>Vehículo asignado</th>
                <th></th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((d) => (
                <tr key={d.id}>
                  <td>{d.full_name}</td>
                  <td className="mono">{d.license_number}</td>
                  <td>{d.license_type ?? "—"}</td>
                  <td className="mono">{d.phone ?? "—"}</td>
                  <td style={{ textTransform: "capitalize" }}>{d.status}</td>
                  <td className="mono">{vehicleLabel(d.assigned_vehicle_id)}</td>
                  <td>
                    <button type="button" className={styles.editLink} onClick={() => openEdit(d)}>
                      Editar
                    </button>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={styles.editLink}
                      onClick={() => setQrDriver(d)}
                      disabled={!d.qr_token}
                      title={d.qr_token ? "Ver código QR de despacho" : "Sin código QR"}
                    >
                      <QrCode size={14} style={{ verticalAlign: "-2px", marginRight: 4 }} />
                      QR
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isModalOpen && (
        <Modal title={editing ? "Editar conductor" : "Nuevo conductor"} onClose={() => setIsModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            {formError && <p className={styles.formError}>{formError}</p>}

            <div className={styles.field}>
              <label htmlFor="full_name">Nombre completo</label>
              <input
                id="full_name"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="license_number">Número de licencia</label>
              <input
                id="license_number"
                value={form.license_number}
                disabled={Boolean(editing)}
                onChange={(e) => setForm({ ...form, license_number: e.target.value })}
                required
              />
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="license_type">Tipo de licencia</label>
                <input
                  id="license_type"
                  value={form.license_type}
                  onChange={(e) => setForm({ ...form, license_type: e.target.value })}
                  placeholder="Tipo E"
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="phone">Teléfono</label>
                <input
                  id="phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </div>
            </div>

            <div className={styles.row2}>
              <div className={styles.field}>
                <label htmlFor="assigned_vehicle_id">Vehículo asignado (para el portal de despacho)</label>
                <select
                  id="assigned_vehicle_id"
                  value={form.assigned_vehicle_id}
                  onChange={(e) => setForm({ ...form, assigned_vehicle_id: e.target.value })}
                >
                  <option value="">Sin asignar</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.plate} — {v.brand} {v.model}
                    </option>
                  ))}
                </select>
              </div>
              {editing && (
                <div className={styles.field}>
                  <label htmlFor="status">Estado</label>
                  <select id="status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                    <option value="activo">Activo</option>
                    <option value="inactivo">Inactivo</option>
                  </select>
                </div>
              )}
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

      {qrDriver && (
        <Modal title="Código QR de despacho" onClose={() => setQrDriver(null)}>
          <div className={styles.qrCard} id="qr-print-area">
            <div className={styles.qrCardHead}>FlotaControl — Tarjeta de cabina</div>
            <div className={styles.qrCode}>
              <QRCodeSVG value={despachoUrl(qrDriver)} size={200} level="M" />
            </div>
            <div className={styles.qrInfo}>
              <div>
                <strong>Conductor:</strong> {qrDriver.full_name}
              </div>
              <div>
                <strong>Vehículo:</strong> {vehicleLabel(qrDriver.assigned_vehicle_id)}
              </div>
            </div>
            <p className={styles.qrHint}>
              Escanear con la cámara del teléfono para abrir el formulario de registro de salida.
            </p>
          </div>

          {!qrDriver.assigned_vehicle_id && (
            <p className={styles.formError}>
              Este conductor todavía no tiene un vehículo asignado — el portal de despacho no va a funcionar hasta
              que se le asigne uno desde "Editar".
            </p>
          )}

          <div className={styles.formActions}>
            <button type="button" className={styles.cancelButton} onClick={handleRegenerateQr} disabled={isRegenerating}>
              <RefreshCw size={14} style={{ verticalAlign: "-2px", marginRight: 4 }} />
              {isRegenerating ? "Generando…" : "Regenerar código"}
            </button>
            <button type="button" className={styles.submitButton} onClick={handlePrintCard}>
              Imprimir tarjeta
            </button>
          </div>
        </Modal>
      )}
    </AppShell>
  );
}

export default DriversPage;
