import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2, X, User, Phone, Mail, MapPin, Home, Building } from 'lucide-react';
import client from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import Pagination from '../../components/Pagination';

interface ClientData {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  client_type: string | null;
  client_type_key: string | null;
  agent_id: string | null;
  agent_name: string | null;
  dni: string | null;
  address: string | null;
  budget_min: number | null;
  budget_max: number | null;
  desired_zones: string | null;
  desired_type: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string | null;
  property_interests: { id: string; property_id: string; property_title: string | null; interest_level: string; notes: string | null }[];
}

interface AgentOption { id: string; full_name: string; }

interface MatchingProperty {
  id: string;
  title: string;
  reference: string | null;
  property_type: string | null;
  price: number;
  city: string | null;
  address: string;
  bedrooms: number;
  bathrooms: number;
  sqm: number;
  status: string | null;
  agent_name: string | null;
  match_score: number;
  match_reasons: string[];
}

const CLIENT_TYPES = [
  { key: 'OWNER', label: 'Propietario', value: 'Propietario' },
  { key: 'BUYER', label: 'Demandante', value: 'Demandante' },
];

const emptyForm = {
  first_name: '', last_name: '', email: '', phone: '', client_type: 'Demandante', agent_id: '',
  dni: '', address: '', budget_min: '', budget_max: '', desired_zones: '', desired_type: '', notes: '',
};

const LIMIT = 25;

