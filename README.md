Requirements
=================

The project uses the following software:

- Python (3.8+)
- Django (3.2+)
- Celery
- FFmpeg (4.0+)
- Gource (0.50+)
- Redis
- SQLite / PostgreSQL


First Steps
=================

Ubuntu 20.04 / 22.04 LTS
------------------------

    sudo apt install ffmpeg git gource libjpeg8-dev libpng-dev mercurial python3 python3-dev python3-venv redis-server sqlite3 zlib1g-dev

**NOTE:** The version of `gource` (0.50/0.51) included with these Ubuntu versions has
an issue where the font scale is not applied to the file extension sidebar.  On larger
resolutions (1920x1080 or higher) this can make the widget text too small to recognize.

To address this, you can manually include a newer version of ``gource`` on the system
and set the absolute path using the ``GOURCE_PATH`` setting.


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

First, copy the sample settings override file into place (and make any needed changes):

    cd gource_studio/gource_studio
    cp custom_settings.py.example custom_settings.py

By default, this will initialize using a SQLite database (`app.db`)
To configure an alternate DB storage, edit the `DATABASES` dictionary
within the `custom_settings.py` file.

Next, with the virtual environment active run the initial migrations

    python3 gource_studio/manage.py migrate

Lastly, create a default superuser account for the application

    python3 gource_studio/manage.py createsuperuser


Run Services
==================

Application uses Redis as a cache backend, so ensure `redis-server` is running.

Next, start the Celery task runner service:

    # Runs in foreground
    ./run_celery.sh

Last, start the main Django application service

    # Runs in foreground
    ./run.sh



Other Notes
==================

Test Suite
----------------------------------

Unit tests can be run by first installing test requirements

    source env/bin/activate     # Activate virtualenv
    pip install -c constraints.txt -r requirements-test.txt

Then, use the provided script

    # Run pytest (optionally with coverage)
    ./run_tests.sh


Run Headless with Xvfb (Linux)
----------------------------------

If you are running on a Linux system, you may be able to run the Gource render
in a headless mode using **Xvfb** (X virtual frame buffer).  This avoids needing
an active GUI (otherwise required by Gource), and may result in faster builds.

On Ubuntu, install the `xvfb` package:

    sudo apt install xvfb

Then enable `USE_XVFB` in the app settings:

    # custom_settings.py
    USE_XVFB = True

