# Frontend - Arquitectura y Componentes

## Estructura General

1. **Django Templates + HTMX**: El frontend utiliza templates Django como base, con HTMX para interacciones dinámicas sin recargas. Alpine.js complementa con lógica del lado del cliente cuando es necesario.

2. **Tailwind CSS v4 + DaisyUI**: Utiliza Tailwind para utility-first styling y DaisyUI como librería de componentes. Variables CSS personalizadas (`--color-primary`, etc.) permiten tema dinámico.

3. **Vite para Assets**: JavaScript/CSS se compilean con Vite y se cargan via django-vite. Los assets compilados se encuentran en `/assets/`.

4. **Django-allauth para Auth**: Manejo de autenticación (login/signup/logout) delegado a django-allauth. Integración CSRF con HTMX seguida según documentación oficial.

5. **Componentes Reutilizables en `includes/`**: Templates parciales como `menu.html`, `benefits.html`, etc. en la carpeta `main/includes/` para evitar duplicación.

## Componentes Disponibles

6. **data_field.html**: Componente que renderiza un label + valor en una tarjeta semi-transparente. Usado para mostrar campos de información (cédula, teléfono, RUT, etc.).

7. **stat_box.html**: Similar a data_field pero con tipografía más grande para destacar métricas (estado membresía, vencimiento, beneficios disponibles).

8. **section_header.html**: Encabezado de sección con label, título y descripción opcionales. Mantiene consistencia en la jerarquía visual.

9. **menu.html**: Barra de navegación sticky que muestra diferentes opciones según estado de autenticación. Incluye responsividad con Alpine.js para toggle mobile.

## Patrones Importantes

10. **Clases CSS Consistentes**: Hero-gradient para encabezados, glass-card para contenedores principales, pill para badges. Usar `mx-auto max-w-6xl px-6` para centering estándar.
