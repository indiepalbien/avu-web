This is a web application for an NGO to handle member subscriptions, show membership
benfits, and share organization news.

This project is built with DJANGO, and relies heavily on django tempaltes + HTMX for the frontend. Please follow the following guidlines when contributing.


## Python

- We use `uv` to handle package management
- Use `uv add <library>` to add a new library
- Follow PEP 20 and PEP 8 as much as possible
- Use `ruff` for code formatting.


## Django

- Name views using: `[application]/[model]_[function].html`
- When using inclusion tags or other other functionality to render partial templates, keep them in an includes directory inside the application template directory, e.g, `address_book/includes/contact_form.html`
- Keep models FAT, with lots of small methods that are then used by views.
- Abstract commong logic into methods of a manager.
- Keep each model on its own file and make the models/ folder a package with `__init__.py` importing each models. 
- Keep views related to the same model into a separte file, and create a package for all views.
- User authentication uses `django-allauth`.
- The front end is mostly standard Django views and templates.
- HTMX and Alpine.js are used to provide single-page-app user experience with Django templates.  HTMX is used for interactions which require accessing the backend, and Alpine.js is used for browser-only interactions.
- JavaScript files are kept in the `/assets/` folder and built by vite.
  JavaScript code is typically loaded via the static files framework inside Django templates using `django-vite`.
- APIs use Django Rest Framework, and JavaScript code that interacts with APIs uses an auto-generated OpenAPI-schema-baesd client.
- The front end uses Tailwind (Version 4) and DaisyUI.
- The main database is Postgres.
- Celery is used for background jobs and scheduled tasks.
- Redis is used as the default cache, and the message broker for Celery.
