import { useEffect, useRef, useState, type FormEvent } from 'react';
import { isAxiosError } from 'axios';
import client from '../api/client';
import SellPropertyModal, { type SaleRevision } from './SellPropertyModal';

type Snapshot = Record<string, string | boolean | number | null>;
interface Detail {
  sale: SaleRevision;
  events: { id: string; kind: string; version: number; actor_name: string; reason: string; created_at: string; before: Snapshot | null; after: Snapshot }[];
  commissions: { id: string; agent_name: string; amount: string; status: string; kind: string; invoice_number: string | null; payment_date: string | null }[];
}
const states = ['CAPTADA', 'PUBLICADA', 'EN_VISITAS', 'RESERVADA', 'PENDIENTE_NOTARIA', 'RETIRADA'];
const labels: Record<string, string> = {
  buyer_name: 'Comprador', agent_name: 'Agente', sale_price: 'Precio', commission_rate: 'Comisión (%)',
  agent_commission_rate: 'Parte del agente (%)', total_commission: 'Comisión total', agent_commission: 'Comisión del agente',
  agency_commission: 'Comisión de la agencia', sale_date: 'Fecha de cierre', notes: 'Notas', property_status: 'Estado de la propiedad',
};
const kindLabel: Record<string, string> = { CLOSED: 'Cierre', CORRECTED: 'Corrección', REOPENED: 'Reapertura' };
const statusLabel: Record<string, string> = { PENDING: 'Pendiente', INVOICED: 'Facturada', PAID: 'Liquidada' };

export default function SaleHistoryModal({ saleId, onClose, onChanged }: {
  saleId: string; onClose: () => void; onChanged: () => void;
}) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [mode, setMode] = useState<'history' | 'correct' | 'reopen'>('history');
  const [reason, setReason] = useState('');
  const [target, setTarget] = useState('PUBLICADA');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submitting = useRef(false);
  const attempt = useRef<{ signature: string; id: string } | null>(null);
  const dialog = useRef<HTMLElement>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    client.get<Detail>(`/sales/${saleId}`, { signal: controller.signal }).then(r => {
      if (!controller.signal.aborted) { setDetail(r.data); setError(''); }
    }).catch(() => { if (!controller.signal.aborted) setError('No se pudo cargar la venta.'); });
    return () => controller.abort();
  }, [saleId, reload]);
  useEffect(() => {
    if (mode === 'correct') return;
    const previous = document.activeElement;
    dialog.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting.current) onClose();
      if (event.key === 'Tab') {
        const controls = dialog.current?.querySelectorAll<HTMLElement>('button:enabled, input:enabled, select:enabled, textarea:enabled');
        if (!controls?.length) return;
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => { document.removeEventListener('keydown', handleKey); if (previous instanceof HTMLElement) previous.focus(); };
  }, [onClose, mode]);
  const changed = () => { setMode('history'); setReload(n => n + 1); onChanged(); };
  const reopen = async (event: FormEvent) => {
    event.preventDefault();
    if (!detail || submitting.current || !reason.trim()) return;
    const payload = { expected_version: detail.sale.version, target_status: target, reason: reason.trim() };
    const signature = JSON.stringify(payload);
    if (attempt.current?.signature !== signature) attempt.current = { signature, id: crypto.randomUUID() };
    submitting.current = true; setSaving(true); setError('');
    try {
      await client.post(`/sales/${saleId}/reopen`, { ...payload, request_id: attempt.current.id });
      changed();
    } catch (err) { setError(isAxiosError(err) && typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'No se pudo confirmar la reapertura. Puedes reintentar.'); }
    finally { submitting.current = false; setSaving(false); }
  };
  if (mode === 'correct' && detail) return <SellPropertyModal propertyId={detail.sale.property_id} revision={detail.sale} onClose={() => setMode('history')} onSold={changed} />;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <section ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="history-title" className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl space-y-4">
      <div className="flex justify-between gap-4"><h2 id="history-title" className="text-xl font-bold">Detalle e historial de la venta</h2><button disabled={saving} onClick={onClose} className="text-indigo-700">Cerrar</button></div>
      {error && <p role="alert" className="text-red-700">{error} <button disabled={saving} className="underline" onClick={() => setReload(n => n + 1)}>Actualizar</button></p>}
      {!detail ? <p>Cargando…</p> : <>
        <p>{detail.sale.is_active ? 'Venta activa' : 'Venta reabierta · sin efecto en los indicadores'} · Versión {detail.sale.version}</p>
        {detail.sale.is_active && mode === 'history' && <div className="flex gap-4"><button className="rounded-lg bg-indigo-600 px-4 py-2 text-white" onClick={() => setMode('correct')}>Corregir venta</button><button className="rounded-lg border border-amber-600 px-4 py-2 text-amber-800" onClick={() => setMode('reopen')}>Reabrir venta</button></div>}
        {mode === 'reopen' && <form onSubmit={reopen} className="space-y-3 rounded-xl bg-amber-50 p-4">
          <p>Se descontará la comisión de esta venta del saldo del agente. Los pagos y las facturas anteriores conservarán su historial. Después podrás registrar otro cierre con los nuevos datos.</p>
          <label className="block">Estado tras reabrir<select aria-label="Estado tras reabrir" disabled={saving} value={target} onChange={e => setTarget(e.target.value)} className="ml-3 rounded border p-2">{states.map(s => <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>)}</select></label>
          <label className="block">Motivo de la reapertura<textarea required disabled={saving} maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} className="mt-1 block w-full rounded border p-2" /></label>
          <button disabled={saving || !reason.trim()} className="rounded bg-amber-700 px-4 py-2 text-white disabled:opacity-50">{saving ? 'Guardando…' : 'Confirmar reapertura'}</button>
          <button type="button" disabled={saving} onClick={() => setMode('history')} className="ml-4">Cancelar</button>
        </form>}
        <h3 className="font-bold">Cambios registrados</h3>
        {!detail.events.length && <p className="text-sm text-slate-500">Venta anterior al registro de revisiones. La primera modificación conservará sus valores originales.</p>}
        {detail.events.map(event => <article key={event.id} className="rounded-xl border p-4 space-y-2">
          <h4 className="font-semibold">{kindLabel[event.kind]} · Versión {event.version}</h4>
          <p className="text-sm text-slate-600">{event.actor_name} · {new Date(event.created_at).toLocaleString('es-ES')}</p><p>{event.reason}</p>
          <dl className="text-sm space-y-1">{Object.entries(labels).filter(([key]) => !event.before || event.before[key] !== event.after[key]).map(([key, label]) => <div key={key}><dt className="inline font-semibold">{label}: </dt><dd className="inline">{event.before && <><span className="text-slate-500">{String(event.before[key] ?? '—')}</span> → </>}{String(event.after[key] ?? '—')}</dd></div>)}</dl>
        </article>)}
        <h3 className="font-bold">Movimientos de comisión</h3>
        <p className="text-sm text-slate-500">Los importes negativos descuentan saldo. Las liquidaciones se gestionan desde Comisiones.</p>
        <ul className="space-y-2">{detail.commissions.map(c => <li key={c.id} className="rounded border p-3 text-sm">{c.kind === 'ADJUSTMENT' ? 'Ajuste' : 'Comisión'} · {c.agent_name} · <strong>{Number(c.amount).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })}</strong> · {statusLabel[c.status]}{c.invoice_number && ` · Factura: ${c.invoice_number}`}{c.payment_date && ` · ${new Date(c.payment_date).toLocaleDateString('es-ES')}`}</li>)}</ul>
      </>}
    </section>
  </div>;
}
