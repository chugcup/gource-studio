#!/bin/bash

# Check run directory
if [ ! -d /var/run/gunicorn ]; then
    echo "Path '/var/run/gunicorn' not found.  Cannot create PID file."
    echo "Run the following to create this folder:"
    echo ""
    echo "  sudo mkdir -p /var/run/gunicorn"
    echo "  sudo chown -R ${USER}:${USER} /var/run/gunicorn"
    echo ""
    exit 1
fi

# Check log directory
if [ ! -d /var/log/gunicorn ]; then
    echo "Path '/var/log/gunicorn' not found.  Cannot create log files."
    echo "Run the following to create this folder:"
    echo ""
    echo "  sudo mkdir -p /var/log/gunicorn"
    echo "  sudo chown -R ${USER}:${USER} /var/log/gunicorn"
    echo ""
    exit 1
fi

source env/bin/activate
(cd gource_studio/; gunicorn -c ../config/gunicorn/dev.py)
sleep 1

if [ ! -f /var/run/gunicorn/dev.pid ]; then
    echo "Gunicorn failed to start properly (no PID detected)"
    echo "Check the application logs for suitable errors:"
    echo ""
    echo "  tail /var/log/gunicorn/dev.log"
    echo ""
    exit 2
fi

GUNICORN_PID=$(cat /var/run/gunicorn/dev.pid)
echo "  **DEVELOPMENT MODE**"
echo "Gunicorn process started (${GUNICORN_PID})"
echo "Use the following to stop running workers:"
echo ""
echo "  killall gunicorn"
echo ""
echo "Use the following to monitor application logs:"
echo ""
echo "  tail -f /var/log/gunicorn/dev.log"
echo ""
