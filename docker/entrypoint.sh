#!/bin/bash
set -euo pipefail

envsubst < statuspage/configuration.py.template > statuspage/configuration.py

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
