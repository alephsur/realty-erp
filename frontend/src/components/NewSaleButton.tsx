import { useEffect, useState } from 'react';
import client from '../api/client';
import SellPropertyModal from './SellPropertyModal';

interface PropertyOption { id: string; title: string; reference: string | null; }

export default function NewSaleButton({ onSold }: { onSold: () => void }) {
  const [open, setOpen] = useState(false);
  const [propertyId, setPropertyId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [properties, setProperties] = useState<PropertyOption[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || propertyId) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setError('');
      try {
        const { data } = await client.get('/properties', {
          params: { search, page, limit: 15, for_sale: true }, signal: controller.signal,
        });
        if (!controller.signal.aborted) {
          setProperties(data.items);
          setPages(data.pages);
        }
      } catch {
        if (!controller.signal.aborted) setError('No se pudieron cargar las propiedades.');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, search ? 250 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, propertyId, search, page]);

  const close = () => { setOpen(false); setPropertyId(null); };
  return <>
    <button type="button" onClick={() => { setSearch(''); setPage(1); setOpen(true); }} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">Registrar venta</button>
    {open && !propertyId && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <section role="dialog" aria-modal="true" aria-labelledby="choose-sale-property" className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="choose-sale-property" className="mb-3 text-lg font-bold">Selecciona la propiedad</h2>
        <input type="search" aria-label="Buscar propiedad" placeholder="Título, dirección o referencia" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {loading ? <p className="text-sm text-slate-500">Cargando…</p> : <ul className="space-y-1">
          {properties.map(prop => <li key={prop.id}><button type="button" onClick={() => setPropertyId(prop.id)} className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-100">{prop.title}{prop.reference && <span className="ml-2 text-xs text-slate-500">{prop.reference}</span>}</button></li>)}
          {!properties.length && !error && <li className="text-sm text-slate-500">No hay propiedades disponibles con esta búsqueda.</li>}
        </ul>}
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="flex gap-3">
            <button disabled={page <= 1 || loading} onClick={() => setPage(p => p - 1)} className="disabled:opacity-40">Anterior</button>
            <span>{page} / {pages}</span>
            <button disabled={page >= pages || loading} onClick={() => setPage(p => p + 1)} className="disabled:opacity-40">Siguiente</button>
          </div>
          <button type="button" onClick={close} className="rounded-lg px-3 py-2 hover:bg-slate-100">Cancelar</button>
        </div>
      </section>
    </div>}
    {open && propertyId && <SellPropertyModal key={propertyId} propertyId={propertyId} onClose={close} onSold={() => { close(); onSold(); }} />}
  </>;
}
