import { useState, useEffect } from 'react';
import client from '../api/client';
import { Building2, UserPlus, Copy, Check, LogOut, ShieldAlert, Mail, Edit, Trash2, X, Save, Users, ToggleLeft, ToggleRight, ChevronDown, ChevronRight, Send } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

interface TenantData {
  id: string;
  name: string;
  plan: string;
  is_active: boolean;
  created_at: string | null;
  user_count: number;
}

interface TenantUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export default function SuperAdminDashboard() {
  const { logout } = useAuth();
  const [tenants, setTenants] = useState<TenantData[]>([]);
  const [loading, setLoading] = useState(true);

  // Create tenant
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [tenantName, setTenantName] = useState('');
  const [tenantPlan, setTenantPlan] = useState('basic');

  // Edit tenant
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', plan: '' });

  // Expanded tenant (show users)
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tenantUsers, setTenantUsers] = useState<TenantUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Invite user
  const [inviteTenantId, setInviteTenantId] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState('ADMIN');
  const [generatedLink, setGeneratedLink] = useState('');
  const [copied, setCopied] = useState(false);

  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchTenants(); }, []);

  const fetchTenants = async () => {
    try { setLoading(true); const r = await client.get('/auth/admin/tenants'); setTenants(r.data); }
    catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      await client.post('/auth/admin/tenants', { name: tenantName, plan: tenantPlan });
      setTenantName(''); setShowCreateForm(false);
      fetchTenants();
    } catch (err: any) { setError(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  const startEdit = (t: TenantData) => {
    setEditingId(t.id);
    setEditForm({ name: t.name, plan: t.plan });
  };

  const handleUpdate = async () => {
    if (!editingId) return;
    try {
      await client.put(`/auth/admin/tenants/${editingId}`, editForm);
      setEditingId(null); fetchTenants();
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const handleToggleActive = async (t: TenantData) => {
    try {
      await client.put(`/auth/admin/tenants/${t.id}`, { is_active: !t.is_active });
      fetchTenants();
    } catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Esto eliminará permanentemente la agencia y TODOS sus datos. ¿Estás seguro?')) return;
    try { await client.delete(`/auth/admin/tenants/${id}`); fetchTenants(); }
    catch (err: any) { alert(err.response?.data?.detail || 'Error'); }
  };

  const toggleExpand = async (id: string) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    setLoadingUsers(true);
    try { const r = await client.get(`/auth/admin/tenants/${id}/users`); setTenantUsers(r.data); }
    catch (err) { console.error(err); }
    finally { setLoadingUsers(false); }
  };

  const openInvite = (tenantId: string) => {
    setInviteTenantId(tenantId);
    setInviteEmail(''); setInviteName(''); setInviteRole('ADMIN');
    setGeneratedLink(''); setCopied(false); setError('');
  };

  const handleInviteUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setGeneratedLink(''); setCopied(false);
    try {
      const r = await client.post('/auth/admin/users/invite', {
        tenant_id: inviteTenantId, email: inviteEmail, full_name: inviteName, role: inviteRole,
      });
      setGeneratedLink(r.data.invite_link);
      setInviteEmail(''); setInviteName('');
      // Refresh user list if expanded
      if (expandedId === inviteTenantId) { const ur = await client.get(`/auth/admin/tenants/${inviteTenantId}/users`); setTenantUsers(ur.data); }
      fetchTenants();
    } catch (err: any) { setError(err.response?.data?.detail || 'Error'); }
  };

  const handleCopyLink = () => { navigator.clipboard.writeText(generatedLink); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  const planColors: Record<string, string> = {
    basic: 'bg-slate-100 text-slate-700',
    premium: 'bg-indigo-100 text-indigo-700',
    enterprise: 'bg-amber-100 text-amber-700',
  };

  const inputCls = "block w-full rounded-lg border-0 py-2 px-3 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm";

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-slate-900 rounded-lg flex items-center justify-center">
                <ShieldAlert className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold tracking-tight text-slate-900">SuperAdmin</span>
            </div>
            <button onClick={logout} className="flex items-center text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors">
              <LogOut className="w-4 h-4 mr-2" /> Cerrar sesión
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        {/* Title + Create button */}
        <div className="flex sm:items-center justify-between flex-col sm:flex-row gap-4">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Gestión de Tenants</h1>
            <p className="mt-1 text-sm text-slate-500">Crea, configura y gestiona todas las agencias registradas y sus usuarios.</p>
          </div>
          <button onClick={() => { setShowCreateForm(!showCreateForm); setError(''); }}
            className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5">
            <Building2 className={`h-5 w-5 transition-transform ${showCreateForm ? 'rotate-45' : ''}`} />
            <span>{showCreateForm ? 'Cancelar' : 'Nuevo Tenant'}</span>
          </button>
        </div>

        {/* Create Tenant Form */}
        {showCreateForm && (
          <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl p-6">
            <h2 className="text-lg font-bold text-slate-800 mb-4">Registrar Nueva Agencia</h2>
            {error && !inviteTenantId && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
            <form onSubmit={handleCreateTenant} className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Nombre de la Empresa *</label>
                <input type="text" required value={tenantName} onChange={e => setTenantName(e.target.value)} placeholder="Agencia XYZ S.L." className={inputCls} />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Plan</label>
                <select value={tenantPlan} onChange={e => setTenantPlan(e.target.value)} className={inputCls + " font-medium"}>
                  <option value="basic">Básico</option>
                  <option value="premium">Premium</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
              <button disabled={saving} type="submit" className="flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 transition-all">
                {saving ? 'Creando...' : 'Registrar Agencia'}
              </button>
            </form>
          </div>
        )}

        {/* Stats overview */}
        {!loading && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
              <p className="text-xs font-semibold text-slate-500 uppercase">Total Tenants</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{tenants.length}</p>
            </div>
            <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
              <p className="text-xs font-semibold text-slate-500 uppercase">Activos</p>
              <p className="text-2xl font-bold text-emerald-600 mt-1">{tenants.filter(t => t.is_active).length}</p>
            </div>
            <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
              <p className="text-xs font-semibold text-slate-500 uppercase">Inactivos</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{tenants.filter(t => !t.is_active).length}</p>
            </div>
            <div className="bg-white rounded-xl p-4 ring-1 ring-slate-900/5 shadow-sm">
              <p className="text-xs font-semibold text-slate-500 uppercase">Total Usuarios</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{tenants.reduce((s, t) => s + t.user_count, 0)}</p>
            </div>
          </div>
        )}

        {/* Tenants Table */}
        <div className="bg-white ring-1 ring-slate-900/5 shadow-sm rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            {loading ? <div className="p-8 text-center text-slate-500">Cargando tenants...</div>
            : tenants.length === 0 ? <div className="p-8 text-center text-slate-500">No hay tenants registrados.</div>
            : (
              <table className="min-w-full divide-y divide-slate-200">
                <thead>
                  <tr className="bg-slate-50">
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase w-8"></th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Agencia</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Plan</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Usuarios</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Estado</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Creado</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase">Acciones</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {tenants.map(t => {
                    const isEditing = editingId === t.id;
                    const isExpanded = expandedId === t.id;
                    return (
                      <>
                        <tr key={t.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-6 py-4">
                            <button onClick={() => toggleExpand(t.id)} className="text-slate-400 hover:text-slate-700">
                              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                            </button>
                          </td>
                          <td className="px-4 py-4">
                            {isEditing ? (
                              <input value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})}
                                className="block w-full rounded border-0 py-1.5 px-2 text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 text-sm" />
                            ) : (
                              <div className="flex items-center">
                                <div className="h-9 w-9 flex-shrink-0 rounded-lg bg-indigo-50 flex items-center justify-center">
                                  <Building2 className="w-4 h-4 text-indigo-600" />
                                </div>
                                <span className="ml-3 text-sm font-medium text-slate-900">{t.name}</span>
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-4">
                            {isEditing ? (
                              <select value={editForm.plan} onChange={e => setEditForm({...editForm, plan: e.target.value})}
                                className="rounded border-0 py-1.5 px-2 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 font-medium">
                                <option value="basic">Básico</option>
                                <option value="premium">Premium</option>
                                <option value="enterprise">Enterprise</option>
                              </select>
                            ) : (
                              <span className={`px-2.5 py-1 text-xs font-semibold rounded-full capitalize ${planColors[t.plan] || 'bg-slate-100 text-slate-700'}`}>{t.plan}</span>
                            )}
                          </td>
                          <td className="px-4 py-4 text-sm text-slate-700 font-medium">{t.user_count}</td>
                          <td className="px-4 py-4">
                            <button onClick={() => handleToggleActive(t)} className="flex items-center gap-1.5 text-xs font-semibold" title="Alternar estado">
                              {t.is_active ? (
                                <><ToggleRight className="w-5 h-5 text-emerald-500" /><span className="text-emerald-700">Activo</span></>
                              ) : (
                                <><ToggleLeft className="w-5 h-5 text-slate-400" /><span className="text-slate-500">Inactivo</span></>
                              )}
                            </button>
                          </td>
                          <td className="px-4 py-4 text-xs text-slate-500">
                            {t.created_at ? new Date(t.created_at).toLocaleDateString('es-ES') : '—'}
                          </td>
                          <td className="px-4 py-4 text-right">
                            <div className="flex items-center justify-end space-x-2">
                              {isEditing ? (
                                <>
                                  <button onClick={handleUpdate} className="text-emerald-600 hover:bg-emerald-50 p-1.5 rounded-lg" title="Guardar"><Save className="w-4 h-4" /></button>
                                  <button onClick={() => setEditingId(null)} className="text-slate-400 hover:bg-slate-100 p-1.5 rounded-lg" title="Cancelar"><X className="w-4 h-4" /></button>
                                </>
                              ) : (
                                <>
                                  <button onClick={() => openInvite(t.id)} className="text-slate-400 hover:text-emerald-600 p-1.5 rounded-lg hover:bg-emerald-50" title="Invitar Usuario"><UserPlus className="w-4 h-4" /></button>
                                  <button onClick={() => startEdit(t)} className="text-slate-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-indigo-50" title="Editar"><Edit className="w-4 h-4" /></button>
                                  <button onClick={() => handleDelete(t.id)} className="text-slate-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50" title="Eliminar"><Trash2 className="w-4 h-4" /></button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                        {/* Expanded: users list */}
                        {isExpanded && (
                          <tr key={t.id + '-users'}>
                            <td colSpan={7} className="bg-slate-50 px-10 py-4 border-t border-slate-100">
                              {loadingUsers ? <p className="text-sm text-slate-500">Cargando usuarios...</p>
                              : tenantUsers.length === 0 ? <p className="text-sm text-slate-500">No hay usuarios en esta agencia.</p>
                              : (
                                <div className="space-y-2">
                                  <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Usuarios de {t.name}</p>
                                  {tenantUsers.map(u => (
                                    <div key={u.id} className="flex items-center justify-between bg-white rounded-lg px-4 py-2.5 ring-1 ring-slate-200">
                                      <div className="flex items-center gap-3">
                                        <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-xs">
                                          {u.full_name?.charAt(0).toUpperCase() || '?'}
                                        </div>
                                        <div>
                                          <p className="text-sm font-medium text-slate-900">{u.full_name}</p>
                                          <p className="text-xs text-slate-500">{u.email}</p>
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-3">
                                        <span className="text-xs font-medium text-slate-600">{u.role}</span>
                                        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${u.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                                          {u.is_active ? 'Activo' : 'Pendiente'}
                                        </span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </main>

      {/* Invite Modal */}
      {inviteTenantId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">Invitar Usuario a la Agencia</h3>
              <button onClick={() => { setInviteTenantId(null); setGeneratedLink(''); }} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
            </div>
            {error && inviteTenantId && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</div>}
            <form onSubmit={handleInviteUser} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-1">Nombre Completo *</label>
                  <input type="text" required value={inviteName} onChange={e => setInviteName(e.target.value)} className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-1">Rol *</label>
                  <select value={inviteRole} onChange={e => setInviteRole(e.target.value)} className={inputCls + " font-medium"}>
                    <option value="ADMIN">Administrador</option>
                    <option value="MANAGER">Gestor</option>
                    <option value="AGENT">Agente</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Correo electrónico *</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input type="email" required value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="admin@agencia.com" className={inputCls + " pl-10"} />
                </div>
              </div>
              <button type="submit" className="w-full flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 transition-all">
                <Send className="w-4 h-4 mr-2" /> Generar Enlace de Invitación
              </button>
            </form>
            {generatedLink && (
              <div className="mt-4 p-3 bg-emerald-50 rounded-lg border border-emerald-100">
                <div className="flex items-center text-emerald-800 text-sm font-medium mb-2">
                  <Check className="w-4 h-4 mr-2" /> ¡Invitación generada! Comparte este enlace:
                </div>
                <div className="flex gap-2">
                  <input readOnly value={generatedLink} className="flex-1 bg-white border border-emerald-200 text-slate-600 text-xs rounded py-1.5 px-2 focus:outline-none" />
                  <button onClick={handleCopyLink} className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded hover:bg-emerald-700 flex items-center">
                    {copied ? <><Check className="w-3 h-3 mr-1" />Copiado</> : <><Copy className="w-3 h-3 mr-1" />Copiar</>}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
