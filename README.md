Requirements
=================

The project uses the following software:

- Python (3.6+)
- Django (3.0+)
- Celery
- FFmpeg (4.0+)
- Gource (0.50+)
- Redis
- SQLite


First Steps
=================

Ubuntu 18.04 LTS
-----------------

    sudo apt install ffmpeg git gource libjpeg8-dev libpng-dev mercurial python3 python3-dev python3-venv redis-server sqlite3 zlib1g-dev

The version of `ffmpeg` (3.4.8) included with Ubuntu 18.04 has some bugs related
to looping audio, which affects the audio mixing process.
While the application will run on 18.04, you should include a custom version
of FFmpeg on the system and set the `FFMPEG_PATH` setting to its local path.


Ubuntu 20.04 LTS
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

Next, copy the sample settings override file into place (and make any needed changes):

    cd gource_studio/gource_studio
    cp custom_settings.py.example custom_settings.py

By default, this will initialize using a SQLite database (`app.db`)
To configure an alternate DB storage, edit the `DATABASES` dictionary
within the `custom_settings.py` file.

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

