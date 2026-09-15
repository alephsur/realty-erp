# Realty ERP

Sistema de gestión inmobiliaria multi-tenant. Permite a múltiples agencias operar de forma aislada sobre una misma instalación, con control total desde un panel de superadministrador.

## Tecnologías

| Capa | Stack |
|------|-------|
| Backend | FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS 4 |
| Infraestructura | Docker Compose |
| Autenticación | JWT en cookie httpOnly + token CSRF |

---

## Arquitectura multi-tenant

Cada **tenant** representa una agencia inmobiliaria independiente. El aislamiento de datos se aplica en dos niveles:

1. **Middleware HTTP** — extrae el `tenant_id` del JWT en cada petición y lo inyecta en el contexto de la aplicación.
2. **Sesión de base de datos** — al abrir cada sesión se ejecuta `SET LOCAL app.current_tenant = '<uuid>'`, lo que permite configurar políticas RLS (Row-Level Security) en PostgreSQL si se desea reforzar el aislamiento a nivel de motor.

Todas las tablas de negocio incluyen una columna `tenant_id` con `CASCADE` en borrado, por lo que eliminar un tenant elimina todos sus datos.

---

## Módulos

### Autenticación y usuarios (`/auth`)

Gestiona el ciclo de vida completo de acceso:

- **Login / Logout** — emite una cookie httpOnly con el JWT y una segunda cookie legible por JS con el token CSRF (doble submit cookie pattern). El endpoint de login está limitado a **5 peticiones por minuto** por IP.
- **Cambio de contraseña** — obligatorio para cuentas marcadas `must_change_password = true`.
- **Invitación de usuarios** — genera un enlace con token de un solo uso que permite al nuevo empleado establecer su contraseña.
- **Registro de empresa** (`POST /auth/register-company`) — crea tenant + usuario ADMIN en una sola operación.

#### Roles

| Rol | Permisos |
|-----|----------|
| `SUPER_ADMIN` | Gestión global de tenants y usuarios de cualquier organización |
| `ADMIN` | Gestión completa de su agencia (empleados, configuración) |
| `MANAGER` | Gestión de agentes y acceso a todos los datos de la agencia |
| `AGENT` | Acceso a sus propios clientes y propiedades asignadas |

---

### Propiedades (`/properties`)

CRUD de inmuebles con ciclo de vida completo:

```
CAPTADA → PUBLICADA → EN_VISITAS → RESERVADA → PENDIENTE_NOTARIA → VENDIDA
                                                                  ↘ RETIRADA
```

Tipos soportados: Piso, Casa, Chalet, Ático, Local, Oficina, Terreno, Garaje, Trastero.

Cada propiedad almacena:
- Datos del inmueble (superficie, habitaciones, baños, dirección)
- Datos del propietario (nombre, teléfono, email)
- Tasas de comisión (general de agencia y override por agente)
- Referencia interna (`INM-2024-001`)

La vista Kanban (`/kanban`) permite arrastrar propiedades entre columnas de estado.

---

### CRM de clientes (`/clients`)

Dos tipos de cliente:

- **Propietario** — propietario del inmueble captado.
- **Demandante** — comprador potencial con preferencias de búsqueda (presupuesto mínimo/máximo, zonas deseadas, tipo de inmueble).

#### Motor de matching

El módulo `core/matching.py` cruza automáticamente demandantes con propiedades activas y viceversa:

- Descarta propiedades que superen el presupuesto máximo del comprador.
- Puntúa coincidencias por presupuesto (+3/+1), tipo de inmueble (+2) y zona geográfica (+2).
- Devuelve resultados ordenados por puntuación con las razones de cada match.

Los intereses de un demandante sobre propiedades concretas se registran en `ClientPropertyInterest` con nivel de interés (low / medium / high).

---

### Visitas (`/visits`)

Registro de visitas a inmuebles. Vinculadas a una propiedad y opcionalmente a un cliente y agente.

---

### Calendario y citas (`/calendar`)

Agenda de la agencia con citas de cuatro tipos: visita, llamada, reunión y otro. Cada cita tiene agente asignado, fecha/hora inicio y fin, y soporte de eventos de día completo. La vista usa **FullCalendar**.

---

