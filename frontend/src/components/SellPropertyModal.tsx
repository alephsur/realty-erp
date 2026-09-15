import { useEffect, useRef, useState, type FormEvent } from 'react';
import { isAxiosError } from 'axios';
import { X } from 'lucide-react';
import client from '../api/client';
import { previewCommission, formatCents } from '../lib/commission';

interface AgentOption { id: string; full_name: string; commission_rate: number | null; }
interface BuyerOption { id: string; full_name: string; }
interface ClosingOptions {
  property: {
    title: string; price: number; status_key: string;
    agent_id: string | null; commission_rate: number | null; agent_commission_rate: number | null;
  };
  agents: AgentOption[];
  buyers: BuyerOption[];
  pages: number;
  total: number;
}

function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return 'Revisa los campos obligatorios y los importes introducidos.';
  }
  return 'No se ha podido confirmar el cierre. Puedes reintentar con los mismos datos.';
}

export interface SaleRevision {
  id: string; version: number; property_id: string; is_active: boolean;
  buyer_id: string | null; buyer_name: string | null; agent_id: string | null;
  sale_price: number | string; commission_rate: number | string | null; agent_commission_rate: number | string | null;
  agent_commission: number | string; notes: string | null; sale_date: string;
}

export default function SellPropertyModal({ propertyId, revision, onClose, onSold }: {
  propertyId: string; revision?: SaleRevision; onClose: () => void; onSold: () => void;
}) {
  const [options, setOptions] = useState<ClosingOptions | null>(null);
  const [buyer, setBuyer] = useState<BuyerOption | null>(null);
  const [agentId, setAgentId] = useState('');
  const [price, setPrice] = useState('');
  const [rate, setRate] = useState('');
  const [agentRate, setAgentRate] = useState('');
  const [reason, setReason] = useState('');
  const [saleDate, setSaleDate] = useState(revision?.sale_date ? new Date(revision.sale_date).toISOString().slice(0, 19) : '');
  const [notes, setNotes] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const initialized = useRef(false);
  const dialog = useRef<HTMLElement>(null);
  const submitting = useRef(false);
  const lastAttempt = useRef<{ signature: string; id: string } | null>(null);
  const preview = previewCommission(price, rate, agentRate);
  const inputCls = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setLoadError('');
      try {
        const { data } = await client.get<ClosingOptions>(`/properties/${propertyId}/closing-options`, {
          params: { search, page }, signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setOptions(data);
        if (!initialized.current) {
          const assigned = data.agents.find(a => a.id === data.property.agent_id);
          setAgentId(assigned?.id ?? '');
          setPrice(String(data.property.price));
          setRate(data.property.commission_rate == null ? '' : String(data.property.commission_rate));
          const share = data.property.agent_commission_rate ?? assigned?.commission_rate;
          setAgentRate(share == null ? '' : String(share));
          if (revision) {
            setBuyer(revision.buyer_id ? { id: revision.buyer_id, full_name: revision.buyer_name ?? 'Comprador anterior' } : null);
            setAgentId(data.agents.some(a => a.id === revision.agent_id) ? revision.agent_id! : '');
            setPrice(String(revision.sale_price));
            setRate(revision.commission_rate == null ? '' : String(revision.commission_rate));
            setAgentRate(revision.agent_commission_rate == null ? '' : String(revision.agent_commission_rate));
            setNotes(revision.notes ?? '');
          }
          initialized.current = true;
        }
      } catch (err) {
        if (!controller.signal.aborted) setLoadError(errorMessage(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, search ? 250 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [propertyId, search, page, reload, revision]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    dialog.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting.current) onClose();
      if (event.key === 'Tab') {
        const controls = dialog.current?.querySelectorAll<HTMLElement>(
          'button:enabled, input:enabled, select:enabled, textarea:enabled',
        );
        if (!controls?.length) { event.preventDefault(); return; }
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, [onClose]);

  const selectAgent = (id: string) => {
    setAgentId(id);
    const selected = options?.agents.find(a => a.id === id);
    const share = id === options?.property.agent_id
      ? options?.property.agent_commission_rate ?? selected?.commission_rate
      : selected?.commission_rate;
    setAgentRate(share == null ? '' : String(share));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting.current || !preview || !buyer || !agentId || (revision && (!reason.trim() || !saleDate))) return;
    submitting.current = true;
    setSaving(true);
    setError('');
    const payload = {
      buyer_id: buyer.id, agent_id: agentId, sale_price: price,
      commission_rate: rate, agent_commission_rate: agentRate, notes: notes || null,
      ...(revision ? { expected_version: revision.version, reason: reason.trim(), sale_date: new Date(`${saleDate}Z`).toISOString() } : {}),
    };
    const signature = JSON.stringify(payload);
    if (lastAttempt.current?.signature !== signature) {
      lastAttempt.current = { signature, id: crypto.randomUUID() };
    }
    try {
      await client.post(revision ? `/sales/${revision.id}/correct` : `/properties/${propertyId}/sell`, {
        ...payload, request_id: lastAttempt.current.id,
      });
    } catch (err) {
      setError(errorMessage(err));
      return;
    } finally {
      submitting.current = false;
      setSaving(false);
    }
    onSold();
  };

  const alreadySold = !revision && options?.property.status_key === 'VENDIDA';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <section ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="sale-title" className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="sale-title" className="text-lg font-bold text-slate-900">{revision ? 'Corregir venta' : 'Registrar venta'}</h2>
            <p className="text-sm text-slate-500">{options?.property.title ?? 'Cargando propiedad…'}</p>
          </div>
          <button type="button" onClick={onClose} disabled={saving} aria-label="Cerrar" className="p-1 text-slate-500 disabled:opacity-50"><X className="h-5 w-5" /></button>
        </div>
        {loadError && <div role="alert" className="mb-3 text-sm text-red-700">{loadError} <button type="button" className="underline" onClick={() => setReload(n => n + 1)}>Reintentar carga</button></div>}
        {alreadySold && <p role="alert" className="mb-3 text-sm text-amber-700">Esta propiedad ya está vendida. Consulta su venta para revisar el cierre.</p>}
        <form onSubmit={submit}>
          <fieldset disabled={saving || !options || alreadySold} className="space-y-4 disabled:opacity-60">
            <div>
              <label htmlFor="buyer-search" className="mb-1 block text-sm font-semibold">Buscar comprador</label>
              <input id="buyer-search" type="search" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} className={inputCls} placeholder="Nombre y apellidos" />
              <label htmlFor="sale-buyer" className="mb-1 mt-2 block text-sm font-semibold">Comprador *</label>
              <select id="sale-buyer" required value={buyer?.id ?? ''} onChange={e => setBuyer(options?.buyers.find(b => b.id === e.target.value) ?? null)} className={inputCls}>
                <option value="">Selecciona un comprador</option>
                {buyer && !options?.buyers.some(b => b.id === buyer.id) && <option value={buyer.id}>{buyer.full_name}</option>}
                {options?.buyers.map(b => <option key={b.id} value={b.id}>{b.full_name}</option>)}
              </select>
              <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                <span>{loading ? 'Buscando…' : `${options?.total ?? 0} compradores disponibles`}</span>
                {(options?.pages ?? 1) > 1 && <div className="flex gap-2">
                  <button type="button" disabled={page <= 1 || loading} onClick={() => setPage(p => p - 1)} className="underline disabled:opacity-40">Anterior</button>
                  <span>{page} / {options?.pages}</span>
                  <button type="button" disabled={page >= (options?.pages ?? 1) || loading} onClick={() => setPage(p => p + 1)} className="underline disabled:opacity-40">Siguiente</button>
                </div>}
              </div>
              {!loading && options?.total === 0 && <p className="mt-1 text-xs text-slate-500">No hay compradores disponibles con esta búsqueda. Puedes registrar un demandante en Clientes.</p>}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label htmlFor="sale-price" className="mb-1 block text-sm font-semibold">Precio final (€) *</label>
                <input id="sale-price" type="number" required min="0.01" step="0.01" value={price} onChange={e => setPrice(e.target.value)} className={inputCls} /></div>
              <div><label htmlFor="sale-agent" className="mb-1 block text-sm font-semibold">Agente de la venta *</label>
                <select id="sale-agent" required value={agentId} onChange={e => selectAgent(e.target.value)} className={inputCls}>
                  <option value="">Selecciona un agente</option>
                  {options?.agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                </select></div>
              <div><label htmlFor="sale-rate" className="mb-1 block text-sm font-semibold">Comisión sobre la venta (%) *</label>
                <input id="sale-rate" type="number" required min="0" max="100" step="0.0001" value={rate} onChange={e => setRate(e.target.value)} className={inputCls} /></div>
              <div><label htmlFor="sale-agent-rate" className="mb-1 block text-sm font-semibold">Parte del agente (%) *</label>
                <input id="sale-agent-rate" type="number" required min="0" max="100" step="0.0001" value={agentRate} onChange={e => setAgentRate(e.target.value)} className={inputCls} /></div>
            </div>
            <p className="text-xs text-slate-500">La parte del agente se calcula sobre la comisión total. El resto corresponde a la agencia.</p>
            {preview ? <dl className="grid grid-cols-1 gap-2 rounded-xl bg-emerald-50 p-3 text-sm sm:grid-cols-3">
              <div><dt>Comisión total</dt><dd className="font-semibold">{formatCents(preview.total)}</dd></div>
              <div><dt>Agente</dt><dd className="font-semibold">{formatCents(preview.agent)}</dd></div>
              <div><dt>Agencia</dt><dd className="font-semibold">{formatCents(preview.agency)}</dd></div>
            </dl> : <p className="text-xs text-slate-500">Introduce un precio positivo con hasta dos decimales y porcentajes entre 0 y 100 con hasta cuatro decimales.</p>}
            {revision && <>
              <p className="rounded-lg bg-amber-50 p-3 text-sm">Comisión anterior del agente: {Number(revision.agent_commission).toLocaleString('es-ES')} €. La diferencia se añadirá al saldo pendiente, también si ya se había pagado. Si cambias de agente, se descontará al anterior y se abonará al nuevo.</p>
              <div><label htmlFor="sale-date" className="mb-1 block text-sm font-semibold">Fecha de cierre (UTC) *</label>
                <input id="sale-date" type="datetime-local" step="1" required value={saleDate} onChange={e => setSaleDate(e.target.value)} className={inputCls} /></div>
              <div><label htmlFor="sale-reason" className="mb-1 block text-sm font-semibold">Motivo de la corrección *</label>
                <textarea id="sale-reason" required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} className={inputCls} /></div>
            </>}
            <div><label htmlFor="sale-notes" className="mb-1 block text-sm font-semibold">Notas</label>
              <textarea id="sale-notes" rows={2} maxLength={10000} value={notes} onChange={e => setNotes(e.target.value)} className={inputCls} /></div>
          </fieldset>
          {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={onClose} disabled={saving} className="rounded-lg px-4 py-2 text-sm text-slate-600 disabled:opacity-50">Cancelar</button>
            <button type="submit" disabled={saving || loading || !!loadError || alreadySold || !preview || !buyer || !agentId || (!!revision && (!reason.trim() || !saleDate))} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">{saving ? 'Guardando…' : revision ? 'Guardar corrección' : 'Confirmar venta'}</button>
          </div>
        </form>
      </section>
    </div>
  );
}
