export interface OperationalMetrics {
  period_start: string | null; period_end: string;
  comparison_start: string | null; comparison_end: string | null;
  completed_visits: number; no_show_visits: number; unresolved_visits: number;
  attendance_denominator: number; visit_attendance_rate: number | null;
  visited_buyer_property_pairs: number; closed_buyer_property_pairs: number;
  visit_to_close_rate: number | null; completed_visits_without_buyer: number;
  visit_to_offer_rate: number | null; offer_to_close_rate: number | null;
  offer_metrics_unavailable_reason: string;
}
const rate = (value: number | null) => value == null ? 'Sin observaciones' : `${value.toFixed(1)}%`;
const instant = (value: string) => new Date(value).toLocaleString('es-ES', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' });

export function ReportPeriodNote({ metrics }: { metrics: OperationalMetrics }) {
  return <div className="rounded-xl bg-indigo-50 p-4 text-sm text-indigo-950 space-y-1">
    <p><strong>Periodo de actividad (UTC):</strong> {metrics.period_start ? `Desde ${instant(metrics.period_start)}` : 'Desde el primer registro'} hasta {instant(metrics.period_end)}.</p>
    <p>{metrics.comparison_start && metrics.comparison_end ? `Variaciones frente a ${instant(metrics.comparison_start)} – ${instant(metrics.comparison_end)} UTC; los periodos en curso se comparan con el mismo tiempo transcurrido, limitado a la duración del periodo anterior.` : 'El histórico total no tiene comparación con un periodo anterior.'}</p>
    <p>La cartera muestra la situación actual. Las series mensuales tienen su propio intervalo, indicado en cada gráfico.</p>
  </div>;
}

export default function ReportMetrics({ metrics }: { metrics: OperationalMetrics }) {
  const cards = [
    { label: 'Asistencia a visitas', value: rate(metrics.visit_attendance_rate),
      formula: 'Realizadas / (realizadas + ausencias). Se excluyen canceladas y pendientes de resultado.',
      detail: `${metrics.completed_visits} realizadas de ${metrics.attendance_denominator} con resultado; ${metrics.unresolved_visits} pendientes de resultado.` },
    { label: 'Visita → cierre', value: rate(metrics.visit_to_close_rate),
      formula: 'Comprador/inmueble con visita realizada en el periodo y cierre posterior hasta el final del periodo / pares comprador/inmueble visitados. Cada par cuenta una vez.',
      detail: `${metrics.closed_buyer_property_pairs} de ${metrics.visited_buyer_property_pairs} pares visitados. ${metrics.completed_visits_without_buyer} visitas sin comprador excluidas. Las ventas reabiertas no cuentan.` },
    { label: 'Visita → oferta', value: 'No disponible',
      formula: 'Pares comprador/inmueble visitados que presentan una oferta / pares visitados.',
      detail: metrics.offer_metrics_unavailable_reason },
    { label: 'Oferta → cierre', value: 'No disponible',
      formula: 'Ofertas que llegan a un cierre activo / ofertas presentadas.',
      detail: metrics.offer_metrics_unavailable_reason },
  ];
  return <section aria-label="Indicadores de asistencia y conversión" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
    {cards.map(card => <article key={card.label} className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-900/5 space-y-2">
      <h2 className="text-sm font-semibold text-slate-700">{card.label}</h2>
      <p className="text-2xl font-bold text-indigo-700">{card.value}</p>
      <p className="text-xs text-slate-600">{card.formula}</p>
      <p className="text-xs text-slate-500">{card.detail}</p>
    </article>)}
  </section>;
}
