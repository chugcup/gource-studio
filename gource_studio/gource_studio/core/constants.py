from datetime import datetime
from django.utils import dateparse

# 16:9 video options
VIDEO_OPTIONS = [
    '1280x720',     # 720p
    '1920x1080',    # 1080p
    '3840x2160'     # 4K
]

## Validators/parsers for options
def range_validator(value, min_value=None, max_value=None):
    if min_validator is not None:
        if value < min_value:
            raise ValueError(f"Value cannot be less than {min_value}")
    if max_value is not None:
        if value > max_value:
            raise ValueError(f"Value cannot be greater than {max_value}")

def validate_range(min_value=None, max_value=None):
    "Factory to run min/max range validation"
    def _do_validate(value):
        return range_validator(value, min_value=min_value, max_value=max_value)
    return _do_validate

def position_validator(value):
    # [start|stop]-position validation (0.0-1.0 or 'random')
    try:
        value = float(value)
        range_validator(min_value=0, max_value=1)
    except:
        if value != 'random':
            raise ValueError(f"Value must be between 0.0 and 1.0 (or 'random')")

def position_parser(value):
    # [start|stop]-position parser (0.0-1.0 or 'random')
    if value == 'random':
        return 'random'
    return float(value)


# Gource options (that can be modified)
# - https://github.com/acaudwell/Gource/blob/master/README
GOURCE_OPTIONS = {
    'seconds-per-day': {
        'label': 'Seconds Per Day',
        'type': 'float',
        'description': "Speed of simulation in seconds per day.",
        'default': 1.0,
        'parser': float,
        'validator': validate_range(min_value=0),
    },
    'auto-skip-seconds': {
        'label': 'Auto-Skip Seconds',
        'type': 'float',
        'description': "Skip to next entry if nothing happens for a number of seconds.",
        'default': 3.0,
        'parser': float,
        'validator': validate_range(min_value=0),
    },
    'start-date': {
        'label': 'Start Date',
        'type': 'datetime',
        'description': "Start with the first entry after the supplied date and optional time.",
        'placeholder': 'YYYY-MM-DD [HH:mm:ss]',
        'parser': dateparse.parse_datetime,
    },
    'stop-date': {
        'label': 'Stop Date',
        'type': 'datetime',
        'description': "Stop after the last entry prior to the supplied date and optional time.",
        'placeholder': 'YYYY-MM-DD [HH:mm:ss]',
        'parser': dateparse.parse_datetime,
    },
    'start-position': {
        'label': 'Start Position',
        'type': 'float',
        'description': "Begin at some position in the log (between 0.0 and 1.0 or 'random').",
        'default': 0.0,
        'parser': position_parser,
        'validator': position_validator,
    },
    'stop-position': {
        'label': 'Stop Position',
        'type': 'float',
        'description': "Stop (exit) at some position in the log (between 0.0 and 1.0 or 'random').",
        'default': 1.0,
        'parser': position_parser,
        'validator': position_validator,
    },
    'stop-at-time': {   # Collides with --stop-at-end
        'label': 'Stop At Time',
        'type': 'float',
        'description': "Stop (exit) after a specified number of seconds.",
        'parser': float,
        'validator': validate_range(min_value=1)
    }
}

def _make_option(key, value_dict):
    "Convert dictionary option into list item (with 'name' set from key)"
    value_dict['name'] = key
    return value_dict

GOURCE_OPTIONS_LIST = [
    _make_option(k, v) for k, v in GOURCE_OPTIONS.items()
]
