import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, Minus, DollarSign, Building2, Users, Home,
  BarChart2, RefreshCw, CalendarDays, Trophy, Star, CheckCircle2, ArrowUpRight,
  Activity, Filter,
} from 'lucide-react';
import apiClient from '../../api/client';

// ─── Types ───────────────────────────────────────────────
interface KpiSummary {
  period: string;
  sales_count: number; sales_count_change: number | null;
  sales_volume: number; sales_volume_change: number | null;
  agency_commission: number; agency_commission_change: number | null;
  agent_commission_total: number;
  avg_ticket: number; avg_commission_pct: number;
  total_properties: number; active_properties: number; unassigned_properties: number;
  total_clients: number; total_agents: number;
  visit_completion_rate: number; portfolio_conversion_rate: number;
}
interface SalesByPeriod { period: string; count: number; volume: number; agency_commission: number; agent_commission: number; }
interface AgentPerformance {
  agent_id: string | null; agent_name: string; agent_email: string;
  sales_count: number; sales_volume: number; agent_commission: number;
  avg_ticket: number; active_properties: number;
  total_visits: number; completed_visits: number; visit_conversion_rate: number;
  avg_client_rating: number | null;
}
interface PipelineItem { status: string; label: string; count: number; total_value: number; avg_price: number; }
interface PropertyTypeItem { type: string; label: string; count: number; percentage: number; avg_price: number; }
interface CommissionSummary { label: string; agency_commission: number; agent_commission: number; total_commission: number; sales_count: number; }
interface VisitAnalytics { period: string; SCHEDULED: number; COMPLETED: number; CANCELLED: number; NO_SHOW: number; total: number; completion_rate: number; }
interface TopSale { id: string; property_title: string | null; agent_name: string | null; sale_price: number; agency_commission: number; sale_date: string | null; }
interface PriceRange { range: string; count: number; }
interface ClientAcquisition { period: string; Propietario: number; Demandante: number; total: number; }
interface AgentMonthly {
  period: string; year: number; month: number;
  sales_count: number; sales_volume: number; agent_commission: number;
  visits_total: number; visits_completed: number;
}
interface AgentEvolutionData {
  agent_id: string; agent_name: string; agent_email: string;
  assigned_properties: number;
  monthly: AgentMonthly[];
}

// ─── Helpers ─────────────────────────────────────────────
const fmt = (n: number) => n.toLocaleString('es-ES', { maximumFractionDigits: 0 });
const fmtEur = (n: number) => fmt(n) + ' €';
const fmtPct = (n: number) => n.toFixed(1) + '%';

const PERIOD_OPTIONS = [
  { value: 'this_month', label: 'Este mes' },
  { value: 'last_month', label: 'Mes anterior' },
  { value: 'this_quarter', label: 'Este trimestre' },
  { value: 'last_quarter', label: 'Trimestre anterior' },
  { value: 'this_year', label: 'Este año' },
  { value: 'last_year', label: 'Año anterior' },
  { value: 'last_12_months', label: 'Últimos 12 meses' },
  { value: 'all', label: 'Histórico total' },
];

const PIE_COLORS = ['#6366f1','#10b981','#f59e0b','#8b5cf6','#06b6d4','#f43f5e','#fb923c','#14b8a6'];
const PIPELINE_COLORS: Record<string, string> = {
  CAPTADA: '#94a3b8', PUBLICADA: '#3b82f6', EN_VISITAS: '#f59e0b',
  RESERVADA: '#8b5cf6', PENDIENTE_NOTARIA: '#fb923c', VENDIDA: '#10b981', RETIRADA: '#f43f5e',
};