### Ventas (`/sales`)

Registro de transacciones cerradas. Calcula y almacena automáticamente:
- `total_commission` — importe total de comisión.
- `agent_commission` — parte correspondiente al agente.
- `agency_commission` — parte correspondiente a la agencia.

El cierre utiliza un formulario común desde Propiedades, el tablero y Ventas.
Exige comprador, precio final, agente y porcentajes de comisión; admite al agente
asignado y a los responsables de la agencia, con protección frente a reintentos.
Las reglas, migración y comprobaciones están en [F0-02 — Cierre único](docs/F0-02.md).

Correcciones, reaperturas y ajustes de comisión: [F0-03](docs/F0-03.md).

---

### Comisiones (`/commissions`)

Seguimiento del cobro de comisiones por venta. Estados: `PENDING → INVOICED → PAID`. Permite registrar número de factura, fecha de pago y notas.

---

### Reportes (`/reports`)

Informes consolidados de actividad: ventas por período, comisiones generadas, rendimiento por agente, y embudo de propiedades por estado.

---

### Notificaciones (`/notifications`)

Sistema interno de notificaciones en tiempo real para eventos relevantes (nuevos matches, cambios de estado de propiedades, etc.).

---

## Seguridad

El backend aplica las siguientes cabeceras de seguridad en todas las respuestas:

| Cabecera | Valor |
|----------|-------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Deshabilita geolocalización, micrófono, cámara y pagos |
| `Content-Security-Policy` | Configurable vía `CSP_POLICY` |

---

## Instalación de desarrollo reproducible (F0-01)

Las dependencias se instalan desde los archivos versionados `backend/uv.lock` y
`frontend/package-lock.json`. Usa `uv sync --locked` y `npm ci`; no es necesario
regenerar estos archivos para arrancar el proyecto.

### Requisitos

- Docker y Docker Compose v2 o posterior.
- Para ejecutar fuera de Docker: **Python 3.12**, **uv 0.11.6** y **Node.js 24** con npm.
- `backend/.python-version` y `frontend/.nvmrc` seleccionan las versiones de Python
  y Node. `uv` puede descargar Python 3.12 si no está instalado.

Los Dockerfiles y Compose están orientados a desarrollo: montan el código local
para recarga automática. Las dependencias del backend viven en `/opt/venv` dentro
del contenedor y no se mezclan con el entorno local `backend/.venv`.

### 1. Configurar el backend

Desde la raíz del repositorio, copia la plantilla **si aún no tienes `.env`**:

```bash
cp -n backend/.env.example backend/.env
```

Genera una clave y guárdala como `SECRET_KEY` en `backend/.env`:

```bash
# Con Python local:
python3 -c 'import secrets; print(secrets.token_hex(32))'
# Alternativa si solo tienes Docker:
docker run --rm python:3.12-slim python -c 'import secrets; print(secrets.token_hex(32))'
```

La plantilla configura cookies para HTTP local y esta conexión:

```env
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:55432/realty_erp
COOKIE_SECURE=False
COOKIE_SAMESITE=lax
CORS_ORIGINS=http://localhost:5173
FRONTEND_URL=http://localhost:5173
```

El backend y Alembic leen el mismo `.env` al ejecutarse desde `backend/`.
Las variables del proceso tienen prioridad. En Docker, Compose carga el archivo
y sustituye `DATABASE_URL` por la conexión interna `db:5432`.

Para crear un superadministrador al arrancar, añade opcionalmente:

```env
BOOTSTRAP_SUPERADMIN_EMAIL=admin@tudominio.com
```

### 2. Arrancar con Docker Compose

Desde la raíz, ejecuta en este orden:

```bash
docker compose config --quiet
docker compose up -d db
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose up -d backend frontend
```

Compose espera a que PostgreSQL esté disponible antes de iniciar el backend.
Las migraciones se aplican **antes del primer arranque de la aplicación**, para que
el bootstrap del superadministrador encuentre las tablas. Ejecuta de nuevo
`docker compose run --rm backend alembic upgrade head` al incorporar migraciones;
si ya está actualizado, no vuelve a aplicarlas.

