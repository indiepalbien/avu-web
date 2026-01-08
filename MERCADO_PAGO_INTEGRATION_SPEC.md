# Especificación: Integración de Mercado Pago - Suscripciones

**Estado:** Especificación / Fase de Diseño  
**Fecha:** 8 de Enero, 2026  
**Requisitos:** Python 3.x, Django 5.x, Redis, Celery, Mercado Pago API

---

## 📋 Resumen Ejecutivo

Implementar un sistema de suscripciones mensuales/anuales usando **Mercado Pago** como procesador de pagos. Los usuarios de tipo "Socio" deben pagar para registrarse (o usar cupones). Las empresas no pagan.

**Decisión Arquitectónica:** Usar **SDK de Mercado Pago directamente** (no django-payments) porque django-payments no soporta suscripciones recurrentes.

---

## 🎯 Requisitos Funcionales

### 1. Flujo de Registro con Pago

1. **Usuario se registra como "Socio"** → Completa paso 4 del signup
2. **Se le ofrece dos opciones:**
   - Opción A: **Aplicar cupón** (generado manualmente, 1 uso, válido por X tiempo)
   - Opción B: **Pagar con Mercado Pago** (crea suscripción recurrente mensual/anual)
3. **Validación:**
   - Si aplica cupón válido → Perfil habilitado inmediatamente
   - Si paga en MP → Redirige a MP para crear suscripción
   - Si no aplica cupón ni paga → Perfil queda deshabilitado hasta que haga uno de los dos

### 2. Usuarios Tipo "Empresa"

- **NO requieren pago** → Se registran normalmente sin suscripción

### 3. Gestión de Suscripciones

**Estados posibles:**
- `pending` → Aguardando primer pago
- `active` → Suscripción activa, perfil habilitado
- `paused` → Pago rechazado (MP reintentar automáticamente)
- `cancelled` → Usuario canceló o MP canceló por exceso de fallos
- `failed` → Demasiados pagos rechazados consecutivos

**Acciones sobre suscripción:**
- **Crear:** Al pagar en MP (MP maneja renovación automática)
- **Detectar cambios:** Vía webhooks de MP
- **Cancelar:** Desde admin (nosotros) o automático (MP si excede 4 fallos)
- **Sincronizar:** Celery task diaria para reconciliación

### 4. Gestión de Cupones

- **Generación:** Manual vía Django admin
- **Formato:** String aleatorio largo (ej: `DXGAKJNASD1234567890`)
- **Validez:** Fecha de expiración (ej: 3 meses)
- **Uso:** 1 sola vez, código único
- **Aplicación:** Durante registro o después (en perfil)

### 5. Permisos y Perfil

**Perfil habilitado cuando:**
- ✅ Usuario es "Empresa" (sin pago)
- ✅ Usuario tiene cupón válido activo
- ✅ Usuario tiene suscripción activa en MP

**Perfil deshabilitado cuando:**
- ❌ Usuario es "Socio" SIN cupón ni suscripción
- ❌ Suscripción expiró, fue cancelada o falló

---

## 🏗️ Arquitectura Técnica

### Base de Datos: Modelos Nuevos

```
Subscription
├── user (FK)
├── mercado_pago_subscription_id (unique)
├── preapproval_id (MP internal ID)
├── status (pending/active/paused/cancelled/failed)
├── payment_frequency (monthly/yearly)
├── amount (Decimal)
├── last_payment_date
├── next_payment_date
├── failed_payment_count
├── last_synced_at
├── created_at
└── updated_at

CouponCode
├── code (unique)
├── created_by (FK User)
├── user (FK User nullable - null si aún no se usó)
├── is_used (boolean)
├── used_at
├── expires_at
├── created_at
└── months_of_validity

SubscriptionEvent (audit log)
├── subscription (FK)
├── event_type (string, ej: "subscription_updated")
├── mercado_pago_event_id (unique - para deduplicar)
├── payload (JSON - el evento completo de MP)
├── processed (boolean)
├── created_at
└── processed_at
```

### Sincronización: Webhooks + Polling

**Webhooks (Tiempo Real)**
- MP → Endpoint Django: `POST /webhooks/mercado-pago/`
- Eventos a escuchar:
  - `subscription_created`
  - `subscription_updated` (para detectar cancelación)
  - `payment.created` (pago iniciado)
  - `payment.updated` (pago completado/rechazado)
