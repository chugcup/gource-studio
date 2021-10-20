#!/bin/bash

source env/bin/activate
cd gource_studio
celery -A gource_studio worker --loglevel=INFO