| Servicio | Dirección local |
|----------|-----------------|
| Aplicación | `http://localhost:5173` |
| API y documentación | `http://localhost:8000/docs` |
| Estado de la API | `http://localhost:8000/health` |
| PostgreSQL | `localhost:55432` (solo acceso local) |

Comprobación básica:

```bash
curl --fail http://localhost:8000/health
docker compose run --rm backend alembic current
```

El estado debe devolver `{"status":"ok"}` y Alembic debe indicar `(head)`.
El estado HTTP comprueba que responde la API; la ejecución de migraciones comprueba
la conexión y preparación de la base de datos.

Si activaste el bootstrap, consulta `docker compose logs backend` para obtener la
contraseña temporal y cámbiala al iniciar sesión. Después elimina
`BOOTSTRAP_SUPERADMIN_EMAIL` de `.env` y ejecuta `docker compose up -d backend` para
recrear el servicio con la configuración actualizada.

Los puertos pueden ajustarse mediante `POSTGRES_PORT`, `BACKEND_PORT` y
`FRONTEND_PORT` al invocar Compose. Si cambias el puerto del frontend, actualiza
también `CORS_ORIGINS` y `FRONTEND_URL` en `backend/.env`; para un backend local,
ajusta `DATABASE_URL` si cambias el puerto de PostgreSQL.

### 3. Alternativa: backend y frontend locales

Utiliza la misma configuración del paso 1. Puedes arrancar únicamente PostgreSQL
con `docker compose up -d db`, que publica el puerto local 55432.

Backend, desde una terminal:

```bash
cd backend
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --reload --port 8000
```

Si `.venv` procede de otro equipo o contenedor y su Python ya no existe, consérvalo
con otro nombre y reconstruye el entorno. No copies entornos virtuales:

```bash
cd backend
mv .venv .venv.backup-$(date +%Y%m%d-%H%M%S)
uv sync --locked
```

Frontend, desde otra terminal:

```bash
cd frontend
nvm use  # si utilizas nvm; en otro caso, usa Node.js 24
npm ci
npm run dev
```

La API por defecto es `http://localhost:8000`. Solo si necesitas otra dirección,
crea `frontend/.env.local` con `VITE_API_URL` y reinicia el frontend.

### Verificación de la instalación

```bash
# Desde frontend/:
npm ci
npm run build

# Desde backend/:
uv sync --locked
uv run --locked pytest
uv run --locked alembic upgrade head
uv run --locked alembic current
```

Las pruebas de F0-01 verifican la carga de `.env`, la prioridad de las variables del
proceso y el arranque de la API y su esquema OpenAPI. Se ejecutan con configuración
temporal y no acceden a la base de datos del desarrollador. Las pruebas completas
del flujo comercial corresponden a F0-06.

Las pruebas de cierre de F0-02 se ejecutan con
`RUN_POSTGRES_TESTS=1 uv run --locked pytest` desde `backend/`; crean y eliminan su
propio contenedor PostgreSQL. Sin esa variable se omiten las pruebas que requieren
PostgreSQL. El frontend incorpora `npm test` para los cálculos y el formulario.

Para verificar las migraciones desde cero sin utilizar los datos habituales,
arranca un proyecto Compose independiente, desde la raíz:

```bash
export COMPOSE_PROJECT_NAME=realty-install-check
export POSTGRES_PORT=55433
export BACKEND_PORT=18000
export FRONTEND_PORT=15173
docker compose up -d db
docker compose build backend
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic current
docker compose run --rm backend alembic upgrade head
docker compose down --volumes
unset COMPOSE_PROJECT_NAME POSTGRES_PORT BACKEND_PORT FRONTEND_PORT
```

Esta comprobación usa un volumen propio. El último comando de Compose borra
únicamente los datos desechables de `realty-install-check`; utiliza ese nombre
solo para pruebas. No ejecutes `down --volumes` sobre un proyecto con datos que
quieras conservar.

---

## Variables de entorno de referencia

