// Gráficas del dashboard (Observable Plot): histograma, dispersión,
// tendencia y barras -- una función build*Plot() por gráfica, consumida
// por PlotFigure.tsx.
import * as Plot from "@observablehq/plot";
import type { ExpenseRecord, MaintenanceMixEntry, RouteSummary, TrendPoint } from "../types/reports";

const currency = new Intl.NumberFormat("es-EC", { style: "currency", currency: "USD" });

/** Tipografía y tinta oscura tipo figura de artículo científico (papel
 * blanco, texto casi negro) en vez del gris apagado de la UI. */
const PLOT_STYLE: Partial<CSSStyleDeclaration> = {
  fontFamily: "var(--font-body)",
  fontSize: "11px",
  background: "transparent",
  color: "var(--ink)",
};

const FRAME = Plot.frame({ stroke: "var(--ink)", strokeWidth: 1 });

/** Tamaño de muestra mínimo convencional para que la forma de un histograma
 * sea razonablemente confiable (regla práctica habitual en estadística
 * introductoria: n≥30) — por debajo de eso, el gráfico se muestra igual
 * pero con una advertencia visible, en vez de aparentar una certeza que
 * los datos no respaldan. */
const MIN_N_HISTOGRAM = 30;

/** Puntos mínimos para dibujar una línea de regresión — con menos de 5
 * puntos, "ajustar una recta" es unir puntos, no estimar una tendencia. */
const MIN_N_REGRESSION = 5;

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

/** R² (coeficiente de determinación) de una regresión lineal simple —
 * mismo cálculo que respalda la línea que dibuja Plot.linearRegressionY,
 * mostrado explícitamente para no insinuar una relación estadística sin
 * reportar qué tan bien ajusta. */
function rSquared(points: { x: number; y: number }[]): number {
  const n = points.length;
  const sumX = points.reduce((a, p) => a + p.x, 0);
  const sumY = points.reduce((a, p) => a + p.y, 0);
  const sumXY = points.reduce((a, p) => a + p.x * p.y, 0);
  const sumX2 = points.reduce((a, p) => a + p.x * p.x, 0);
  const sumY2 = points.reduce((a, p) => a + p.y * p.y, 0);
  const numerator = n * sumXY - sumX * sumY;
  const denominator = Math.sqrt((n * sumX2 - sumX ** 2) * (n * sumY2 - sumY ** 2));
  if (denominator === 0) return 0;
  const r = numerator / denominator;
  return r * r;
}

/** Traduce R² a una frase que un gerente puede leer sin saber estadística:
 * ¿el gasto acompaña al kilometraje del vehículo, o son cosas separadas? */
function relationshipLabel(r2: number): string {
  if (r2 < 0.1) return "El gasto no parece depender del kilometraje del vehículo";
  if (r2 < 0.3) return "El gasto acompaña apenas un poco al kilometraje del vehículo";
  if (r2 < 0.6) return "El gasto acompaña moderadamente al kilometraje del vehículo";
  return "El gasto acompaña claramente al kilometraje del vehículo";
}

/** Da al legend de swatches que genera Plot (sin marco por defecto) el
 * recuadro con borde que trae la figura de referencia. */
function boxLegend<T extends SVGElement | HTMLElement | null>(figure: T): T {
  if (!figure || !("querySelector" in figure)) return figure;
  const legend = (figure as HTMLElement).querySelector<HTMLElement>('[class*="-swatches"]');
  if (legend) {
    Object.assign(legend.style, {
      display: "inline-flex",
      border: "1px solid var(--ink)",
      borderRadius: "0",
      background: "var(--surface)",
      padding: "0.3rem 0.65rem",
      marginBottom: "0.4rem",
      fontSize: "11px",
    });
  }
  return figure;
}

/** Panel "a": distribución de los montos individuales de una categoría de
 * gasto, con una línea punteada marcando la media — igual patrón que un
 * histograma de calibración (densidad + media), aplicado a montos de gasto. */
