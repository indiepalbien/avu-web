from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.db import IntegrityError

from avuweb.main.forms import (
    SignupStep1Form,
    SignupStep2Form,
    SignupStep3SocioForm,
    SignupStep3EmpresaForm,
    SignupStep4Form,
)
from avuweb.main.models import UserProfile


@csrf_protect
@require_http_methods(["GET", "POST"])
def signup(request):
    """Multi-step signup process"""
    if request.user.is_authenticated:
        return redirect('main:profile')

    step = request.GET.get('step', '1')
    
    # Initialize session data if not present
    if 'signup_data' not in request.session:
        request.session['signup_data'] = {}
    
    signup_data = request.session['signup_data']

    if request.method == 'POST':
        if step == '1':
            return handle_step_1(request, signup_data)
        elif step == '2':
            return handle_step_2(request, signup_data)
        elif step == '3':
            return handle_step_3(request, signup_data)
        elif step == '4':
            return handle_step_4(request, signup_data)

    # GET request - show form for current step
    context = {
        'step': step,
        'user_type': signup_data.get('user_type'),
    }

    if step == '1':
        context['form'] = SignupStep1Form()
        return render(request, 'main/signup/step1.html', context)
    elif step == '2':
        if not signup_data.get('user_type'):
            return redirect('main:signup') + '?step=1'
        context['form'] = SignupStep2Form()
        return render(request, 'main/signup/step2.html', context)
    elif step == '3':
        if not signup_data.get('user_type'):
            return redirect('main:signup') + '?step=1'
        if signup_data.get('user_type') == 'socio':
            context['form'] = SignupStep3SocioForm()
            return render(request, 'main/signup/step3_socio.html', context)
        else:
            context['form'] = SignupStep3EmpresaForm()
            return render(request, 'main/signup/step3_empresa.html', context)
    elif step == '4':
        if not signup_data.get('user_type'):
            return redirect('main:signup') + '?step=1'
        context['form'] = SignupStep4Form()
        return render(request, 'main/signup/step4.html', context)
    
    # Default to step 1
    return redirect('main:signup') + '?step=1'


def handle_step_1(request, signup_data):
    """Handle user type selection"""
    form = SignupStep1Form(request.POST)
    if form.is_valid():
        signup_data['user_type'] = form.cleaned_data['user_type']
        request.session['signup_data'] = signup_data
        return redirect(f'{request.path}?step=2')
    
    return render(request, 'main/signup/step1.html', {
        'form': form,
        'step': '1'
    })


def handle_step_2(request, signup_data):
    """Handle full name and email"""
    form = SignupStep2Form(request.POST)
    if form.is_valid():
        signup_data['full_name'] = form.cleaned_data['full_name']
        signup_data['email'] = form.cleaned_data.get('email', '')
        signup_data['password'] = form.cleaned_data.get('password', '')
        request.session['signup_data'] = signup_data
        return redirect(f'{request.path}?step=3')
    
    return render(request, 'main/signup/step2.html', {
        'form': form,
        'step': '2',
        'user_type': signup_data.get('user_type')
    })


def handle_step_3(request, signup_data):
    """Handle document number (cédula/RUT) and phone"""
    user_type = signup_data.get('user_type')
    
    if user_type == 'socio':
        form = SignupStep3SocioForm(request.POST)
        if form.is_valid():
            signup_data['identity_number'] = form.cleaned_data['identity_number']
            signup_data['phone_number'] = form.cleaned_data['phone_number']
            request.session['signup_data'] = signup_data
            return redirect(f'{request.path}?step=4')
        
        return render(request, 'main/signup/step3_socio.html', {
            'form': form,
            'step': '3',
            'user_type': user_type
        })
    else:
        form = SignupStep3EmpresaForm(request.POST)
        if form.is_valid():
            signup_data['rut'] = form.cleaned_data['rut']
            request.session['signup_data'] = signup_data
            return redirect(f'{request.path}?step=4')
        
        return render(request, 'main/signup/step3_empresa.html', {
            'form': form,
            'step': '3',
            'user_type': user_type
        })


def handle_step_4(request, signup_data):
    """Handle address and create user"""
    form = SignupStep4Form(request.POST)
    if form.is_valid():
        signup_data['address'] = form.cleaned_data['address']
        
        # Create user and profile
        try:
            email = signup_data.get('email')
            password = signup_data.get('password')
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                messages.error(request, 'El email ya está registrado.')
                return redirect('main:signup') + '?step=2'
            
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
            )
            
            profile = UserProfile.objects.create(
                user=user,
                user_type=signup_data.get('user_type'),
                full_name=signup_data.get('full_name'),
                address=signup_data.get('address'),
                identity_number=signup_data.get('identity_number', ''),
                phone_number=signup_data.get('phone_number', ''),
                rut=signup_data.get('rut', ''),
            )
            
            # Clear session
            del request.session['signup_data']
            
            # Login user
            user = authenticate(
                username=email,
                password=password
            )
            login(request, user)
            
            messages.success(request, '¡Bienvenido! Tu cuenta ha sido creada exitosamente.')
            return redirect('main:profile')
            
        except IntegrityError as e:
            messages.error(request, f'Error al crear la cuenta: {str(e)}')
            return redirect('main:signup') + '?step=1'
        except Exception as e:
            messages.error(request, f'Error inesperado: {str(e)}')
            return redirect('main:signup') + '?step=1'
    
    return render(request, 'main/signup/step4.html', {
        'form': form,
        'step': '4',
        'user_type': signup_data.get('user_type')
    })
