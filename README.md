# CRM básico (Django)

Gestor de clientes para equipos comerciales, hecho con Django 5.2 y SQLite.

## Acceso a la demo

**URL de la demo: [https://crm-django-a1et.onrender.com](https://crm-django-a1et.onrender.com)**

| Usuario | Contraseña | Qué ve |
|---|---|---|
| `admin` | `demo-crm-django` | Todos los clientes. |
| `marta` | `demo-crm-django` | Solo sus clientes. |
| `jorge` | `demo-crm-django` | Solo sus clientes. |

Son credenciales de demostración y los datos son ficticios: se reinician cada vez que el servicio se reinicia. El plan gratuito de Render duerme el servicio tras 15 minutos sin visitas, así que la primera carga puede tardar ~1 minuto.

## Funcionalidades

- CRUD de clientes, empresas e interacciones (llamadas, emails, reuniones, otros).
- Permisos por comercial: cada comercial solo ve y gestiona sus clientes (y sus interacciones); el superusuario lo ve todo.
- Búsqueda en vivo en la lista de clientes (nombre, apellidos, email o empresa), con paginación.
- Filtros y ordenación de la lista.
- Exportación de clientes a CSV.
- Estadísticas con gráficos ECharts.
- Deshacer el borrado.

## Ejecutar en local

```
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser   # opcional
python manage.py runserver
```

Abrir http://127.0.0.1:8000/. Tests: `python manage.py test`.

## Usuarios demo

`seed_demo` crea los comerciales `marta` y `jorge` (más 8 empresas, 25 clientes y 60 interacciones). En local, sin `DEMO_PASSWORD`, no hay contraseña fija: se genera una aleatoria al crear cada usuario y se guarda en `credenciales-dev.txt` (en la raíz del proyecto, ignorado por git). Con `DEMO_PASSWORD` definida (como en Render, ver "Acceso a la demo") los usuarios demo usan esa contraseña y no se escribe `credenciales-dev.txt`. El comando es idempotente; `--reset` recrea empresas, clientes e interacciones.

## Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `DJANGO_DEBUG` | `1` | `0` para producción. |
| `DJANGO_SECRET_KEY` | clave de desarrollo | Obligatoria si `DJANGO_DEBUG=0`. |
| `DJANGO_ALLOWED_HOSTS` | vacío | Hosts permitidos, separados por comas (en Render: `.onrender.com`). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vacío | Orígenes separados por comas, p. ej. `https://crm-django-a1et.onrender.com`. |
| `DJANGO_HTTPS` | `0` | `1` solo si se sirve por HTTPS (activa cookies Secure). |
| `DEMO_PASSWORD` | sin definir | Contraseña de los usuarios demo en Render (`admin`, `marta`, `jorge`). |

Con `DJANGO_DEBUG=0` los estáticos se sirven con WhiteNoise desde `staticfiles/` (`collectstatic`).

## Despliegue en Render

1. Crea una cuenta en [render.com](https://render.com) y conecta tu cuenta de GitHub.
2. **New → Blueprint** y elige este repositorio (Render lee `render.yaml`).
3. Escribe el valor de `DEMO_PASSWORD` (la contraseña de los usuarios demo) cuando lo pida.
4. **Apply**. Al terminar, la app queda en la URL `https://crm-django-a1et.onrender.com` (HTTPS automático).

`render.yaml` ya define el resto de variables (`DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` generada, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_HTTPS=1`). En cada arranque ejecuta las migraciones y `seed_demo`; para actualizar basta con hacer `git push` a `main` (Render redespliega solo).

Usuarios demo: `admin`, `marta` y `jorge`, todos con la contraseña `DEMO_PASSWORD`.

Avisos del plan gratuito: el servicio se duerme tras 15 min sin tráfico y tarda ~1 min en despertar. El disco es efímero: la base SQLite se recrea (migraciones + datos demo) en cada arranque, así que los cambios se pierden.
