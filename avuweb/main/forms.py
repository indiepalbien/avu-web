from django import forms
from django.contrib.auth.models import User
from avuweb.main.models import UserProfile


class SignupStep1Form(forms.Form):
    """Step 1: User type selection"""
    user_type = forms.ChoiceField(
        choices=UserProfile.USER_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label="¿Qué tipo de usuario eres?",
    )


class SignupStep2Form(forms.Form):
    """Step 2: Full name, email and password"""
    full_name = forms.CharField(
        max_length=255,
        label="Nombre completo",
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Tu nombre completo'
        })
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'tu@email.com'
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Tu contraseña'
        })
    )
    password_confirm = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Confirma tu contraseña'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        
        email = cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email ya está registrado.")
        
        return cleaned_data


class SignupStep3SocioForm(forms.Form):
    """Step 3: Socio - Identity number and phone"""
    identity_number = forms.CharField(
        max_length=20,
        label="Cédula de identidad",
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Ej: 12.345.678-9'
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        label="Número de teléfono",
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '+598 9 XXXX XXXX'
        })
    )


class SignupStep3EmpresaForm(forms.Form):
    """Step 3: Empresa - RUT"""
    rut = forms.CharField(
        max_length=20,
        label="RUT de la empresa",
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Ej: 12.345.678-9'
        })
    )


class SignupStep4Form(forms.Form):
    """Step 4: Address"""
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full',
            'placeholder': 'Tu dirección completa',
            'rows': 3
        }),
        label="Dirección"
    )
