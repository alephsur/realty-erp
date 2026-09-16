import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import client from '../src/api/client';
import Clients from '../src/pages/tenant/Clients';
import Visits from '../src/pages/tenant/Visits';

const session = vi.hoisted(() => ({ role: 'MANAGER' }));
vi.mock('../src/hooks/useAuth', () => ({ useAuth: () => ({ user: { id: 'agent', role: session.role } }) }));
vi.mock('../src/api/client', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }));

const buyer = { id: 'buyer', first_name: 'Ana', last_name: 'García', full_name: 'Ana García',
  client_type: 'Demandante', client_type_key: 'BUYER', agent_id: 'agent', agent_name: 'Agente activo',
  is_active: true, property_interests: [] };
const employees = [
  { id: 'agent', full_name: 'Agente activo', is_active: true, role: 'AGENT' },
  { id: 'other', full_name: 'Segundo agente', is_active: true, role: 'AGENT' },
  { id: 'inactive', full_name: 'Agente de baja', is_active: false, role: 'AGENT' },
];

beforeEach(() => {
  vi.resetAllMocks();
  session.role = 'MANAGER';
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(client.get).mockImplementation(async url => ({ data: url === '/auth/tenant/users' ? employees :
    { items: [buyer], total: 1, page: 1, pages: 1 } }));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

test('manager archives and restores a client without erasing the record', async () => {
  let active = true;
  vi.mocked(client.delete).mockImplementation(async () => { active = false; return { data: {} }; });
  vi.mocked(client.put).mockImplementation(async () => { active = true; return { data: {} }; });
  vi.mocked(client.get).mockImplementation(async (url, config) => ({ data: url === '/auth/tenant/users' ? employees :
    { items: active || config?.params?.include_inactive ? [{ ...buyer, is_active: active }] : [], total: 1, page: 1, pages: 1 } }));
  render(<Clients />);
  fireEvent.click(await screen.findByTitle('Archivar'));
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('Se conservarán'));
  await waitFor(() => expect(screen.queryByText('Ana García')).toBeNull());
  fireEvent.click(screen.getByLabelText('Incluir clientes archivados'));
  expect(await screen.findByText('Archivado')).toBeTruthy();
  fireEvent.click(screen.getByTitle('Restaurar cliente'));
  await waitFor(() => expect(client.put).toHaveBeenCalledWith('/clients/buyer', { is_active: true }));
  await waitFor(() => expect(screen.queryByText('Archivado')).toBeNull());
});

test('an agent edits contact data without sending reassignment privileges', async () => {
  session.role = 'AGENT';
  render(<Clients />);
  fireEvent.click(await screen.findByTitle('Editar'));
  const form = screen.getByDisplayValue('Ana').closest('form')!;
  fireEvent.change(screen.getByDisplayValue('Ana'), { target: { value: 'Ana María' } });
  fireEvent.submit(form);
  await waitFor(() => expect(client.put).toHaveBeenCalled());
  expect(vi.mocked(client.put).mock.calls[0][1]).toMatchObject({ first_name: 'Ana María' });
  expect(vi.mocked(client.put).mock.calls[0][1]).not.toHaveProperty('agent_id');
  expect(screen.queryByTitle('Archivar')).toBeNull();
  expect(vi.mocked(client.get).mock.calls.some(([url]) => url === '/auth/tenant/users')).toBe(false);
});

test('manager can reassign a client and cannot select an inactive employee', async () => {
  render(<Clients />);
  fireEvent.click(await screen.findByTitle('Editar'));
  const option = await screen.findByRole('option', { name: 'Segundo agente' });
  expect(screen.queryByRole('option', { name: 'Agente de baja' })).toBeNull();
  fireEvent.change(option.closest('select')!, { target: { value: 'other' } });
  fireEvent.submit(screen.getByDisplayValue('Ana').closest('form')!);
  await waitFor(() => expect(client.put).toHaveBeenCalledWith('/clients/buyer', expect.objectContaining({ agent_id: 'other' })));
});

test('visit references narrow to the selected agent and clear previous choices', async () => {
  vi.mocked(client.get).mockImplementation(async url => ({ data:
    url === '/auth/tenant/users' ? employees : url === '/visits/stats' ? {} :
    url === '/properties' ? { items: [
      { id: 'home', title: 'Casa asignada', agent_id: 'agent' },
      { id: 'other-home', title: 'Casa ajena', agent_id: 'other' },
    ] } : url === '/clients' ? { items: [buyer, { ...buyer, id: 'other-buyer', full_name: 'Otro comprador', agent_id: 'other' }] } :
    { items: [], total: 0, pages: 1 } }));
  render(<Visits />);
  fireEvent.click(screen.getByRole('button', { name: /Nueva Visita/i }));
  const propertySelect = (await screen.findByRole('option', { name: 'Casa ajena' })).closest('select')!;
  fireEvent.change(propertySelect, { target: { value: 'other-home' } });
  const agentSelect = screen.getByRole('option', { name: 'Agente activo' }).closest('select')!;
  fireEvent.change(agentSelect, { target: { value: 'agent' } });
  expect(propertySelect.value).toBe('');
  expect(screen.queryByRole('option', { name: 'Casa ajena' })).toBeNull();
  expect(screen.queryByRole('option', { name: 'Otro comprador' })).toBeNull();
  expect(screen.queryByRole('option', { name: 'Agente de baja' })).toBeNull();
  expect(screen.getByRole('option', { name: 'Casa asignada' })).toBeTruthy();
});
