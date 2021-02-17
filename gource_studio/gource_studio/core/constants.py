from datetime import datetime
from django.utils import dateparse

# 16:9 video options
VIDEO_OPTIONS = [
    '1280x720',     # 720p
    '1920x1080',    # 1080p
    '3840x2160'     # 4K
]

# Gource options (that can be modified)
# - https://github.com/acaudwell/Gource/blob/master/README
GOURCE_OPTIONS = {
    'seconds-per-day': {
        'label': 'Seconds Per Day', 'type': 'float', 'default': 1.0,
        'description': "Speed of simulation in seconds per day.",
        'parser': float,
    },
    'auto-skip-seconds': {
        'label': 'Auto-Skip Seconds', 'type': 'float', 'default': 3.0,
        'description': "Skip to next entry if nothing happens for a number of seconds.",
        'parser': float,
    },
    'start-date': {
        'label': 'Start Date', 'type': 'datetime',
        'description': "Start with the first entry after the supplied date and optional time.",
        'parser': dateparse.parse_datetime,
    },
    'stop-date': {
        'label': 'Stop Date', 'type': 'datetime',
        'description': "Stop after the last entry prior to the supplied date and optional time.",
        'parser': dateparse.parse_datetime,
    },
}
