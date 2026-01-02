from django.db import models
from django.contrib.auth.models import User


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

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.email} ({self.get_user_type_display()})"

    def is_socio(self):
        return self.user_type == 'socio'

    def is_empresa(self):
        return self.user_type == 'empresa'
