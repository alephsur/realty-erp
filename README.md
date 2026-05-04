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

## Despliegue con Docker Compose

### Requisitos previos

- Docker ≥ 24 y Docker Compose v2
- `git`

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd realty-erp
```

### 2. Crear el fichero de variables de entorno

Copia la plantilla y ajusta los valores:

```bash
cp backend/.env.example backend/.env   # si existe, o crear desde cero
```

Contenido mínimo del fichero `backend/.env`:

```env
# OBLIGATORIO — mínimo 32 caracteres
# Genera una clave con: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=cambia_esto_por_una_clave_segura_de_al_menos_32_caracteres

# URL de conexión a la base de datos (en Docker Compose, usa el nombre del servicio)
DATABASE_URL=postgresql://postgres:postgrespassword@db:5432/realty_erp

# Email del superadmin que se crea en el primer arranque (déjalo vacío tras el primer deploy)
BOOTSTRAP_SUPERADMIN_EMAIL=admin@tudominio.com

# Orígenes permitidos por CORS (separados por coma)
CORS_ORIGINS=http://localhost:5173

# En desarrollo local sin HTTPS, cambiar a False
COOKIE_SECURE=False
COOKIE_SAMESITE=lax
```

> **Importante:** Tras el primer arranque, elimina o deja en blanco `BOOTSTRAP_SUPERADMIN_EMAIL` para evitar que el proceso de bootstrap se ejecute en reinicios posteriores. La contraseña temporal aparece en los logs del backend.

### 3. Levantar los servicios

```bash
docker compose up --build -d
```

Servicios que se levantan:

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| `db` | — (interno) | PostgreSQL 15 |
| `backend` | `8000` | API FastAPI |
| `frontend` | `5173` | SPA React |

### 4. Aplicar las migraciones de base de datos

En el primer arranque las tablas no existen todavía. Ejecuta Alembic dentro del contenedor:

```bash
docker compose exec backend alembic upgrade head
```

### 5. Reiniciar el backend para el bootstrap del superadmin

Si configuraste `BOOTSTRAP_SUPERADMIN_EMAIL`, el superadmin se crea durante el evento `lifespan` de FastAPI. Si el contenedor arrancó antes de aplicar las migraciones, reinícialo:

```bash
docker compose restart backend
```

Busca en los logs la contraseña temporal:

```bash
docker compose logs backend | grep "SUPERADMIN CREATED"
```

La salida tendrá este formato:

```
==================================================
SUPERADMIN CREATED — CHANGE PASSWORD IMMEDIATELY
   Email:    admin@tudominio.com
   Password: <contraseña-generada>
   This account requires a password change on first login.
==================================================
```

Inicia sesión en `http://localhost:5173` con esas credenciales. El sistema te forzará a cambiar la contraseña antes de continuar.

---

## Desarrollo local sin Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .          # o: uv sync

# Variables de entorno
export SECRET_KEY="clave-local-de-desarrollo-suficientemente-larga"
export DATABASE_URL="postgresql://postgres:postgrespassword@localhost:5432/realty_erp"
export COOKIE_SECURE=False
export COOKIE_SAMESITE=lax

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
# Crea frontend/.env.local con:
# VITE_API_URL=http://localhost:8000
npm run dev
```

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
