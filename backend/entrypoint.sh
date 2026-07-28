#!/bin/sh
set -eu

if [ "${SKIP_STARTUP:-false}" != "true" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi
exec "$@"
