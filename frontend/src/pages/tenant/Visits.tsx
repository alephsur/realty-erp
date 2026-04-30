import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2, X, Calendar, Clock, MapPin, User, Home, MessageSquare, Star, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import client from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import Pagination from '../../components/Pagination';

interface VisitData {
  id: string;
  property_id: string;
  property_title: string | null;
  property_address: string | null;
  client_id: string | null;
  client_name: string | null;
  agent_id: string | null;
  agent_name: string | null;
  scheduled_at: string | null;
  duration_minutes: number;
  status: string | null;
  status_key: string | null;
  feedback: string | null;
  rating: number | null;
  notes: string | null;
  created_at: string | null;
}

interface VisitStats {
  total: number;
  scheduled: number;
  completed: number;
  cancelled: number;
  no_show: number;
}

interface PropertyOption { id: string; title: string; }
interface ClientOption { id: string; full_name: string; }
interface AgentOption { id: string; full_name: string; }

const VISIT_STATUSES = [
  { key: 'SCHEDULED', label: 'Programada', color: 'bg-blue-100 text-blue-800', icon: Clock },
  { key: 'COMPLETED', label: 'Realizada', color: 'bg-emerald-100 text-emerald-800', icon: CheckCircle },
  { key: 'CANCELLED', label: 'Cancelada', color: 'bg-red-100 text-red-800', icon: XCircle },
  { key: 'NO_SHOW', label: 'No Show', color: 'bg-amber-100 text-amber-800', icon: AlertCircle },
];

const emptyForm = {
  property_id: '', client_id: '', agent_id: '', scheduled_at: '', duration_minutes: '30', notes: '',
};

const LIMIT = 25;

