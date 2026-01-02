# Tarea

- Crea una landing page para el sitio. Tiene que que tener un menu que sea
responsive. 
- El menu tiene que ser un componente (archivo distinto) que se importa en el template.
- Debería crear un css con los colores primarios y usarlos. 
- El menu debe tener un boton para hacer login, o para registarse. Si el usuario está registrado, debe mostrar la opción de cerrar sesión.

Recuerda usar HTMX, y tailwind y manejar correctamente los tokens de autenticación

## Plan de acción
- Crear la app principal (main) con vistas y urls para la landing y parciales HTMX.
- Configurar settings: templates dir, static dir, allauth, CSRF para HTMX y rutas.
- Definir paleta AVU en `static/css/theme.css` y cargar Tailwind vía CDN.
- Maquetar landing `main/home.html` usando include del menú responsive `main/includes/menu.html`.
- Añadir parcial HTMX (beneficios/noticias) y botones login/registro/logout según autenticación.