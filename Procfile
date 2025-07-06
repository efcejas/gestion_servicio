web: gunicorn gestion_estudios.wsgi:application --log-file -
release: python manage.py collectstatic --noinput && python manage.py migrate
