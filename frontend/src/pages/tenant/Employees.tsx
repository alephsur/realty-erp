import { Plus, Search, Send, Trash2, Edit, X, Save, ShieldAlert, Mail } from 'lucide-react';
import { useState, useEffect } from 'react';
import client from '../../api/client';

interface Employee {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  phone: string | null;
  license_number: string | null;
  commission_rate: number | null;
  hire_date: string | null;
}

export default function Employees() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  
  // Create form state
  const [form, setForm] = useState({ email: '', full_name: '', role: 'AGENT', phone: '', license_number: '', commission_rate: '0', hire_date: '' });
  // Edit form state 
  const [editForm, setEditForm] = useState({ full_name: '', role: '', phone: '', license_number: '', commission_rate: '', hire_date: '' });
  
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [inviteLinks, setInviteLinks] = useState<{ [key: string]: string }>({});
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => { fetchEmployees(); }, []);

  const fetchEmployees = async () => {
    try {
      setLoading(true);
      const response = await client.get('/auth/tenant/users');
      setEmployees(response.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setCreating(true);
    try {
      await client.post('/auth/tenant/users', {
        email: form.email,
        full_name: form.full_name,
        role: form.role,
        phone: form.phone || null,
        license_number: form.license_number || null,
        commission_rate: parseFloat(form.commission_rate) || 0,
        hire_date: form.hire_date || null,
      });
      setForm({ email: '', full_name: '', role: 'AGENT', phone: '', license_number: '', commission_rate: '0', hire_date: '' });
      setShowAddForm(false);
      fetchEmployees();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error creating employee');
    } finally { setCreating(false); }
  };

  const startEdit = (emp: Employee) => {
    setEditingId(emp.id);
    setEditForm({
      full_name: emp.full_name || '',
      role: emp.role || 'AGENT',
      phone: emp.phone || '',
      license_number: emp.license_number || '',
      commission_rate: String(emp.commission_rate ?? '0'),
      hire_date: emp.hire_date || '',
    });
  };

  const handleUpdate = async () => {
    if (!editingId) return;
    try {
      await client.put(`/auth/tenant/users/${editingId}`, {
        full_name: editForm.full_name,
        role: editForm.role,
        phone: editForm.phone || null,
        license_number: editForm.license_number || null,
        commission_rate: parseFloat(editForm.commission_rate) || 0,
        hire_date: editForm.hire_date || null,
      });
      setEditingId(null);
      fetchEmployees();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error updating employee');
    }
  };

  const handleDelete = async (userId: string) => {
    if (!confirm('¿Estás seguro de que deseas eliminar este empleado?')) return;
    try {
      await client.delete(`/auth/tenant/users/${userId}`);
      fetchEmployees();
    } catch (err: any) { alert(err.response?.data?.detail || 'Error deleting'); }
  };

  const handleGenerateInvite = async (userId: string) => {
    try {
      const response = await client.post(`/auth/tenant/users/${userId}/invite`);
      setInviteLinks(prev => ({ ...prev, [userId]: response.data.invite_link }));
    } catch (err: any) { alert(err.response?.data?.detail || 'Error generating invite'); }
  };

  const handleCopyLink = (link: string) => {
    navigator.clipboard.writeText(link);
  };

  const filteredEmployees = employees.filter(e =>
    e.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    e.email?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const inputCls = "block w-full rounded-lg border-0 py-2 px-3 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm";
  const inputClsSm = "block w-full rounded border-0 py-1.5 px-2 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 text-xs";

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex sm:items-center justify-between flex-col sm:flex-row gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Empleados</h1>
          <p className="text-slate-500 mt-1">Registra agentes, gestiona sus datos y envía invitaciones de acceso.</p>
        </div>
        <button onClick={() => { setShowAddForm(!showAddForm); setError(''); }}
          className="flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5">
          <Plus className={`h-5 w-5 transition-transform ${showAddForm ? 'rotate-45' : ''}`} />
          <span>{showAddForm ? 'Cancelar' : 'Nuevo Empleado'}</span>
        </button>
      </div>

      {/* Create form */}
      {showAddForm && (
        <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl p-6">
          <h2 className="text-lg font-bold text-slate-800 mb-4">Registrar Nuevo Empleado</h2>
          {error && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Nombre Completo *</label>
                <input type="text" required value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Correo electrónico *</label>
                <input type="email" required value={form.email} onChange={e => setForm({...form, email: e.target.value})} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Rol *</label>
                <select value={form.role} onChange={e => setForm({...form, role: e.target.value})} className={inputCls + " font-medium"}>
                  <option value="ADMIN">Administrador</option>
                  <option value="MANAGER">Gestor</option>
                  <option value="AGENT">Agente</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Teléfono</label>
                <input type="tel" value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} className={inputCls} placeholder="+34 600 000 000" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Nº Licencia/Colegiado</label>
                <input type="text" value={form.license_number} onChange={e => setForm({...form, license_number: e.target.value})} className={inputCls} placeholder="COL-1234" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Comisión %</label>
                <input type="number" step="0.1" min="0" max="100" value={form.commission_rate} onChange={e => setForm({...form, commission_rate: e.target.value})} className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Fecha de Alta</label>
                <input type="date" value={form.hire_date} onChange={e => setForm({...form, hire_date: e.target.value})} className={inputCls} />
              </div>
            </div>
            <div className="flex justify-end">
              <button disabled={creating} type="submit" className="flex items-center rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 transition-all">
                {creating ? 'Guardando...' : 'Guardar Empleado'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Table */}
      <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input type="text" placeholder="Buscar empleados..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border-0 ring-1 ring-inset ring-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-inset focus:ring-indigo-600 bg-white" />
          </div>
        </div>
        
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Cargando...</div>
          ) : filteredEmployees.length === 0 ? (
            <div className="p-8 text-center text-slate-500">No se encontraron empleados.</div>
          ) : (
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Miembro</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Rol</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Teléfono</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Licencia</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Comisión</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Estado</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {filteredEmployees.map(person => {
                  const isEditing = editingId === person.id;
                  return (
                    <tr key={person.id} className="hover:bg-slate-50/50 transition-colors">
                      {/* Name + Email */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {isEditing ? (
                          <input value={editForm.full_name} onChange={e => setEditForm({...editForm, full_name: e.target.value})} className={inputClsSm} />
                        ) : (
                          <div className="flex items-center">
                            <div className="h-9 w-9 flex-shrink-0 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm">
                              {person.full_name?.charAt(0).toUpperCase() || '?'}
                            </div>
                            <div className="ml-3">
                              <div className="text-sm font-medium text-slate-900">{person.full_name}</div>
                              <div className="text-xs text-slate-500 flex items-center">
                                {person.role === 'ADMIN' && <ShieldAlert className="w-3 h-3 text-red-500 mr-1" />}
                                {person.email}
                              </div>
                            </div>
                          </div>
                        )}
                      </td>
                      {/* Role */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        {isEditing ? (
                          <select value={editForm.role} onChange={e => setEditForm({...editForm, role: e.target.value})} className={inputClsSm + " font-medium"}>
                            <option value="ADMIN">Administrador</option>
                            <option value="MANAGER">Gestor</option>
                            <option value="AGENT">Agente</option>
                          </select>
                        ) : <span className="text-sm font-medium text-slate-700">{person.role}</span>}
                      </td>
                      {/* Phone */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        {isEditing ? (
                          <input value={editForm.phone} onChange={e => setEditForm({...editForm, phone: e.target.value})} className={inputClsSm} />
                        ) : <span className="text-sm text-slate-600">{person.phone || '—'}</span>}
                      </td>
                      {/* License */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        {isEditing ? (
                          <input value={editForm.license_number} onChange={e => setEditForm({...editForm, license_number: e.target.value})} className={inputClsSm} />
                        ) : <span className="text-sm text-slate-600">{person.license_number || '—'}</span>}
                      </td>
                      {/* Commission */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        {isEditing ? (
                          <input type="number" step="0.1" value={editForm.commission_rate} onChange={e => setEditForm({...editForm, commission_rate: e.target.value})} className={inputClsSm + " w-20"} />
                        ) : <span className="text-sm text-slate-600">{person.commission_rate ?? 0}%</span>}
                      </td>
                      {/* Status */}
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span className={`px-2 py-0.5 inline-flex text-xs font-semibold rounded-full ${person.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                          {person.is_active ? 'Activo' : 'Pendiente'}
                        </span>
                        {inviteLinks[person.id] && (
                          <button onClick={() => handleCopyLink(inviteLinks[person.id])} className="mt-1 block text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1">
                             <Mail className="w-3 h-3" /> Copiar Enlace
                          </button>
                        )}
                      </td>
                      {/* Actions */}
                      <td className="px-4 py-4 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end space-x-2">
                          {isEditing ? (
                            <>
                              <button onClick={handleUpdate} className="text-emerald-600 hover:bg-emerald-50 p-1.5 rounded-lg" title="Guardar"><Save className="w-4 h-4" /></button>
                              <button onClick={() => setEditingId(null)} className="text-slate-400 hover:bg-slate-100 p-1.5 rounded-lg" title="Cancelar"><X className="w-4 h-4" /></button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => startEdit(person)} className="text-slate-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-indigo-50" title="Editar"><Edit className="w-4 h-4" /></button>
                              <button onClick={() => handleGenerateInvite(person.id)} className="text-slate-400 hover:text-emerald-600 p-1.5 rounded-lg hover:bg-emerald-50" title="Enviar Invitación"><Send className="w-4 h-4" /></button>
                              <button onClick={() => handleDelete(person.id)} className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50" title="Eliminar"><Trash2 className="w-4 h-4" /></button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
