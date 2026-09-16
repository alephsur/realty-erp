import { test, expect, type Page, type Response } from '@playwright/test';
import { readFileSync } from 'node:fs';

interface Account { id: string; email: string; password: string; name: string }
interface PropertyFixture { id: string; title: string }
const seed: { accounts: Record<string, Account>; properties: Record<string, PropertyFixture> } =
  JSON.parse(readFileSync(process.env.E2E_SEED_PATH!, 'utf8'));
const api = process.env.E2E_API_URL!;

const runtimeErrors = new Map<Page, string[]>();
test.beforeEach(({ page }) => {
  const errors: string[] = [];
  runtimeErrors.set(page, errors);
  page.on('pageerror', error => errors.push(error.message));
});
test.afterEach(({ page }) => {
  expect(runtimeErrors.get(page), 'The browser must not have uncaught application errors').toEqual([]);
  runtimeErrors.delete(page);
});

async function successful(response: Promise<Response>) {
  const result = await response;
  expect(result.ok(), `${result.url()}: ${await result.text()}`).toBeTruthy();
  return result.json();
}

async function login(page: Page, account: Account) {
  await page.goto('/login');
  await page.getByLabel('Correo electrónico').fill(account.email);
  await page.getByLabel('Contraseña', { exact: true }).fill(account.password);
  const authenticated = page.waitForResponse(r => r.url() === `${api}/auth/login` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await successful(authenticated);
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Menú de usuario' })).toContainText(account.name);
  const cookies = await page.context().cookies();
  expect(cookies.find(cookie => cookie.name === 'access_token')?.httpOnly).toBe(true);
  expect(cookies.find(cookie => cookie.name === 'csrf_token')?.httpOnly).toBe(false);
}

async function createProperty(page: Page, title: string, agent: Account) {
  await page.goto('/properties');
  await page.getByRole('button', { name: 'Nueva Propiedad' }).click();
  await page.getByLabel('Título *', { exact: true }).fill(title);
  await page.getByLabel('Precio (€) *', { exact: true }).fill('200000');
  await page.getByLabel('Dirección *', { exact: true }).fill('Calle del recorrido comercial 20');
  await page.getByLabel('Comisión Propietario %', { exact: true }).fill('3');
  await page.getByLabel('Agente Asignado', { exact: true }).selectOption({ label: agent.name });
  const created = page.waitForResponse(r => r.url() === `${api}/properties` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Guardar Propiedad', exact: true }).click();
  const body = await successful(created);
  await expect(page.getByRole('row').filter({ hasText: title })).toBeVisible();
  return body.id as string;
}

async function createBuyer(page: Page, suffix: string, agent?: Account) {
  await page.goto('/clients');
  await page.getByRole('button', { name: 'Nuevo Cliente' }).click();
  await page.getByLabel('Nombre *', { exact: true }).fill('Comprador');
  await page.getByLabel('Apellidos *', { exact: true }).fill(suffix);
  await page.getByLabel('Tipo *', { exact: true }).selectOption('Demandante');
  if (agent) await page.getByLabel('Agente Asignado', { exact: true }).selectOption({ label: agent.name });
  const created = page.waitForResponse(r => r.url() === `${api}/clients` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Guardar Cliente', exact: true }).click();
  const body = await successful(created);
  const name = `Comprador ${suffix}`;
  await expect(page.getByRole('row').filter({ hasText: name })).toBeVisible();
  return { id: body.id as string, name };
}

async function completeVisit(page: Page, property: PropertyFixture, buyer: { id: string; name: string }, agent?: Account) {
  await page.goto('/visits');
  await page.getByRole('button', { name: 'Nueva Visita' }).click();
  if (agent) await page.getByLabel('Agente', { exact: true }).selectOption({ label: agent.name });
  await page.getByLabel('Propiedad *', { exact: true }).selectOption({ label: property.title });
  await page.getByLabel('Cliente', { exact: true }).selectOption({ label: buyer.name });
  await page.getByLabel('Fecha y Hora *', { exact: true }).fill('2026-01-10T10:00');
  const created = page.waitForResponse(r => r.url() === `${api}/visits` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Programar Visita', exact: true }).click();
  const visit = await successful(created);
  const row = page.getByRole('row').filter({ hasText: property.title });
  await expect(row).toBeVisible();
  const completed = page.waitForResponse(r => r.url() === `${api}/visits/${visit.id}` && r.request().method() === 'PUT');
  await row.getByRole('combobox').selectOption('COMPLETED');
  await successful(completed);
  await page.reload();
  await expect(page.getByRole('row').filter({ hasText: property.title }).getByRole('combobox')).toHaveValue('COMPLETED');
}

async function closeSale(page: Page, entry: string, property: PropertyFixture, buyerId: string, agent: Account) {
  if (entry === 'properties') {
    await page.goto('/properties');
    await page.getByRole('row').filter({ hasText: property.title }).getByTitle('Registrar Venta').click();
  } else if (entry === 'kanban') {
    await page.goto('/kanban');
    await page.locator('[draggable="true"]').filter({ hasText: property.title }).getByRole('button', { name: 'Registrar venta' }).click();
  } else {
    await page.goto('/sales');
    await page.getByRole('button', { name: 'Registrar venta', exact: true }).click();
    await page.getByRole('dialog', { name: 'Selecciona la propiedad' }).getByRole('button', { name: property.title, exact: true }).click();
  }
  const dialog = page.getByRole('dialog', { name: 'Registrar venta', exact: true });
  await expect(dialog.getByRole('button', { name: 'Confirmar venta' })).toBeDisabled();
  await dialog.getByLabel('Comprador *', { exact: true }).selectOption(buyerId);
  await dialog.getByLabel('Agente de la venta *', { exact: true }).selectOption(agent.id);
  await dialog.getByLabel('Precio final (€) *', { exact: true }).fill('200000');
  await dialog.getByLabel('Comisión sobre la venta (%) *', { exact: true }).fill('3');
  await dialog.getByLabel('Parte del agente (%) *', { exact: true }).fill('40');
  const sold = page.waitForResponse(r => r.url() === `${api}/properties/${property.id}/sell` && r.request().method() === 'POST');
  await dialog.getByRole('button', { name: 'Confirmar venta', exact: true }).click();
  const body = await successful(sold);
  expect(body).toMatchObject({ total_commission: 6000, agent_commission: 2400, agency_commission: 3600, replayed: false });
  await expect(dialog).toBeHidden();
  await page.goto('/sales');
  await expect(page.getByRole('row').filter({ hasText: property.title })).toBeVisible();
  // These are reads through the same real session, never mocked API responses.
  const detailResponse = await page.request.get(`${api}/sales/${body.sale_id}`);
  expect(detailResponse.ok()).toBeTruthy();
  const detail = await detailResponse.json();
  expect(detail.sale).toMatchObject({ property_id: property.id, buyer_id: buyerId, agent_id: agent.id, is_active: true });
  expect(detail.commissions).toHaveLength(1);
  expect(Number(detail.commissions[0].amount)).toBe(2400);
  const properties = await page.request.get(`${api}/properties/${property.id}`);
  expect((await properties.json()).status_key).toBe('VENDIDA');
  const sales = await page.request.get(`${api}/properties/sales/list`);
  expect((await sales.json()).items.filter((sale: { property_id: string }) => sale.property_id === property.id)).toHaveLength(1);
  return body.sale_id as string;
}

test('anonymous access and invalid credentials do not open the application', async ({ page }) => {
  const preflight = await page.request.fetch(`${api}/auth/login`, {
    method: 'OPTIONS', headers: {
      Origin: process.env.E2E_BASE_URL!,
      'Access-Control-Request-Method': 'POST',
      'Access-Control-Request-Headers': 'content-type',
    },
  });
  expect(preflight.status()).toBe(200);
  expect(preflight.headers()['access-control-allow-origin']).toBe(process.env.E2E_BASE_URL);
  await page.goto('/properties');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Correo electrónico').fill(seed.accounts.manager.email);
  await page.getByLabel('Contraseña', { exact: true }).fill('incorrect-password');
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await expect(page.getByText('Invalid credentials', { exact: true })).toBeVisible();
  expect((await page.request.get(`${api}/properties`)).status()).toBe(401);
});

for (const entry of ['properties', 'kanban', 'sales']) {
  test(`manager completes opportunity, visit, sale and commission from ${entry}`, async ({ page }) => {
    const manager = seed.accounts.manager;
    await login(page, manager);
    const title = `Vivienda recorrido ${entry}`;
    const property = { id: await createProperty(page, title, manager), title };
    const buyer = await createBuyer(page, entry, manager);
    await completeVisit(page, property, buyer, manager);
    const saleId = await closeSale(page, entry, property, buyer.id, manager);
    await page.goto('/commissions');
    await expect(page.getByRole('heading', { name: /Comisiones/ })).toBeVisible();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    const pendingResponse = await page.request.get(`${api}/commissions/pending`);
    expect(pendingResponse.ok()).toBeTruthy();
    const pending = await pendingResponse.json();
    const entries = pending.flatMap((group: { commissions: { sale_id: string; amount: number }[] }) => group.commissions);
    expect(entries.find((payment: { sale_id: string }) => payment.sale_id === saleId)?.amount).toBe(2400);

    if (entry === 'properties') {
      await test.step('correction and reopening adjust the commission and retain history', async () => {
        await page.goto('/sales');
        await page.getByRole('row').filter({ hasText: title }).getByRole('button', { name: 'Ver / gestionar' }).click();
        await page.getByRole('button', { name: 'Corregir venta', exact: true }).click();
        await page.getByLabel('Precio final (€) *', { exact: true }).fill('150000');
        await page.getByLabel('Motivo de la corrección *', { exact: true }).fill('Precio final rectificado en prueba');
        const corrected = page.waitForResponse(r => r.url() === `${api}/sales/${saleId}/correct` && r.request().method() === 'POST');
        await page.getByRole('button', { name: 'Guardar corrección', exact: true }).click();
        await successful(corrected);
        await expect(page.getByText('Precio final rectificado en prueba', { exact: true })).toBeVisible();
        const correctedDetail = await (await page.request.get(`${api}/sales/${saleId}`)).json();
        expect(correctedDetail.commissions.reduce((sum: number, cp: { amount: number }) => sum + Number(cp.amount), 0)).toBe(1800);
        await page.getByRole('button', { name: 'Reabrir venta', exact: true }).click();
        await page.getByLabel('Motivo de la reapertura', { exact: true }).fill('Operación reabierta en prueba');
        const reopened = page.waitForResponse(r => r.url() === `${api}/sales/${saleId}/reopen` && r.request().method() === 'POST');
        await page.getByRole('button', { name: 'Confirmar reapertura', exact: true }).click();
        await successful(reopened);
        await expect(page.getByText(/Venta reabierta · sin efecto/)).toBeVisible();
        const reopenedDetail = await (await page.request.get(`${api}/sales/${saleId}`)).json();
        expect(reopenedDetail.sale.is_active).toBe(false);
        expect(reopenedDetail.events).toHaveLength(3);
        expect(reopenedDetail.commissions.reduce((sum: number, cp: { amount: number }) => sum + Number(cp.amount), 0)).toBe(0);
        await page.getByRole('button', { name: 'Cerrar', exact: true }).click();
      });
    }
    await page.getByRole('button', { name: 'Menú de usuario' }).click();
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto('/sales');
    await expect(page).toHaveURL(/\/login$/);
    expect((await page.request.get(`${api}/properties`)).status()).toBe(401);
  });
}

test('assigned agent completes a sale while other agencies and management pages stay inaccessible', async ({ page }) => {
  const agent = seed.accounts.agent;
  await login(page, agent);
  await page.goto('/properties');
  await expect(page.getByText(seed.properties.assigned.title, { exact: true })).toBeVisible();
  await expect(page.getByText(seed.properties.foreign.title, { exact: true })).toHaveCount(0);
  expect((await page.request.get(`${api}/properties/${seed.properties.foreign.id}`)).status()).toBe(404);
  await page.goto('/commissions');
  await expect(page).toHaveURL(/\/unauthorized$/);
  const buyer = await createBuyer(page, 'Agente');
  await completeVisit(page, seed.properties.assigned, buyer);
  await closeSale(page, 'sales', seed.properties.assigned, buyer.id, agent);
});
