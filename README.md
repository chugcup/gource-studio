Requirements
=================

The project uses the following software:

- Python (3.6+)
- Django (3.0+)
- Celery
- Redis
- SQLite
- FFmpeg


First Steps
=================

Ubuntu 18.04+
-----------------

    sudo apt install ffmpeg git gource libjpeg8-dev libpng-dev mercurial python3 python3-dev python3-venv redis-server sqlite3 zlib1g-dev


Python Setup
-----------------

Create a virtual environment and install needed packages

    python3 -m venv env         # Create virtualenv
    source env/bin/activate     # Activate virtualenv
    pip install -c constraints.txt -r requirements.txt

On MacOS, if certain packages give you trouble, you can set the ARCHFLAGS
environment variable to prevent Xcode from building the wrong binary type

    ARCHFLAGS="-arch x86_64" pip install Pillow


Initialize App
=================

With environment active, run initial migrations

    python3 gource_studio/manage.py migrate

By default, this will initialize using a SQLite database (`app.db`)
To configure an alternate DB storage, edit the following settings file:

    gource_studio/gource_studio/custom_settings.py


Run Services
==================

Application uses Redis as a cache backend, so ensure `redis-server` is running.

Next, start the Celery task runner service:

    # Runs in foreground
    ./run_celery.sh

Last, start the main Django application service

    # Runs in foreground
    ./run.sh



