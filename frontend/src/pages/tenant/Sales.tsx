import { useState, useEffect } from 'react';
import { Search, DollarSign, Home, User, Calendar, FileText } from 'lucide-react';
import client from '../../api/client';
import { useAuth } from '../../hooks/useAuth';

interface SaleData {
  id: string;
  property_id: string;
  property_title: string | null;
  property_reference: string | null;
  agent_id: string | null;
  agent_name: string | null;
  buyer_id: string | null;
  buyer_name: string | null;
  sale_price: number;
  total_commission: number;
  agent_commission: number;
  agency_commission: number;
  notes: string | null;
  sale_date: string | null;
  created_at: string | null;
}

interface AgentOption { id: string; full_name: string; }

export default function Sales() {
  const { user } = useAuth();
  const isManager = user?.role === 'ADMIN' || user?.role === 'MANAGER';
  const [sales, setSales] = useState<SaleData[]>([]);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [agentFilter, setAgentFilter] = useState('ALL');

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [salesRes, agentsRes] = await Promise.all([
        client.get('/properties/sales/list'),
        // Only managers need the agents list for the filter dropdown
        isManager
          ? client.get('/auth/tenant/users').catch(() => ({ data: [] }))
          : Promise.resolve({ data: [] }),
      ]);
      setSales(salesRes.data);
      setAgents(agentsRes.data.map((u: any) => ({ id: u.id, full_name: u.full_name })));
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const filtered = sales.filter(s => {
    const matchesSearch =
      (s.property_title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.property_reference || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.agent_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.buyer_name || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesAgent = agentFilter === 'ALL' || s.agent_id === agentFilter;
    return matchesSearch && matchesAgent;
  });

  const totalVolume = filtered.reduce((sum, s) => sum + s.sale_price, 0);
  const totalCommission = filtered.reduce((sum, s) => sum + s.total_commission, 0);
  const totalAgentComm = filtered.reduce((sum, s) => sum + s.agent_commission, 0);
  const totalAgencyComm = filtered.reduce((sum, s) => sum + s.agency_commission, 0);

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Ventas</h1>
        <p className="text-slate-500 mt-1">Historial de ventas y desglose de comisiones.</p>
      </div>

      {/* Summary Cards */}
      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
            <p className="text-xs font-semibold text-slate-500 uppercase">Total Ventas</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{filtered.length}</p>
          </div>
          <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
            <p className="text-xs font-semibold text-slate-500 uppercase">Volumen Total</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{totalVolume.toLocaleString('es-ES')} €</p>
          </div>
          <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
            <p className="text-xs font-semibold text-slate-500 uppercase">Comisión Agentes</p>
            <p className="text-2xl font-bold text-emerald-600 mt-1">{totalAgentComm.toLocaleString('es-ES')} €</p>
          </div>
          <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
            <p className="text-xs font-semibold text-slate-500 uppercase">Comisión Agencia</p>
            <p className="text-2xl font-bold text-indigo-600 mt-1">{totalAgencyComm.toLocaleString('es-ES')} €</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex flex-wrap gap-4 items-center">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input type="text" placeholder="Buscar por propiedad, agente, comprador..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border-0 ring-1 ring-inset ring-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-inset focus:ring-indigo-600 bg-white" />
          </div>
          {isManager && agents.length > 0 && (
            <select value={agentFilter} onChange={e => setAgentFilter(e.target.value)}
              className="rounded-lg border-0 py-2 px-3 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 font-medium">
              <option value="ALL">Todos los Agentes</option>
              {agents.map(a => <option key={a.id} value={a.id}>{a.full_name}</option>)}
            </select>
          )}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          {loading ? <div className="p-8 text-center text-slate-500">Cargando ventas...</div>
          : filtered.length === 0 ? <div className="p-8 text-center text-slate-500">No se encontraron ventas.</div>
          : (
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Propiedad</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Agente</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Comprador</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Precio Venta</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Comisión Total</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Agente</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Agencia</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Fecha</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {filtered.map(s => (
                  <tr key={s.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 flex-shrink-0 rounded-lg bg-indigo-50 flex items-center justify-center">
                          <Home className="w-4 h-4 text-indigo-600" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">{s.property_title}</p>
                          {s.property_reference && <p className="text-xs text-slate-400">Ref: {s.property_reference}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {s.agent_name ? <span className="flex items-center gap-1"><User className="w-3 h-3" />{s.agent_name}</span> : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-600">
                      {s.buyer_name || <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-4 text-sm font-semibold text-slate-900 text-right">{s.sale_price.toLocaleString('es-ES')} €</td>
                    <td className="px-4 py-4 text-sm font-semibold text-slate-700 text-right">{s.total_commission.toLocaleString('es-ES')} €</td>
                    <td className="px-4 py-4 text-sm font-medium text-emerald-700 text-right">{s.agent_commission.toLocaleString('es-ES')} €</td>
                    <td className="px-4 py-4 text-sm font-medium text-indigo-700 text-right">{s.agency_commission.toLocaleString('es-ES')} €</td>
                    <td className="px-4 py-4 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {s.sale_date ? new Date(s.sale_date).toLocaleDateString('es-ES') : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