export function buildHistogramPlot(
  records: ExpenseRecord[],
  width: number,
  color: string,
): SVGElement | HTMLElement | null {
  if (records.length === 0) return null;
  const amounts = records.map((r) => Number(r.amount));
  const n = amounts.length;
  const mean = amounts.reduce((a, b) => a + b, 0) / n;
  const med = median(amounts);
  const insufficientN = n < MIN_N_HISTOGRAM;

  return Plot.plot({
    width,
    height: 240,
    marginLeft: 44,
    marginBottom: 34,
    // Dos líneas de texto siempre se dibujan por encima del marco del
    // gráfico, nunca dentro -- por eso el margen reserva espacio propio en
    // vez de dejar que las etiquetas floten sobre las barras.
    marginTop: 54,
    style: PLOT_STYLE,
    x: { label: "Monto por registro (USD)", labelAnchor: "center", labelArrow: false, tickFormat: (d: number) => `$${d}` },
    y: { label: "N.º de registros", labelArrow: false, grid: true, tickFormat: "d" },
    marks: [
      FRAME,
      Plot.rectY(records, {
        ...Plot.binX({ y: "count" }, { x: (d: ExpenseRecord) => Number(d.amount) }),
        fill: color,
        stroke: "var(--ink)",
        strokeWidth: 1,
        inset: 1,
      }),
      Plot.ruleX([mean], { stroke: "var(--danger)", strokeDasharray: "5,4", strokeWidth: 2 }),
      Plot.ruleX([med], { stroke: "var(--ink)", strokeDasharray: "2,2", strokeWidth: 2 }),
      // Fila superior: aviso de muestra pequeña (si aplica). Fila inferior,
      // ya pegada al marco: promedio y mediana. Separadas 24px entre sí y
      // ambas fuera del área donde se dibujan las barras, para que nunca se
      // toquen sin importar el ancho del texto.
      insufficientN
        ? Plot.text([{ label: `Pocos registros todavía (${n}) — la forma del gráfico puede cambiar con más datos` }], {
            frameAnchor: "top",
            dy: -34,
            text: "label",
            fontWeight: 700,
            fontSize: 10.5,
            fill: "var(--warning)",
          })
        : null,
      Plot.text([{ label: `— Promedio ${currency.format(mean)}` }], {
        frameAnchor: "top",
        dx: -70,
        dy: -10,
        text: "label",
        fontWeight: 700,
        fill: "var(--danger)",
      }),
      Plot.text([{ label: `┄ Mediana ${currency.format(med)}` }], {
        frameAnchor: "top",
        dx: 70,
        dy: -10,
        text: "label",
        fontWeight: 700,
        fill: "var(--ink)",
      }),
    ].filter((m) => m !== null) as Plot.Markish[],
  });
}

const MIX_LABELS: Record<string, string> = {
  preventivo: "Preventivo",
  correctivo: "Correctivo",
  programado_km: "Programado por km",
};

const MIX_COLORS: Record<string, string> = {
  preventivo: "var(--success)",
  correctivo: "var(--danger)",
  programado_km: "var(--chart-peaje)",
};

/** Barras horizontales preventivo/correctivo/programado — cuánto de lo que
 * ya se gastó en mantenimiento fue planificado vs. a la fuerza. Un gerente
 * que ve "correctivo" dominar sabe que necesita más mantenimiento
 * preventivo, no solo reaccionar cuando algo se rompe. */
export function buildMaintenanceMixPlot(mix: MaintenanceMixEntry[], width: number): SVGElement | HTMLElement | null {
  if (mix.length === 0) return null;
  const data = mix.map((m) => ({
    label: MIX_LABELS[m.category] ?? m.category,
    cost: Number(m.total_cost),
    count: m.count,
    color: MIX_COLORS[m.category] ?? "var(--chart-mantenimiento)",
  }));

  return Plot.plot({
    width,
    height: 190,
    marginLeft: 130,
    marginBottom: 34,
    style: PLOT_STYLE,
    x: { label: "Costo total (USD)", labelAnchor: "center", labelArrow: false, tickFormat: (d: number) => `$${d}` },
    y: { label: null },
    marks: [
      FRAME,
      Plot.barX(data, {
        x: "cost",
        y: "label",
        fill: "color",
        stroke: "var(--ink)",
        strokeWidth: 1,
        sort: { y: "-x" },
      }),
      Plot.text(data, {
        x: "cost",
        y: "label",
        text: (d) => `${currency.format(d.cost)} · ${d.count} reg.`,
        dx: -8,
        textAnchor: "end",
        fill: "#fff",
        fontWeight: 700,
        fontSize: 11,
      }),
    ],
  });
}