- Validación: Verificar firma HMAC de MP
- Respuesta: Quedar en < 1 segundo, procesar async vía Celery

**Polling (Red de Seguridad)**
- Celery task: `sync_subscriptions_reconciliation`
- Frecuencia: Diaria (2 AM)
- Lógica: Consultar suscripciones activas/pendientes en MP
- Objetivo: Detectar webhooks perdidos

### Flujo de Pago: Checkout Pro o Checkout Bricks

**Usuario hace clic en "Pagar con MP":**

1. Backend crea `Subscription` con estado `pending`
2. Backend genera preferencia de pago en MP (para suscripción recurrente)
3. Redirige usuario a MP (sin guardar tarjeta localmente)
4. Usuario paga en MP
5. MP crea suscripción con `preapproval_id` y envía webhook
6. Webhook → Actualiza nuestro `Subscription` a `active`
7. Usuario redirigido a `/profile/` con perfil habilitado

**Renovaciones automáticas:** MP maneja, nosotros sincronizamos vía webhook

### API Mercado Pago a Usar

| Acción | Endpoint | Método |
|--------|----------|--------|
| Crear preferencia de pago | `POST /checkout/preferences` | - |
| Obtener estado suscripción | `GET /v1/subscriptions/{id}` | API |
| Cancelar suscripción | `PUT /v1/subscriptions/{id}` | API |
| Listar pagos de suscripción | `GET /v1/subscriptions/{id}/payments` | API |
| Webhook validation | SHA256 HMAC | Signature check |

---

## 📁 Estructura de Carpetas Propuesta

```
avuweb/
├── main/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── static_page.py
│   │   ├── user_profile.py
│   │   ├── subscription.py          [NEW]
│   │   └── coupon_code.py           [NEW]
│   │
│   ├── views/
│   │   ├── __init__.py
│   │   ├── home.py
│   │   ├── profile.py
│   │   ├── signup.py
│   │   ├── static_page.py
│   │   └── webhooks.py              [NEW]
│   │
│   ├── management/
│   │   └── commands/
│   │       ├── create_test_users.py
│   │       └── sync_mercado_pago.py [NEW]
│   │
│   ├── tasks.py                     [NEW] - Celery tasks
│   ├── services.py                  [NEW] - MP SDK wrapper
│   ├── forms.py                     [UPDATED] - Coupon form
│   ├── urls.py                      [UPDATED] - Webhook endpoint
│   │
│   ├── templates/main/
│   │   ├── signup/
│   │   │   ├── step4.html           [UPDATED] - Add coupon/payment options
│   │   │   └── payment_success.html [NEW]
│   │   │
│   │   ├── profile.html             [UPDATED] - Show subscription status
│   │   │
│   │   └── includes/
│   │       ├── subscription_status.html [NEW]
│   │       └── coupon_form.html     [NEW]
│   │
│   ├── migrations/
│   │   └── 000X_add_subscription_models.py [NEW]
│   │
│   └── admin.py                     [UPDATED] - Admin para Coupons y Subscriptions
│
└── (project root)
    └── docker-compose.yml           [OPTIONAL] - Para Redis + Celery en desarrollo
```

---

## 🔄 Flujos Detallados

### Flujo 1: Registro de Socio con Pago en MP

```
Usuario rellena step4 → Envía form
    ↓
Vista signup valida usuario
    ↓
Crea UserProfile con tipo "socio" + status "disabled"
    ↓
Muestra opciones: [Aplicar cupón] [Pagar con MP]
    ↓
Usuario elige [Pagar con MP]
    ↓
Backend:
  - Crea Subscription(status='pending')
  - Llama SDK MP: crear preferencia de pago (recurrente)
  - Redirige a MP link
    ↓
Usuario paga en MP (tarjeta no se guarda localmente)
    ↓
MP procesa pago + crea suscripción automática
    ↓
MP envía webhook: 'subscription_created' + 'payment.approved'
    ↓
Webhook handler:
  - Valida firma HMAC
  - Crea SubscriptionEvent (idempotencia)
  - Envia Celery task: procesar_webhook
    ↓
Celery task:
  - Actualiza Subscription(status='active')
  - Actualiza UserProfile(subscription_status='active')
  - Event.processed = True
    ↓
Usuario redirigido a /profile/ → Perfil HABILITADO ✅
```

