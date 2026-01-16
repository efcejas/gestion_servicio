web: gunicorn gestion_estudios.wsgi:application --log-file - --timeout 120
release: python manage.py collectstatic --noinput && python manage.py migrate
