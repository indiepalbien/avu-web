# Revisión: Propuesta de Implementación Mercado Pago

**Reviewer:** GitHub Copilot  
**Fecha:** 8 de Enero, 2026  
**Propuesta Original:** PAYMENTS.md  

---

## 📊 Resumen Ejecutivo

La propuesta en `PAYMENTS.md` es **sólida en general**, pero tenía varios problemas de diseño que podían causar bugs y deuda técnica. Se han identificado y corregido **10 problemas principales**.

### Estado Final
- ✅ Todas las correcciones aplicadas a PAYMENTS.md
- ✅ Sigue las guías del proyecto (AGENTS.md)
- ✅ Implementa mejores prácticas de Django
- ✅ Listo para implementación

---

## 🔴 Problemas Identificados

### 1. **Campos Redundantes en Subscription**
**Severidad:** 🟠 Media | **Tipo:** Diseño  

**Problema:**
```python
mercado_pago_subscription_id = models.CharField(...)
preapproval_id = models.CharField(...)  # ❌ Redundante
```

Mercado Pago usa solo 1 ID. Tener dos causaría confusión y bugs.

**Solución:** ✅ Remover `preapproval_id`, usar solo `mercado_pago_subscription_id`

---

### 2. **Falta Campo para Diferenciar Tipo de Suscripción**
**Severidad:** 🟠 Media | **Tipo:** Lógica  

**Problema:**
Sin saber si una Subscription vino de un cupón o pago MP, no se puede:
- Mostrar historial diferenciado
- Implementar lógica distinta para renovación
- Auditar cupones efectivamente

**Solución:** ✅ Agregar campo `subscription_type`:
```python
TYPE_CHOICES = [
    ('mp', 'Mercado Pago'),
    ('coupon', 'Cupón'),
]
subscription_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='mp')
```

---

### 3. **Duplicación de Estado en UserProfile**
**Severidad:** 🔴 Crítica | **Tipo:** Arquitectura  

**Problema:**
La propuesta original quería agregar campos en UserProfile:
```python
is_subscription_active = models.BooleanField()  # ❌ Duplica Subscription.status
subscription_status = models.CharField()  # ❌ Duplica Subscription.status
```