### Flujo 2: Registro de Socio con Cupón

```
Usuario rellena step4
    ↓
Muestra opciones: [Aplicar cupón] [Pagar con MP]
    ↓
Usuario elige [Aplicar cupón] + ingresa código
    ↓
Backend valida:
  - Cupón existe
  - Cupón no expirado
  - Cupón no usado
    ↓
Si válido:
  - Marca CouponCode(is_used=True, user=user)
  - Crea Subscription(status='active', tipo='coupon')
  - Perfil habilitado
    ↓
Si inválido:
  - Muestra error
  - Perfil sigue deshabilitado
```

### Flujo 3: Usuario Cancela Suscripción en MP

```
Usuario cancela suscripción en MP (su panel)
    ↓
MP envía webhook: 'subscription_updated' (status=cancelled)
    ↓
Webhook handler procesa
    ↓
Celery task:
  - Actualiza Subscription(status='cancelled')
  - Actualiza UserProfile (perfil deshabilitado)
  - Log: cancellation timestamp
```

### Flujo 4: Pago Fallido (Reintentos MP)

```
Ciclo de renovación → MP intenta cobro
    ↓
Tarjeta rechazada (fondos insuficientes, etc)
    ↓
MP envía webhook: 'payment.updated' (status=rejected)
    ↓
Celery task:
  - Incrementa Subscription.failed_payment_count
  - Si failed_payment_count < 4:
      → Subscription(status='paused')
      → MP reintentará automáticamente
  - Si failed_payment_count >= 4:
      → Subscription(status='failed')
      → Perfil deshabilitado
      → Log: Too many failed payments
```

### Flujo 5: Sincronización Diaria (Reconciliación)

```
Celery beat schedule: Cada día 2 AM
    ↓
Task: sync_subscriptions_reconciliation
    ↓
Consulta todas las Subscription(status='active')
    ↓
Para cada una:
  - Llamar API MP: GET /subscriptions/{id}
  - Comparar estado local vs MP
  - Si diferencia:
      → Log warning
      → Actualizar local al estado de MP
      → Procesar cambios (ej: si fue cancelada, deshabilitar perfil)
    ↓
Finaliza
```

---

## 🔐 Seguridad

### Validación de Webhooks

```python
# MP envía: X-Signature: ts=<timestamp>,v1=<hmac_sha256>
# Nosotros verificamos:
signature_string = f"{request_id}.{timestamp}.{body}"
expected_hash = SHA256(signature_string, secret=WEBHOOK_SECRET)
# Validar que incoming v1 == expected_hash (timing-safe comparison)
```

### Protección CSRF

- Endpoints de webhook: `@csrf_exempt` (MP no puede enviar CSRF token)
- Forms normales: Django CSRF estándar + HTMX headers

### No Guardar Datos Sensibles

- ❌ NO guardamos tarjetas
- ❌ NO guardamos números de tarjeta
- ✅ MP gestiona todo → nosotros solo guardamos IDs y estado

---

## 🗂️ Requisitos de Configuración

### Variables de Entorno

```bash
# .env
MERCADO_PAGO_ACCESS_TOKEN=APP_USR_xxxxxxxxxxxxxx
MERCADO_PAGO_WEBHOOK_SECRET=webhook_secret_xxxxxx
MERCADO_PAGO_SANDBOX=True  # False en producción

# Redis (para Celery)
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Dependencias Python a Agregar

```
mercadopago>=3.0.0  # SDK oficial de Mercado Pago
celery>=5.3.0       # (ya debería estar)
redis>=5.0.0        # (ya debería estar)
```

### Configuración Django

```python
# settings.py
INSTALLED_APPS += ['main']  # ya lo está

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')
CELERY_BEAT_SCHEDULE = {
    'sync-subscriptions-daily': {
        'task': 'main.tasks.sync_subscriptions_reconciliation',
        'schedule': crontab(hour=2, minute=0),
    },
}

