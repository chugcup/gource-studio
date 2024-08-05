FROM debian:bookworm-slim
MAINTAINER jgordon005@gmail.com

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/gource_studio

# Install OS packages
RUN apt update && apt install -y ffmpeg git gource libjpeg-dev libpng-dev \
                mercurial python3 python3-dev python3-pip python3-venv \
                redis-server sqlite3 xvfb zlib1g-dev

# Copy in needed artifacts
COPY constraints.txt ./
COPY requirements.txt ./

# Install Python environment packages
RUN pip install --break-system-packages --upgrade -c constraints.txt pip \
    && pip install --break-system-packages -c constraints.txt -r requirements.txt

# Copy application code, startup scripts and Docker settings
COPY ./docker/celery-entrypoint.sh ./
COPY ./docker/django-entrypoint.sh ./
COPY gource_studio ./
COPY ./docker/docker_settings.py ./gource_studio/custom_settings.py

# Run command on container startup (in foreground)
CMD ["/opt/gource_studio/django-entrypoint.sh"]
