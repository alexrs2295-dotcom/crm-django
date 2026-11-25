#!/usr/bin/env bash
# Despliegue idempotente. Ejecutar como root desde /srv/crm-django (tras clonar y crear .env).
set -euo pipefail
cd /srv/crm-django

[ -f .env ] || { echo "Falta /srv/crm-django/.env (copia deploy/.env.example)"; exit 1; }

[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt

set -a; . ./.env; set +a
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput

if [ "$(venv/bin/python manage.py shell -c 'from crm.models import Client; print(Client.objects.count())')" = "0" ]; then
    venv/bin/python manage.py seed_demo
fi

# SQLite necesita escribir en el directorio (journal), no solo en el fichero.
chown www-data:www-data /srv/crm-django db.sqlite3
chown -R www-data:www-data staticfiles

systemctl restart crm
