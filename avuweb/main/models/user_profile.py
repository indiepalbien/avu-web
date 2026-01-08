from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ('socio', 'Socio'),
        ('empresa', 'Empresa'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    
    # Common fields
    full_name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    
    # Socio specific fields
    identity_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Cédula de identidad"
    )
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Empresa specific fields
    rut = models.CharField(
        max_length=20,
        blank=True,
        help_text="RUT de la empresa"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Estado de suscripción y habilitación de perfil
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('no_subscription', 'Sin suscripción'),
            ('active', 'Activa'),
            ('inactive', 'Inactiva'),
            ('cancelled', 'Cancelada'),
        ],
        default='no_subscription',
        help_text="Estado sincronizado de la suscripción"
    )

    is_subscription_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True si tiene cupón o suscripción activa en MP"
    )

    subscription_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.email} ({self.get_user_type_display()})"

    def is_socio(self):
        return self.user_type == 'socio'

    def is_empresa(self):
        return self.user_type == 'empresa'

    def enable_profile(self):
        """Habilita el perfil (usuario pagó o aplicó cupón)"""
        self.is_subscription_active = True
        self.subscription_status = 'active'
        self.subscription_last_updated = timezone.now()
        self.save(update_fields=['is_subscription_active', 'subscription_status', 'subscription_last_updated'])

    def disable_profile(self):
        """Deshabilita el perfil (suscripción venció o fue cancelada)"""
        # Empresas mantienen acceso; socios se deshabilitan
        if self.is_empresa():
            self.is_subscription_active = True
            self.subscription_status = 'active'
        else:
            self.is_subscription_active = False
            self.subscription_status = 'inactive'
        self.subscription_last_updated = timezone.now()
        self.save(update_fields=['is_subscription_active', 'subscription_status', 'subscription_last_updated'])

    def can_view_content(self):
        """Determina si el usuario puede ver contenido premium"""
        if self.is_empresa():
            return True
        return self.is_subscription_active
