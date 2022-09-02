from datetime import datetime
import re

from django.core.validators import RegexValidator
from django.utils import dateparse


# 16:9 video options
VIDEO_OPTIONS = [
    ('1024x576',  '1024 x 576'),
    ('1280x720',  '1280 x 720'),    # 720p
    ('1600x900',  '1600 x 900'),
    ('1920x1080', '1920 x 1080'),   # 1080p
    ('2560x1440', '2560 x 1440'),
    ('3840x2160', '3840 x 2160'),   # 4K
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

def length_validator(value, min_length=None, max_length=None):
    if min_length is not None:
        if len(value) < min_length:
            raise ValueError(f"Value must be at least {min_length} characters")
    if max_length is not None:
        if len(value) > max_length:
            raise ValueError(f"Value cannot exceed {max_length} characters")

def validate_length(min_length=None, max_length=None):
    "Factory to run min/max length validation"
    def _do_validate(value):
        return length_validator(value, min_length=min_length, max_length=max_length)
    return _do_validate


# Gource options (that can be modified)
# - https://github.com/acaudwell/Gource/blob/master/README
GOURCE_OPTIONS = {
    'seconds-per-day': {
        'label': 'Seconds Per Day',
        'type': 'float',
        'description': "Speed of simulation in seconds per day.",
        'description_help': "This is the main setting to adjust when determining video length.  Lower means a shorter video, and for most projects this should be less than 0.5.",
        'default': 1.0,
        'parser': float,
        'validator': validate_range(min_value=0),
    },
    'auto-skip-seconds': {
        'label': 'Auto-Skip Seconds',
        'type': 'float',
        'description': "Skip to next entry if nothing happens for a number of seconds.",
        'description_help': "A lower value will help skip large segments of idle time.",
        'default': 3.0,
        'parser': float,
        'validator': validate_range(min_value=0),
    },
    'start-date': {
        'label': 'Start Date',
        'type': 'datetime',
        'description': "Start with the first entry after the supplied date and optional time.",
        'description_help': "This can be used to cut off an early period of a project, or generate a video focusing on a specific period of time (e.g. last quarter or year).",
        'placeholder': 'YYYY-MM-DD [HH:mm:ss]',
        'parser': dateparse.parse_datetime,
    },
    'stop-date': {
        'label': 'Stop Date',
        'type': 'datetime',
        'description': "Stop after the last entry prior to the supplied date and optional time.",
        'description_help': "This can be used to cut off the end period of a project, or generate a video focusing on a specific period of time (e.g. last quarter or year).",
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
        'description_help': "This is useful to generate a video of an exact duration.",
        'parser': float,
        'validator': validate_range(min_value=1)
    },
    # Captions
    'caption-size': {
        'label': 'Caption Size',
        'type': 'int',
        'description': "Caption font size (1-100).",
        'parser': int,
        'default': 25,  # ???
        'validator': validate_range(min_value=1, max_value=100)
    },
    'caption-colour': {
        'label': 'Caption Color',
        'type': 'str',
        'description': "Caption color (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFFFF',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value")
    },
    'caption-duration': {
        'label': 'Caption Duration',
        'type': 'float',
        'description': "Caption duration (in seconds).",
        'parser': float,
        'default': 10.0,
        'validator': validate_range(min_value=0.5)
    },
    'caption-offset': {
        'label': 'Caption Offset',
        'type': 'int',
        'description': "Caption horizontal (x) offset (0 to center captions).",
        'parser': int,
        'default': 0,
        #'validator': validate_range(min_value=0)   # Can be negative?
    },
    'font-scale': {
        'label': 'Font Scale',
        'type': 'float',
        'description': "Scale the size of all fonts (0.0-10.0).",
        'parser': float,
        'default': 1.0,
        'validator': validate_range(min_value=0.0, max_value=10.0),
        'version': (0, 50),
    },
    'font-size': {
        'label': 'Font Size',
        'type': 'int',
        'description': "Font size used by date and title (1-100).",
        'parser': int,
        'default': 16,
        'validator': validate_range(min_value=1, max_value=100),
    },
    'file-font-size': {
        'label': 'Font Size (Files)',
        'type': 'int',
        'description': "Font size used for filenames (1-100).",
        'parser': int,
        'default': 14,
        'validator': validate_range(min_value=1, max_value=100),
        'version': (0, 50),
    },
    'dir-font-size': {
        'label': 'Font Size (Dirs)',
        'type': 'int',
        'description': "Font size used for directory names (1-100).",
        'parser': int,
        'default': 14,
        'validator': validate_range(min_value=1, max_value=100),
        'version': (0, 50),
    },
    'user-font-size': {
        'label': 'Font Size (Users)',
        'type': 'int',
        'description': "Font size used for user names (1-100).",
        'parser': int,
        'default': 14,
        'validator': validate_range(min_value=1, max_value=100),
        'version': (0, 50),
    },
    'font-colour': {
        'label': 'Font Color',
        'type': 'str',
        'description': "Font color used by date and title (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFFFF',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value")
    },
    'background-colour': {
        'label': 'Background Color',
        'type': 'str',
        'description': "Background color (in RRGGBB hex).",
        'parser': str,
        'default': '000000',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value")
    },
    'filename-colour': {
        'label': 'Filename Color',
        'type': 'str',
        'description': "Font color for filenames (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFFFF',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value")
    },
    'dir-colour': {
        'label': 'Directory Color',
        'type': 'str',
        'description': "Font color for directories (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFFFF',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value")
    },
    'logo-offset': {
        'label': 'Logo Offset',
        'type': 'str',
        'description': "Offset position of the logo (XxY format).",
        'description_help': "Logo defaults to bottom-right corner. This is only used if a logo image has been uploaded.",
        'parser': str,
        'default': '20x20',
        'validator': RegexValidator('^[0-9]+x[0-9]+$', message="Invalid XxY offset value")
    },
    'title': {
        'label': 'Video Title',
        'type': 'str',
        'description': "Set a video title.",
        'description_help': "This is centered in the bottom-left of the video.",
        'default': '',
        'parser': str,
    },
}

def _make_option(key, value_dict):
    "Convert dictionary option into list item (with 'name' set from key)"
    value_dict['name'] = key
    return value_dict

def option_to_dict(key):
    "Convert to object suitable for JSON serialization"
    opt = GOURCE_OPTIONS[key]
    return {
        'name': key,
        'label': opt['label'],
        'type': opt['type'],
        'description': opt['description'],
        'description_help': opt.get('description_help', None),
        'placeholder': opt.get('placeholder', None),
        'default': opt.get('default', None),
    }


def filter_by_version(input_list, version=None):
    """
    Given an input list, return options filted by minimum 'version'.

    If 'version' key unavailable, will attempt to look up using 'name'.

    Input `version` should be a string or integer list (X, Y, Z).
    """
    if version is None:
        return input_list
    if isinstance(version, str):
        version = tuple([int(n) for n in version.split('.')])
    def _check(opt):
        if opt.get('version') is None:
            if 'name' in opt and opt['name'] in GOURCE_OPTIONS \
                    and GOURCE_OPTIONS[opt['name']].get('version') is not None:
                return GOURCE_OPTIONS[opt['name']]['version'] <= version
            return True
        return opt['version'] <= version
    return [opt for opt in input_list if _check(opt)]


GOURCE_OPTIONS_LIST = [
    _make_option(k, v) for k, v in GOURCE_OPTIONS.items()
]
GOURCE_OPTIONS_JSON = [
    option_to_dict(k) for k, v in GOURCE_OPTIONS.items()
]
