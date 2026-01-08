from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets


class CouponCode(models.Model):
    code = models.CharField(max_length=100, unique=True, db_index=True, help_text="Código único del cupón")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='coupons_created')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='used_coupons',
                             help_text="Usuario que lo utilizó (null si no fue usado)")

    is_used = models.BooleanField(default=False, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(db_index=True, help_text="Fecha de expiración del cupón")

    months_of_validity = models.IntegerField(default=3, help_text="Meses de validez desde la creación (informativo)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Coupon({self.code[:10]}..., used={self.is_used})"

    @classmethod
    def generate_code(cls):
        """Genera un código aleatorio de 32 caracteres"""
        return secrets.token_hex(16).upper()

    def is_valid(self):
        now = timezone.now()
        return (not self.is_used) and (self.expires_at > now)

    def use_coupon(self, user):
        if not self.is_valid():
            raise ValueError(f"Cupón {self.code} no es válido")
        self.user = user
        self.is_used = True
        self.used_at = timezone.now()
        self.save()

    @classmethod
    def validate_and_use(cls, code, user):
        try:
            coupon = cls.objects.get(code=code.upper())
        except cls.DoesNotExist:
            raise ValueError("Cupón no existe")

        if not coupon.is_valid():
            if coupon.is_used:
                raise ValueError("Cupón ya fue utilizado")
            else:
                raise ValueError("Cupón expiró")

        coupon.use_coupon(user)
        return coupon