| Variable | Requerida | Valor por defecto | Descripción |
|----------|-----------|-------------------|-------------|
| `SECRET_KEY` | **Sí** | — | Clave para firmar JWT. Mínimo 32 caracteres. |
| `DATABASE_URL` | **Sí** | `postgresql://postgres:postgrespassword@localhost:5432/realty_erp` | Cadena de conexión PostgreSQL |
| `BOOTSTRAP_SUPERADMIN_EMAIL` | No | — | Email para crear el superadmin en el primer arranque |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Orígenes CORS permitidos, separados por coma |
| `COOKIE_SECURE` | No | `True` | `False` en desarrollo HTTP, `True` en producción HTTPS |
| `COOKIE_SAMESITE` | No | `strict` | `lax` en desarrollo, `strict` en producción |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `10080` (7 días) | Duración del token JWT |
| `CSP_POLICY` | No | Política restrictiva | Valor completo de la cabecera `Content-Security-Policy` |
| `VITE_API_URL` | No (frontend) | `http://localhost:8000` | URL base del backend para el cliente Axios |

---

## Creación de tenants (agencias)

Existen dos formas de crear un nuevo tenant:

### Opción A — Auto-registro (sin superadmin)

Cualquier usuario puede registrar su propia agencia enviando una petición al endpoint público:

```http
POST /auth/register-company
Content-Type: application/json

{
  "company_name": "Inmobiliaria Ejemplo S.L.",
  "admin_email": "admin@ejemplo.com",
  "admin_password": "ContraseñaSegura123",
  "admin_full_name": "María García",
  "plan": "basic"
}
```

Esto crea el tenant y su usuario ADMIN en una sola operación. El admin puede iniciar sesión de inmediato.

### Opción B — Creación por superadmin

El superadmin puede crear tenants desde el panel de administración (`/admin/tenants` en la SPA) o vía API:

```http
POST /auth/admin/tenants
Authorization: (cookie de sesión de superadmin)
X-CSRF-Token: (token CSRF)
Content-Type: application/json

{
  "name": "Inmobiliaria Norte",
  "plan": "premium"
}
```

Después, para añadir el primer admin del nuevo tenant:

```http
POST /auth/admin/users/invite
Content-Type: application/json

{
  "tenant_id": "<uuid-del-tenant>",
  "email": "admin@norte.com",
  "full_name": "Carlos López",
  "role": "ADMIN"
}
```

La respuesta incluye un `invite_link`. El usuario accede a ese enlace, establece su contraseña y queda activado.

---

## Gestión de empleados dentro de un tenant

Una vez autenticado como ADMIN o MANAGER:

### Crear empleado

```http
POST /auth/tenant/users
Content-Type: application/json

{
  "email": "agente@ejemplo.com",
  "full_name": "Ana Martínez",
  "role": "AGENT",
  "phone": "600123456",
  "license_number": "COL-0001",
  "commission_rate": 40.0,
  "hire_date": "2024-01-15"
}
```

El empleado se crea como inactivo. Para que pueda acceder hay que generar su enlace de invitación:

```http
POST /auth/tenant/users/{user_id}/invite
```

El enlace resultante tiene validez de un solo uso y fuerza al empleado a establecer su propia contraseña.

---

## Estructura del proyecto

```
realty-erp/
├── backend/
│   ├── app/
│   │   ├── api/            # Routers FastAPI (auth, properties, clients, visits, reports, notifications, calendar, commissions)
│   │   ├── auth/           # Generación y decodificación de JWT
│   │   ├── core/           # Configuración, middleware tenant, seguridad, CSRF, matching
│   │   ├── models/         # Modelos SQLAlchemy (auth, properties, crm, transactions, appointments, notifications, commissions)
│   │   ├── schemas/        # Esquemas Pydantic
│   │   ├── database.py     # Engine, sesión y lógica de tenant en contexto
│   │   └── main.py         # Aplicación FastAPI, middlewares y lifespan
│   ├── alembic/            # Migraciones de base de datos
│   ├── scripts/            # Script alternativo de creación de superadmin
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/            # Cliente Axios con interceptores de CSRF
│   │   ├── components/     # Layout, notificaciones, paginación, rutas protegidas
│   │   ├── hooks/          # useAuth
│   │   └── pages/          # Login, SuperAdminDashboard, AcceptInvite, y páginas de tenant
│   └── package.json
└── docker-compose.yml
```

---

## Documentación de la API

Con el backend en marcha, accede a la documentación interactiva generada automáticamente por FastAPI:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health check**: `http://localhost:8000/health`