/** Panel "b": dispersión kilometraje-vs-monto por vehículo, con línea de
 * regresión — mismo patrón que confianza-vs-tasa de error, aplicado a
 * kilometraje-vs-costo (¿el gasto crece con el uso del vehículo?). */
export function buildScatterPlot(records: ExpenseRecord[], width: number): SVGElement | HTMLElement | null {
  const points = records.filter((r) => r.mileage_km != null);
  if (points.length === 0) return null;

  const xy = points.map((p) => ({ x: p.mileage_km as number, y: Number(p.amount) }));
  const canFitLine = points.length >= MIN_N_REGRESSION;
  const r2 = canFitLine ? rSquared(xy) : null;

  const marks: Plot.Markish[] = [FRAME];

  if (canFitLine) {
    marks.push(
      Plot.linearRegressionY(points, {
        x: (d: ExpenseRecord) => d.mileage_km,
        y: (d: ExpenseRecord) => Number(d.amount),
        stroke: "var(--ink)",
        strokeDasharray: "6,4",
        strokeWidth: 1.5,
        ci: 0,
      }),
    );
  }

  marks.push(
    Plot.dot(points, {
      x: (d: ExpenseRecord) => d.mileage_km,
      y: (d: ExpenseRecord) => Number(d.amount),
      fill: "vehicle_plate",
      r: 5.5,
      stroke: "var(--ink)",
      strokeWidth: 1,
    }),
  );

  // Lenguaje llano en vez del coeficiente estadístico crudo: la pregunta que
  // le importa a un gerente es si el gasto acompaña al uso real del
  // vehículo, no el valor exacto de R². La cifra sigue disponible para
  // quien la necesite (ver rSquared() más arriba), solo no se expone así en
  // el panel principal.
  marks.push(
    Plot.text(
      [
        {
          label: canFitLine
            ? relationshipLabel(r2!)
            : `Muy pocos registros (${points.length}) para saber si hay una relación — se necesitan al menos ${MIN_N_REGRESSION}`,
        },
      ],
      {
        frameAnchor: "top",
        dy: -18,
        text: "label",
        fontSize: 10.5,
        fontWeight: 700,
        fill: canFitLine ? "var(--ink-muted)" : "var(--warning)",
      },
    ),
  );

  return boxLegend(
    Plot.plot({
      width,
      height: 240,
      marginLeft: 52,
      marginRight: 16,
      marginBottom: 40,
      marginTop: 42,
      style: PLOT_STYLE,
      // labelAnchor: "center" evita que Plot ancle la etiqueta del eje X a la
      // derecha (su posición por defecto) -- con un texto largo como este,
      // ese anclaje la hace sobresalir del ancho de la tarjeta en vez de
      // quedar contenida dentro del gráfico.
      x: { label: "Kilometraje del vehículo (km)", labelAnchor: "center", labelArrow: false, grid: true },
      y: { label: "Monto (USD)", labelArrow: false, tickFormat: (d: number) => `$${d}` },
      color: { legend: true, label: "Vehículo" },
      marks,
    }),
  );
}

/** Períodos mínimos para que una media móvil de 3 diga algo distinto del
 * dato crudo — con menos, "suavizar" es solo borrar el único quiebre real. */
const MIN_N_SMOOTHING = 4;
const SMOOTHING_WINDOW = 3;

/** Media móvil final (ventana de los últimos `window` períodos) — reduce el
 * ruido punto-a-punto sin inventar un ciclo estacional que un año de datos
 * no puede sustentar. */
