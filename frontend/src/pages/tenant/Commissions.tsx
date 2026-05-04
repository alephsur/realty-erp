import { useState, useEffect, useCallback } from 'react';
import {
  Euro, Clock, CheckCircle, FileText, ChevronDown, ChevronRight,
  Printer, X, AlertCircle,
} from 'lucide-react';
import client from '../../api/client';

// ─── Types ──────────────────────────────────────────────────────────────────

interface CommissionItem {
  id: string;
  sale_id: string;
  agent_id: string | null;
  agent_name: string;
  amount: number;
  status: 'PENDING' | 'INVOICED' | 'PAID';
  payment_date: string | null;
  invoice_number: string | null;
  notes: string | null;
  created_at: string | null;
  property_title: string | null;
  property_reference: string | null;
  sale_price: number | null;
  sale_date: string | null;
}

interface AgentGroup {
  agent_id: string;
  agent_name: string;
  total_pending: number;
  commissions: CommissionItem[];
}

interface Summary {
  total: number;
  pending: number;
  invoiced: number;
  paid: number;
  count_total: number;
  count_pending: number;
  count_invoiced: number;
  count_paid: number;
}

interface Agent {
  id: string;
  full_name: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function fmt(n: number | null) {
  if (n == null) return '—';
  return n.toLocaleString('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 });
}

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-ES');
}

function statusBadge(status: CommissionItem['status']) {
  const map = {
    PENDING:  { label: 'Pendiente',  cls: 'bg-amber-100 text-amber-800' },
    INVOICED: { label: 'Facturada',  cls: 'bg-blue-100 text-blue-800' },
    PAID:     { label: 'Pagada',     cls: 'bg-emerald-100 text-emerald-800' },
  };
  const { label, cls } = map[status] ?? { label: status, cls: 'bg-slate-100 text-slate-700' };
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>;
}

function periodOptions() {
  const year = new Date().getFullYear();
  const opts = [{ label: 'Todo el tiempo', value: 'all' }];
  for (let y = year; y >= year - 2; y--) {
    opts.push({ label: String(y), value: String(y) });
    for (let q = 4; q >= 1; q--) {
      opts.push({ label: `Q${q} ${y}`, value: `${y}-Q${q}` });
    }
  }
  return opts;
}

// ─── PDF export ─────────────────────────────────────────────────────────────

function exportPDF(agents: AgentGroup[], period: string) {
  const win = window.open('', '_blank');
  if (!win) return;
  const rows = agents.flatMap(ag =>
    ag.commissions.map(c => `
      <tr>
        <td>${ag.agent_name}</td>
        <td>${c.property_reference ?? '—'}</td>
        <td>${c.property_title ?? '—'}</td>
        <td>${fmtDate(c.sale_date)}</td>
        <td style="text-align:right">${fmt(c.sale_price)}</td>
        <td style="text-align:right">${fmt(c.amount)}</td>
        <td>${statusBadge(c.status).props.children}</td>
        <td>${c.invoice_number ?? '—'}</td>
        <td>${fmtDate(c.payment_date)}</td>
      </tr>`)
  ).join('');

  const total = agents.reduce((s, ag) => s + ag.total_pending, 0);

  win.document.write(`<!DOCTYPE html><html lang="es"><head>
    <meta charset="UTF-8">
    <title>Liquidación de Comisiones</title>
    <style>
      body { font-family: Arial, sans-serif; font-size: 12px; color: #1e293b; margin: 32px; }
      h1 { font-size: 20px; margin-bottom: 4px; }
      .meta { color: #64748b; margin-bottom: 24px; font-size: 11px; }
      table { width: 100%; border-collapse: collapse; }
      th { background: #1e40af; color: #fff; text-align: left; padding: 6px 8px; font-size: 11px; }
      td { border-bottom: 1px solid #e2e8f0; padding: 5px 8px; }
      tr:nth-child(even) td { background: #f8fafc; }
      .total-row td { font-weight: bold; border-top: 2px solid #1e40af; background: #eff6ff; }
      @media print { body { margin: 0; } }
    </style>
  </head><body>
    <h1>Liquidación de Comisiones</h1>
    <div class="meta">Período: ${period === 'all' ? 'Todo el tiempo' : period} &nbsp;|&nbsp; Generado: ${new Date().toLocaleDateString('es-ES')}</div>
    <table>
      <thead>
        <tr>
          <th>Agente</th><th>Ref.</th><th>Propiedad</th><th>Fecha venta</th>
          <th style="text-align:right">Precio venta</th><th style="text-align:right">Comisión</th>
          <th>Estado</th><th>Nº factura</th><th>Fecha pago</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
        <tr class="total-row">
          <td colspan="5">TOTAL PENDIENTE DE LIQUIDAR</td>
          <td style="text-align:right">${fmt(total)}</td>
          <td colspan="3"></td>
        </tr>
      </tbody>
    </table>
  </body></html>`);
  win.document.close();
  win.print();
}

// ─── Pay / Invoice Modal ─────────────────────────────────────────────────────

interface ActionModalProps {
  mode: 'pay' | 'invoice';
  commissionId: string;   // sale_id
  agentName: string;
  amount: number;
  onClose: () => void;
  onSuccess: () => void;
}

function ActionModal({ mode, commissionId, agentName, amount, onClose, onSuccess }: ActionModalProps) {
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = mode === 'pay' ? 'pay' : 'invoice';
      const body = mode === 'pay'
        ? { payment_date: paymentDate, invoice_number: invoiceNumber || null, notes: notes || null }
        : { invoice_number: invoiceNumber || null, notes: notes || null };
      await client.post(`/commissions/${commissionId}/${endpoint}`, body);
      onSuccess();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Error al procesar la comisión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900">
            {mode === 'pay' ? 'Marcar como pagada' : 'Marcar como facturada'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button>
        </div>

        <p className="text-sm text-slate-600 mb-4">
          Agente: <span className="font-semibold">{agentName}</span> — Importe: <span className="font-semibold text-indigo-700">{fmt(amount)}</span>
        </p>

        {error && (
          <div className="flex items-center gap-2 mb-4 text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />{error}
          </div>
        )}

        <div className="space-y-3">
          {mode === 'pay' && (
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Fecha de pago</label>
              <input type="date" value={paymentDate} onChange={e => setPaymentDate(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Nº de factura <span className="font-normal text-slate-400">(opcional)</span></label>
            <input type="text" placeholder="FAC-2026-001" value={invoiceNumber} onChange={e => setInvoiceNumber(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Notas <span className="font-normal text-slate-400">(opcional)</span></label>
            <textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
          </div>
        </div>

        <div className="flex gap-3 mt-5">
          <button onClick={onClose}
            className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Cancelar
          </button>
          <button onClick={submit} disabled={loading}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors ${
              mode === 'pay' ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-blue-600 hover:bg-blue-500'
            } disabled:opacity-60`}>
            {loading ? 'Guardando…' : mode === 'pay' ? 'Confirmar pago' : 'Confirmar factura'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Agent row (expandable) ──────────────────────────────────────────────────

function AgentRow({ group, onAction }: { group: AgentGroup; onAction: (c: CommissionItem, mode: 'pay' | 'invoice') => void }) {
  const [open, setOpen] = useState(true);
  const Icon = open ? ChevronDown : ChevronRight;

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center justify-between bg-slate-50 px-4 py-3 hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="h-4 w-4 text-slate-500" />
          <span className="font-semibold text-slate-900">{group.agent_name}</span>
          <span className="text-xs text-slate-500">{group.commissions.length} venta{group.commissions.length !== 1 ? 's' : ''}</span>
        </div>
        <span className="text-base font-bold text-amber-700">{fmt(group.total_pending)}</span>
      </button>

      {open && (
        <div className="divide-y divide-slate-100">
          {group.commissions.map(c => (
            <div key={c.id} className="flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-3 bg-white">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  {c.property_reference && (
                    <span className="text-xs font-mono text-slate-500">{c.property_reference}</span>
                  )}
                  <span className="text-sm font-semibold text-slate-800 truncate">{c.property_title ?? '—'}</span>
                  {statusBadge(c.status)}
                </div>
                <div className="text-xs text-slate-500 mt-0.5 flex flex-wrap gap-3">
                  <span>Venta: {fmtDate(c.sale_date)}</span>
                  <span>P. venta: {fmt(c.sale_price)}</span>
                  {c.invoice_number && <span>Factura: {c.invoice_number}</span>}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-indigo-700 whitespace-nowrap">{fmt(c.amount)}</span>
                {c.status !== 'PAID' && (
                  <div className="flex gap-2">
                    {c.status === 'PENDING' && (
                      <button onClick={() => onAction(c, 'invoice')}
                        className="flex items-center gap-1 rounded-lg border border-blue-300 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors">
                        <FileText className="h-3.5 w-3.5" />Facturar
                      </button>
                    )}
                    <button onClick={() => onAction(c, 'pay')}
                      className="flex items-center gap-1 rounded-lg border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors">
                      <CheckCircle className="h-3.5 w-3.5" />Pagar
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function Commissions() {
  const [tab, setTab] = useState<'pending' | 'history'>('pending');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [pendingGroups, setPendingGroups] = useState<AgentGroup[]>([]);
  const [historyItems, setHistoryItems] = useState<CommissionItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [filterAgent, setFilterAgent] = useState('');
  const [filterPeriod, setFilterPeriod] = useState('all');
  const [histPage, setHistPage] = useState(1);
  const [histPages, setHistPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ commission: CommissionItem; mode: 'pay' | 'invoice' } | null>(null);

  const periods = periodOptions();

  // Fetch summary and pending
  const fetchPending = useCallback(async () => {
    const [pendRes, sumRes] = await Promise.all([
      client.get('/commissions/pending'),
      client.get('/commissions/summary'),
    ]);
    setPendingGroups(pendRes.data);
    setSummary(sumRes.data);
  }, []);

  // Fetch history
  const fetchHistory = useCallback(async (page = 1) => {
    const params: Record<string, string | number> = { page, limit: 50, period: filterPeriod };
    if (filterAgent) params.agent_id = filterAgent;
    const res = await client.get('/commissions/history', { params });
    setHistoryItems(res.data.items);
    setHistoryTotal(res.data.total);
    setHistPages(res.data.pages);
    setHistPage(page);
  }, [filterAgent, filterPeriod]);

  // Fetch agents for filter dropdown
  const fetchAgents = useCallback(async () => {
    try {
      const res = await client.get('/auth/tenant/users');
      setAgents((res.data as any[]).filter((u: any) => u.role === 'AGENT' || u.role === 'MANAGER' || u.role === 'ADMIN'));
    } catch { /* non-critical */ }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([fetchPending(), fetchHistory(1), fetchAgents()]);
    } finally {
      setLoading(false);
    }
  }, [fetchPending, fetchHistory, fetchAgents]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Re-fetch history when filters change
  useEffect(() => {
    if (!loading) fetchHistory(1);
  }, [filterAgent, filterPeriod]); // eslint-disable-line react-hooks/exhaustive-deps

  const onModalSuccess = async () => {
    setModal(null);
    setLoading(true);
    try { await Promise.all([fetchPending(), fetchHistory(histPage)]); }
    finally { setLoading(false); }
  };

  if (loading && !summary) {
    return <div className="flex items-center justify-center h-64 text-slate-500">Cargando comisiones…</div>;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Comisiones</h1>
          <p className="text-sm text-slate-500 mt-1">Liquidación y seguimiento de pagos a agentes</p>
        </div>
        <button
          onClick={() => exportPDF(pendingGroups, 'Pendientes')}
          className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-sm"
        >
          <Printer className="h-4 w-4" />Exportar liquidación PDF
        </button>
      </div>

      {/* KPI cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total devengado', value: summary.total, count: summary.count_total, icon: Euro, color: 'text-slate-600', bg: 'bg-slate-50', border: 'border-slate-200' },
            { label: 'Pendiente de pago', value: summary.pending, count: summary.count_pending, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200' },
            { label: 'Facturado', value: summary.invoiced, count: summary.count_invoiced, icon: FileText, color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
            { label: 'Pagado', value: summary.paid, count: summary.count_paid, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
          ].map(({ label, value, count, icon: Icon, color, bg, border }) => (
            <div key={label} className={`rounded-xl border ${border} ${bg} p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className={`h-4 w-4 ${color}`} />
                <span className="text-xs font-semibold text-slate-600">{label}</span>
              </div>
              <p className={`text-xl font-bold ${color}`}>{fmt(value)}</p>
              <p className="text-xs text-slate-500 mt-0.5">{count} comisión{count !== 1 ? 'es' : ''}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200 flex gap-6">
        {([['pending', 'Por cobrar'], ['history', 'Historial']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`pb-3 text-sm font-semibold border-b-2 transition-colors ${
              tab === key ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Por cobrar tab ─────────────────────────────────────────────── */}
      {tab === 'pending' && (
        <div className="space-y-3">
          {pendingGroups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <CheckCircle className="h-10 w-10 mb-3 text-emerald-400" />
              <p className="font-semibold">Todo al día</p>
              <p className="text-sm">No hay comisiones pendientes de pago</p>
            </div>
          ) : pendingGroups.map(group => (
            <AgentRow key={group.agent_id} group={group}
              onAction={(c, mode) => setModal({ commission: c, mode })} />
          ))}
        </div>
      )}

      {/* ── Historial tab ─────────────────────────────────────────────── */}
      {tab === 'history' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <select value={filterAgent} onChange={e => setFilterAgent(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="">Todos los agentes</option>
              {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
            </select>
            <select value={filterPeriod} onChange={e => setFilterPeriod(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
              {periods.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
            <span className="ml-auto self-center text-xs text-slate-500">{historyTotal} registros</span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  {['Agente', 'Propiedad', 'Fecha venta', 'P. Venta', 'Comisión', 'Estado', 'Nº Factura', 'Fecha pago', ''].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {historyItems.length === 0 && (
                  <tr><td colSpan={9} className="py-10 text-center text-slate-400">Sin registros para los filtros seleccionados</td></tr>
                )}
                {historyItems.map(c => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-900 whitespace-nowrap">{c.agent_name}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{c.property_title ?? '—'}</div>
                      {c.property_reference && <div className="text-xs text-slate-400 font-mono">{c.property_reference}</div>}
                    </td>
                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{fmtDate(c.sale_date)}</td>
                    <td className="px-4 py-3 text-slate-700 whitespace-nowrap">{fmt(c.sale_price)}</td>
                    <td className="px-4 py-3 font-semibold text-indigo-700 whitespace-nowrap">{fmt(c.amount)}</td>
                    <td className="px-4 py-3">{statusBadge(c.status)}</td>
                    <td className="px-4 py-3 text-slate-600 font-mono text-xs">{c.invoice_number ?? '—'}</td>
                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{fmtDate(c.payment_date)}</td>
                    <td className="px-4 py-3">
                      {c.status !== 'PAID' && (
                        <div className="flex gap-1">
                          {c.status === 'PENDING' && (
                            <button onClick={() => setModal({ commission: c, mode: 'invoice' })}
                              className="text-xs text-blue-600 hover:underline">Facturar</button>
                          )}
                          <button onClick={() => setModal({ commission: c, mode: 'pay' })}
                            className="text-xs text-emerald-600 hover:underline ml-2">Pagar</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {histPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button disabled={histPage <= 1} onClick={() => fetchHistory(histPage - 1)}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg disabled:opacity-40 hover:bg-slate-50">
                ‹ Anterior
              </button>
              <span className="text-sm text-slate-600">Pág. {histPage} / {histPages}</span>
              <button disabled={histPage >= histPages} onClick={() => fetchHistory(histPage + 1)}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg disabled:opacity-40 hover:bg-slate-50">
                Siguiente ›
              </button>
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <ActionModal
          mode={modal.mode}
          commissionId={modal.commission.sale_id}
          agentName={modal.commission.agent_name}
          amount={modal.commission.amount}
          onClose={() => setModal(null)}
          onSuccess={onModalSuccess}
        />
      )}
    </div>
  );
}