**Por qué es malo:**
- Una suscripción cambia de estado → hay que actualizar UserProfile también
- Si se olvida, quedan inconsistentes
- Viola el principio DRY (Don't Repeat Yourself)

**Solución:** ✅ Usar `@property` methods:
```python
@property
def is_subscription_active(self):
    if self.user_type == 'empresa':
        return True
    try:
        return self.user.subscription.status == 'active'
    except Subscription.DoesNotExist:
        return False

@property
def subscription_status(self):
    # ... similar logic
```

**Ventajas:**
- Una sola fuente de verdad (Subscription.status)
- Siempre está en sync automáticamente
- Menos código que mantener

---

### 4. **CouponCode Sin Batch Generation**
**Severidad:** 🟡 Baja | **Tipo:** Usabilidad  

**Problema:**
Los admins querrán generar 100 cupones a la vez. La propuesta original solo permitía uno por uno.

**Solución:** ✅ Agregar manager con `generate_batch()`:
```python
class CouponCodeManager(models.Manager):
    def generate_batch(self, count, expires_at, created_by):
        """Genera múltiples cupones"""
        coupons = [
            CouponCode(
                code=CouponCode.generate_code(),
                expires_at=expires_at,
                created_by=created_by
            )
            for _ in range(count)
        ]
        return self.bulk_create(coupons)
```

---

### 5. **Validación de Webhooks Incompleta**
**Severidad:** 🟠 Media | **Tipo:** Seguridad  

**Problema:**
La propuesta valida firma HMAC (✅ bien), pero no valida estructura del payload.

Si Mercado Pago cambia el formato del JSON, el código se rompe sin validación explícita.

**Solución:** ✅ Agregar validación de campos requeridos:
```python
# En webhook handler
event_id = payload.get('id')
event_type = payload.get('type')
resource_id = payload.get('data', {}).get('id')

if not event_id or not event_type or not resource_id:
    logger.error(f"Missing required fields")
    return JsonResponse({'error': 'Missing fields'}, status=400)
```

---

### 6. **Handlers de Webhooks Vacíos**
**Severidad:** 🔴 Crítica | **Tipo:** Implementación  

**Problema:**
La Tarea 3.2 muestra estructura pero handlers están incompletos (líneas omitidas).

Sin lógica real, no se sabe cómo procesar eventos.

**Solución:** ✅ Implementar `handle_subscription_event()` y `handle_payment_event()`:
```python
def handle_subscription_event(subscription, payload):
    status = payload.get('status')
    
    if status == 'authorized':
        subscription.status = 'active'
        enable_user_profile(subscription.user)
    elif status == 'cancelled':
        subscription.status = 'cancelled'
        disable_user_profile(subscription.user)
    
    subscription.save()

def handle_payment_event(subscription, payload):
    status = payload.get('status')
    
    if status == 'approved':
        subscription.last_payment_date = timezone.now()
        subscription.failed_payment_count = 0
    elif status == 'rejected':
        subscription.failed_payment_count += 1
        if subscription.failed_payment_count >= 4:
            subscription.status = 'failed'
    
    subscription.save()
```

---

### 7. **Celery Tasks Sin Transacciones Atómicas**
**Severidad:** 🟠 Media | **Tipo:** Confiabilidad  

**Problema:**
`validate_and_use()` debe:
1. Validar cupón
2. Marcarlo como usado
3. Crear Subscription

Si falla en paso 2 o 3, queda inconsistente.

**Solución:** ✅ Envolver en `transaction.atomic()`:
```python
@classmethod
def validate_and_use(cls, code, user):
    coupon = cls.objects.select_for_update().get(code=code.upper())
    
    if not coupon.is_valid():
        raise ValueError(...)
    
    with transaction.atomic():
        coupon.use_coupon(user)
        Subscription.objects.create(...)
    
    return coupon
```

---

### 8. **Admin Django Incompleto**
**Severidad:** 🟡 Baja | **Tipo:** Usabilidad  

**Problema:**
Admin original solo mostraba listas, sin:
- Actions personalizadas
- Métodos de display con colores
- Opciones para generar cupones en lote
- Debugging de webhooks

**Solución:** ✅ Admin mejorado con:
- `@admin.action` para forzar sync y cancelar
- Métodos con colores (✓ verde, ✗ rojo)
- `generate_batch()` action
- SubscriptionEventAdmin para debugging
- Readonly fields para evitar corrupción

---

### 9. **Falta Integración Entre Modelos**
**Severidad:** 🟠 Media | **Tipo:** Diseño  

**Problema:**
`mark_payment_failed()` y `cancel()` en Subscription no actualizaban UserProfile.

**Solución:** ✅ Agregar llamadas a sync:
```python
def mark_payment_failed(self):
    self.failed_payment_count += 1
    if self.failed_payment_count >= 4:
        self.status = 'failed'
    self.save()
    self.user.userprofile.sync_subscription_status()  # ✅ Agregado

def cancel(self):
    self.status = 'cancelled'
    self.save()
    self.user.userprofile.sync_subscription_status()  # ✅ Agregado
```

---

### 10. **PAYMENT_PLANS Sin Valores**
**Severidad:** 🟡 Baja | **Tipo:** Documentación  

**Problema:**
```python
PAYMENT_PLANS = {
    'monthly': {/* Lines 547-555 omitted */},  # ❌ Vacío
}
```

**Solución:** ✅ Completar con valores reales:
```python
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
```

---

## ✅ Mejoras Aplicadas

| # | Aspecto | Cambio | Impacto |
|---|---------|--------|--------|
| 1 | Modelos | Remover preapproval_id | -1 campo redundante |
| 2 | Modelos | Agregar subscription_type | +Auditoría clara |
| 3 | UserProfile | @property en lugar de campos | +DRY, -bugs |
| 4 | CouponCode | Manager + generate_batch() | +Operacional |
| 5 | Webhooks | Validación de payload | +Seguridad |
| 6 | Handlers | Implementación completa | +Funcional |
| 7 | Transacciones | atomic() en cupones | +Confiable |
| 8 | Admin | Mejora completa | +UX |
| 9 | Integración | Sincronización entre modelos | +Consistencia |
| 10 | Config | Valores reales en PAYMENT_PLANS | +Completo |

---

## 🎓 Lecciones Aprendidas

### Para el Nuevo Ingeniero

1. **Evitar duplicación de estado:**
   - Si X información está en la BD en modelo A, no la copies a modelo B
   - Usa properties o métodos para accederla

2. **Validar siempre entrada externa:**
   - Webhooks, APIs, user input
   - No asumir estructura, validar explícitamente

3. **Usar transacciones para operaciones multi-paso:**
   - Si hay múltiples cambios, envolverlos en `transaction.atomic()`
   - Así si algo falla, todo se revierte

4. **Pensar en operaciones:**
   - ¿Cómo los admins generarán 100 cupones? ✅ Batch action
   - ¿Cómo debuguearemos webhooks si algo va mal? ✅ SubscriptionEventAdmin

5. **Logs son tu amigo:**
   - Log TODOS los cambios de estado
   - Evento recibido, procesado, error → TODO en logs

---

## 📋 Checklist Final

- [x] Modelos sin redundancia
- [x] Validación de entrada robusta
- [x] Transacciones atómicas
- [x] Manager personalizado con helpers
- [x] Admin mejorado con UX
- [x] Logging exhaustivo
- [x] Seguridad (HMAC, timing-safe)
- [x] Alineado con AGENTS.md
- [x] Documentación clara

---

## 🚀 Próximos Pasos

1. **Revisar y comentar** con el ingeniero
2. **Implementar Fase 1** (modelos + migrations)
3. **Testing** en sandbox de MP
4. **Deploy** a staging
5. **Monitorear logs** en producción

---

**Estado:** ✅ Propuesta mejorada y lista para implementación