export default function Visits() {
  const { user } = useAuth();
  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';

  const [visits, setVisits] = useState<VisitData[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [stats, setStats] = useState<VisitStats | null>(null);
  const [properties, setProperties] = useState<PropertyOption[]>([]);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Feedback modal
  const [feedbackVisit, setFeedbackVisit] = useState<VisitData | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackRating, setFeedbackRating] = useState(3);

  const fetchVisits = async (p = page, search = searchQuery, status = statusFilter) => {
    try {
      setLoading(true);
      const params: Record<string, any> = { page: p, limit: LIMIT };
      if (search) params.search = search;
      if (status !== 'ALL') params.status = status;
      const r = await client.get('/visits', { params });
      setVisits(r.data.items);
      setTotal(r.data.total);
      setPages(r.data.pages);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const fetchAuxData = async () => {
    const isAgent = user?.role === 'AGENT';
    const [statsRes, propsRes, clientsRes, agentsRes] = await Promise.all([
      client.get('/visits/stats'),
      isAgent ? client.get('/properties/my') : client.get('/properties', { params: { limit: 200 } }),
      client.get('/clients', { params: { limit: 200 } }).catch(() => ({ data: { items: [] } })),
      isAgent ? Promise.resolve({ data: [] }) : client.get('/auth/tenant/users').catch(() => ({ data: [] })),
    ]);
    setStats(statsRes.data);
    setProperties((propsRes.data.items ?? propsRes.data).map((p: any) => ({ id: p.id, title: p.title })));
    setClients((clientsRes.data.items ?? clientsRes.data).map((c: any) => ({ id: c.id, full_name: c.full_name })));
    setAgents(agentsRes.data.map((u: any) => ({ id: u.id, full_name: u.full_name })));
  };

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      fetchVisits(1, searchQuery, statusFilter);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    fetchVisits(page, searchQuery, statusFilter);
  }, [page, statusFilter]);

  useEffect(() => {
    fetchAuxData();
  }, []);

  const openCreate = () => { setForm(emptyForm); setShowForm(true); setError(''); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setSaving(true);
    try {
      await client.post('/visits', {
        property_id: form.property_id,
        client_id: form.client_id || null,
        agent_id: form.agent_id || null,
        scheduled_at: form.scheduled_at,
        duration_minutes: parseInt(form.duration_minutes),
        notes: form.notes || null,
      });
      setShowForm(false);
      fetchVisits(page, searchQuery, statusFilter);
      fetchAuxData();
    } catch (err: any) { setError(err.response?.data?.detail || 'Error creating visit'); }
    finally { setSaving(false); }
  };

  const handleStatusChange = async (visitId: string, newStatus: string) => {
    try {
      await client.put(`/visits/${visitId}`, { status: newStatus });
      fetchVisits(page, searchQuery, statusFilter);
      fetchAuxData();
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar esta visita?')) return;
    try {
      await client.delete(`/visits/${id}`);
      fetchVisits(page, searchQuery, statusFilter);
      fetchAuxData();
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const openFeedback = (v: VisitData) => {
    setFeedbackVisit(v);
    setFeedbackText(v.feedback || '');
    setFeedbackRating(v.rating || 3);
  };

  const handleSaveFeedback = async () => {
    if (!feedbackVisit) return;
    try {
      await client.put(`/visits/${feedbackVisit.id}`, {
        feedback: feedbackText,
        rating: feedbackRating,
        status: 'COMPLETED',
      });
      setFeedbackVisit(null);
      fetchVisits(page, searchQuery, statusFilter);
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const statusColor = (key: string | null) => VISIT_STATUSES.find(s => s.key === key)?.color || 'bg-slate-100 text-slate-800';
  const inputCls = "block w-full rounded-lg border-0 py-2 px-3 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm";

  return (
    <div className="p-8 space-y-6">
      <div className="flex sm:items-center justify-between flex-col sm:flex-row gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Visitas</h1>
          <p className="text-slate-500 mt-1">Programa y gestiona las visitas de propiedades.</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5">
          <Plus className="h-5 w-5" /> <span>Nueva Visita</span>
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            { label: 'Total', value: stats.total, color: 'text-slate-900' },
            { label: 'Programadas', value: stats.scheduled, color: 'text-blue-600' },
            { label: 'Realizadas', value: stats.completed, color: 'text-emerald-600' },
            { label: 'Canceladas', value: stats.cancelled, color: 'text-red-600' },
            { label: 'No Show', value: stats.no_show, color: 'text-amber-600' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
              <p className="text-xs font-semibold text-slate-500 uppercase">{s.label}</p>
              <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Create Form */}
      {showForm && (
        <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-slate-800">Programar Nueva Visita</h2>
            <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
          </div>
          {error && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Propiedad *</label>
                <select required value={form.property_id} onChange={e => setForm({...form, property_id: e.target.value})} className={inputCls}>
                  <option value="">Seleccionar propiedad...</option>
                  {properties.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
                </select></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Cliente</label>
                <select value={form.client_id} onChange={e => setForm({...form, client_id: e.target.value})} className={inputCls}>
                  <option value="">— Sin cliente —</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.full_name}</option>)}
                </select></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {isManager && (
                <div><label className="block text-sm font-semibold text-slate-700 mb-1">Agente</label>
                  <select value={form.agent_id} onChange={e => setForm({...form, agent_id: e.target.value})} className={inputCls}>
                    <option value="">— Sin Agente —</option>
                    {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                  </select></div>
              )}
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Fecha y Hora *</label>
                <input type="datetime-local" required value={form.scheduled_at} onChange={e => setForm({...form, scheduled_at: e.target.value})} className={inputCls} /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1">Duración (min)</label>
                <input type="number" min="15" step="15" value={form.duration_minutes} onChange={e => setForm({...form, duration_minutes: e.target.value})} className={inputCls} /></div>
            </div>
            <div><label className="block text-sm font-semibold text-slate-700 mb-1">Notas</label>
              <textarea rows={2} value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} className={inputCls} placeholder="Detalles de la visita..." /></div>
            <div className="flex justify-end">
              <button disabled={saving} type="submit" className="flex items-center rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 transition-all">
                {saving ? 'Guardando...' : 'Programar Visita'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Status Filters */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => { setStatusFilter('ALL'); setPage(1); }}
          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${statusFilter === 'ALL' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>
          Todas
        </button>
        {VISIT_STATUSES.map(s => (
          <button key={s.key} onClick={() => { setStatusFilter(s.key); setPage(1); }}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${statusFilter === s.key ? 'bg-slate-900 text-white' : s.color + ' hover:opacity-80'}`}>
            {s.label}
          </button>
        ))}
      </div>

      {/* Visits Table */}
      <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input type="text" placeholder="Buscar por propiedad o cliente..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border-0 ring-1 ring-inset ring-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-inset focus:ring-indigo-600 bg-white" />
          </div>
        </div>

        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando...</div>
          ) : visits.length === 0 ? (
            <div className="p-8 text-center text-slate-500">No se encontraron visitas.</div>
          ) : (
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Fecha</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Propiedad</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Cliente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Agente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Estado</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Valoración</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {visits.map(v => (
                  <tr key={v.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-indigo-600" />
                        <div>
                          <p className="text-sm font-medium text-slate-900">
                            {v.scheduled_at ? new Date(v.scheduled_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                          </p>
                          <p className="text-xs text-slate-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {v.scheduled_at ? new Date(v.scheduled_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }) : ''}
                            {v.duration_minutes ? ` · ${v.duration_minutes} min` : ''}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div>
                        <p className="text-sm font-medium text-slate-900 flex items-center gap-1"><Home className="w-3.5 h-3.5 text-indigo-600" />{v.property_title}</p>
                        {v.property_address && <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5"><MapPin className="w-3 h-3" />{v.property_address}</p>}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {v.client_name ? <span className="flex items-center gap-1"><User className="w-3 h-3" />{v.client_name}</span> : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {v.agent_name || <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-4">
                      <select value={v.status_key || ''} onChange={e => handleStatusChange(v.id, e.target.value)}
                        className={`rounded-full px-2.5 py-1 text-xs font-semibold border-0 cursor-pointer ${statusColor(v.status_key)}`}>
                        {VISIT_STATUSES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-4">
                      {v.rating ? (
                        <div className="flex items-center gap-0.5">
                          {[1, 2, 3, 4, 5].map(n => (
                            <Star key={n} className={`w-3.5 h-3.5 ${n <= v.rating! ? 'text-amber-500 fill-amber-500' : 'text-slate-300'}`} />
                          ))}
                        </div>
                      ) : <span className="text-xs text-slate-400">Sin valorar</span>}
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        <button onClick={() => openFeedback(v)} className="text-slate-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-indigo-50" title="Feedback">
                          <MessageSquare className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleDelete(v.id)} className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50" title="Eliminar">
                          <Trash2 className="w-4 h-4" />
                        </button>
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

      {/* Feedback Modal */}
      {feedbackVisit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">Feedback de Visita</h3>
              <button onClick={() => setFeedbackVisit(null)} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            <p className="text-sm text-slate-600 mb-4">{feedbackVisit.property_title} — {feedbackVisit.client_name || 'Sin cliente'}</p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Valoración del interés del cliente</label>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map(n => (
                    <button key={n} onClick={() => setFeedbackRating(n)} className="p-1 hover:scale-110 transition-transform">
                      <Star className={`w-6 h-6 ${n <= feedbackRating ? 'text-amber-500 fill-amber-500' : 'text-slate-300'}`} />
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Comentarios</label>
                <textarea rows={3} value={feedbackText} onChange={e => setFeedbackText(e.target.value)}
                  className={inputCls} placeholder="¿Cómo fue la visita? ¿Qué comentó el cliente?" />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setFeedbackVisit(null)} className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg">Cancelar</button>
              <button onClick={handleSaveFeedback} className="px-4 py-2 text-sm font-semibold text-white bg-emerald-600 rounded-lg hover:bg-emerald-500">Guardar Feedback</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
