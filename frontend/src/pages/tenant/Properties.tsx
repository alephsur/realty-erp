import { useState, useEffect, useCallback } from 'react';
import { Plus, Search, Edit, Trash2, X, Home, MapPin, User, UserPlus, Users } from 'lucide-react';
import client from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import Pagination from '../../components/Pagination';

interface PropertyData {
  id: string;
  title: string;
  description: string | null;
  property_type: string | null;
  price: number;
  address: string;
  city: string | null;
  postal_code: string | null;
  reference: string | null;
  status: string | null;
  status_key: string | null;
  bedrooms: number;
  bathrooms: number;
  sqm: number;
  owner_name: string | null;
  owner_phone: string | null;
  owner_email: string | null;
  commission_rate: number;
  agent_commission_rate: number | null;
  agent_id: string | null;
  agent_name: string | null;
  created_at: string | null;
}

interface AgentOption { id: string; full_name: string; }

interface MatchingBuyer {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  budget_min: number | null;
  budget_max: number | null;
  desired_zones: string | null;
  desired_type: string | null;
  agent_name: string | null;
  match_score: number;
  match_reasons: string[];
}

const STATUSES = [
  { key: 'CAPTADA', label: 'Captada', color: 'bg-slate-100 text-slate-800' },
  { key: 'PUBLICADA', label: 'Publicada', color: 'bg-blue-100 text-blue-800' },
  { key: 'EN_VISITAS', label: 'En Visitas', color: 'bg-amber-100 text-amber-800' },
  { key: 'RESERVADA', label: 'Reservada', color: 'bg-purple-100 text-purple-800' },
  { key: 'PENDIENTE_NOTARIA', label: 'Pendiente Notaría', color: 'bg-orange-100 text-orange-800' },
  { key: 'VENDIDA', label: 'Vendida', color: 'bg-emerald-100 text-emerald-800' },
  { key: 'RETIRADA', label: 'Retirada', color: 'bg-red-100 text-red-800' },
];

const PROPERTY_TYPES = [
  { key: 'PISO', label: 'Piso' },
  { key: 'CASA', label: 'Casa' },
  { key: 'CHALET', label: 'Chalet' },
  { key: 'ATICO', label: 'Ático' },
  { key: 'LOCAL', label: 'Local Comercial' },
  { key: 'OFICINA', label: 'Oficina' },
  { key: 'TERRENO', label: 'Terreno' },
  { key: 'GARAJE', label: 'Garaje' },
  { key: 'TRASTERO', label: 'Trastero' },
];

const emptyForm = {
  title: '', description: '', property_type: 'PISO', price: '', address: '', city: '', postal_code: '', reference: '',
  bedrooms: '0', bathrooms: '0', sqm: '0', owner_name: '', owner_phone: '', owner_email: '', commission_rate: '0',
  agent_id: '', agent_commission_rate: '',
};

const LIMIT = 25;

