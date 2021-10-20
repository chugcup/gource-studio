#!/bin/bash

source env/bin/activate
cd gource_studio
python manage.py runserver 0.0.0.0:8000
