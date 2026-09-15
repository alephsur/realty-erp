import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import client from '../src/api/client';
import Properties from '../src/pages/tenant/Properties';
import PropertyKanban from '../src/pages/tenant/PropertyKanban';
import NewSaleButton from '../src/components/NewSaleButton';

vi.mock('../src/api/client', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }));
const actor = vi.hoisted(() => ({ id: 'manager', role: 'MANAGER' }));
vi.mock('../src/hooks/useAuth', () => ({ useAuth: () => ({ user: actor }) }));
vi.mock('../src/components/SellPropertyModal', () => ({
  default: ({ propertyId, onClose }: { propertyId: string; onClose: () => void }) =>
    <div role="dialog" aria-label="Cierre común">{propertyId}<button onClick={onClose}>Cancelar cierre</button></div>,
}));

const property = {
  id: 'property-id', title: 'Casa de prueba', address: 'Calle de prueba', price: 200000,
  property_type: 'CASA', status_key: 'CAPTADA', status: 'Captada', agent_id: 'agent',
  agent_name: 'Agente asignado', commission_rate: 3, agent_commission_rate: 40,
  created_at: new Date().toISOString(), status_changed_at: new Date().toISOString(),
};

beforeEach(() => {
  vi.resetAllMocks();
  actor.id = 'manager';
  actor.role = 'MANAGER';
  vi.mocked(client.get).mockImplementation(async url => ({ data: url === '/auth/tenant/users'
    ? [] : { items: [property], total: 1, pages: 1, page: 1 } }));
});
afterEach(cleanup);

test('the property status selector opens the shared form without changing state', async () => {
  render(<Properties />);
  const row = await screen.findByRole('row', { name: /Casa de prueba/ });
  const select = within(row).getByRole('combobox') as HTMLSelectElement;
  fireEvent.change(select, { target: { value: 'VENDIDA' } });
  expect(screen.getByRole('dialog', { name: 'Cierre común' })).toBeTruthy();
  expect(client.put).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar cierre' }));
  expect(select.value).toBe('CAPTADA');
  expect(client.post).not.toHaveBeenCalled();
});

test('the property sale button opens the same form', async () => {
  render(<Properties />);
  const button = await screen.findByTitle('Registrar Venta');
  fireEvent.click(button);
  expect(screen.getByRole('dialog', { name: 'Cierre común' }).textContent).toContain('property-id');
});

test('the assigned agent can open the closing form from Properties', async () => {
  actor.id = 'agent';
  actor.role = 'AGENT';
  render(<Properties />);
  fireEvent.click(await screen.findByTitle('Registrar Venta'));
  expect(screen.getByRole('dialog', { name: 'Cierre común' })).toBeTruthy();
});

test('the assigned agent can close from the board without gaining other state changes', async () => {
  actor.id = 'agent';
  actor.role = 'AGENT';
  const { container } = render(<PropertyKanban />);
  await screen.findByText('Casa de prueba');
  const card = container.querySelector('[draggable="true"]')!;
  const reserved = screen.getByText('Reservada').parentElement!.parentElement!;
  fireEvent.dragStart(card, { dataTransfer: { effectAllowed: '' } });
  fireEvent.drop(reserved);
  expect(client.put).not.toHaveBeenCalled();
  expect(screen.getByRole('alert').textContent).toContain('columna Vendida');
  fireEvent.click(screen.getByRole('button', { name: 'Registrar venta' }));
  expect(screen.getByRole('dialog', { name: 'Cierre común' })).toBeTruthy();
});

test('dropping into Vendida opens the form and cancellation leaves the card in place', async () => {
  const { container } = render(<PropertyKanban />);
  await screen.findByText('Casa de prueba');
  const card = container.querySelector('[draggable="true"]')!;
  const sourceColumn = screen.getByText('Captada').parentElement!.parentElement!;
  const soldColumn = screen.getByText('Vendida').parentElement!.parentElement!;
  fireEvent.dragStart(card, { dataTransfer: { effectAllowed: '' } });
  fireEvent.drop(soldColumn);
  expect(screen.getByRole('dialog', { name: 'Cierre común' })).toBeTruthy();
  expect(client.put).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar cierre' }));
  expect(sourceColumn.contains(screen.getByText('Casa de prueba'))).toBe(true);
  expect(soldColumn.contains(screen.getByText('Casa de prueba'))).toBe(false);
});

test('registration from Sales selects a property and opens the shared form', async () => {
  render(<NewSaleButton onSold={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Registrar venta' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Casa de prueba' }));
  await waitFor(() => expect(screen.getByRole('dialog', { name: 'Cierre común' })).toBeTruthy());
  expect(client.get).toHaveBeenCalledWith('/properties', expect.objectContaining({
    params: expect.objectContaining({ for_sale: true }),
  }));
});