function movingAverage(points: TrendPoint[], window: number): { period_label: string; ma: number }[] {
  return points.map((_, i) => {
    const slice = points.slice(Math.max(0, i - window + 1), i + 1);
    const ma = slice.reduce((a, p) => a + Number(p.total_cost), 0) / slice.length;
    return { period_label: points[i].period_label, ma };
  });
}

/** Umbral compartido con `trendPlotHeight()`: por encima de esto, el eje X
 * inclina sus etiquetas y necesita más alto -- el contenedor de PlotFigure
 * (con su propio alto fijo en CSS) tiene que crecer exactamente cuando esto
 * pasa, o el SVG más alto se corta contra el contenedor. */
const MAX_X_TICKS = 14;

/** Alto que debe reservarle el contenedor (PlotFigure) a buildTrendPlot,
 * calculado con la misma condición que usa la función internamente -- para
 * que el `<div>` de altura fija nunca quede más bajo que el SVG real. */
export function trendPlotHeight(points: TrendPoint[]): number {
  return points.length > MAX_X_TICKS ? 320 : 260;
}

/** Panel "d": tendencia del costo en el tiempo, con línea punteada de
 * promedio y, si hay suficientes períodos, una media móvil que suaviza el
 * ruido punto-a-punto — sin simular una estacionalidad que un solo año de
 * historia no permite validar. */
export function buildTrendPlot(
  points: TrendPoint[],
  width: number,
  color: string,
): SVGElement | HTMLElement | null {
  if (points.length === 0) return null;
  const values = points.map((p) => Number(p.total_cost));
  const average = values.reduce((a, b) => a + b, 0) / values.length;
  const last = points[points.length - 1];
  const canSmooth = points.length >= MIN_N_SMOOTHING;
  const smoothed = canSmooth ? movingAverage(points, SMOOTHING_WINDOW) : [];

  const marks: Plot.Markish[] = [
    FRAME,
    Plot.ruleY([average], { stroke: "var(--danger)", strokeDasharray: "5,4", strokeWidth: 2 }),
    Plot.line(points, { x: "period_label", y: (d: TrendPoint) => Number(d.total_cost), stroke: color, strokeWidth: 1.5, strokeOpacity: 0.45 }),
    Plot.dot(points, {
      x: "period_label",
      y: (d: TrendPoint) => Number(d.total_cost),
      fill: "var(--surface)",
      stroke: color,
      strokeWidth: 1.5,
      strokeOpacity: 0.45,
      r: 3,
    }),
  ];

  if (canSmooth) {
    marks.push(Plot.line(smoothed, { x: "period_label", y: "ma", stroke: color, strokeWidth: 2.5 }));
  }

  // Las etiquetas de "promedio" y "tendencia" van fijas en la esquina
  // superior del marco -- no ancladas al valor de datos que describen,
  // porque ese valor puede caer en cualquier punto del eje Y. Con dy
  // negativo quedan por encima del área donde se dibuja la línea (en el
  // margen reservado abajo), así el texto nunca se dibuja encima de un
  // punto de datos ni de la otra etiqueta, sin importar qué tan cerca
  // caigan el promedio y la tendencia una de la otra.
  marks.push(
    Plot.text([{ label: `Promedio: ${currency.format(average)}` }], {
      frameAnchor: "top-right",
      dx: -6,
      dy: -12,
      text: "label",
      textAnchor: "end",
      fontWeight: 700,
      fontSize: 10.5,
      fill: "var(--danger)",
    }),
  );

  if (canSmooth) {
    marks.push(
      Plot.text([{ label: `Tendencia (promedio de los últimos ${SMOOTHING_WINDOW} meses)` }], {
        frameAnchor: "top-right",
        dx: -6,
        dy: -32,
        text: "label",
        textAnchor: "end",
        fontWeight: 700,
        fontSize: 10.5,
        fill: color,
      }),
    );
  } else {
    marks.push(
      Plot.text(
        [{ label: `Muy pocos meses todavía para trazar una tendencia (se necesitan al menos ${MIN_N_SMOOTHING})` }],
        { frameAnchor: "top-right", dx: -6, dy: -32, text: "label", textAnchor: "end", fontSize: 10, fontWeight: 700, fill: "var(--ink-muted)" },
      ),
    );
  }

  // En la vista "Semana" un año completo son más de 50 períodos -- mostrar
  // una etiqueta por cada uno los amontona hasta hacerlos ilegibles. Se
  // muestra como máximo ~14 etiquetas (una de cada N), siempre incluyendo la
  // más reciente, e inclinadas cuando hay muchas para que quepan sin
  // encimarse. Los puntos y la línea de datos siguen dibujándose todos;
  // solo se reduce cuántas etiquetas de fecha se imprimen debajo.
  const tickStep = Math.max(1, Math.ceil(points.length / MAX_X_TICKS));
  const tickValues = points
    .filter((_, i) => i % tickStep === 0 || i === points.length - 1)
    .map((p) => p.period_label);
  const rotateTicks = points.length > MAX_X_TICKS;

  return Plot.plot({
    width,
    // Mismo cálculo que trendPlotHeight() -- el contenedor de PlotFigure en
    // DashboardPage.tsx reserva exactamente este alto, así que si esto
    // cambia sin tocar esa función el SVG queda más alto que su contenedor
    // y se corta contra el borde inferior de la tarjeta.
    height: trendPlotHeight(points),
    marginLeft: 52,
    // Una etiqueta inclinada a -40° ocupa bastante más alto que una
    // horizontal (ancho del texto × seno del ángulo) -- 56px la dejaba
    // cortada a la mitad; con el texto más largo de esta vista ("Sem 37
    // (08/09)") hace falta bastante más margen para que se vea completa.
    marginBottom: rotateTicks ? 100 : 34,
    marginTop: 46,
    style: PLOT_STYLE,
    // period_label es texto ("Sep 2025", "Abr 2026", ...), asi que Plot lo
    // trata como escala ordinal; sin domain explicito, Plot ordena el
    // dominio inferido alfabeticamente (A-Z), no cronologicamente -- por
    // eso "Abr 2026" aparecia antes que "Sep 2025". `points` ya viene
    // ordenado por fecha real desde el backend (bucket_start en
    // service.py), asi que fijar el domain en ese mismo orden alcanza.
    x: {
      label: null,
      domain: points.map((p) => p.period_label),
      ticks: tickValues,
      tickRotate: rotateTicks ? -40 : 0,
    },
    y: { label: "Costo (USD)", labelArrow: false, grid: true, tickFormat: (d: number) => `$${d}` },
    marks,
  });
}

