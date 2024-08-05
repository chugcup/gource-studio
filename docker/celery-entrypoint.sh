#!/bin/sh

BASE_DIR=/opt/gource_studio

# Start Celery worker
celery -A gource_studio worker --loglevel=INFO
