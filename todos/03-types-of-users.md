# Tarea

En Goals.txt describimos dos tipos de usuarios: los socios y las empresas.

Vamos a implementar los dos tipos. Cuando un usario se registra, entonces puede elegir que tipo de usario quiere crear y completa la información relevante.

Luego, en la vista de perfil deberíamos mostrar una etiqueta que diferencie si el usuario es tipo "socio" o tipo "empresa"

## Plan de Implementación ✅

### ✅ 1. Crear modelo UserProfile
- Archivo: [avuweb/main/models/user_profile.py](avuweb/main/models/user_profile.py)
- Campos comunes: full_name, address
- Campos Socio: identity_number, phone_number
- Campos Empresa: rut
- Métodos: is_socio(), is_empresa()

### ✅ 2. Crear formularios multi-paso
- Archivo: [avuweb/main/forms.py](avuweb/main/forms.py)
- Paso 1: SignupStep1Form (seleccionar tipo)
- Paso 2: SignupStep2Form (nombre, email, contraseña)
- Paso 3: SignupStep3SocioForm / SignupStep3EmpresaForm (documento)
- Paso 4: SignupStep4Form (dirección)

### ✅ 3. Vista signup multi-paso
- Archivo: [avuweb/main/views/signup.py](avuweb/main/views/signup.py)
- Manejo de sesión para guardar datos entre pasos
- Validación por paso
- Creación de usuario y perfil al finalizar

### ✅ 4. Templates de signup
- [avuweb/main/templates/main/signup_base.html](avuweb/main/templates/main/signup_base.html) - Base con barra de progreso
- [avuweb/main/templates/main/signup_step1.html](avuweb/main/templates/main/signup_step1.html) - Seleccionar tipo
- [avuweb/main/templates/main/signup_step2.html](avuweb/main/templates/main/signup_step2.html) - Datos personales
- [avuweb/main/templates/main/signup_step3_socio.html](avuweb/main/templates/main/signup_step3_socio.html) - Cédula y teléfono
- [avuweb/main/templates/main/signup_step3_empresa.html](avuweb/main/templates/main/signup_step3_empresa.html) - RUT
- [avuweb/main/templates/main/signup_step4.html](avuweb/main/templates/main/signup_step4.html) - Dirección

### ✅ 5. Actualizar perfil.html
- Muestra el tipo de usuario (Socio/Empresa) en un badge
- Muestra información específica del tipo

### ✅ 6. Actualizar URLs
- Añadida ruta: `path("signup/", signup, name="signup")`

### ✅ 7. Registrar en admin
- Archivo: [avuweb/main/admin.py](avuweb/main/admin.py)
- UserProfileAdmin con filtros y búsqueda

### ✅ 8. Migraciones
- Ejecutadas migraciones: `0001_initial.py` - Crea tabla UserProfile



## Comentarios extra

- El campo dirección no valida correctamente que sea una dirección real
- El campo teléfono tampoco valida que sea una dirección real

### Script de datos de prueba ✅

Se creó un comando Django para insertar usuarios y empresas de prueba:

```bash
python manage.py create_test_users
```

**Usuarios creados:**
- **5 Socios**: socio1@test.com a socio5@test.com (contraseña: test1234)
  - Cada uno tiene cédula, teléfono y dirección
- **2 Empresas**: empresa1@test.com, empresa2@test.com (contraseña: test1234)
  - Cada una tiene RUT y dirección

El script **valida automáticamente** si los usuarios ya existen antes de agregarlos, evitando duplicados.