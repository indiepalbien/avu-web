from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')

    mercado_pago_subscription_id = models.CharField(max_length=255, unique=True, db_index=True)
    preapproval_id = models.CharField(max_length=255, null=True, blank=True, help_text="ID de preaprobación en MP")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    payment_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    amount = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    last_payment_date = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True, db_index=True)

    failed_payment_count = models.IntegerField(default=0)

    last_synced_at = models.DateTimeField(auto_now=True)
    mercado_pago_updated_at = models.DateTimeField(null=True, blank=True, help_text="Última vez que sincronizamos con MP")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['mercado_pago_subscription_id']),
            models.Index(fields=['next_payment_date']),
        ]

    def __str__(self):
        return f"Subscription({self.user.email}, {self.status})"

    def is_active(self):
        return self.status == 'active'

    def can_be_renewed(self):
        return self.status in ['active', 'pending']

    def mark_payment_failed(self):
        self.failed_payment_count += 1
        if self.failed_payment_count >= 4:
            self.status = 'failed'
        else:
            self.status = 'paused'
        self.save()


class SubscriptionEvent(models.Model):
    """Registro de eventos de webhook para auditoría e idempotencia"""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=100, help_text="Ej: subscription_updated, payment.updated")

    mercado_pago_event_id = models.CharField(max_length=255, unique=True, db_index=True,
                                             help_text="ID único del evento en MP")

    payload = models.JSONField()

    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True, help_text="Mensaje de error si falló el procesamiento")

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
