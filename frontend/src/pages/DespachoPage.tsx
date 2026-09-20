import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Fuel, MapPin, Truck } from "lucide-react";
import { despachoApi } from "../services/despachoApi";
import { ApiError } from "../services/apiClient";
import type { DespachoInfo, DespachoInput } from "../types/despacho";
import styles from "./DespachoPage.module.css";

const CIUDADES = [
  "Guayaquil", "Quito", "Machala", "Cuenca", "Manta", "Ambato",
  "Durán", "Loja", "Babahoyo", "Riobamba", "Esmeraldas", "Puerto de Machala",
];

/** Hora local actual en el formato que espera <input type="datetime-local">. */
function nowLocalInputValue(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

/** Clave de localStorage para el borrador de un conductor sin señal (ver submitDespacho). */
function pendingKey(driverId: string) {
  return `flotacontrol.despacho.pendiente.${driverId}`;
}

/** RF-18: portal móvil del conductor -- se abre desde el QR de la cabina
 * (sin sesión de administrador), muestra el vehículo asignado y registra
 * el viaje. Si falla el envío por falta de señal, guarda el borrador en
 * localStorage para reintentarlo cuando vuelva la conexión. */
function DespachoPage() {
  const [searchParams] = useSearchParams();
  const driverId = searchParams.get("driverId") ?? "";
  const qrToken = searchParams.get("token") ?? "";

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [info, setInfo] = useState<DespachoInfo | null>(null);

  const [form, setForm] = useState<DespachoInput>({
    origin: "",
    destination: "",
    start_mileage_km: 0,
    remission_guide: "",
    cargo_type: "",
    notes: "",
  });
  const [departureLocal, setDepartureLocal] = useState(nowLocalInputValue());
  const [loadPlace, setLoadPlace] = useState("");
  const [showFuel, setShowFuel] = useState(false);
  const [fuelAmount, setFuelAmount] = useState("");
  const [fuelLiters, setFuelLiters] = useState("");

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [hasOfflineDraft, setHasOfflineDraft] = useState(false);

  useEffect(() => {
    if (!driverId || !qrToken) {
      setLoadError("Este enlace no es válido — falta información del conductor o del código QR.");
      setIsLoading(false);
      return;
    }
    despachoApi
      .getInfo(driverId, qrToken)
      .then((data) => {
        setInfo(data);
        setForm((f) => ({ ...f, start_mileage_km: data.vehicle_current_mileage_km }));
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : "No se pudo cargar la información del vehículo."),
      )
      .finally(() => setIsLoading(false));

    setHasOfflineDraft(Boolean(localStorage.getItem(pendingKey(driverId))));
  }, [driverId, qrToken]);

  const submitDespacho = async (payload: DespachoInput) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const result = await despachoApi.registrarSalida(driverId, qrToken, payload);
      localStorage.removeItem(pendingKey(driverId));
      setHasOfflineDraft(false);
      setSuccessMessage(result.message);
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else {
        // Sin conexión o el servidor no respondió: se guarda localmente
        // para reintentar, en vez de perder lo que el conductor ya escribió.
        localStorage.setItem(pendingKey(driverId), JSON.stringify(payload));
        setHasOfflineDraft(true);
        setSubmitError("Sin conexión a internet. El viaje quedó guardado en este teléfono — presioná \"Reintentar envío\" cuando vuelva la señal.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const payload: DespachoInput = {
      ...form,
      origin: loadPlace ? `${form.origin} (${loadPlace})` : form.origin,
      departure_at: departureLocal ? new Date(departureLocal).toISOString() : undefined,
      remission_guide: form.remission_guide || undefined,
      cargo_type: form.cargo_type || undefined,
      notes: form.notes || undefined,
      fuel_amount: showFuel && fuelAmount ? Number(fuelAmount) : undefined,
      fuel_liters: showFuel && fuelLiters ? Number(fuelLiters) : undefined,
    };
    submitDespacho(payload);
  };

  const handleRetryOffline = () => {
    const raw = localStorage.getItem(pendingKey(driverId));
    if (!raw) return;
    submitDespacho(JSON.parse(raw) as DespachoInput);
  };

  if (isLoading) {
    return (
      <div className={styles.screen}>
        <p className={styles.loading}>Cargando…</p>
      </div>
    );
  }

  if (loadError || !info) {
    return (
      <div className={styles.screen}>
        <div className={styles.errorCard}>
          <p className={styles.errorTitle}>No se pudo abrir el despacho</p>
          <p>{loadError ?? "Enlace inválido."}</p>
        </div>
      </div>
    );
  }

  if (successMessage) {
    return (
      <div className={styles.screen}>
        <div className={styles.successCard}>
          <div className={styles.successIcon}>✓</div>
          <p className={styles.successTitle}>{successMessage}</p>
          <p className={styles.successHint}>Ya podés cerrar esta pantalla.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.screen}>
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <Truck size={20} />
          <span>
            <strong>{info.vehicle_plate}</strong> — {info.vehicle_brand} {info.vehicle_model}
          </span>
        </div>
        {info.vehicle_registration_number && (
          <div className={styles.headerRow}>
            <MapPin size={16} />
            <span>Matrícula: {info.vehicle_registration_number}</span>
          </div>
        )}
        <div className={styles.headerRow}>
          <span>Conductor: {info.driver_name}</span>
        </div>
        <div className={styles.readyBadge}>Listo para ruta</div>
      </header>

      {hasOfflineDraft && !isSubmitting && (
        <div className={styles.offlineBanner}>
          <span>Hay un viaje guardado en este teléfono que no se pudo enviar todavía.</span>
          <button type="button" className={styles.retryButton} onClick={handleRetryOffline}>
            Reintentar envío
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className={styles.form}>
        {submitError && <p className={styles.formError}>{submitError}</p>}

        <div className={styles.field}>
          <label htmlFor="origin">Origen</label>
          <input
            id="origin"
            list="ciudades"
            value={form.origin}
            onChange={(e) => setForm({ ...form, origin: e.target.value })}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="destination">Destino</label>
          <input
            id="destination"
            list="ciudades"
            value={form.destination}
            onChange={(e) => setForm({ ...form, destination: e.target.value })}
            required
          />
        </div>
        <datalist id="ciudades">
          {CIUDADES.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>

        <div className={styles.field}>
          <label htmlFor="loadPlace">Lugar de carga específico (opcional)</label>
          <input
            id="loadPlace"
            value={loadPlace}
            onChange={(e) => setLoadPlace(e.target.value)}
            placeholder="Terminal Marítimo Puerto Bolívar - Muelle 5"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="remission_guide">Número de guía de remisión</label>
          <input
            id="remission_guide"
            value={form.remission_guide}
            onChange={(e) => setForm({ ...form, remission_guide: e.target.value })}
            placeholder="GR-001-99823"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="cargo_type">Tipo de carga / mercadería</label>
          <input
            id="cargo_type"
            value={form.cargo_type}
            onChange={(e) => setForm({ ...form, cargo_type: e.target.value })}
            placeholder="Banano de exportación, contenedor refrigerado…"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="start_mileage_km">Kilometraje de salida (odómetro)</label>
          <input
            id="start_mileage_km"
            type="number"
            min={info.vehicle_current_mileage_km}
            value={form.start_mileage_km}
            onChange={(e) => setForm({ ...form, start_mileage_km: Number(e.target.value) })}
            required
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="departure">Hora y fecha de salida</label>
          <input
            id="departure"
            type="datetime-local"
            value={departureLocal}
            onChange={(e) => setDepartureLocal(e.target.value)}
          />
        </div>

        <button
          type="button"
          className={styles.fuelToggle}
          onClick={() => setShowFuel((v) => !v)}
        >
          <Fuel size={16} />
          {showFuel ? "Ocultar recarga de combustible" : "¿Tanqueó antes de salir? (opcional)"}
        </button>
        {showFuel && (
          <div className={styles.fuelBox}>
            <div className={styles.field}>
              <label htmlFor="fuelAmount">Monto (USD)</label>
              <input id="fuelAmount" type="number" min={0} step="0.01" value={fuelAmount} onChange={(e) => setFuelAmount(e.target.value)} />
            </div>
            <div className={styles.field}>
              <label htmlFor="fuelLiters">Litros cargados</label>
              <input id="fuelLiters" type="number" min={0} step="0.01" value={fuelLiters} onChange={(e) => setFuelLiters(e.target.value)} />
            </div>
          </div>
        )}

        <div className={styles.field}>
          <label htmlFor="notes">Observaciones / novedades</label>
          <textarea
            id="notes"
            rows={3}
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Carga pesada 28 toneladas, sellos de seguridad #A-9923"
          />
        </div>

        <button type="submit" className={styles.submitButton} disabled={isSubmitting}>
          {isSubmitting ? "Registrando…" : "🚀 Registrar y iniciar viaje"}
        </button>
      </form>
    </div>
  );
}

export default DespachoPage;