export default function Clients() {
  const { user } = useAuth();
  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';

  const [clients, setClients] = useState<ClientData[]>([]);
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
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Detail view
  const [selectedClient, setSelectedClient] = useState<ClientData | null>(null);

  // Matching modal
  const [matchClient, setMatchClient] = useState<ClientData | null>(null);
  const [matchProps, setMatchProps] = useState<MatchingProperty[]>([]);
  const [loadingMatch, setLoadingMatch] = useState(false);

  const fetchClients = async (p = page, search = searchQuery, type = typeFilter) => {
    try {
      setLoading(true);
      const params: Record<string, any> = { page: p, limit: LIMIT };
      if (search) params.search = search;
      if (type !== 'ALL') params.client_type = type === 'OWNER' ? 'Propietario' : 'Demandante';
      const r = await client.get('/clients', { params });
      setClients(r.data.items);
      setTotal(r.data.total);
      setPages(r.data.pages);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const fetchAgents = async () => {
    try {
      const r = await client.get('/auth/tenant/users');
      setAgents(r.data.map((u: any) => ({ id: u.id, full_name: u.full_name })));
    } catch { /* ignore */ }
  };

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      fetchClients(1, searchQuery, typeFilter);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    fetchClients(page, searchQuery, typeFilter);
  }, [page, typeFilter]);

  useEffect(() => {
    fetchAgents();
  }, []);

  const openCreate = () => { setForm(emptyForm); setEditingId(null); setShowForm(true); setError(''); };

  const openEdit = (c: ClientData) => {
    setEditingId(c.id);
    setForm({
      first_name: c.first_name, last_name: c.last_name, email: c.email || '', phone: c.phone || '',
      client_type: c.client_type || 'Demandante', agent_id: c.agent_id || '',
      dni: c.dni || '', address: c.address || '', budget_min: String(c.budget_min || ''),
      budget_max: String(c.budget_max || ''), desired_zones: c.desired_zones || '',
      desired_type: c.desired_type || '', notes: c.notes || '',
    });
    setShowForm(true); setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setSaving(true);
    const payload = {
      first_name: form.first_name, last_name: form.last_name, email: form.email || null,
      phone: form.phone || null, client_type: form.client_type, agent_id: form.agent_id || null,
      dni: form.dni || null, address: form.address || null,
      budget_min: form.budget_min ? parseFloat(form.budget_min) : null,
      budget_max: form.budget_max ? parseFloat(form.budget_max) : null,
      desired_zones: form.desired_zones || null, desired_type: form.desired_type || null,
      notes: form.notes || null,
    };
    try {
      if (editingId) { await client.put(`/clients/${editingId}`, payload); }
      else { await client.post('/clients', payload); }
      setShowForm(false); setEditingId(null);
      fetchClients(1, searchQuery, typeFilter);
    } catch (err: any) { setError(err.response?.data?.detail || 'Error saving client'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar este cliente?')) return;
    try {
      await client.delete(`/clients/${id}`);
      fetchClients(page, searchQuery, typeFilter);
      if (selectedClient?.id === id) setSelectedClient(null);
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const openMatchModal = async (c: ClientData) => {
    setMatchClient(c);
    setMatchProps([]);
    setLoadingMatch(true);
    try {
      const res = await client.get(`/clients/${c.id}/matching-properties`);
      setMatchProps(res.data.matches);
    } catch { /* ignore */ }
    finally { setLoadingMatch(false); }
  };

  const inputCls = "block w-full rounded-lg border-0 py-2 px-3 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm";

  return (
    <div className="p-8 space-y-6">
      <div className="flex sm:items-center justify-between flex-col sm:flex-row gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Clientes</h1>
          <p className="text-slate-500 mt-1">Gestiona propietarios y demandantes.</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5">
          <Plus className="h-5 w-5" /> <span>Nuevo Cliente</span>
        </button>
      </div>

      {/* Create/Edit Form */}
      {showForm && (
        <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-slate-800">{editingId ? 'Editar Cliente' : 'Registrar Nuevo Cliente'}</h2>
            <button onClick={() => { setShowForm(false); setEditingId(null); }} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
          </div>
          {error && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Nombre *</label>
                <input required value={form.first_name} onChange={e => setForm({...form, first_name: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Apellidos *</label>
                <input required value={form.last_name} onChange={e => setForm({...form, last_name: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Tipo *</label>
                <select value={form.client_type} onChange={e => setForm({...form, client_type: e.target.value})} className={inputCls + " font-medium"}>
                  {CLIENT_TYPES.map(t => <option key={t.key} value={t.value}>{t.label}</option>)}
                </select></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Email</label>
                <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Teléfono</label>
                <input type="tel" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} className={inputCls} placeholder="+34 600 000 000" /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">DNI / NIE</label>
                <input value={form.dni} onChange={e => setForm({...form, dni: e.target.value})} className={inputCls} /></div>
              {isManager && (
                <div><label className="block text-sm font-semibold text-slate-700 mb-1">Agente Asignado</label>
                  <select value={form.agent_id} onChange={e => setForm({...form, agent_id: e.target.value})} className={inputCls}>
                    <option value="">— Sin Agente —</option>
                    {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                  </select></div>
              )}
            </div>
            {form.client_type === 'Demandante' && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div><label className="block text-sm font-semibold text-slate-700 mb-1">Presupuesto Mín. (€)</label>
                  <input type="number" value={form.budget_min} onChange={e => setForm({...form, budget_min: e.target.value})} className={inputCls} /></div>
                <div><label className="block text-sm font-semibold text-slate-700 mb-1">Presupuesto Máx. (€)</label>
                  <input type="number" value={form.budget_max} onChange={e => setForm({...form, budget_max: e.target.value})} className={inputCls} /></div>
                <div><label className="block text-sm font-semibold text-slate-700 mb-1">Zonas Deseadas</label>
                  <input value={form.desired_zones} onChange={e => setForm({...form, desired_zones: e.target.value})} className={inputCls} placeholder="Centro, Ensanche..." /></div>
                <div><label className="block text-sm font-semibold text-slate-700 mb-1">Tipo Preferido</label>
                  <input value={form.desired_type} onChange={e => setForm({...form, desired_type: e.target.value})} className={inputCls} placeholder="PISO, CHALET..." /></div>
              </div>
            )}
            <div><label className="block text-sm font-semibold text-slate-700 mb-1">Notas</label>
              <textarea rows={2} value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} className={inputCls} /></div>
            <div className="flex justify-end">
              <button disabled={saving} type="submit" className="flex items-center rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 transition-all">
                {saving ? 'Guardando...' : editingId ? 'Actualizar Cliente' : 'Guardar Cliente'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Matching Properties Modal */}
      {matchClient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Propiedades compatibles</h3>
                <p className="text-sm text-slate-500 mt-0.5">{matchClient.full_name}</p>
              </div>
              <button onClick={() => setMatchClient(null)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto">
              {loadingMatch ? (
                <div className="p-8 text-center text-slate-500">Buscando propiedades compatibles...</div>
              ) : matchProps.length === 0 ? (
                <div className="p-8 text-center">
                  <Building className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-slate-500 font-medium">Sin propiedades compatibles</p>
                  <p className="text-sm text-slate-400 mt-1">Ninguna propiedad publicada encaja con el presupuesto, zona y tipo de este comprador.</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {matchProps.map(p => (
                    <div key={p.id} className="px-6 py-4 hover:bg-slate-50">
                      <div className="flex items-start gap-4">
                        <div className="w-9 h-9 rounded-lg bg-indigo-100 flex items-center justify-center flex-shrink-0">
                          <Home className="w-4 h-4 text-indigo-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-sm font-semibold text-slate-900">{p.title}</p>
                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">
                              Match {p.match_score}pts
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-3 mt-1 text-xs text-slate-500">
                            <span className="font-semibold text-slate-700">{p.price.toLocaleString('es-ES')} €</span>
                            {p.city && <span><MapPin className="w-3 h-3 inline" /> {p.city}</span>}
                            {p.property_type && <span>{p.property_type}</span>}
                            <span>{p.bedrooms}hab · {p.bathrooms}baños · {p.sqm}m²</span>
                            {p.agent_name && <span>Agente: {p.agent_name}</span>}
                          </div>
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {p.match_reasons.map(r => (
                              <span key={r} className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-xs">{r}</span>
                            ))}
                          </div>
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

      {/* Type Filter Pills */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setTypeFilter('ALL'); setPage(1); }}
          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${typeFilter === 'ALL' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>
          Todos
        </button>
        <button onClick={() => { setTypeFilter('OWNER'); setPage(1); }}
          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${typeFilter === 'OWNER' ? 'bg-slate-900 text-white' : 'bg-blue-100 text-blue-800 hover:opacity-80'}`}>
          Propietarios
        </button>
        <button onClick={() => { setTypeFilter('BUYER'); setPage(1); }}
          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${typeFilter === 'BUYER' ? 'bg-slate-900 text-white' : 'bg-emerald-100 text-emerald-800 hover:opacity-80'}`}>
          Demandantes
        </button>
      </div>

      {/* Clients Table */}
      <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input type="text" placeholder="Buscar clientes..." value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border-0 ring-1 ring-inset ring-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-inset focus:ring-indigo-600 bg-white" />
          </div>
        </div>

        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando...</div>
          ) : clients.length === 0 ? (
            <div className="p-8 text-center text-slate-500">No se encontraron clientes.</div>
          ) : (
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Cliente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Contacto</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Agente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Presupuesto</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {clients.map(c => (
                  <tr key={c.id} className="hover:bg-slate-50/50 transition-colors cursor-pointer" onClick={() => setSelectedClient(c)}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`h-9 w-9 flex-shrink-0 rounded-full flex items-center justify-center font-bold text-sm ${
                          c.client_type_key === 'OWNER' ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700'
                        }`}>
                          {c.first_name?.charAt(0).toUpperCase()}{c.last_name?.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">{c.full_name}</p>
                          {c.dni && <p className="text-xs text-slate-400">DNI: {c.dni}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${
                        c.client_type_key === 'OWNER' ? 'bg-blue-100 text-blue-800' : 'bg-emerald-100 text-emerald-800'
                      }`}>{c.client_type}</span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="space-y-0.5">
                        {c.email && <p className="text-xs text-slate-600 flex items-center gap-1"><Mail className="w-3 h-3" />{c.email}</p>}
                        {c.phone && <p className="text-xs text-slate-600 flex items-center gap-1"><Phone className="w-3 h-3" />{c.phone}</p>}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {c.agent_name ? <span className="flex items-center gap-1"><User className="w-3 h-3" />{c.agent_name}</span> : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {c.budget_min || c.budget_max ? (
                        <span>{c.budget_min ? `${c.budget_min.toLocaleString('es-ES')}€` : '—'} – {c.budget_max ? `${c.budget_max.toLocaleString('es-ES')}€` : '—'}</span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-4 text-right" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center justify-end space-x-1">
                        {/* Match button for buyers */}
                        {c.client_type_key === 'BUYER' && (
                          <button onClick={() => openMatchModal(c)}
                            className="text-slate-400 hover:text-purple-600 p-1.5 rounded-lg hover:bg-purple-50" title="Propiedades compatibles">
                            <Home className="w-4 h-4" />
                          </button>
                        )}
                        <button onClick={() => openEdit(c)} className="text-slate-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-indigo-50" title="Editar">
                          <Edit className="w-4 h-4" />
                        </button>
                        {isManager && (
                          <button onClick={() => handleDelete(c.id)} className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50" title="Eliminar">
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

      {/* Client Detail Modal */}
      {selectedClient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSelectedClient(null)}>
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">{selectedClient.full_name}</h3>
              <button onClick={() => setSelectedClient(null)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex gap-2">
                <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${
                  selectedClient.client_type_key === 'OWNER' ? 'bg-blue-100 text-blue-800' : 'bg-emerald-100 text-emerald-800'
                }`}>{selectedClient.client_type}</span>
              </div>
              {selectedClient.email && <p className="flex items-center gap-2 text-slate-600"><Mail className="w-4 h-4 text-slate-400" />{selectedClient.email}</p>}
              {selectedClient.phone && <p className="flex items-center gap-2 text-slate-600"><Phone className="w-4 h-4 text-slate-400" />{selectedClient.phone}</p>}
              {selectedClient.address && <p className="flex items-center gap-2 text-slate-600"><MapPin className="w-4 h-4 text-slate-400" />{selectedClient.address}</p>}
              {selectedClient.dni && <p className="text-slate-600"><span className="font-medium">DNI:</span> {selectedClient.dni}</p>}
              {selectedClient.agent_name && <p className="text-slate-600"><span className="font-medium">Agente:</span> {selectedClient.agent_name}</p>}
              {selectedClient.desired_zones && <p className="text-slate-600"><span className="font-medium">Zonas:</span> {selectedClient.desired_zones}</p>}
              {selectedClient.desired_type && <p className="text-slate-600"><span className="font-medium">Tipo preferido:</span> {selectedClient.desired_type}</p>}
              {(selectedClient.budget_min || selectedClient.budget_max) && (
                <p className="text-slate-600"><span className="font-medium">Presupuesto:</span> {selectedClient.budget_min?.toLocaleString('es-ES') || '—'} € – {selectedClient.budget_max?.toLocaleString('es-ES') || '—'} €</p>
              )}
              {selectedClient.notes && (
                <div className="mt-3 p-3 bg-slate-50 rounded-lg">
                  <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Notas</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedClient.notes}</p>
                </div>
              )}
              {selectedClient.property_interests.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Propiedades de Interés</p>
                  <div className="space-y-2">
                    {selectedClient.property_interests.map(pi => (
                      <div key={pi.id} className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
                        <Home className="w-4 h-4 text-indigo-600" />
                        <span className="text-sm text-slate-700">{pi.property_title || pi.property_id}</span>
                        <span className={`ml-auto px-2 py-0.5 text-xs font-semibold rounded-full ${
                          pi.interest_level === 'high' ? 'bg-emerald-100 text-emerald-800' :
                          pi.interest_level === 'medium' ? 'bg-amber-100 text-amber-800' :
                          'bg-slate-100 text-slate-700'
                        }`}>{pi.interest_level}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
