# CRM básico (Django)

Gestor de clientes para equipos comerciales, hecho con Django 5.2 y SQLite.

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

`seed_demo` crea los comerciales `marta` y `jorge` (más 8 empresas, 25 clientes y 60 interacciones). No hay contraseña fija: se genera una aleatoria al crear cada usuario y se guarda en `credenciales-dev.txt` (en la raíz del proyecto, ignorado por git). El comando es idempotente; `--reset` recrea empresas, clientes e interacciones.

## Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `DJANGO_DEBUG` | `1` | `0` para producción. |
| `DJANGO_SECRET_KEY` | clave de desarrollo | Obligatoria si `DJANGO_DEBUG=0`. |
| `DJANGO_ALLOWED_HOSTS` | vacío | Hosts permitidos, separados por comas. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vacío | Orígenes, p. ej. `http://1.2.3.4`. |
| `DJANGO_HTTPS` | `0` | `1` solo si se sirve por HTTPS (activa cookies Secure). |

Con `DJANGO_DEBUG=0` los estáticos se sirven con WhiteNoise desde `staticfiles/` (`collectstatic`).

## Despliegue en un droplet Ubuntu (nginx + gunicorn, sin dominio ni HTTPS)

Como root:

```
apt update && apt install -y python3-venv nginx git
git clone <URL-del-repositorio> /srv/crm-django
cd /srv/crm-django
cp deploy/.env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # úsala como DJANGO_SECRET_KEY
nano .env                        # SECRET_KEY, y la IP del droplet en ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS
cp deploy/crm.service /etc/systemd/system/crm.service
systemctl daemon-reload && systemctl enable crm
bash deploy/deploy.sh            # instala dependencias, migra, collectstatic, seed y arranca el servicio
ln -sf /srv/crm-django/deploy/crm.nginx /etc/nginx/sites-enabled/crm
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
ufw allow 80
```

La app queda en `http://IP/`. Para actualizar: `git pull && bash deploy/deploy.sh`. Las credenciales demo se generan en `/srv/crm-django/credenciales-dev.txt`.
