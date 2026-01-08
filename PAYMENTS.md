# Implementación: Integración Mercado Pago - Suscripciones

**Fecha inicio:** 8 de Enero, 2026  
**Estado global:** 🟡 Planificación → Implementación

---

## 📌 Revisión y Mejoras Aplicadas

Esta es una revisión y mejora de la propuesta inicial. Los cambios principales fueron:

### ✅ Cambios Realizados

| Área | Cambio | Razón |
|------|--------|-------|
| **Modelos** | Remover `preapproval_id` redundante | MP usa solo 1 ID (subscription_id) |
| **Modelos** | Agregar `subscription_type` a Subscription | Diferenciar cupones vs pagos MP |
| **UserProfile** | Cambiar campos a `@property` | Evitar duplicación de estado |
| **CouponCode** | Agregar manager + `generate_batch()` | Generar lotes desde admin |
| **Webhook** | Agregar validación de payload | Evitar errores si MP cambia formato |
| **Celery** | Agregar transacciones atómicas | Evitar inconsistencias |
| **Admin** | Agregar actions y colores | Mejor UX y operaciones |
| **Admin** | Agregar SubscriptionEventAdmin | Debugging de webhooks |

### 🎯 Principios de Diseño Aplicados

1. **DRY (Don't Repeat Yourself):** UserProfile usa properties para evitar duplicar estado
2. **Idempotencia:** Webhooks deduplicados por evento ID
3. **Atomicidad:** Cupones validados y aplicados en transacción
4. **Seguridad:** Timing-safe HMAC, validación de payload, readonly fields
5. **Operacionalidad:** Admin mejorado, logging exhaustivo, actions útiles

---

## 📋 Resumen de Tareas

### Fase 1: Modelos + Migrations ⏳

#### Tarea 1.1: Crear modelo `Subscription`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/models/subscription.py`

**Detalles de implementación:**
```python
# avuweb/main/models/subscription.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class SubscriptionManager(models.Manager):
    """Manager personalizado para consultas comunes"""
    def active(self):
        return self.filter(status='active')
    
    def pending_renewal(self):
        return self.filter(
            status='active',
            next_payment_date__lte=timezone.now()
        )

class Subscription(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Esperando primer pago'),
        ('active', 'Activa'),
        ('paused', 'Pausada (fallo de pago)'),
        ('cancelled', 'Cancelada'),
        ('failed', 'Fallo permanente'),
    ]
    
    FREQUENCY_CHOICES = [
        ('monthly', 'Mensual'),
        ('yearly', 'Anual'),
    ]
    
    TYPE_CHOICES = [
        ('mp', 'Mercado Pago'),
        ('coupon', 'Cupón'),
    ]

    # Relaciones
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')

    # ID único de Mercado Pago (es el preapproval_id internamente)
    mercado_pago_subscription_id = models.CharField(
        max_length=255, 
        unique=True, 
        db_index=True,
        help_text="ID de suscripción en MP"
    )
    
    # Tipo de suscripción: Para diferenciar entre pago en MP y cupón
    subscription_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='mp',
        help_text="Cómo se originó: Mercado Pago o Cupón"
    )

    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    # Datos de pago
    payment_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    
    # Fechas de pago
    last_payment_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Reintentos
    failed_payment_count = models.IntegerField(default=0)
    
    # Sincronización
    last_synced_at = models.DateTimeField(auto_now=True)
    mercado_pago_updated_at = models.DateTimeField(null=True, blank=True, help_text="Última vez que sincronizamos con MP")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'next_payment_date']),
            models.Index(fields=['mercado_pago_subscription_id']),
        ]
    
    objects = SubscriptionManager()
    
    def __str__(self):
        return f"Subscription({self.user.email}, {self.status})"
    
    def is_active(self):
        return self.status == 'active'
    
    def can_be_renewed(self):
        """Determina si se puede renovar automáticamente"""
        return self.status in ['active', 'pending']
    
    def mark_payment_failed(self):
        """Incrementa contador de fallos y actualiza estado"""
        self.failed_payment_count += 1
        if self.failed_payment_count >= 4:
            self.status = 'failed'
        else:
            self.status = 'paused'
        self.save()
        # Actualizar perfil del usuario
        from main.models import UserProfile
        self.user.userprofile.sync_subscription_status()
    
    def cancel(self):
        """Cancela la suscripción"""
        self.status = 'cancelled'
        self.save()
        from main.models import UserProfile
        self.user.userprofile.sync_subscription_status()
```

**Notas de implementación:**
- `OneToOneField` porque un usuario solo puede tener una suscripción activa a la vez
- `unique=True` en `mercado_pago_subscription_id` para evitar duplicados
- Índices en campos que consultaremos frecuentemente
- Métodos helper para lógica común

---

#### Tarea 1.2: Crear modelo `CouponCode`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/models/coupon_code.py`

**Detalles de implementación:**
```python
# avuweb/main/models/coupon_code.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets

class CouponCodeManager(models.Manager):
    """Manager personalizado para cupones"""
    def valid(self):
        """Solo cupones no usados y no expirados"""
        return self.filter(
            is_used=False,
            expires_at__gt=timezone.now()
        )
    
    def generate_batch(self, count, expires_at, created_by):
        """Genera múltiples cupones de una vez"""
        coupons = [
            CouponCode(
                code=CouponCode.generate_code(),
                expires_at=expires_at,
                created_by=created_by
            )
            for _ in range(count)
        ]
        return self.bulk_create(coupons)

class CouponCode(models.Model):
    # Código único
    code = models.CharField(max_length=100, unique=True, db_index=True, help_text="Código único del cupón (ej: DXGAKJNASD...)")
    
    # Quién lo creó
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='coupons_created')
    
    # Quién lo usó
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='used_coupons',
                             help_text="Usuario que lo utilizó (null si no fue usado)")
    
    # Estado de uso
    is_used = models.BooleanField(default=False, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Expiración
    expires_at = models.DateTimeField(db_index=True, help_text="Fecha de expiración del cupón")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = CouponCodeManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_used']),
            models.Index(fields=['expires_at', 'is_used']),
        ]
    
    def __str__(self):
        return f"Coupon({self.code[:10]}..., used={self.is_used})"
    
    @classmethod
    def generate_code(cls):
        """Genera un código aleatorio de 32 caracteres"""
        return secrets.token_hex(16).upper()  # ej: DXGAKJNASD1234567890...
    
    def is_valid(self):
        """Verifica si el cupón es válido para usar"""
        return (
            not self.is_used and 
            self.expires_at > timezone.now()
        )
    
    def use_coupon(self, user):
        """Marca el cupón como usado por un usuario"""
        if not self.is_valid():
            raise ValueError(f"Cupón {self.code} no es válido o ya fue usado")
        self.user = user
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    @classmethod
    def validate_and_use(cls, code, user):
        """Valida un código de cupón y lo marca como usado (TRANSACCIÓN ATÓMICA)
        
        Returns: CouponCode si es válido
        Raises: ValueError si no es válido
        """
        from django.db import transaction
        
        try:
            coupon = cls.objects.select_for_update().get(code=code.upper())
        except cls.DoesNotExist:
            raise ValueError(f"Cupón '{code}' no existe")
        
        if not coupon.is_valid():
            raise ValueError(f"Cupón '{code}' no es válido o ya fue usado")
        
        with transaction.atomic():
            coupon.use_coupon(user)
            # Crear Subscription de tipo 'coupon'
            from main.models import Subscription
            Subscription.objects.create(
                user=user,
                mercado_pago_subscription_id=f"coupon_{code.upper()}_{user.id}",
                subscription_type='coupon',
                status='active',
                amount=0,  # Cupones no tienen costo
            )
        return coupon
```

**Notas de implementación:**
- Manager personalizado para operaciones comunes (`.valid()`, `.generate_batch()`)
- `select_for_update()` evita race conditions al aplicar cupón
- `generate_batch()` para generar lotes desde admin
- `validate_and_use()` es atómico: valida + marca como usado + crea Subscription
- `amount=0` para cupones (no hay costo real)

---
            if coupon.is_used:
                raise ValueError("Cupón ya fue utilizado")
            else:
                raise ValueError("Cupón expiró")
        
        coupon.use_coupon(user)
        return coupon
```

**Notas de implementación:**
- `secrets.token_hex()` para generar códigos aleatorios seguros
- Método class method para validar y usar en una transacción
- `is_valid()` encapsula la lógica de validación

---

#### Tarea 1.3: Crear modelo `SubscriptionEvent` (audit log)
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/models/subscription.py` (agregar a este archivo)

**Detalles de implementación:**
```python
# En avuweb/main/models/subscription.py (agregado al final del archivo)

class SubscriptionEvent(models.Model):
    """Registro de eventos de webhook para auditoría e idempotencia"""
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=100, help_text="Ej: subscription_updated, payment.updated")
    
    # Para deduplicación
    mercado_pago_event_id = models.CharField(max_length=255, unique=True, db_index=True,
                                             help_text="ID único del evento en MP")
    
    # Payload completo del webhook
    payload = models.JSONField()
    
    # Procesamiento
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True, help_text="Mensaje de error si falló el procesamiento")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'created_at']),
            models.Index(fields=['processed']),
            models.Index(fields=['event_type']),
        ]
    
    def __str__(self):
        return f"Event({self.event_type}, processed={self.processed})"
```

**Notas de implementación:**
- `unique=True` en `mercado_pago_event_id` para evitar procesar el mismo webhook dos veces
- `processed` y `error_message` para debugging
- JSONField para guardar el payload completo

---

#### Tarea 1.4: Actualizar `models/__init__.py`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/models/__init__.py`

**Detalles de implementación:**
```python
# avuweb/main/models/__init__.py

from .static_page import StaticPage
from .user_profile import UserProfile
from .subscription import Subscription, SubscriptionEvent
from .coupon_code import CouponCode

__all__ = [
    'StaticPage',
    'UserProfile',
    'Subscription',
    'SubscriptionEvent',
    'CouponCode',
]
```

**Notas:** Asegurarse de que UserProfile tendrá campos relacionados con suscripción (ver Tarea 1.6)

---

#### Tarea 1.5: Crear migration inicial
**Estado:** 🟣 not-started  
**Comando:**
```bash
python manage.py makemigrations main --name add_subscription_models
python manage.py migrate
```

**Detalles:**
- Django generará automáticamente el archivo de migration basado en los modelos
- Verificar que la migration incluya todos los índices

---

#### Tarea 1.6: Actualizar modelo `UserProfile`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/models/user_profile.py`

**Detalles de implementación:**
```python
# En avuweb/main/models/user_profile.py - AGREGAR ESTOS MÉTODOS

class UserProfile(models.Model):
    # ... campos existentes (NO agregar campos de suscripción, usar properties) ...
    
    @property
    def is_subscription_active(self):
        """
        Property: Determina si el usuario puede acceder a contenido premium.
        IMPORTANTE: Siempre consulta el estado real en Subscription, no duplica.
        """
        # Las empresas siempre tienen acceso
        if self.user_type == 'empresa':
            return True
        
        # Los socios solo si tienen Subscription activa
        try:
            return self.user.subscription.status == 'active'
        except Subscription.DoesNotExist:
            return False
    
    @property
    def subscription_status(self):
        """Property: Retorna el estado de suscripción del usuario"""
        if self.user_type == 'empresa':
            return 'company_no_payment_required'
        
        try:
            return self.user.subscription.status
        except Subscription.DoesNotExist:
            return 'no_subscription'
    
    def sync_subscription_status(self):
        """
        Método auxiliar para forzar sincronización desde vistas.
        En realidad, es solo un refresh que consulta las properties.
        """
        # Las properties ya consultan el estado real, pero este método
        # permite que las vistas fuerzen una verificación explícita
        # Útil para debugging
        from main.models import Subscription
        try:
            subscription = self.user.subscription
            # Si llegaste aquí, existe. Las properties la consultarán.
            return subscription.status
        except Subscription.DoesNotExist:
            return None
    
    def can_view_content(self):
        """Determina si el usuario puede ver contenido premium"""
        return self.is_subscription_active
```

**NOTAS CRÍTICAS DE IMPLEMENTACIÓN:**
- ⚠️ **NO duplicar estado**: Usamos `@property` para evitar mantener dos fuentes de verdad
- ⚠️ Cada vez que se consulta `is_subscription_active`, se consulta el estado real en BD
- ✅ Empresas siempre retornan `True` sin consultar Subscription
- ✅ Socios retornan estado real de `Subscription.status`
- ✅ Si no existe Subscription, retorna `False` (sin pago, sin cupón)
- ✅ El método `sync_subscription_status()` sirve para vistas que quieren forzar check explícito

---
        return True
    return self.is_subscription_active
```

**Notas:**
- Las empresas siempre tienen `is_subscription_active = True`
- Los socios solo si tienen cupón válido o suscripción activa en MP
- Esta es la fuente de verdad para permisos en vistas

---

### Fase 2: Servicios y Wrappers ⏳

#### Tarea 2.1: Crear `MercadoPagoService`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/services.py`

**Detalles de implementación:**
```python
# avuweb/main/services.py

import requests
import logging
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)

class MercadoPagoService:
    """Wrapper del SDK de Mercado Pago para gestionar suscripciones"""
    
    def __init__(self):
        self.base_url = "https://api.mercadopago.com"
        if settings.MERCADO_PAGO_SANDBOX:
            self.base_url = "https://api.sandbox.mercadopago.com"
        
        self.access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def create_preference(self, email, plan_id, plan_amount, plan_frequency):
        """
        Crea una preferencia de pago para iniciar suscripción
        
        Args:
            email: Email del usuario
            plan_id: ID del plan (ej: 'monthly', 'yearly')
            plan_amount: Monto a cobrar
            plan_frequency: 'monthly' o 'yearly'
        
        Returns:
            dict: Respuesta de MP con URL de pago y init_point
        
        Raises:
            MPException: Si falla la creación
        """
        frequency_map = {
            'monthly': {'frequency': 1, 'frequency_type': 'months'},
            'yearly': {'frequency': 1, 'frequency_type': 'years'},
        }
        
        freq = frequency_map.get(plan_frequency, frequency_map['monthly'])
        
        payload = {
            "payer_email": email,
            "auto_recurring": {
                "frequency": freq['frequency'],
                "frequency_type": freq['frequency_type'],
                "transaction_amount": float(plan_amount),
                "currency_id": "UYU",  # Uruguay Pesos
            },
            "back_urls": {
                "success": settings.MERCADO_PAGO_SUCCESS_URL,
                "failure": settings.MERCADO_PAGO_FAILURE_URL,
                "pending": settings.MERCADO_PAGO_PENDING_URL,
            },
            "notification_url": settings.MERCADO_PAGO_WEBHOOK_URL,
        }
        
        url = f"{self.base_url}/checkout/preferences"
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Preference created: {data.get('id')}")
            return data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create preference: {e}")
            raise MPException(f"Error creating preference: {str(e)}")
    
    def get_subscription(self, subscription_id):
        """
        Obtiene detalles de una suscripción
        
        Args:
            subscription_id: ID de la suscripción en MP
        
        Returns:
            dict: Datos de la suscripción
        """
        url = f"{self.base_url}/v1/subscriptions/{subscription_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get subscription {subscription_id}: {e}")
            raise MPException(f"Error fetching subscription: {str(e)}")
    
    def cancel_subscription(self, subscription_id):
        """
        Cancela una suscripción en MP
        
        Args:
            subscription_id: ID de la suscripción
        
        Returns:
            dict: Respuesta de MP
        """
        url = f"{self.base_url}/v1/subscriptions/{subscription_id}"
        payload = {"status": "cancelled"}
        
        try:
            response = requests.put(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Subscription {subscription_id} cancelled")
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise MPException(f"Error cancelling subscription: {str(e)}")
    
    def list_subscription_payments(self, subscription_id, limit=100):
        """
        Lista todos los pagos de una suscripción
        
        Args:
            subscription_id: ID de la suscripción
            limit: Cantidad máxima de pagos a retornar
        
        Returns:
            list: Lista de pagos
        """
        url = f"{self.base_url}/v1/subscriptions/{subscription_id}/payments"
        params = {'limit': limit}
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list payments for {subscription_id}: {e}")
            raise MPException(f"Error fetching payments: {str(e)}")


class MPException(Exception):
    """Excepción personalizada para errores de Mercado Pago"""
    pass
```

**Notas de implementación:**
- Usar `requests` en lugar del SDK oficial para más control
- Logging detallado para debugging
- URLs de callback configurables en settings
- Currency hardcodeado a UYU (Uruguay) - puede hacerse dinámico después

---

#### Tarea 2.2: Agregar configuración en `settings.py`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/settings.py`

**Detalles de implementación:**
```python
# En avuweb/settings.py - AGREGAR AL FINAL

# ============================================================================
# MERCADO PAGO CONFIGURATION
# ============================================================================

MERCADO_PAGO_ACCESS_TOKEN = os.getenv('MERCADO_PAGO_ACCESS_TOKEN', '')
MERCADO_PAGO_WEBHOOK_SECRET = os.getenv('MERCADO_PAGO_WEBHOOK_SECRET', '')
MERCADO_PAGO_SANDBOX = os.getenv('MERCADO_PAGO_SANDBOX', 'True') == 'True'

# URLs de callback después de pago
MERCADO_PAGO_SUCCESS_URL = os.getenv('MERCADO_PAGO_SUCCESS_URL', 'http://localhost:8000/profile/')
MERCADO_PAGO_FAILURE_URL = os.getenv('MERCADO_PAGO_FAILURE_URL', 'http://localhost:8000/signup/error/')
MERCADO_PAGO_PENDING_URL = os.getenv('MERCADO_PAGO_PENDING_URL', 'http://localhost:8000/signup/pending/')
MERCADO_PAGO_WEBHOOK_URL = os.getenv('MERCADO_PAGO_WEBHOOK_URL', 'http://localhost:8000/webhooks/mercado-pago/')

# Planes de pago disponibles (precios en UYU)
PAYMENT_PLANS = {
    'monthly': {
        'name': 'Suscripción Mensual',
        'amount': 500.00,
        'frequency': 'monthly',
    },
    'yearly': {
        'name': 'Suscripción Anual',
        'amount': 5000.00,
        'frequency': 'yearly',
    },
}

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'sync-subscriptions-daily': {
        'task': 'main.tasks.sync_subscriptions_reconciliation',
        'schedule': crontab(hour=2, minute=0),  # 2 AM UTC
    },
    'check-pending-payments': {
        'task': 'main.tasks.check_pending_payment_dates',
        'schedule': crontab(hour=9, minute=0),  # 9 AM UTC
    },
}
```

**Variables de entorno necesarias:**
```bash
# .env
MERCADO_PAGO_ACCESS_TOKEN=APP_USR_xxxxxxxxxxxxxx
MERCADO_PAGO_WEBHOOK_SECRET=webhook_secret_xxxxxx
MERCADO_PAGO_SANDBOX=True

# URLs (en desarrollo)
MERCADO_PAGO_SUCCESS_URL=http://localhost:8000/profile/
MERCADO_PAGO_FAILURE_URL=http://localhost:8000/signup/error/
MERCADO_PAGO_PENDING_URL=http://localhost:8000/signup/pending/
MERCADO_PAGO_WEBHOOK_URL=http://localhost:8000/webhooks/mercado-pago/

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

### Fase 3: Webhooks y Celery ⏳

#### Tarea 3.1: Crear vista webhook
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/views/webhooks.py`

**Detalles de implementación:**
```python
# avuweb/main/views/webhooks.py

import hashlib
import hmac
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from main.models import Subscription, SubscriptionEvent
from main.tasks import process_subscription_event

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def mercado_pago_webhook(request):
    """
    Maneja webhooks de Mercado Pago
    
    Flujo:
    1. Valida firma HMAC
    2. Extrae datos del evento
    3. Almacena evento (para idempotencia)
    4. Encola task async para procesamiento
    5. Responde inmediatamente (< 1 seg)
    """
    try:
        # PASO 1: Validar firma
        signature = request.headers.get('X-Signature', '')
        request_id = request.headers.get('X-Request-Id', '')
        
        if not signature or not request_id:
            logger.warning("Missing signature or request ID in webhook")
            return JsonResponse({'error': 'Missing headers'}, status=400)
        
        if not validate_webhook_signature(request.body, signature, request_id):
            logger.warning(f"Invalid webhook signature: {request_id}")
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # PASO 2: Parsear payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # PASO 3: Extraer información
        event_id = payload.get('id')
        event_type = payload.get('type')
        resource_id = payload.get('data', {}).get('id')
        
        if not event_id or not event_type or not resource_id:
            logger.error(f"Missing required fields in webhook: {request_id}")
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        # Ignorar eventos que no son de suscripción/pago
        if 'subscription' not in event_type and 'payment' not in event_type:
            logger.info(f"Ignoring event type: {event_type}")
            return JsonResponse({'status': 'ignored'}, status=200)
        
        # PASO 4: Encontrar suscripción
        try:
            subscription = Subscription.objects.get(
                mercado_pago_subscription_id=resource_id
            )
        except Subscription.DoesNotExist:
            # Intentar encontrar por preapproval_id (para pagos)
            try:
                subscription = Subscription.objects.get(
                    preapproval_id=resource_id
                )
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription not found for resource: {resource_id}")
                return JsonResponse({'error': 'Subscription not found'}, status=404)
        
        # PASO 5: Crear/recuperar evento (idempotencia)
        event, created = SubscriptionEvent.objects.get_or_create(
            mercado_pago_event_id=event_id,
            defaults={
                'subscription': subscription,
                'event_type': event_type,
                'payload': payload,
            }
        )
        
        if not created:
            logger.info(f"Duplicate webhook received: {event_id}")
            return JsonResponse({'status': 'already_processed'}, status=200)
        
        # PASO 6: Encolar procesamiento async
        process_subscription_event.delay(event.id)
        
        # PASO 7: Responder inmediatamente
        logger.info(f"Webhook received and queued: {event_id}")
        return JsonResponse({'status': 'received'}, status=200)
    
    except Exception as e:
        logger.exception(f"Webhook handler error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def validate_webhook_signature(body, signature, request_id):
    """
    Valida la firma HMAC-SHA256 de Mercado Pago
    
    Formato de signature: ts=<timestamp>,v1=<hash>
    Signing string: {request_id}.{timestamp}.{body}
    
    Args:
        body: bytes - cuerpo del request
        signature: str - header X-Signature
        request_id: str - header X-Request-Id
    
    Returns:
        bool: True si es válido
    """
    try:
        # Parsear signature
        parts = {}
        for part in signature.split(','):
            key, value = part.split('=', 1)
            parts[key] = value
        
        timestamp = parts.get('ts')
        received_hash = parts.get('v1')
        
        if not timestamp or not received_hash:
            logger.warning("Invalid signature format")
            return False
        
        # Construir signing string
        if isinstance(body, bytes):
            body_str = body.decode('utf-8')
        else:
            body_str = body
        
        signing_string = f"{request_id}.{timestamp}.{body_str}"
        
def validate_webhook_signature(body, signature, request_id):
    """
    Valida la firma HMAC-SHA256 de Mercado Pago
    
    Formato de signature: ts=<timestamp>,v1=<hash>
    Signing string: {request_id}.{timestamp}.{body}
    
    Args:
        body: bytes - cuerpo del request
        signature: str - header X-Signature
        request_id: str - header X-Request-Id
    
    Returns:
        bool: True si es válido
    """
    try:
        # Parsear signature
        parts = {}
        for part in signature.split(','):
            key, value = part.split('=', 1)
            parts[key] = value
        
        timestamp = parts.get('ts')
        received_hash = parts.get('v1')
        
        if not timestamp or not received_hash:
            logger.warning("Invalid signature format")
            return False
        
        # Construir signing string
        if isinstance(body, bytes):
            body_str = body.decode('utf-8')
        else:
            body_str = body
        
        signing_string = f"{request_id}.{timestamp}.{body_str}"
        
        # Calcular hash esperado (timing-safe comparison)
        expected_hash = hmac.new(
            settings.MERCADO_PAGO_WEBHOOK_SECRET.encode(),
            signing_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Comparación timing-safe para evitar timing attacks
        return hmac.compare_digest(received_hash, expected_hash)
    
    except (ValueError, AttributeError) as e:
        logger.error(f"Signature validation error: {e}")
        return False
```
        secret = settings.MERCADO_PAGO_WEBHOOK_SECRET.encode()
        calculated_hash = hashlib.sha256(
            signing_string.encode('utf-8')
        ).hexdigest()
        
        # Comparación timing-safe
        return hmac.compare_digest(calculated_hash, received_hash)
    
    except Exception as e:
        logger.error(f"Signature validation error: {e}")
        return False
```

**Notas de implementación:**
- `@csrf_exempt` porque MP no puede enviar CSRF token
- Comparación timing-safe de hash para evitar timing attacks
- Deduplicación por `mercado_pago_event_id`
- Respuesta rápida (< 1 seg) y procesamiento async

---

#### Tarea 3.2: Crear Celery tasks
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/tasks.py`

**Detalles de implementación (parte 1 - handlers de eventos):**
```python
# avuweb/main/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from main.models import Subscription, SubscriptionEvent, UserProfile
from main.services import MercadoPagoService, MPException

logger = logging.getLogger(__name__)
mp_service = MercadoPagoService()

# ============================================================================
# MAIN WEBHOOK PROCESSOR
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_subscription_event(self, event_id):
    """
    Procesa evento de webhook de Mercado Pago
    
    Reintentos: 3 veces con backoff exponencial (60s, 120s, 240s)
    
    Args:
        event_id: ID del SubscriptionEvent en BD
    """
    try:
        event = SubscriptionEvent.objects.get(id=event_id)
        subscription = event.subscription
        payload = event.payload
        event_type = event.event_type
        
        logger.info(f"Processing event {event_type} for subscription {subscription.id}")
        
        # Rutear al handler apropiado
        if 'subscription' in event_type:
            handle_subscription_event(subscription, payload)
        elif 'payment' in event_type:
            handle_payment_event(subscription, payload)
        
        # Marcar como procesado
        event.processed = True
        event.processed_at = timezone.now()
        event.save()
        
        logger.info(f"Event {event_id} processed successfully")
    
    except SubscriptionEvent.DoesNotExist:
        logger.error(f"Event {event_id} not found")
    except MPException as e:
        logger.warning(f"MP error processing event {event_id}: {e}")
        # Reintentar
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    except Exception as e:
        logger.exception(f"Error processing event {event_id}: {e}")
        # Guardar error
        try:
            event = SubscriptionEvent.objects.get(id=event_id)
            event.error_message = str(e)
            event.save()
        except:
            pass
        # Reintentar
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


def handle_subscription_event(subscription, payload):
    """
    Maneja eventos de cambio de estado de suscripción
    
    Eventos:
    - subscription_created: Nueva suscripción creada
    - subscription_updated: Cambio de estado
    - subscription_preapproval_id: Preaprobación autorizada
    """
    status = payload.get('status')
    
    logger.info(f"Handling subscription event: status={status}")
    
    if status == 'authorized':
        # Suscripción autorizada y activa
        subscription.status = 'active'
        subscription.preapproval_id = payload.get('id')
        enable_user_profile(subscription.user)
        logger.info(f"Subscription {subscription.id} activated")
    
    elif status == 'paused':
        # Pago rechazado, MP reintentar
        subscription.status = 'paused'
        logger.warning(f"Subscription {subscription.id} paused")
    
    elif status == 'cancelled':
        # Usuario canceló o MP canceló por exceso de fallos
        subscription.status = 'cancelled'
        subscription.next_payment_date = None
        disable_user_profile(subscription.user)
        logger.warning(f"Subscription {subscription.id} cancelled by user/system")
    
    elif status == 'pending':
        # Esperando primer pago
        subscription.status = 'pending'
    
    subscription.mercado_pago_updated_at = timezone.now()
    subscription.save()


def handle_payment_event(subscription, payload):
    """
    Maneja eventos de pago
    
    Eventos:
    - payment_successful: Pago completado
    - payment_failed: Pago rechazado
    - payment_authorized: Pago autorizado
    """
    status = payload.get('status')
    
    logger.info(f"Handling payment event: status={status}")
    
    if status == 'approved':
        # Pago exitoso
        subscription.last_payment_date = timezone.now()
        subscription.failed_payment_count = 0  # Reset
        
        # Calcular próximo pago (asumir renovación automática)
        days_delta = 365 if subscription.payment_frequency == 'yearly' else 30
        subscription.next_payment_date = timezone.now() + timedelta(days=days_delta)
        
        enable_user_profile(subscription.user)
        logger.info(f"Payment approved for subscription {subscription.id}")
    
    elif status == 'rejected':
        # Pago rechazado
        subscription.failed_payment_count += 1
        logger.warning(
            f"Payment failed for subscription {subscription.id} "
            f"(attempt {subscription.failed_payment_count})"
        )
        
        # Si excede reintentos, marcar como fallido permanentemente
        if subscription.failed_payment_count >= 4:
            subscription.status = 'failed'
            disable_user_profile(subscription.user)
            logger.error(f"Subscription {subscription.id} marked as failed (too many attempts)")
        else:
            # MP reintentará automáticamente
            subscription.status = 'paused'
    
    elif status == 'authorized':
        # Pre-autorización
        subscription.next_payment_date = timezone.now() + timedelta(
            days=365 if subscription.payment_frequency == 'yearly' else 30
        )
    
    subscription.mercado_pago_updated_at = timezone.now()
    subscription.save()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def enable_user_profile(user):
    """
    Habilita el perfil del usuario.
    NOTA: Ahora solo resetea la property is_subscription_active consultando Subscription.
    """
    # Las properties en UserProfile se encargan de consultar el estado real
    # No necesitamos actualizar nada aquí, solo loguear
    logger.info(f"Profile enable triggered for user {user.id} (uses properties)")


def disable_user_profile(user):
    """
    Deshabilita el perfil del usuario.
    NOTA: La property is_subscription_active siempre consultará Subscription.status.
    """
    # Las properties en UserProfile se encargan de consultar el estado real
    # No necesitamos actualizar nada aquí, solo loguear
    logger.info(f"Profile disable triggered for user {user.id} (uses properties)")


# ============================================================================
# RECONCILIATION TASKS
# ============================================================================

@shared_task
def sync_subscriptions_reconciliation():
    """
    Tarea de reconciliación diaria
    
    Sincroniza estado de subscripciones con Mercado Pago
    para detectar webhooks perdidos
    
    Ejecutar: Diariamente 2 AM UTC
    """
    logger.info("Starting subscription reconciliation")
    
    # Subscripciones que no se han sincronizado en las últimas 6+ horas
    cutoff_time = timezone.now() - timedelta(hours=6)
    stale_subscriptions = Subscription.objects.filter(
        last_synced_at__lt=cutoff_time,
        status__in=['active', 'pending']
    )
    
    synced_count = 0
    error_count = 0
    
    for subscription in stale_subscriptions:
        try:
            # Consultar estado actual en MP
            mp_data = mp_service.get_subscription(subscription.mercado_pago_subscription_id)
            mp_status = mp_data.get('status')
            
            # Si el estado cambió, actualizar localmente
            if mp_status != subscription.status:
                logger.info(
                    f"Status mismatch for subscription {subscription.id}: "
                    f"local={subscription.status}, mp={mp_status}"
                )
                
                # Simular evento de cambio
                subscription.status = mp_status
                subscription.mercado_pago_updated_at = timezone.now()
                
                if mp_status == 'active':
                    enable_user_profile(subscription.user)
                else:
                    disable_user_profile(subscription.user)
            
            subscription.save()
            synced_count += 1
        
        except MPException as e:
            logger.warning(f"Failed to sync subscription {subscription.id}: {e}")
            error_count += 1
        except Exception as e:
            logger.exception(f"Unexpected error syncing subscription {subscription.id}: {e}")
            error_count += 1
    
    logger.info(f"Reconciliation complete: {synced_count} synced, {error_count} errors")


@shared_task
def check_pending_payment_dates():
    """
    Verifica próximos pagos (opcional, para notificaciones)
    
    Ejecutar: Diariamente 9 AM UTC
    """
    logger.info("Checking pending payment dates")
    
    tomorrow = timezone.now() + timedelta(days=1)
    upcoming = Subscription.objects.filter(
        next_payment_date__gte=timezone.now(),
        next_payment_date__lte=tomorrow,
        status='active'
    )
    
    for subscription in upcoming:
        logger.info(f"Payment due soon for subscription {subscription.id}")
        # Aquí iría lógica para enviar email de recordatorio
        # send_payment_reminder(subscription)
```

**Notas de implementación:**
- Task con retries y backoff exponencial
- Deduplicación por evento ID
- Handlers separados para tipos de eventos
- Logging exhaustivo para debugging

---

#### Tarea 3.3: Actualizar `urls.py`
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/urls.py`

**Detalles de implementación:**
```python
# En avuweb/main/urls.py - AGREGAR

from django.urls import path
from main.views import webhooks

urlpatterns = [
    # ... URLs existentes ...
    
    # Webhooks
    path('webhooks/mercado-pago/', webhooks.mercado_pago_webhook, name='mp_webhook'),
]
```

---

### Fase 4: Integración con Signup ⏳

#### Tarea 4.1: Crear vista para crear suscripción
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/views/signup.py` (agregar)

**Detalles de implementación:**
```python
# En avuweb/main/views/signup.py - AGREGAR ESTAS FUNCIONES

from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.conf import settings

from main.models import Subscription, CouponCode, UserProfile
from main.services import MercadoPagoService, MPException

@require_http_methods(["POST"])
def apply_coupon(request):
    """
    Aplica un cupón durante el registro
    
    POST /signup/apply-coupon/
    {
        "coupon_code": "DXGAKJNASD1234567890",
        "user_id": 123
    }
    """
    try:
        coupon_code = request.POST.get('coupon_code', '').strip().upper()
        user_id = request.POST.get('user_id')
        
        if not coupon_code or not user_id:
            return JsonResponse({'error': 'Faltan datos'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Validar y usar cupón
        coupon = CouponCode.validate_and_use(coupon_code, user)
        
        # Crear suscripción dummy (solo para tracking)
        subscription = Subscription.objects.create(
            user=user,
            mercado_pago_subscription_id=f"coupon_{coupon.id}",
            status='active',
            amount=0,  # Cupones son gratis
            payment_frequency='monthly',
        )
        
        # Habilitar perfil
        profile = UserProfile.objects.get(user=user)
        profile.enable_profile()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Cupón aplicado correctamente',
            'redirect_url': '/profile/',
        })
    
    except CouponCode.DoesNotExist:
        return JsonResponse({'error': 'Cupón no existe'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no existe'}, status=404)
    except Exception as e:
        logger.exception(f"Error applying coupon: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)


@require_http_methods(["POST"])
def create_payment_preference(request):
    """
    Crea una preferencia de pago en MP para iniciar suscripción
    
    POST /signup/create-preference/
    {
        "user_id": 123,
        "plan": "monthly"  # 'monthly' o 'yearly'
    }
    """
    try:
        user_id = request.POST.get('user_id')
        plan = request.POST.get('plan', 'monthly')
        
        if not user_id:
            return JsonResponse({'error': 'Faltan datos'}, status=400)
        
        if plan not in settings.PAYMENT_PLANS:
            return JsonResponse({'error': 'Plan inválido'}, status=400)
        
        user = User.objects.get(id=user_id)
        plan_data = settings.PAYMENT_PLANS[plan]
        
        # Crear preferencia en MP
        mp_service = MercadoPagoService()
        preference = mp_service.create_preference(
            email=user.email,
            plan_id=plan,
            plan_amount=plan_data['amount'],
            plan_frequency=plan_data['frequency'],
        )
        
        # Crear modelo de Subscription (pendiente)
        subscription = Subscription.objects.create(
            user=user,
            mercado_pago_subscription_id=preference.get('id'),
            status='pending',
            amount=plan_data['amount'],
            payment_frequency=plan,
        )
        
        # Retornar URL de checkout
        return JsonResponse({
            'status': 'success',
            'init_point': preference.get('init_point'),  # URL del checkout
            'redirect_url': preference.get('init_point'),  # Para redirigir
        })
    
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no existe'}, status=404)
    except MPException as e:
        logger.error(f"MP error: {e}")
        return JsonResponse({'error': 'Error al crear preferencia'}, status=500)
    except Exception as e:
        logger.exception(f"Error creating preference: {e}")
        return JsonResponse({'error': 'Error interno'}, status=500)


@require_http_methods(["GET"])
def payment_success(request):
    """
    Callback después de pago exitoso en MP
    
    GET /signup/payment-success/?preference_id=xxx&collection_id=yyy
    """
    logger.info("Payment success callback received")
    # El estado real se actualiza via webhook
    # Esta es solo una página de confirmación
    return render(request, 'main/signup/payment_success.html')


@require_http_methods(["GET"])
def payment_failure(request):
    """
    Callback después de pago fallido en MP
    
    GET /signup/payment-failure/
    """
    logger.warning("Payment failure callback received")
    return render(request, 'main/signup/payment_failure.html', {
        'message': 'El pago no se completó. Por favor intente nuevamente.'
    })
```

**Notas:**
- Endpoints AJAX-friendly (retornan JSON)
- Cupones crean suscripción dummy con mercado_pago_subscription_id ficticio
- El estado real se actualiza via webhook

---

#### Tarea 4.2: Actualizar templates de signup
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/templates/main/signup/step4.html`

**Detalles de implementación:**

Template actualizado debe mostrar:
1. Opción 1: "Aplicar cupón"
   - Input para código de cupón
   - Botón "Validar cupón"
   
2. Opción 2: "Pagar con Mercado Pago"
   - Radio buttons para elegir plan (mensual/anual)
   - Botón "Ir a pagar"
   - Muestra precios

3. Para empresas: Omitir ambas opciones (no requieren pago)

Estructura HTML recomendada:
```html
<!-- step4.html -->
{% if user_type == 'socio' %}
<div class="payment-options">
    <h3>Completa tu registración</h3>
    
    <!-- OPCIÓN 1: CUPÓN -->
    <div class="option coupon-option">
        <h4>¿Ya tienes un cupón?</h4>
        <input type="text" id="coupon_code" placeholder="Ingresa tu código...">
        <button id="apply_coupon_btn" hx-post="/signup/apply-coupon/" hx-target="#result">
            Validar Cupón
        </button>
    </div>
    
    <!-- OPCIÓN 2: PAGAR CON MP -->
    <div class="option payment-option">
        <h4>O paga directamente</h4>
        
        <div class="plans">
            <label>
                <input type="radio" name="plan" value="monthly" checked>
                Mensual - ${{ payment_plans.monthly.amount }}
            </label>
            <label>
                <input type="radio" name="plan" value="yearly">
                Anual - ${{ payment_plans.yearly.amount }}
            </label>
        </div>
        
        <button id="pay_button" hx-post="/signup/create-preference/">
            Ir a Mercado Pago
        </button>
    </div>
</div>
{% endif %}
```

---

### Fase 5: Admin Django ⏳

#### Tarea 5.1: Registrar modelos en admin
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/admin.py`

**Detalles de implementación:**
```python
# En avuweb/main/admin.py - AGREGAR

from django.contrib import admin
from django.utils.html import format_html
from main.models import Subscription, CouponCode, SubscriptionEvent
import secrets

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user_email', 
        'status_colored', 
        'subscription_type',
        'amount', 
        'last_payment_date', 
        'next_payment_date',
        'failed_count'
    )
    list_filter = ('status', 'subscription_type', 'payment_frequency', 'created_at')
    search_fields = ('user__email', 'mercado_pago_subscription_id')
    readonly_fields = (
        'mercado_pago_subscription_id',
        'mercado_pago_updated_at',
        'created_at',
        'last_synced_at',
    )
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Mercado Pago', {
            'fields': (
                'mercado_pago_subscription_id',
                'mercado_pago_updated_at',
            ),
            'description': 'Información de integración con MP (readonly)'
        }),
        ('Datos de Pago', {
            'fields': (
                'subscription_type',
                'status',
                'payment_frequency',
                'amount',
                'failed_payment_count',
            )
        }),
        ('Fechas', {
            'fields': (
                'last_payment_date',
                'next_payment_date',
                'created_at',
                'last_synced_at',
            ),
            'description': 'Todas las fechas en UTC'
        }),
    )
    actions = ['force_sync_subscription', 'cancel_subscription']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def status_colored(self, obj):
        """Muestra status con color"""
        colors = {
            'active': 'green',
            'pending': 'blue',
            'paused': 'orange',
            'cancelled': 'red',
            'failed': 'darkred',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Estado'
    
    def failed_count(self, obj):
        """Muestra contador de fallos"""
        if obj.failed_payment_count > 0:
            return format_html(
                '<span style="color: orange;">⚠️ {}</span>',
                obj.failed_payment_count
            )
        return '—'
    failed_count.short_description = 'Pagos fallidos'
    
    def force_sync_subscription(self, request, queryset):
        """Action para forzar sincronización manual"""
        from main.tasks import sync_subscriptions_reconciliation
        count = queryset.count()
        # Encolar tarea
        sync_subscriptions_reconciliation.delay()
        self.message_user(request, f'Sincronización iniciada para {count} suscripción(es)')
    force_sync_subscription.short_description = 'Forzar sincronización con MP'
    
    def cancel_subscription(self, request, queryset):
        """Action para cancelar suscripciones"""
        updated = 0
        for subscription in queryset.filter(status__in=['active', 'pending']):
            subscription.cancel()
            updated += 1
        self.message_user(request, f'{updated} suscripción(es) cancelada(s)')
    cancel_subscription.short_description = 'Cancelar suscripción'


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = (
        'code_preview',
        'is_used_status',
        'user_email',
        'expires_at',
        'created_by_name',
        'created_at'
    )
    list_filter = ('is_used', 'expires_at', 'created_at')
    search_fields = ('code', 'user__email', 'created_by__email')
    readonly_fields = ('code', 'created_at', 'used_at')
    fieldsets = (
        ('Código', {
            'fields': ('code',),
            'description': 'Generado automáticamente (readonly)'
        }),
        ('Estado', {
            'fields': ('is_used', 'used_at')
        }),
        ('Usuario', {
            'fields': ('user',),
            'description': 'Se completa automáticamente cuando se usa el cupón'
        }),
        ('Metadata', {
            'fields': ('created_by', 'expires_at', 'created_at'),
        }),
    )
    actions = ['generate_bulk_coupons', 'mark_expired']
    
    def code_preview(self, obj):
        """Muestra vista previa del código"""
        return f"{obj.code[:10]}..."
    code_preview.short_description = 'Código'
    
    def is_used_status(self, obj):
        """Muestra estado de uso con emoji"""
        if obj.is_used:
            return format_html('<span style="color: green;">✓ Usado</span>')
        elif obj.expires_at < timezone.now():
            return format_html('<span style="color: gray;">✗ Expirado</span>')
        else:
            return format_html('<span style="color: blue;">◯ Disponible</span>')
    is_used_status.short_description = 'Estado'
    
    def user_email(self, obj):
        return obj.user.email if obj.user else '—'
    user_email.short_description = 'Usuario'
    
    def created_by_name(self, obj):
        return obj.created_by.email if obj.created_by else 'Sistema'
    created_by_name.short_description = 'Creado por'
    
    def generate_bulk_coupons(self, request):
        """Custom action para generar lotes de cupones"""
        from django.contrib.admin.views.decorators import staff_member_required
        from django.shortcuts import render, redirect
        from django.urls import path
        
        # Aquí simplificaremos: usar una forma simple en admin
        # En producción, hacer una página con form personalizado
        count = int(request.POST.get('count', 10))
        days_valid = int(request.POST.get('days_valid', 90))
        
        from datetime import timedelta
        expires = timezone.now() + timedelta(days=days_valid)
        
        created = CouponCode.objects.generate_batch(count, expires, request.user)
        self.message_user(request, f'{len(created)} cupón(es) generado(s) exitosamente')
    
    generate_bulk_coupons.short_description = 'Generar lote de cupones'
    
    def mark_expired(self, request, queryset):
        """Marcar cupones como expirados (útil para cleanup)"""
        # En realidad, no marcamos nada, solo es informativo
        expired_count = queryset.filter(expires_at__lt=timezone.now()).count()
        self.message_user(request, f'{expired_count} cupón(es) están expirado(s)')
    mark_expired.short_description = 'Ver cupones expirados'


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = (
        'subscription_user',
        'event_type',
        'processed_status',
        'created_at'
    )
    list_filter = ('event_type', 'processed', 'created_at')
    search_fields = (
        'subscription__user__email',
        'mercado_pago_event_id',
        'event_type'
    )
    readonly_fields = (
        'subscription',
        'mercado_pago_event_id',
        'payload_display',
        'created_at',
    )
    fieldsets = (
        ('Suscripción', {
            'fields': ('subscription',)
        }),
        ('Evento', {
            'fields': (
                'mercado_pago_event_id',
                'event_type',
                'payload_display',
            )
        }),
        ('Procesamiento', {
            'fields': (
                'processed',
                'processed_at',
                'error_message',
            )
        }),
        ('Auditoría', {
            'fields': ('created_at',)
        }),
    )
    
    def subscription_user(self, obj):
        return obj.subscription.user.email
    subscription_user.short_description = 'Usuario'
    
    def processed_status(self, obj):
        """Muestra estado de procesamiento"""
        if obj.error_message:
            return format_html('<span style="color: red;">✗ Error</span>')
        elif obj.processed:
            return format_html('<span style="color: green;">✓ Procesado</span>')
        else:
            return format_html('<span style="color: orange;">⏳ Pendiente</span>')
    processed_status.short_description = 'Estado'
    
    def payload_display(self, obj):
        """Muestra payload JSON formateado"""
        import json
        try:
            formatted = json.dumps(obj.payload, indent=2, ensure_ascii=False)
            return f"<pre>{formatted}</pre>"
        except:
            return str(obj.payload)
    payload_display.short_description = 'Payload'
```

**Notas de implementación:**
- ✅ Actions personalizadas para operaciones comunes
- ✅ Métodos con colores para mejor UX
- ✅ `generate_batch()` disponible en CouponCodeAdmin
- ✅ SubscriptionEventAdmin para debugging de webhooks
- ✅ Readonly fields para evitar corrupción de datos

---
        ('Detalles de Pago', {
            'fields': (
                'status',
                'payment_frequency',
                'amount',
            )
        }),
        ('Fechas', {
            'fields': (
                'last_payment_date',
                'next_payment_date',
                'created_at',
                'last_synced_at',
            )
        }),
        ('Reintentos', {
            'fields': ('failed_payment_count',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Las suscripciones se crean automaticamente
        return False


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_used', 'user', 'expires_at', 'created_by', 'created_at')
    list_filter = ('is_used', 'expires_at', 'created_at')
    search_fields = ('code', 'user__email')
    readonly_fields = ('code', 'created_at', 'used_at')
    
    fieldsets = (
        ('Código', {
            'fields': ('code',)
        }),
        ('Uso', {
            'fields': ('user', 'is_used', 'used_at')
        }),
        ('Expiración', {
            'fields': ('expires_at',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es nueva
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'event_type', 'processed', 'created_at')
    list_filter = ('event_type', 'processed', 'created_at')
    search_fields = ('subscription__user__email', 'mercado_pago_event_id')
    readonly_fields = (
        'subscription',
        'event_type',
        'mercado_pago_event_id',
        'payload',
        'created_at',
    )
    
    def has_add_permission(self, request):
        # Los eventos se crean automaticamente
        return False
    
    def has_delete_permission(self, request, obj=None):
        # No borrar eventos (son auditoría)
        return False
```

---

### Fase 6: Testing y Documentación ⏳

#### Tarea 6.1: Tests unitarios básicos
**Estado:** 🟣 not-started  
**Archivo:** `avuweb/main/tests/test_subscriptions.py`

**Detalles de implementación:**
```python
# avuweb/main/tests/test_subscriptions.py

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from main.models import Subscription, CouponCode, UserProfile

class CouponCodeTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_generate_coupon_code(self):
        """Genera un código válido"""
        code = CouponCode.generate_code()
        assert len(code) == 32
        assert code.isupper()
    
    def test_coupon_validity(self):
        """Valida que cupón no expirado es válido"""
        coupon = CouponCode.objects.create(
            code=CouponCode.generate_code(),
            expires_at=timezone.now() + timedelta(days=30)
        )
        assert coupon.is_valid()
    
    def test_coupon_expiration(self):
        """Detecta cupones expirados"""
        coupon = CouponCode.objects.create(
            code=CouponCode.generate_code(),
            expires_at=timezone.now() - timedelta(days=1)
        )
        assert not coupon.is_valid()
    
    def test_coupon_use(self):
        """Marca cupón como usado"""
        coupon = CouponCode.objects.create(
            code=CouponCode.generate_code(),
            expires_at=timezone.now() + timedelta(days=30)
        )
        coupon.use_coupon(self.user)
        
        assert coupon.is_used
        assert coupon.user == self.user
        assert coupon.used_at is not None


class SubscriptionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            user_type='socio'
        )
    
    def test_subscription_creation(self):
        """Crea una suscripción"""
        subscription = Subscription.objects.create(
            user=self.user,
            mercado_pago_subscription_id='MP_SUB_123',
            status='pending',
            amount=500.00,
            payment_frequency='monthly'
        )
        
        assert subscription.user == self.user
        assert subscription.status == 'pending'
    
    def test_mark_payment_failed(self):
        """Incrementa contador de fallos"""
        subscription = Subscription.objects.create(
            user=self.user,
            mercado_pago_subscription_id='MP_SUB_456',
            status='active',
            amount=500.00,
            payment_frequency='monthly'
        )
        
        # Primer fallo
        subscription.mark_payment_failed()
        assert subscription.failed_payment_count == 1
        assert subscription.status == 'paused'
        
        # Múltiples fallos
        for _ in range(3):
            subscription.mark_payment_failed()
        
        assert subscription.failed_payment_count == 4
        assert subscription.status == 'failed'
```

---

## 📝 Notas Generales de Implementación

### Orden Recomendado de Trabajo

1. **Fase 1:** Crear modelos y migrations (fundamental)
2. **Fase 2:** Crear servicios y configuración
3. **Fase 3:** Implementar webhooks y Celery
4. **Fase 4:** Integrar con signup
5. **Fase 5:** Admin Django
6. **Fase 6:** Tests y documentación

### Consideraciones de Seguridad

- ✅ Validar siempre firma HMAC de webhooks
- ✅ No guardar datos sensibles (tarjetas)
- ✅ Usar timing-safe comparison para hashes
- ✅ Loguear todos los cambios de estado
- ✅ Deduplicar eventos por ID
- ✅ Usar HTTPS en producción

### Logging Recomendado

```python
# Siempre loguear:
- Creación de preferencia MP
- Webhooks recibidos (SIN payload sensible)
- Cambios de estado de suscripción
- Pagos rechazados
- Errores de API MP
- Discrepancias en reconciliación
```

### Variables de Entorno Requeridas

```bash
# Core
MERCADO_PAGO_ACCESS_TOKEN=APP_USR_...
MERCADO_PAGO_WEBHOOK_SECRET=webhook_secret_...
MERCADO_PAGO_SANDBOX=True  # False en prod

# URLs
MERCADO_PAGO_SUCCESS_URL=http://localhost:8000/profile/
MERCADO_PAGO_FAILURE_URL=http://localhost:8000/signup/error/
MERCADO_PAGO_PENDING_URL=http://localhost:8000/signup/pending/
MERCADO_PAGO_WEBHOOK_URL=http://localhost:8000/webhooks/mercado-pago/

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## 🔗 Referencias de Especificación

Ver `MERCADO_PAGO_INTEGRATION_SPEC.md` para:
- Flujos detallados de usuario
- Arquitectura general
- Edge cases
- Plan de implementación general

---

## ✅ Progreso – 2026-01-08

- Implementado modelos: [Subscription](avuweb/main/models/subscription.py), [CouponCode](avuweb/main/models/coupon_code.py), [SubscriptionEvent](avuweb/main/models/subscription.py#L45).
- Extendido perfil de usuario: [UserProfile](avuweb/main/models/user_profile.py) con estado de suscripción y helpers.
- Servicio MP: [MercadoPagoService](avuweb/main/services.py) (create preference, get/cancel/list payments).
- Webhook MP: [mercado_pago_webhook](avuweb/main/views/webhooks.py) + validación HMAC.
- Tasks Celery: [tasks](avuweb/main/tasks.py) para procesar eventos y reconciliación.
- URLs: agregado endpoint webhook en [avuweb/main/urls.py](avuweb/main/urls.py).
- Admin: registrado `Subscription`, `CouponCode`, `SubscriptionEvent` en [avuweb/main/admin.py](avuweb/main/admin.py).
- Settings: configuración de Mercado Pago y Celery en [avuweb/settings.py](avuweb/settings.py).
- Dependencias: instaladas con `uv` y migraciones aplicadas.

Estado de TODOs clave:
- Backend base de suscripciones: completado.
- Signup (cupones + preferencia MP): pendiente.
- Plantilla `step4` con opciones: pendiente.
- Bootstrap de Celery app: pendiente.
- Webhook en entorno dev (túnel): pendiente.

## ▶️ Próximos Pasos (prioridad)

1. Implementar handlers de signup:
    - `apply_coupon()` y `create_payment_preference()` en [avuweb/main/views/signup.py](avuweb/main/views/signup.py).
2. Actualizar plantilla de registro:
    - `avuweb/main/templates/main/signup/step4.html`: mostrar "Aplicar cupón" y "Pagar con Mercado Pago" (mensual/anual).
3. Bootstrap de Celery:
    - Crear `avuweb/celery.py` y `avuweb/__init__.py` para inicializar app Celery y permitir `worker`/`beat`.
4. Configurar webhook en dev:
    - Exponer `http://localhost:8000/webhooks/mercado-pago/` con túnel (ngrok/cloudflared) y setear `MERCADO_PAGO_WEBHOOK_URL`.
5. Variables de entorno (sandbox):
    - `MERCADO_PAGO_ACCESS_TOKEN`, `MERCADO_PAGO_WEBHOOK_SECRET`, `MERCADO_PAGO_SANDBOX=True`.

## 🔧 Cómo reanudar mañana

1) Levantar el server:

```bash
uv run python manage.py runserver
```

2) (Después de crear el bootstrap Celery) levantar workers/beat:

```bash
uv run celery -A avuweb worker -l info
uv run celery -A avuweb beat -l info
```

3) Exponer webhook (ejemplo ngrok):

```bash
ngrok http 8000
# Luego setear MERCADO_PAGO_WEBHOOK_URL con el URL público
```

4) Probar flujo:
- Signup como "Socio" → aplicar cupón (válido/expirado) y pagar con MP (sandbox).
- Confirmar cambios en perfil y estado de suscripción.