# Mercado Pago
MERCADO_PAGO_ACCESS_TOKEN = os.getenv('MERCADO_PAGO_ACCESS_TOKEN')
MERCADO_PAGO_WEBHOOK_SECRET = os.getenv('MERCADO_PAGO_WEBHOOK_SECRET')
MERCADO_PAGO_SANDBOX = os.getenv('MERCADO_PAGO_SANDBOX', 'True') == 'True'
```

---

## 📊 Admin Django Necesario

**CouponCode Admin:**
- Listar, crear, editar coupons
- Filtrar por: is_used, expires_at, created_by
- Acciones: generar lote de coupons, marcar como expirado
- Mostrar: usuario que utilizó, fecha de uso

**Subscription Admin:**
- Listar suscripciones
- Filtrar por: status, user, last_synced_at
- Acciones: forzar sincronización, cancelar manualmente
- Mostrar: MP subscription ID, próximo pago, count de fallos
- Read-only: mercado_pago_updated_at, created_at

---

## 🧪 Testing / Sandbox

- MP proporciona ambiente de prueba (Sandbox)
- Tarjetas de prueba: https://www.mercadopago.com/developers/es/docs/checkout-api/additional-content/testing
- Credenciales: Usar `APP_USR_...` de cuenta sandbox de MP
- Configuración: `MERCADO_PAGO_SANDBOX=True` en `.env`

---

## 📈 Monitoreo y Logging

```python
# Loguear:
- Creación de preferencia de pago
- Webhooks recibidos (con payload)
- Cambios de estado de suscripción
- Pagos rechazados y count de reintentos
- Errores de API de MP
- Discrepancias en reconciliación
```

---

## ⚠️ Edge Cases y Consideraciones

| Caso | Manejo |
|------|--------|
| Usuario aplica cupón pero luego quiere pagar | Permitir (puede tener ambos) |
| Suscripción se cancela en MP pero webhook no llega | Detectado por reconciliación diaria |
| MP rechaza pago 4+ veces seguidas | Cambiar a `failed`, deshabilitar perfil |
| Usuario intenta usar mismo cupón 2 veces | Rechazar (is_used check) |
| Cupón expira mientras usuario lo aplica | Validar antes de guardar |
| Webhook duplicado | Deduplicar por mercado_pago_event_id |

---

## 📋 Plan de Implementación (Fases)

### Fase 1: Modelos + Admin (1-2 días)
- ✅ Crear modelos: Subscription, CouponCode, SubscriptionEvent
- ✅ Crear migrations
- ✅ Admin interface completa
- ✅ Tests unitarios básicos

### Fase 2: SDK + Servicio de MP (1-2 días)
- ✅ Wrapper del SDK de MP (MercadoPagoService)
- ✅ Crear preferencia de pago
- ✅ Consultar estado de suscripción
- ✅ Manejo de errores

### Fase 3: Webhooks + Celery (1-2 días)
- ✅ Endpoint `/webhooks/mercado-pago/`
- ✅ Validación de firma HMAC
- ✅ Celery task: procesar evento
- ✅ Sincronización diaria (reconciliación)

### Fase 4: Integramos Signup (1 día)
- ✅ Modificar step 4 del signup
- ✅ Mostrar opciones: cupón vs pago
- ✅ Validar y procesar cupones
- ✅ Redirigir a MP si elige pagar
- ✅ Callback después de pago exitoso

### Fase 5: Perfil + Frontend (1 día)
- ✅ Mostrar estado de suscripción en perfil
- ✅ Permitir cancelar suscripción (desde perfil)
- ✅ Deshabilitar perfil si se vence/cancela

### Fase 6: Testing + Documentación (1-2 días)
- ✅ Tests de integración con sandbox de MP
- ✅ Documentación de API interna
- ✅ Guía de troubleshooting

---

## ✅ Siguientes Pasos

1. **Obtener credenciales de MP:** Access token + webhook secret de sandbox
2. **Revisar esta especificación** con el equipo
3. **Aprobar design** (modelos, flujos, seguridad)
4. **Iniciar Fase 1** cuando esté listo

---

## 📚 Referencias

- [Mercado Pago Suscripciones API](https://www.mercadopago.com.uy/developers/es/docs/subscriptions/landing)
- [Django Celery Beat](https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html)
- [Best Practices Webhooks](https://www.mercadopago.com/developers/es/docs/webhooks/v1)