/** Costo por km de cada ruta — el contexto de dificultad que falta para
 * leer con justicia el ranking de costo/km por conductor: un número alto
 * puede ser mala conducción, o puede ser que le tocaron las rutas caras. */
export function buildRouteCostPlot(routes: RouteSummary[], width: number): SVGElement | HTMLElement | null {
  const data = routes
    .filter((r) => r.cost_per_km != null)
    .map((r) => ({
      label: `${r.origin} → ${r.destination}`,
      costPerKm: Number(r.cost_per_km),
      trips: r.trip_count,
    }))
    .sort((a, b) => b.costPerKm - a.costPerKm)
    .slice(0, 8);
  if (data.length === 0) return null;

  return Plot.plot({
    width,
    height: 220,
    marginLeft: 160,
    marginBottom: 34,
    style: PLOT_STYLE,
    x: { label: "Costo por km (USD/km)", labelAnchor: "center", labelArrow: false, tickFormat: (d: number) => `$${d.toFixed(2)}` },
    y: { label: null },
    marks: [
      FRAME,
      Plot.barX(data, {
        x: "costPerKm",
        y: "label",
        fill: "var(--chart-peaje)",
        stroke: "var(--ink)",
        strokeWidth: 1,
        sort: { y: "-x" },
      }),
      Plot.text(data, {
        x: "costPerKm",
        y: "label",
        text: (d) => `$${d.costPerKm.toFixed(2)}/km · ${d.trips} viajes`,
        dx: -8,
        textAnchor: "end",
        fill: "#fff",
        fontWeight: 700,
        fontSize: 10.5,
      }),
    ],
  });
}
