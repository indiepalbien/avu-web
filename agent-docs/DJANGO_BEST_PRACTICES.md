# Mejores Prácticas Django - Lecciones del Review

Este documento recopila las mejores prácticas de Django aprendidas durante el review de la propuesta de Mercado Pago.

---

## 1. 🚫 No Duplicar Estado en la Base de Datos

### ❌ MAL - Duplicar información en múltiples modelos:

```python
class Subscription(models.Model):
    status = models.CharField(...)  # 'active', 'cancelled', etc

class UserProfile(models.Model):
    # ❌ Duplica el estado
    is_subscription_active = models.BooleanField(default=False)
    subscription_status = models.CharField(...)
```

**Problema:** Si cambias `Subscription.status`, debes recordar actualizar `UserProfile` también. Si olvidas, quedan inconsistentes.

### ✅ BIEN - Una sola fuente de verdad con properties:

```python
class Subscription(models.Model):
    status = models.CharField(...)

class UserProfile(models.Model):
    # ✅ Property que consulta el estado real
    @property
    def is_subscription_active(self):
        try:
            return self.user.subscription.status == 'active'
        except Subscription.DoesNotExist:
            return False
    
    @property
    def subscription_status(self):
        try:
            return self.user.subscription.status
        except Subscription.DoesNotExist:
            return 'no_subscription'
```

**Ventajas:**
- Siempre está sincronizado automáticamente
- No necesitas `save()` cuando cambias Subscription
- Menos código y menos bugs

---

## 2. 🔒 Transacciones Atómicas para Operaciones Multi-Paso

### ❌ MAL - Sin transacción:

```python
def validate_and_use_coupon(code, user):
    coupon = CouponCode.objects.get(code=code)
    
    if not coupon.is_valid():
        raise ValueError("Cupón inválido")
    
    # ❌ Si esto falla después de marcar como usado, queda inconsistente
    coupon.is_used = True
    coupon.save()
    
    # ❌ Si esto falla, cupón quedó marcado pero no hay Subscription
    subscription = Subscription.objects.create(...)
```

### ✅ BIEN - Con transacción atómica:

```python
from django.db import transaction

@transaction.atomic
def validate_and_use_coupon(code, user):
    # select_for_update() bloquea la fila para evitar race conditions
    coupon = CouponCode.objects.select_for_update().get(code=code)
    
    if not coupon.is_valid():
        raise ValueError("Cupón inválido")
    
    # ✅ Todo dentro de la transacción
    coupon.is_used = True
    coupon.save()
    
    subscription = Subscription.objects.create(...)
    
    # Si cualquier cosa falla, TODO se revierte automáticamente
    return coupon
```

**Ventajas:**
- Si algo falla, la BD queda en estado consistente
- `select_for_update()` evita que dos usuarios usen el mismo cupón al mismo tiempo

---

## 3. 📦 Managers Personalizados para Lógica Común

### ❌ MAL - Queries repetidos en views:

```python
# En view 1:
active_subscriptions = Subscription.objects.filter(status='active')

# En view 2:
active_subscriptions = Subscription.objects.filter(status='active')

# En view 3:
active_subscriptions = Subscription.objects.filter(status='active')
```

### ✅ BIEN - Manager centralizado:

```python
class SubscriptionManager(models.Manager):
    def active(self):
        return self.filter(status='active')
    
    def pending_renewal(self):
        return self.filter(
            status='active',
            next_payment_date__lte=timezone.now()
        )

class Subscription(models.Model):
    # ... campos ...
    objects = SubscriptionManager()

# Uso en views:
active_subscriptions = Subscription.objects.active()
pending = Subscription.objects.pending_renewal()
```

**Ventajas:**
- Queries complejos en un solo lugar
- Si cambias lógica, cambias en 1 lugar
- Más legible y semántico

---

## 4. 🎨 Admin Django con Display Methods

### ❌ MAL - Admin básico:

```python
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'amount')
```

Resultado: Todo texto plano, difícil de leer.

### ✅ BIEN - Con display methods y colores:

```python
from django.utils.html import format_html

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'status_colored', 'amount', 'failed_count')
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def status_colored(self, obj):
        colors = {
            'active': 'green',
            'pending': 'blue',
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
        if obj.failed_payment_count > 0:
            return format_html(
                '<span style="color: orange;">⚠️ {}</span>',
                obj.failed_payment_count
            )
        return '—'
    failed_count.short_description = 'Fallos'
```

**Ventajas:**
- Visual y fácil de escanear
- Status importantes resaltan
- Info útil concentrada

---

## 5. 🛡️ Validación de Entrada Externa (Webhooks, APIs)

### ❌ MAL - Asumir estructura:

```python
def webhook_handler(request):
    payload = json.loads(request.body)
    
    # ❌ Si MP cambia formato, esto se rompe
    subscription_id = payload['data']['id']
    event_type = payload['type']
```

### ✅ BIEN - Validar explícitamente:

```python
def webhook_handler(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # ✅ Usar .get() con defaults
    event_id = payload.get('id')
    event_type = payload.get('type')
    resource_id = payload.get('data', {}).get('id')
    
    # ✅ Validar campos requeridos
    if not event_id or not event_type or not resource_id:
        logger.error(f"Missing required fields: {payload}")
        return JsonResponse({'error': 'Missing fields'}, status=400)
    
    # Ahora es seguro usar estas variables
```

**Ventajas:**
- Código defensivo
- No se rompe si payload cambia
- Logs indican qué faltó

---

## 6. 🔐 Seguridad: Timing-Safe Comparisons

### ❌ MAL - Comparación normal de hashes:

```python
if received_hash == calculated_hash:  # ❌ Vulnerable a timing attacks
    return True
```

**Problema:** Python compara strings carácter por carácter. Si el atacante mide el tiempo de respuesta, puede adivinar el hash correcto.

### ✅ BIEN - Timing-safe comparison:

```python
import hmac

if hmac.compare_digest(received_hash, calculated_hash):  # ✅ Seguro
    return True
```

**Ventaja:** Tiempo de comparación constante, no importa dónde difieren.

---

## 7. 📝 Logging Exhaustivo

### ❌ MAL - Sin logs:

```python
def process_payment(subscription):
    subscription.status = 'active'
    subscription.save()
```

**Problema:** Si algo va mal, no sabes qué pasó.

### ✅ BIEN - Con logging estratégico:

```python
import logging

logger = logging.getLogger(__name__)

def process_payment(subscription):
    logger.info(f"Processing payment for subscription {subscription.id}")
    
    try:
        subscription.status = 'active'
        subscription.save()
        logger.info(f"Payment successful for subscription {subscription.id}")
    except Exception as e:
        logger.exception(f"Payment failed for subscription {subscription.id}: {e}")
        raise
```

**Qué loguear:**
- Entrada de funciones importantes
- Cambios de estado
- Errores (con `logger.exception()` para stack trace)
- Eventos de negocio (pago aprobado, suscripción cancelada)

---

## 8. 🏭 Bulk Operations para Performance

### ❌ MAL - Loop con save():

```python
def generate_100_coupons():
    coupons = []
    for i in range(100):
        coupon = CouponCode(code=generate_code(), ...)
        coupon.save()  # ❌ 100 queries a la BD
        coupons.append(coupon)
    return coupons
```

### ✅ BIEN - bulk_create():

```python
def generate_100_coupons():
    coupons = [
        CouponCode(code=generate_code(), ...)
        for i in range(100)
    ]
    return CouponCode.objects.bulk_create(coupons)  # ✅ 1 query
```

**Ventaja:** 100x más rápido.

---

## 9. 🎯 Admin Actions para Operaciones Comunes

### ✅ Ejemplo - Forzar sincronización:

```python
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    actions = ['force_sync']
    
    def force_sync(self, request, queryset):
        """Action personalizada"""
        from main.tasks import sync_subscriptions_reconciliation
        
        count = queryset.count()
        sync_subscriptions_reconciliation.delay()
        
        self.message_user(
            request,
            f'Sincronización iniciada para {count} suscripción(es)'
        )
    force_sync.short_description = 'Forzar sincronización con MP'
```

**Ventajas:**
- Operaciones comunes sin escribir views
- Interfaz uniforme en admin

---

## 10. 🔍 Index Strategy para Queries Comunes

### ❌ MAL - Sin índices:

```python
class Subscription(models.Model):
    user = models.ForeignKey(User)
    status = models.CharField(...)
    next_payment_date = models.DateTimeField()

# Query frecuente SIN índice:
Subscription.objects.filter(status='active', next_payment_date__lte=today)
# ❌ Full table scan, lento con muchos registros
```

### ✅ BIEN - Con índices compuestos:

```python
class Subscription(models.Model):
    user = models.ForeignKey(User)
    status = models.CharField(...)
    next_payment_date = models.DateTimeField()
    
    class Meta:
        indexes = [
            # ✅ Índice compuesto para query común
            models.Index(fields=['status', 'next_payment_date']),
        ]

# Ahora este query usa el índice:
Subscription.objects.filter(status='active', next_payment_date__lte=today)
```

**Regla:** Si haces un `.filter()` frecuente con 2+ campos, agrega índice compuesto.

---

## 📚 Referencias

- [Django Best Practices](https://docs.djangoproject.com/en/stable/misc/design-philosophies/)
- [Two Scoops of Django](https://www.feldroy.com/books/two-scoops-of-django-3-x)
- [Django Anti-Patterns](https://www.django-antipatterns.com/)

---

## 🎓 Checklist para Nuevas Features

- [ ] Sin duplicación de estado (usar properties)
- [ ] Transacciones atómicas en operaciones multi-paso
- [ ] Manager para queries comunes
- [ ] Display methods en admin
- [ ] Validación de entrada externa
- [ ] Timing-safe comparisons para seguridad
- [ ] Logging exhaustivo
- [ ] Bulk operations para performance
- [ ] Admin actions para operaciones
- [ ] Índices en queries frecuentes

---

**Mantener este documento actualizado** con lecciones futuras.
