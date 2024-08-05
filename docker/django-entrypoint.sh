#!/bin/sh

BASE_DIR=/opt/gource_studio

# Perform database migrations/upgrades
python3 ${BASE_DIR}/manage.py migrate

# Create default superuser
python3 ${BASE_DIR}/manage.py initadmin

# Start Django application
python3 ${BASE_DIR}/manage.py runserver 0.0.0.0:8000
