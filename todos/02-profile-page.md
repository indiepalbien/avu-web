# Tarea

Queremos tener una página de perfil que se vea solo para los usuarios
logeados. Cuando un usuario se logea, se le deberá redirigir a esta página.

Por ahora, queremos que solo diga, "hola, %nombre%", estas logeado.

## Plan de Acción Completado

✅ **Vista de Perfil**: Creada en `avuweb/main/views/profile.py`
   - Usa `@login_required` para proteger la vista
   - Renderiza el template `main/profile.html`

✅ **Template**: Creado `avuweb/main/templates/main/profile.html`
   - Muestra "Hola, {nombre}" usando `{{ user.first_name }}`
   - Mensaje "Estás logeado"

✅ **URLs**: Agregada ruta `/profile/` en `avuweb/main/urls.py`

✅ **Redirección**: Configurada en `settings.py`
   - `LOGIN_REDIRECT_URL = '/profile/'`
   - Los usuarios serán redirigidos automáticamente al perfil después de login

✅ **Verificación**: Django check sin errores