export default function Properties() {
  const { user } = useAuth();
  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';

  const [properties, setProperties] = useState<PropertyData[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Sell modal
  const [sellModal, setSellModal] = useState<string | null>(null);
  const [sellPrice, setSellPrice] = useState('');
  const [sellNotes, setSellNotes] = useState('');

  // Bulk assignment
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showBulkAssign, setShowBulkAssign] = useState(false);
  const [bulkAgent, setBulkAgent] = useState('');
  const [bulkCommission, setBulkCommission] = useState('');

  // Assign modal
  const [assignModal, setAssignModal] = useState<string | null>(null);
  const [assignAgent, setAssignAgent] = useState('');
  const [assignCommission, setAssignCommission] = useState('');

  // Matching buyers modal
  const [matchModal, setMatchModal] = useState<PropertyData | null>(null);
  const [matchBuyers, setMatchBuyers] = useState<MatchingBuyer[]>([]);
  const [loadingMatch, setLoadingMatch] = useState(false);

  const fetchProperties = useCallback(async (p = page, search = searchQuery, status = statusFilter) => {
    try {
      setLoading(true);
      const url = isManager ? '/properties' : '/properties/my';
      const params: Record<string, any> = { page: p, limit: LIMIT };
      if (search) params.search = search;
      if (status !== 'ALL') params.status = status;
      const r = await client.get(url, { params });
      setProperties(r.data.items);
      setTotal(r.data.total);
      setPages(r.data.pages);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [isManager, page, searchQuery, statusFilter]);

  const fetchAgents = async () => {
    try {
      const r = await client.get('/auth/tenant/users');
      setAgents(r.data.map((u: any) => ({ id: u.id, full_name: u.full_name })));
    } catch (err) { console.error(err); }
  };

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      fetchProperties(1, searchQuery, statusFilter);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Immediate filter/page change
  useEffect(() => {
    fetchProperties(page, searchQuery, statusFilter);
  }, [page, statusFilter]);

  useEffect(() => {
    if (isManager) fetchAgents();
  }, [isManager]);

  const openCreate = () => { setForm(emptyForm); setEditingId(null); setShowForm(true); setError(''); };

  const openEdit = (p: PropertyData) => {
    setEditingId(p.id);
    setForm({
      title: p.title, description: p.description || '', property_type: p.property_type || 'PISO',
      price: String(p.price), address: p.address, city: p.city || '', postal_code: p.postal_code || '',
      reference: p.reference || '', bedrooms: String(p.bedrooms), bathrooms: String(p.bathrooms), sqm: String(p.sqm),
      owner_name: p.owner_name || '', owner_phone: p.owner_phone || '', owner_email: p.owner_email || '',
      commission_rate: String(p.commission_rate), agent_id: p.agent_id || '',
      agent_commission_rate: p.agent_commission_rate != null ? String(p.agent_commission_rate) : '',
    });
    setShowForm(true);
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    const payload = {
      title: form.title, description: form.description || null, property_type: form.property_type,
      price: parseFloat(form.price), address: form.address, city: form.city || null, postal_code: form.postal_code || null,
      reference: form.reference || null, bedrooms: parseInt(form.bedrooms), bathrooms: parseInt(form.bathrooms),
      sqm: parseFloat(form.sqm), owner_name: form.owner_name || null, owner_phone: form.owner_phone || null,
      owner_email: form.owner_email || null, commission_rate: parseFloat(form.commission_rate),
      agent_id: form.agent_id || null,
      agent_commission_rate: form.agent_commission_rate ? parseFloat(form.agent_commission_rate) : null,
    };
    try {
      if (editingId) { await client.put(`/properties/${editingId}`, payload); }
      else { await client.post('/properties', payload); }
      setShowForm(false);
      setEditingId(null);
      fetchProperties(1, searchQuery, statusFilter);
    } catch (err: any) { setError(err.response?.data?.detail || 'Error saving property'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar esta propiedad?')) return;
    try { await client.delete(`/properties/${id}`); fetchProperties(page, searchQuery, statusFilter); }
    catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    try { await client.put(`/properties/${id}`, { status: newStatus }); fetchProperties(page, searchQuery, statusFilter); }
    catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const handleSell = async () => {
    if (!sellModal) return;
    try {
      const res = await client.post(`/properties/${sellModal}/sell`, { sale_price: parseFloat(sellPrice), notes: sellNotes || null });
      alert(`Venta registrada.\nComisión total: ${res.data.total_commission}€\nAgente: ${res.data.agent_commission}€\nAgencia: ${res.data.agency_commission}€`);
      setSellModal(null); setSellPrice(''); setSellNotes('');
      fetchProperties(page, searchQuery, statusFilter);
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const openAssign = (p: PropertyData) => {
    setAssignModal(p.id);
    setAssignAgent(p.agent_id || '');
    setAssignCommission(p.agent_commission_rate != null ? String(p.agent_commission_rate) : '');
  };

  const handleAssign = async () => {
    if (!assignModal) return;
    try {
      await client.put(`/properties/${assignModal}/assign`, {
        agent_id: assignAgent || null,
        agent_commission_rate: assignCommission ? parseFloat(assignCommission) : null,
      });
      setAssignModal(null);
      fetchProperties(page, searchQuery, statusFilter);
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === properties.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(properties.map(p => p.id)));
  };

  const handleBulkAssign = async () => {
    try {
      await client.put('/properties/bulk-assign', {
        property_ids: Array.from(selectedIds),
        agent_id: bulkAgent || null,
        agent_commission_rate: bulkCommission ? parseFloat(bulkCommission) : null,
      });
      setSelectedIds(new Set());
      setShowBulkAssign(false);
      setBulkAgent(''); setBulkCommission('');
      fetchProperties(page, searchQuery, statusFilter);
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const openMatchModal = async (p: PropertyData) => {
    setMatchModal(p);
    setMatchBuyers([]);
    setLoadingMatch(true);
    try {
      const res = await client.get(`/properties/${p.id}/matching-buyers`);
      setMatchBuyers(res.data.matches);
    } catch { /* ignore */ }
    finally { setLoadingMatch(false); }
  };

  const statusColor = (key: string | null) => STATUSES.find(s => s.key === key)?.color || 'bg-slate-100 text-slate-800';

  const inputCls = "block w-full rounded-lg border-0 py-2 px-3 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm";

  return (
    <div className="p-8 space-y-6">
      <div className="flex sm:items-center justify-between flex-col sm:flex-row gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Propiedades</h1>
          <p className="text-slate-500 mt-1">
            {isManager ? 'Gestiona las propiedades, asigna agentes y registra ventas.' : 'Tus propiedades asignadas.'}
          </p>
        </div>
        <div className="flex gap-2">
          {isManager && selectedIds.size > 0 && (
            <button onClick={() => setShowBulkAssign(true)}
              className="flex items-center space-x-2 bg-slate-900 hover:bg-slate-800 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all">
              <UserPlus className="h-5 w-5" /> <span>Asignar {selectedIds.size} seleccionadas</span>
            </button>
          )}
          {isManager && (
            <button onClick={openCreate}
              className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5">
              <Plus className="h-5 w-5" /> <span>Nueva Propiedad</span>
            </button>
          )}
        </div>
      </div>

      {/* Create/Edit Panel */}
      {showForm && (
        <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-slate-800">{editingId ? 'Editar Propiedad' : 'Registrar Nueva Propiedad'}</h2>
            <button onClick={() => { setShowForm(false); setEditingId(null); }} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
          </div>
          {error && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Título *</label>
                <input required value={form.title} onChange={e => setForm({...form, title: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Referencia</label>
                <input value={form.reference} onChange={e => setForm({...form, reference: e.target.value})} className={inputCls} placeholder="INM-2024-001" /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Tipo</label>
                <select value={form.property_type} onChange={e => setForm({...form, property_type: e.target.value})} className={inputCls + " font-medium"}>
                  {PROPERTY_TYPES.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}</select></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Precio (€) *</label>
                <input type="number" required step="0.01" value={form.price} onChange={e => setForm({...form, price: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Habitaciones</label>
                <input type="number" min="0" value={form.bedrooms} onChange={e => setForm({...form, bedrooms: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Baños</label>
                <input type="number" min="0" value={form.bathrooms} onChange={e => setForm({...form, bathrooms: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Superficie (m²)</label>
                <input type="number" step="0.1" value={form.sqm} onChange={e => setForm({...form, sqm: e.target.value})} className={inputCls} /></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Dirección *</label>
                <input required value={form.address} onChange={e => setForm({...form, address: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Ciudad</label>
                <input value={form.city} onChange={e => setForm({...form, city: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Código Postal</label>
                <input value={form.postal_code} onChange={e => setForm({...form, postal_code: e.target.value})} className={inputCls} /></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Nombre del Propietario</label>
                <input value={form.owner_name} onChange={e => setForm({...form, owner_name: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Teléfono del Propietario</label>
                <input value={form.owner_phone} onChange={e => setForm({...form, owner_phone: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Comisión Propietario %</label>
                <input type="number" step="0.1" min="0" value={form.commission_rate} onChange={e => setForm({...form, commission_rate: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Agente Asignado</label>
                <select value={form.agent_id} onChange={e => setForm({...form, agent_id: e.target.value})} className={inputCls}>
                  <option value="">— Sin Agente —</option>
                  {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}</select></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Comisión Agente % <span className="text-xs text-slate-400">(override)</span></label>
                <input type="number" step="0.1" min="0" value={form.agent_commission_rate} onChange={e => setForm({...form, agent_commission_rate: e.target.value})} className={inputCls}
                  placeholder="Dejar vacío = tasa base del agente" /></div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Descripción</label>
              <textarea rows={2} value={form.description} onChange={e => setForm({...form, description: e.target.value})} className={inputCls} />
            </div>
            <div className="flex justify-end">
              <button disabled={saving} type="submit" className="flex items-center rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 transition-all">
                {saving ? 'Guardando...' : editingId ? 'Actualizar Propiedad' : 'Guardar Propiedad'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Sell Modal */}
      {sellModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Registrar Venta</h3>
            <div className="space-y-3">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Precio Final de Venta (€) *</label>
                <input type="number" step="0.01" required value={sellPrice} onChange={e => setSellPrice(e.target.value)} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Notas</label>
                <textarea rows={2} value={sellNotes} onChange={e => setSellNotes(e.target.value)} className={inputCls} /></div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setSellModal(null)} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg">Cancelar</button>
              <button onClick={handleSell} disabled={!sellPrice} className="px-4 py-2 text-sm font-semibold text-white bg-emerald-600 rounded-lg hover:bg-emerald-500 disabled:opacity-50">Confirmar Venta</button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Modal */}
      {assignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">Asignar Agente</h3>
              <button onClick={() => setAssignModal(null)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Agente</label>
                <select value={assignAgent} onChange={e => setAssignAgent(e.target.value)} className={inputCls}>
                  <option value="">— Sin Agente —</option>
                  {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                </select></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Comisión del Agente % <span className="text-xs text-slate-400">(override)</span></label>
                <input type="number" step="0.1" min="0" value={assignCommission} onChange={e => setAssignCommission(e.target.value)} className={inputCls}
                  placeholder="Vacío = tasa base del agente" /></div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setAssignModal(null)} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg">Cancelar</button>
              <button onClick={handleAssign} className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-500">Guardar Asignación</button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Assign Modal */}
      {showBulkAssign && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">Asignación Masiva ({selectedIds.size} propiedades)</h3>
              <button onClick={() => setShowBulkAssign(false)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Agente</label>
                <select value={bulkAgent} onChange={e => setBulkAgent(e.target.value)} className={inputCls}>
                  <option value="">— Sin Agente (desasignar) —</option>
                  {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                </select></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Comisión del Agente %</label>
                <input type="number" step="0.1" min="0" value={bulkCommission} onChange={e => setBulkCommission(e.target.value)} className={inputCls}
                  placeholder="Opcional" /></div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowBulkAssign(false)} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg">Cancelar</button>
              <button onClick={handleBulkAssign} className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-800">Asignar Todas</button>
            </div>
          </div>
        </div>
      )}

      {/* Matching Buyers Modal */}
      {matchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Compradores potenciales</h3>
                <p className="text-sm text-slate-500 mt-0.5">{matchModal.title}</p>
              </div>
              <button onClick={() => setMatchModal(null)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto">
              {loadingMatch ? (
                <div className="p-8 text-center text-slate-500">Buscando compradores compatibles...</div>
              ) : matchBuyers.length === 0 ? (
                <div className="p-8 text-center">
                  <Users className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-slate-500 font-medium">Sin compradores compatibles</p>
                  <p className="text-sm text-slate-400 mt-1">Ningún comprador del CRM encaja con el precio, zona y tipo de esta propiedad.</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {matchBuyers.map(b => (
                    <div key={b.id} className="px-6 py-4 hover:bg-slate-50 flex items-start gap-4">
                      <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                        <User className="w-4 h-4 text-indigo-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-sm font-semibold text-slate-900">{b.full_name}</p>
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">
                            Match {b.match_score}pts
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-3 mt-1 text-xs text-slate-500">
                          {b.email && <span>{b.email}</span>}
                          {b.phone && <span>{b.phone}</span>}
                          {(b.budget_min || b.budget_max) && (
                            <span>Presup: {b.budget_min?.toLocaleString('es-ES') ?? '?'} — {b.budget_max?.toLocaleString('es-ES') ?? '?'} €</span>
                          )}
                          {b.desired_zones && <span>Zonas: {b.desired_zones}</span>}
                          {b.agent_name && <span>Agente: {b.agent_name}</span>}
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {b.match_reasons.map(r => (
                            <span key={r} className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-xs">{r}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Status Filter Pills */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setStatusFilter('ALL'); setPage(1); }}
          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${statusFilter === 'ALL' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>
          Todas
        </button>
        {STATUSES.map(s => (
          <button key={s.key} onClick={() => { setStatusFilter(s.key); setPage(1); }}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${statusFilter === s.key ? 'bg-slate-900 text-white' : s.color + ' hover:opacity-80'}`}>
            {s.label}
          </button>
        ))}
      </div>

      {/* Properties Table */}
      <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input type="text" placeholder="Buscar por título, dirección, referencia..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border-0 ring-1 ring-inset ring-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-inset focus:ring-indigo-600 bg-white" />
          </div>
        </div>

        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando...</div>
          ) : properties.length === 0 ? (
            <div className="p-8 text-center text-slate-500">No se encontraron propiedades.</div>
          ) : (
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr className="bg-slate-50">
                  {isManager && (
                    <th className="px-4 py-3 text-left">
                      <input type="checkbox" checked={selectedIds.size === properties.length && properties.length > 0}
                        onChange={toggleSelectAll}
                        className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600" />
                    </th>
                  )}
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Propiedad</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Precio</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Agente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Estado</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {properties.map(p => (
                  <tr key={p.id} className={`hover:bg-slate-50/50 transition-colors ${selectedIds.has(p.id) ? 'bg-indigo-50/30' : ''}`}>
                    {isManager && (
                      <td className="px-4 py-4">
                        <input type="checkbox" checked={selectedIds.has(p.id)} onChange={() => toggleSelect(p.id)}
                          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600" />
                      </td>
                    )}
                    <td className="px-6 py-4">
                      <div className="flex items-start">
                        <div className="h-9 w-9 flex-shrink-0 rounded-lg bg-indigo-50 flex items-center justify-center">
                          <Home className="w-4 h-4 text-indigo-600" />
                        </div>
                        <div className="ml-3">
                          <div className="text-sm font-medium text-slate-900">{p.title}</div>
                          <div className="text-xs text-slate-500 flex items-center mt-0.5"><MapPin className="w-3 h-3 mr-1" />{p.address}{p.city ? `, ${p.city}` : ''}</div>
                          {p.reference && <div className="text-xs text-slate-400 mt-0.5">Ref: {p.reference}</div>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm font-semibold text-slate-900">{p.price.toLocaleString('es-ES')} €</td>
                    <td className="px-4 py-4 text-sm text-slate-600">{PROPERTY_TYPES.find(t => t.key === p.property_type)?.label || p.property_type}</td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {p.agent_name ? (
                        <div>
                          <span className="flex items-center gap-1"><User className="w-3 h-3" />{p.agent_name}</span>
                          {p.agent_commission_rate != null && (
                            <span className="text-xs text-slate-400 mt-0.5 block">Com: {p.agent_commission_rate}%</span>
                          )}
                        </div>
                      ) : <span className="text-slate-400">— Sin asignar</span>}
                    </td>
                    <td className="px-4 py-4">
                      {isManager ? (
                        <select value={p.status_key || ''} onChange={e => handleStatusChange(p.id, e.target.value)}
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold border-0 cursor-pointer ${statusColor(p.status_key)}`}>
                          {STATUSES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                        </select>
                      ) : (
                        <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${statusColor(p.status_key)}`}>
                          {STATUSES.find(s => s.key === p.status_key)?.label || p.status || '—'}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        {/* Matching buyers — visible to all roles for non-sold properties */}
                        {p.status_key !== 'VENDIDA' && p.status_key !== 'RETIRADA' && (
                          <button onClick={() => openMatchModal(p)}
                            className="text-slate-400 hover:text-purple-600 p-1.5 rounded-lg hover:bg-purple-50" title="Compradores potenciales">
                            <Users className="w-4 h-4" />
                          </button>
                        )}
                        {isManager && (
                          <button onClick={() => openAssign(p)} className="text-slate-400 hover:text-blue-600 p-1.5 rounded-lg hover:bg-blue-50" title="Asignar Agente">
                            <UserPlus className="w-4 h-4" />
                          </button>
                        )}
                        {isManager && (
                          <button onClick={() => openEdit(p)} className="text-slate-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-indigo-50" title="Editar">
                            <Edit className="w-4 h-4" />
                          </button>
                        )}
                        {isManager && p.status_key !== 'VENDIDA' && (
                          <button onClick={() => { setSellModal(p.id); setSellPrice(String(p.price)); }}
                            className="text-slate-400 hover:text-emerald-600 p-1.5 rounded-lg hover:bg-emerald-50 text-xs font-bold" title="Registrar Venta">
                            €
                          </button>
                        )}
                        {isManager && (
                          <button onClick={() => handleDelete(p.id)} className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50" title="Eliminar">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <Pagination page={page} pages={pages} total={total} limit={LIMIT} onPageChange={setPage} />
      </div>
    </div>
  );
}