// ─── Trend Arrow ─────────────────────────────────────────
function Trend({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null;
  if (value > 0) return (
    <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded-full">
      <TrendingUp className="w-3 h-3" />+{value.toFixed(1)}%
    </span>
  );
  if (value < 0) return (
    <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded-full">
      <TrendingDown className="w-3 h-3" />{value.toFixed(1)}%
    </span>
  );
  return <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded-full"><Minus className="w-3 h-3" />0%</span>;
}

// ─── Inline SVG Bar Chart ─────────────────────────────────
function BarChartSVG({ data, valueKey, labelKey, colorFn, height = 180, formatVal = fmtEur }: {
  data: Record<string, any>[]; valueKey: string; labelKey: string;
  colorFn?: (i: number) => string; height?: number; formatVal?: (n: number) => string;
}) {
  if (!data.length) return <div className="flex items-center justify-center h-32 text-sm text-slate-400">Sin datos</div>;
  const max = Math.max(...data.map(d => d[valueKey] as number), 1);
  const barW = Math.max(8, Math.floor(480 / data.length) - 8);

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${Math.max(480, data.length * (barW + 8))} ${height + 40}`} className="w-full" style={{ minWidth: 300 }}>
        {data.map((d, i) => {
          const x = i * (barW + 8) + 4;
          const val = d[valueKey] as number;
          const barH = Math.max(2, (val / max) * height);
          const y = height - barH;
          const color = colorFn ? colorFn(i) : PIE_COLORS[i % PIE_COLORS.length];
          return (
            <g key={i}>
              <rect x={x} y={y} width={barW} height={barH} rx={3} fill={color} opacity={0.85} />
              <text x={x + barW / 2} y={height + 14} textAnchor="middle" fontSize={9} fill="#94a3b8">
                {String(d[labelKey]).slice(-5)}
              </text>
              <title>{d[labelKey]}: {formatVal(val)}</title>
            </g>
          );
        })}
        <line x1={0} y1={height} x2={Math.max(480, data.length * (barW + 8))} y2={height} stroke="#e2e8f0" strokeWidth={1} />
      </svg>
    </div>
  );
}

// ─── SVG Area/Line Chart ──────────────────────────────────
function AreaChartSVG({ data, keys, colors, labelKey, height = 200 }: {
  data: Record<string, any>[]; keys: string[]; colors: string[]; labelKey: string; height?: number;
}) {
  if (!data.length) return <div className="flex items-center justify-center h-32 text-sm text-slate-400">Sin datos</div>;
  const W = 540; const H = height; const pad = { t: 10, r: 10, b: 30, l: 50 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;

  const allVals = data.flatMap(d => keys.map(k => d[k] as number));
  const maxVal = Math.max(...allVals, 1);

  const xStep = data.length > 1 ? innerW / (data.length - 1) : innerW;
  const scaleY = (v: number) => innerH - (v / maxVal) * innerH;

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(f => ({ v: maxVal * f, y: scaleY(maxVal * f) }));

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 300 }}>
        <defs>
          {keys.map((k, ki) => (
            <linearGradient key={k} id={`grad-${ki}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={colors[ki]} stopOpacity={0.2} />
              <stop offset="95%" stopColor={colors[ki]} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>

        {/* Y grid */}
        {yTicks.map(t => (
          <g key={t.v}>
            <line x1={pad.l} y1={pad.t + t.y} x2={W - pad.r} y2={pad.t + t.y} stroke="#f1f5f9" strokeWidth={1} />
            <text x={pad.l - 4} y={pad.t + t.y + 4} textAnchor="end" fontSize={9} fill="#94a3b8">
              {t.v >= 1000 ? `${(t.v / 1000).toFixed(0)}K` : t.v.toFixed(0)}
            </text>
          </g>
        ))}

        {/* Areas + lines */}
        {keys.map((k, ki) => {
          const pts = data.map((d, i) => ({
            x: pad.l + i * xStep,
            y: pad.t + scaleY(d[k] as number),
          }));
          const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
          const areaPath = linePath
            + ` L${pts[pts.length - 1].x},${pad.t + innerH} L${pts[0].x},${pad.t + innerH} Z`;

          return (
            <g key={k}>
              <path d={areaPath} fill={`url(#grad-${ki})`} />
              <path d={linePath} fill="none" stroke={colors[ki]} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              {pts.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={3} fill={colors[ki]}>
                  <title>{data[i][labelKey]}: {fmtEur(data[i][k])}</title>
                </circle>
              ))}
            </g>
          );
        })}

        {/* X labels */}
        {data.map((d, i) => (
          <text key={i} x={pad.l + i * xStep} y={H - 4} textAnchor="middle" fontSize={9} fill="#94a3b8">
            {String(d[labelKey]).slice(-5)}
          </text>
        ))}
      </svg>

      {/* Legend */}
      <div className="flex gap-4 mt-2 justify-center">
        {keys.map((k, ki) => (
          <div key={k} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: colors[ki] }} />
            <span className="text-xs text-slate-500 capitalize">{k.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SVG Stacked Bar ─────────────────────────────────────
function StackedBarSVG({ data, keys, colors, labelKey, height = 180 }: {
  data: Record<string, any>[]; keys: string[]; colors: string[]; labelKey: string; height?: number;
}) {
  if (!data.length) return <div className="flex items-center justify-center h-32 text-sm text-slate-400">Sin datos en el período</div>;
  const max = Math.max(...data.map(d => keys.reduce((s, k) => s + (d[k] as number), 0)), 1);
  const barW = Math.max(24, Math.floor(480 / data.length) - 12);

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${Math.max(480, data.length * (barW + 12))} ${height + 40}`} className="w-full" style={{ minWidth: 300 }}>
        {data.map((d, i) => {
          const x = i * (barW + 12) + 6;
          let yOffset = 0;
          return (
            <g key={i}>
              {keys.map((k, ki) => {
                const val = d[k] as number;
                const barH = Math.max(val > 0 ? 2 : 0, (val / max) * height);
                const y = height - yOffset - barH;
                yOffset += barH;
                return (
                  <rect key={k} x={x} y={y} width={barW} height={barH}
                    rx={ki === keys.length - 1 ? 3 : 0}
                    fill={colors[ki]} opacity={0.85}>
                    <title>{d[labelKey]} — {k}: {fmtEur(val)}</title>
                  </rect>
                );
              })}
              <text x={x + barW / 2} y={height + 14} textAnchor="middle" fontSize={9} fill="#94a3b8">
                {String(d[labelKey]).slice(-6)}
              </text>
            </g>
          );
        })}
        <line x1={0} y1={height} x2={Math.max(480, data.length * (barW + 12))} y2={height} stroke="#e2e8f0" strokeWidth={1} />
      </svg>
      <div className="flex gap-4 mt-2 justify-center flex-wrap">
        {keys.map((k, ki) => (
          <div key={k} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: colors[ki] }} />
            <span className="text-xs text-slate-500">{k.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SVG Donut chart ─────────────────────────────────────
function DonutSVG({ data, labelKey, valueKey }: {
  data: Record<string, any>[]; labelKey: string; valueKey: string;
}) {
  if (!data.length) return <div className="flex items-center justify-center h-32 text-sm text-slate-400">Sin datos</div>;
  const total = data.reduce((s, d) => s + (d[valueKey] as number), 0);
  const cx = 80; const cy = 80; const R = 62; const r = 40;

  let angle = -Math.PI / 2;
  const slices = data.map((d, i) => {
    const val = d[valueKey] as number;
    const sweep = (val / total) * 2 * Math.PI;
    const x1 = cx + R * Math.cos(angle); const y1 = cy + R * Math.sin(angle);
    angle += sweep;
    const x2 = cx + R * Math.cos(angle); const y2 = cy + R * Math.sin(angle);
    const ix1 = cx + r * Math.cos(angle - sweep); const iy1 = cy + r * Math.sin(angle - sweep);
    const ix2 = cx + r * Math.cos(angle); const iy2 = cy + r * Math.sin(angle);
    const large = sweep > Math.PI ? 1 : 0;
    const path = `M${x1},${y1} A${R},${R} 0 ${large},1 ${x2},${y2} L${ix2},${iy2} A${r},${r} 0 ${large},0 ${ix1},${iy1} Z`;
    return { path, color: PIE_COLORS[i % PIE_COLORS.length], label: d[labelKey], val, pct: Math.round(val / total * 100) };
  });

  return (
    <div className="flex items-center gap-4 flex-wrap">
      <svg viewBox="0 0 160 160" className="w-36 h-36 flex-shrink-0">
        {slices.map((s, i) => (
          <path key={i} d={s.path} fill={s.color} opacity={0.9}>
            <title>{s.label}: {s.val} ({s.pct}%)</title>
          </path>
        ))}
        <text x={cx} y={cy - 6} textAnchor="middle" fontSize={18} fontWeight="700" fill="#1e293b">{total}</text>
        <text x={cx} y={cy + 12} textAnchor="middle" fontSize={9} fill="#94a3b8">total</text>
      </svg>
      <div className="flex-1 space-y-2 min-w-[120px]">
        {slices.slice(0, 6).map((s, i) => (
          <div key={i} className="flex items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: s.color }} />
              <span className="text-slate-600 truncate max-w-[100px]">{s.label}</span>
            </div>
            <span className="font-semibold text-slate-800">{s.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Agent colour palette (stable per index) ─────────────
const AGENT_COLORS = [
  '#6366f1','#10b981','#f59e0b','#f43f5e','#06b6d4',
  '#8b5cf6','#fb923c','#14b8a6','#3b82f6','#ec4899',
];

// ─── Multi-line SVG chart ─────────────────────────────────
interface LineSeries { label: string; color: string; values: number[]; }

function MultiLineSVG({
  periods, series, formatY = fmtEur, height = 220,
}: {
  periods: string[]; series: LineSeries[]; formatY?: (n: number) => string; height?: number;
}) {
  if (!periods.length || !series.length) {
    return <div className="flex items-center justify-center h-40 text-sm text-slate-400">Sin datos para el período seleccionado</div>;
  }

  const W = 560; const H = height;
  const pad = { t: 14, r: 80, b: 32, l: 56 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;

  const allVals = series.flatMap(s => s.values);
  const maxVal = Math.max(...allVals, 1);
  const xStep = periods.length > 1 ? innerW / (periods.length - 1) : innerW;
  const scaleY = (v: number) => innerH - (v / maxVal) * innerH;

  // Y ticks: 5 levels
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(f => ({
    v: maxVal * f,
    y: scaleY(maxVal * f),
  }));

  // Show every Nth x label to avoid overlap
  const xLabelStep = Math.max(1, Math.ceil(periods.length / 8));

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 320 }}>
        <defs>
          {series.map((s, si) => (
            <linearGradient key={si} id={`evo-grad-${si}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={s.color} stopOpacity={0.15} />
              <stop offset="90%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>

        {/* Y grid + labels */}
        {yTicks.map((t, ti) => (
          <g key={ti}>
            <line
              x1={pad.l} y1={pad.t + t.y}
              x2={W - pad.r} y2={pad.t + t.y}
              stroke="#f1f5f9" strokeWidth={1}
            />
            <text x={pad.l - 6} y={pad.t + t.y + 4} textAnchor="end" fontSize={9} fill="#94a3b8">
              {t.v >= 1_000_000
                ? `${(t.v / 1_000_000).toFixed(1)}M`
                : t.v >= 1_000
                ? `${(t.v / 1_000).toFixed(0)}K`
                : t.v.toFixed(0)}
            </text>
          </g>
        ))}

        {/* Area fills */}
        {series.map((s, si) => {
          if (s.values.every(v => v === 0)) return null;
          const pts = s.values.map((v, i) => ({
            x: pad.l + i * xStep,
            y: pad.t + scaleY(v),
          }));
          const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
          const areaPath = linePath
            + ` L${pts[pts.length - 1].x.toFixed(1)},${(pad.t + innerH).toFixed(1)}`
            + ` L${pts[0].x.toFixed(1)},${(pad.t + innerH).toFixed(1)} Z`;
          return (
            <path key={`area-${si}`} d={areaPath} fill={`url(#evo-grad-${si})`} />
          );
        })}

        {/* Lines + dots */}
        {series.map((s, si) => {
          if (s.values.every(v => v === 0)) return null;
          const pts = s.values.map((v, i) => ({
            x: pad.l + i * xStep,
            y: pad.t + scaleY(v),
            v,
          }));
          const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
          return (
            <g key={`line-${si}`}>
              <path d={linePath} fill="none" stroke={s.color} strokeWidth={2.5}
                strokeLinecap="round" strokeLinejoin="round" />
              {pts.map((p, i) => (
                <g key={i}>
                  <circle cx={p.x} cy={p.y} r={4} fill={s.color} opacity={0.9} />
                  <circle cx={p.x} cy={p.y} r={2} fill="white" />
                  <title>{periods[i]} — {s.label}: {formatY(p.v)}</title>
                </g>
              ))}
              {/* Inline label at line end */}
              <text
                x={pts[pts.length - 1].x + 6}
                y={pts[pts.length - 1].y + 4}
                fontSize={9} fill={s.color} fontWeight="600"
              >
                {s.label.split(' ')[0]}
              </text>
            </g>
          );
        })}

        {/* X axis labels */}
        {periods.map((p, i) => i % xLabelStep === 0 && (
          <text key={i} x={pad.l + i * xStep} y={H - 6}
            textAnchor="middle" fontSize={9} fill="#94a3b8">
            {p.slice(-5)}
          </text>
        ))}

        {/* X axis line */}
        <line x1={pad.l} y1={pad.t + innerH} x2={W - pad.r} y2={pad.t + innerH}
          stroke="#e2e8f0" strokeWidth={1} />
      </svg>
    </div>
  );
}

// ─── Agent Evolution Section ─────────────────────────────
type EvoKpi = 'sales_volume' | 'sales_count' | 'agent_commission' | 'visits_completed' | 'visits_total';

const KPI_TABS: { key: EvoKpi; label: string; format: (n: number) => string }[] = [
  { key: 'sales_volume',      label: 'Volumen Ventas',    format: fmtEur },
  { key: 'sales_count',       label: 'Nº Ventas',         format: n => String(n) },
  { key: 'agent_commission',  label: 'Comisión Agente',   format: fmtEur },
  { key: 'visits_completed',  label: 'Visitas Realizadas',format: n => String(n) },
  { key: 'visits_total',      label: 'Total Visitas',     format: n => String(n) },
];

const MONTH_OPTIONS = [
  { value: 6,  label: '6 meses' },
  { value: 12, label: '12 meses' },
  { value: 24, label: '24 meses' },
];

function AgentEvolutionSection({
  data, loading, months, onMonthsChange,
  selectedAgents, onSelectedAgentsChange, kpi, onKpiChange,
}: {
  data: AgentEvolutionData[];
  loading: boolean;
  months: number;
  onMonthsChange: (m: number) => void;
  selectedAgents: Set<string>;
  onSelectedAgentsChange: (s: Set<string>) => void;
  kpi: EvoKpi;
  onKpiChange: (k: EvoKpi) => void;
}) {
  const kpiDef = KPI_TABS.find(k => k.key === kpi)!;

  // Build periods from first agent (all have same periods)
  const periods = data[0]?.monthly.map(m => m.period) ?? [];

  // Build series only for selected agents
  const activeSeries: LineSeries[] = data
    .filter(a => selectedAgents.has(a.agent_id))
    .map((a, i) => ({
      label: a.agent_name,
      color: AGENT_COLORS[data.indexOf(a) % AGENT_COLORS.length],
      values: a.monthly.map(m => m[kpi]),
    }));

  const toggleAgent = (id: string) => {
    const next = new Set(selectedAgents);
    if (next.has(id)) {
      if (next.size > 1) next.delete(id); // keep at least one
    } else {
      next.add(id);
    }
    onSelectedAgentsChange(next);
  };

  const selectAll = () => onSelectedAgentsChange(new Set(data.map(a => a.agent_id)));
  const selectNone = () => onSelectedAgentsChange(new Set([data[0]?.agent_id].filter(Boolean)));

  return (
    <div className="bg-white rounded-2xl shadow-sm ring-1 ring-slate-900/5 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-indigo-50 flex items-center justify-center">
              <Activity className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Evolución de Agentes</h2>
              <p className="text-xs text-slate-400">Seguimiento mensual de KPIs por agente</p>
            </div>
          </div>
          {/* Window selector */}
          <div className="flex items-center gap-2">
            <CalendarDays className="w-4 h-4 text-slate-400" />
            <div className="flex rounded-xl overflow-hidden ring-1 ring-slate-200">
              {MONTH_OPTIONS.map(o => (
                <button
                  key={o.value}
                  onClick={() => onMonthsChange(o.value)}
                  className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
                    months === o.value
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-slate-500 hover:bg-slate-50'
                  }`}
                >{o.label}</button>
              ))}
            </div>
          </div>
        </div>

        {/* KPI Tabs */}
        <div className="mt-4 flex flex-wrap gap-2">
          {KPI_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => onKpiChange(tab.key)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                kpi === tab.key
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >{tab.label}</button>
          ))}
        </div>
      </div>

      <div className="p-6 flex flex-col lg:flex-row gap-6">
        {/* Agent filter panel */}
        <div className="w-full lg:w-56 flex-shrink-0">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
              <Filter className="w-3.5 h-3.5" /> Agentes
            </div>
            <div className="flex gap-2">
              <button onClick={selectAll} className="text-[10px] text-indigo-600 hover:underline font-medium">Todos</button>
              <span className="text-slate-300">·</span>
              <button onClick={selectNone} className="text-[10px] text-slate-400 hover:underline font-medium">Solo 1</button>
            </div>
          </div>

          <div className="space-y-1.5">
            {data.map((agent, i) => {
              const color = AGENT_COLORS[i % AGENT_COLORS.length];
              const isSelected = selectedAgents.has(agent.agent_id);
              const totalKpi = agent.monthly.reduce((s, m) => s + m[kpi], 0);
              return (
                <button
                  key={agent.agent_id}
                  onClick={() => toggleAgent(agent.agent_id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left transition-all ${
                    isSelected
                      ? 'ring-2 bg-slate-50'
                      : 'ring-1 ring-slate-100 opacity-40 hover:opacity-60'
                  }`}
                  style={{ ringColor: isSelected ? color : undefined }}
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full flex-shrink-0 transition-all"
                    style={{ background: isSelected ? color : '#cbd5e1' }}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-800 truncate">{agent.agent_name}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {kpiDef.format(totalKpi)} total · {agent.assigned_properties} props
                    </p>
                  </div>
                  <div
                    className="h-6 w-1 rounded-full flex-shrink-0"
                    style={{ background: isSelected ? color : '#e2e8f0' }}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {/* Chart */}
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="flex items-center justify-center h-52">
              <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-indigo-600" />
            </div>
          ) : (
            <>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                {kpiDef.label} — evolución mensual
              </p>
              <MultiLineSVG
                periods={periods}
                series={activeSeries}
                formatY={kpiDef.format}
                height={220}
              />
              {/* Summary stats for selected agents */}
              {activeSeries.length > 0 && (
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {activeSeries.slice(0, 4).map((s, i) => {
                    const total = s.values.reduce((a, b) => a + b, 0);
                    const peak = Math.max(...s.values);
                    const peakIdx = s.values.indexOf(peak);
                    return (
                      <div key={i} className="bg-slate-50 rounded-xl p-3">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                          <span className="text-[10px] font-semibold text-slate-500 uppercase truncate">{s.label}</span>
                        </div>
                        <p className="text-sm font-bold text-slate-900">{kpiDef.format(total)}</p>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          Pico: {kpiDef.format(peak)} ({periods[peakIdx]?.slice(-5) ?? '—'})
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────
export default function Reports() {
  const [period, setPeriod] = useState('this_year');
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [salesTrend, setSalesTrend] = useState<SalesByPeriod[]>([]);
  const [agentPerf, setAgentPerf] = useState<AgentPerformance[]>([]);
  const [pipeline, setPipeline] = useState<PipelineItem[]>([]);
  const [propTypes, setPropTypes] = useState<PropertyTypeItem[]>([]);
  const [commissions, setCommissions] = useState<CommissionSummary[]>([]);
  const [visits, setVisits] = useState<VisitAnalytics[]>([]);
  const [clients, setClients] = useState<ClientAcquisition[]>([]);
  const [topSales, setTopSales] = useState<TopSale[]>([]);
  const [priceRange, setPriceRange] = useState<PriceRange[]>([]);

  // Agent evolution
  const [agentEvolution, setAgentEvolution] = useState<AgentEvolutionData[]>([]);
  const [evoMonths, setEvoMonths] = useState(12);
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());
  const [evoKpi, setEvoKpi] = useState<
    'sales_volume' | 'sales_count' | 'agent_commission' | 'visits_completed' | 'visits_total'
  >('sales_volume');
  const [evoLoading, setEvoLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [kpiR, salesR, agentR, pipeR, typeR, commR, visitR, clientR, topR, priceR] =
        await Promise.all([
          apiClient.get(`/reports/kpi-summary?period=${period}`),
          apiClient.get('/reports/sales-by-period?months=12'),
          apiClient.get(`/reports/agent-performance?period=${period}`),
          apiClient.get('/reports/pipeline-funnel'),
          apiClient.get('/reports/property-type-breakdown'),
          apiClient.get(`/reports/commission-summary?period=${period}`),
          apiClient.get('/reports/visit-analytics?months=6'),
          apiClient.get('/reports/client-acquisition?months=12'),
          apiClient.get(`/reports/top-sales?period=${period}&limit=7`),
          apiClient.get('/reports/price-distribution'),
        ]);
      setKpi(kpiR.data);
      setSalesTrend(salesR.data);
      const perfData: AgentPerformance[] = agentR.data;
      setAgentPerf(perfData);
      setPipeline(pipeR.data);
      setPropTypes(typeR.data);
      setCommissions(commR.data);
      setVisits(visitR.data);
      setClients(clientR.data);
      setTopSales(topR.data);
      setPriceRange(priceR.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [period, refreshKey]);

  const fetchEvolution = useCallback(async () => {
    setEvoLoading(true);
    try {
      const res = await apiClient.get(`/reports/agent-evolution?months=${evoMonths}`);
      const data: AgentEvolutionData[] = res.data;
      setAgentEvolution(data);
      // Default: select all agents
      setSelectedAgents(prev =>
        prev.size === 0 ? new Set(data.map(a => a.agent_id)) : prev
      );
    } catch (e) { console.error(e); }
    finally { setEvoLoading(false); }
  }, [evoMonths, refreshKey]);

  useEffect(() => { fetchEvolution(); }, [fetchEvolution]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // KPI card definitions
  const kpiCards = kpi ? [
    { label: 'Ventas cerradas', value: String(kpi.sales_count), sub: fmtEur(kpi.sales_volume) + ' en ventas', change: kpi.sales_count_change, icon: CheckCircle2, bg: 'bg-indigo-50', text: 'text-indigo-600' },
    { label: 'Comisión Agencia', value: fmtEur(kpi.agency_commission), sub: fmtPct(kpi.avg_commission_pct) + ' sobre venta', change: kpi.agency_commission_change, icon: DollarSign, bg: 'bg-emerald-50', text: 'text-emerald-600' },
    { label: 'Ticket Medio', value: fmtEur(kpi.avg_ticket), sub: kpi.active_properties + ' propiedades activas', change: null, icon: Building2, bg: 'bg-amber-50', text: 'text-amber-600' },
    { label: 'Visitas Completadas', value: fmtPct(kpi.visit_completion_rate), sub: fmtPct(kpi.portfolio_conversion_rate) + ' conv. portfolio', change: null, icon: CalendarDays, bg: 'bg-violet-50', text: 'text-violet-600' },
    { label: 'Clientes / Agentes', value: `${kpi.total_clients} / ${kpi.total_agents}`, sub: kpi.unassigned_properties + ' props. sin agente', change: null, icon: Users, bg: 'bg-rose-50', text: 'text-rose-600' },
  ] : [];

  if (loading) return (
    <div className="flex items-center justify-center min-h-[70vh] flex-col gap-4">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600" />
      <p className="text-slate-500 text-sm font-medium">Cargando analíticas...</p>
    </div>
  );

  const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
    <div className={`bg-white rounded-2xl p-6 shadow-sm ring-1 ring-slate-900/5 ${className}`}>{children}</div>
  );

  const SectionHeader = ({ icon: Icon, title, subtitle }: { icon: React.ElementType; title: string; subtitle?: string }) => (
    <div className="flex items-center gap-3 mb-5">
      <div className="h-9 w-9 rounded-xl bg-indigo-50 flex items-center justify-center flex-shrink-0">
        <Icon className="h-5 w-5 text-indigo-600" />
      </div>
      <div>
        <h2 className="text-sm font-bold text-slate-900">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>
    </div>
  );

  return (
    <div className="p-6 lg:p-8 space-y-8 max-w-[1600px] mx-auto">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Reportes y Analíticas</h1>
          <p className="text-slate-500 mt-1 text-sm">Visión integral del rendimiento del negocio inmobiliario.</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={period} onChange={e => setPeriod(e.target.value)}
            className="rounded-xl border-0 ring-1 ring-slate-300 py-2 pl-3 pr-8 text-sm font-medium text-slate-800 bg-white focus:ring-2 focus:ring-indigo-600 shadow-sm">
            {PERIOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button onClick={() => setRefreshKey(k => k + 1)}
            className="p-2 rounded-xl bg-white ring-1 ring-slate-200 text-slate-500 hover:text-indigo-600 hover:ring-indigo-300 transition-all shadow-sm" title="Actualizar">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── KPI Cards ── */}
      {kpi && (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          {kpiCards.map(card => {
            const Icon = card.icon;
            return (
              <div key={card.label} className="bg-white rounded-2xl p-5 shadow-sm ring-1 ring-slate-900/5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide leading-tight">{card.label}</p>
                  <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${card.bg} flex-shrink-0`}>
                    <Icon className={`h-4 w-4 ${card.text}`} />
                  </div>
                </div>
                <p className="text-2xl font-bold text-slate-900 leading-tight">{card.value}</p>
                <div className="flex items-center justify-between mt-2 gap-2">
                  <p className="text-xs text-slate-400 truncate">{card.sub}</p>
                  {card.change !== null && <Trend value={card.change} />}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Unassigned Alert ── */}
      {kpi && kpi.unassigned_properties > 0 && (
        <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
          <Home className="h-4 w-4 text-amber-600 flex-shrink-0" />
          <p className="text-sm text-amber-800 font-medium">
            <span className="font-bold">{kpi.unassigned_properties}</span> propiedad{kpi.unassigned_properties !== 1 ? 'es' : ''} activa{kpi.unassigned_properties !== 1 ? 's' : ''} sin agente asignado.
          </p>
          <a href="/properties" className="ml-auto text-xs font-semibold text-amber-700 hover:underline flex items-center gap-1">Ver <ArrowUpRight className="w-3 h-3" /></a>
        </div>
      )}

      {/* ── Row 1: Sales Trend + Pipeline ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        <Card className="xl:col-span-2">
          <SectionHeader icon={TrendingUp} title="Tendencia de Ventas" subtitle="Últimos 12 meses — volumen y comisiones" />
          <AreaChartSVG
            data={salesTrend}
            keys={['volume', 'agency_commission']}
            colors={['#6366f1', '#10b981']}
            labelKey="period"
          />
        </Card>

        <Card>
          <SectionHeader icon={BarChart2} title="Pipeline Inmobiliario" subtitle="Propiedades por estado del proceso" />
          <div className="space-y-3">
            {pipeline.map(p => {
              const maxCount = Math.max(...pipeline.map(x => x.count), 1);
              const pct = (p.count / maxCount) * 100;
              return (
                <div key={p.status}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium text-slate-700">{p.label}</span>
                    <span className="font-bold text-slate-900 tabular-nums">{p.count}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${pct}%`, backgroundColor: PIPELINE_COLORS[p.status] || '#6366f1' }} />
                  </div>
                  {p.total_value > 0 && (
                    <p className="text-[10px] text-slate-400 mt-0.5">{fmtEur(p.total_value)} · avg {fmtEur(p.avg_price)}</p>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* ── Row 2: Commissions Stacked + Visits ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <SectionHeader icon={DollarSign} title="Desglose de Comisiones" subtitle="Agencia vs. Agentes por trimestre" />
          <StackedBarSVG
            data={commissions}
            keys={['agency_commission', 'agent_commission']}
            colors={['#6366f1', '#10b981']}
            labelKey="label"
          />
        </Card>

        <Card>
          <SectionHeader icon={CalendarDays} title="Analítica de Visitas" subtitle="Últimos 6 meses por estado" />
          <StackedBarSVG
            data={visits}
            keys={['COMPLETED', 'SCHEDULED', 'CANCELLED', 'NO_SHOW']}
            colors={['#10b981', '#3b82f6', '#f43f5e', '#f59e0b']}
            labelKey="period"
          />
        </Card>
      </div>

      {/* ── Row 3: Donut + Price Histogram + Client Acquisition ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <Card>
          <SectionHeader icon={Home} title="Composición del Portfolio" subtitle="Por tipo de inmueble" />
          <DonutSVG data={propTypes} labelKey="label" valueKey="count" />
        </Card>

        <Card>
          <SectionHeader icon={BarChart2} title="Distribución de Precios" subtitle="Nº de inmuebles por rango" />
          <BarChartSVG
            data={priceRange}
            valueKey="count"
            labelKey="range"
            formatVal={(n) => String(n) + ' props.'}
          />
        </Card>

        <Card>
          <SectionHeader icon={Users} title="Captación de Clientes" subtitle="Nuevos clientes por mes" />
          <AreaChartSVG
            data={clients}
            keys={['Propietario', 'Demandante']}
            colors={['#3b82f6', '#8b5cf6']}
            labelKey="period"
            height={160}
          />
        </Card>
      </div>

      {/* ── Row 4: Agent Performance Table ── */}
      <div className="bg-white rounded-2xl shadow-sm ring-1 ring-slate-900/5 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-amber-50 flex items-center justify-center">
            <Trophy className="h-5 w-5 text-amber-500" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Rendimiento por Agente</h2>
            <p className="text-xs text-slate-400">{PERIOD_OPTIONS.find(o => o.value === period)?.label}</p>
          </div>
        </div>
        {agentPerf.length === 0 ? (
          <p className="p-8 text-center text-slate-400 text-sm">Sin agentes con actividad en el período.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead>
                <tr className="bg-slate-50/50">
                  {['#', 'Agente', 'Ventas', 'Volumen', 'Comisión', 'Props', 'Visitas', 'Conversión', 'Rating', 'Performance'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {agentPerf.map((agent, idx) => {
                  const maxVol = agentPerf.find(a => a.agent_id !== null)?.sales_volume || 1;
                  const barPct = (agent.sales_volume / maxVol) * 100;
                  const isUnassigned = agent.agent_id === null;
                  const medal = isUnassigned
                    ? 'bg-amber-100 text-amber-700'
                    : idx === 0 ? 'bg-amber-100 text-amber-700'
                    : idx === 1 ? 'bg-slate-200 text-slate-600'
                    : idx === 2 ? 'bg-orange-100 text-orange-600'
                    : 'bg-slate-100 text-slate-400';
                  return (
                    <tr
                      key={agent.agent_id ?? `unassigned-${idx}`}
                      className={`transition-colors ${
                        isUnassigned
                          ? 'bg-amber-50/60 hover:bg-amber-50'
                          : 'hover:bg-slate-50/50'
                      }`}
                    >
                      <td className="px-4 py-4">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${medal}`}>
                          {isUnassigned ? '!' : idx + 1}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2.5">
                          <div className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0 ${
                            isUnassigned ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700'
                          }`}>
                            {isUnassigned ? '?' : (agent.agent_name?.charAt(0).toUpperCase() ?? '?')}
                          </div>
                          <div>
                            <p className={`text-sm font-semibold ${
                              isUnassigned ? 'text-amber-800' : 'text-slate-900'
                            }`}>{agent.agent_name}</p>
                            <p className="text-xs text-slate-400">{agent.agent_email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm font-bold text-center text-slate-900">{agent.sales_count}</td>
                      <td className="px-4 py-4 text-sm font-semibold text-slate-800 whitespace-nowrap">{fmtEur(agent.sales_volume)}</td>
                      <td className="px-4 py-4 text-sm font-semibold text-emerald-700 whitespace-nowrap">{fmtEur(agent.agent_commission)}</td>
                      <td className="px-4 py-4 text-sm text-center text-slate-600">{isUnassigned ? '—' : agent.active_properties}</td>
                      <td className="px-4 py-4 text-sm text-center text-slate-600">{isUnassigned ? '—' : agent.total_visits}</td>
                      <td className="px-4 py-4">
                        {isUnassigned ? (
                          <span className="text-slate-300 text-xs">—</span>
                        ) : (
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 bg-slate-100 rounded-full overflow-hidden">
                              <div className="h-full rounded-full bg-blue-500" style={{ width: `${agent.visit_conversion_rate}%` }} />
                            </div>
                            <span className="text-xs font-medium text-slate-600 tabular-nums">{fmtPct(agent.visit_conversion_rate)}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {agent.avg_client_rating !== null ? (
                          <span className="inline-flex items-center gap-1"><Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" /><span className="text-xs font-semibold text-slate-700">{agent.avg_client_rating.toFixed(1)}</span></span>
                        ) : <span className="text-slate-300 text-xs">—</span>}
                      </td>
                      <td className="px-4 py-4 min-w-[120px]">
                        {isUnassigned ? (
                          <span className="text-xs text-amber-600 font-medium">Ventas sin asignar</span>
                        ) : (
                          <>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div className="h-full rounded-full transition-all duration-700" style={{ width: `${barPct}%`, background: 'linear-gradient(90deg, #6366f1, #8b5cf6)' }} />
                            </div>
                            <p className="text-[10px] text-slate-400 mt-0.5">{barPct.toFixed(0)}% del top</p>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Row 5: Agent Evolution Charts ── */}
      <AgentEvolutionSection
        data={agentEvolution}
        loading={evoLoading}
        months={evoMonths}
        onMonthsChange={setEvoMonths}
        selectedAgents={selectedAgents}
        onSelectedAgentsChange={setSelectedAgents}
        kpi={evoKpi}
        onKpiChange={setEvoKpi}
      />

      {/* ── Row 6: Top Sales + Business Metrics ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

        <Card>
          <div className="flex items-center gap-2 mb-5">
            <Trophy className="h-5 w-5 text-amber-500" />
            <h2 className="text-sm font-bold text-slate-900">Top Ventas del Período</h2>
          </div>
          {topSales.length === 0 ? (
            <p className="text-center text-slate-400 text-sm py-6">Sin ventas en el período.</p>
          ) : (
            <div className="divide-y divide-slate-100 -mx-2">
              {topSales.map((s, i) => (
                <div key={s.id} className="flex items-center gap-3 px-2 py-3 hover:bg-slate-50 rounded-xl transition-colors">
                  <span className={`text-sm font-bold w-5 text-center flex-shrink-0 ${i === 0 ? 'text-amber-500' : 'text-slate-300'}`}>{i + 1}</span>
                  <div className="h-8 w-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                    <Building2 className="w-4 h-4 text-indigo-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-900 truncate">{s.property_title || '—'}</p>
                    <p className="text-xs text-slate-400">{s.agent_name || 'Sin agente'} · {s.sale_date ? new Date(s.sale_date).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-bold text-slate-900">{fmtEur(s.sale_price)}</p>
                    <p className="text-xs text-emerald-600 font-medium">{fmtEur(s.agency_commission)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {kpi && (
          <Card>
            <SectionHeader icon={BarChart2} title="Métricas Clave de Negocio" subtitle="Ratios de gestión del período" />
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Comisión media', value: fmtPct(kpi.avg_commission_pct), color: 'text-indigo-600' },
                { label: 'Ticket medio', value: fmtEur(kpi.avg_ticket), color: 'text-emerald-600' },
                { label: 'Conv. portfolio', value: fmtPct(kpi.portfolio_conversion_rate), color: 'text-amber-600' },
                { label: 'Tasa visitas OK', value: fmtPct(kpi.visit_completion_rate), color: 'text-violet-600' },
                { label: 'Sin agente', value: String(kpi.unassigned_properties), color: kpi.unassigned_properties > 0 ? 'text-rose-600' : 'text-emerald-600' },
                { label: 'Total clientes', value: String(kpi.total_clients), color: 'text-blue-600' },
                { label: 'Pago a agentes', value: fmtEur(kpi.agent_commission_total), color: 'text-slate-700' },
                { label: 'Props activas', value: `${kpi.active_properties} / ${kpi.total_properties}`, color: 'text-slate-700' },
              ].map(m => (
                <div key={m.label} className="bg-slate-50 rounded-xl p-4">
                  <p className="text-xs text-slate-500 mb-1">{m.label}</p>
                  <p className={`text-lg font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
