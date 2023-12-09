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

# Default fonts to match normal text size from 720p
# - Applied to video by default unless 'font-scale' set
VIDEO_FONT_DEFAULTS = {
    '1024x576':  {'font-scale': '0.9'},
    '1280x720':  {'font-scale': '1.0'},
    '1600x900':  {'font-scale': '1.25'},
    '1920x1080': {'font-scale': '1.5'},
    '2560x1440': {'font-scale': '2'},
    '3840x2160': {'font-scale': '3'},
}


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

def position_validator(value, random=True):
    # [start|stop]-position validation (0.0-1.0 or 'random')
    try:
        value = float(value)
        range_validator(min_value=0, max_value=1)
    except:
        if not random or value != 'random':
            raise ValueError(f"Value must be between 0.0 and 1.0 (or 'random')")

def validate_position(random=True):
    "Factory to run position (0.0-1.0) range validation"
    def _do_validate(value):
        return position_validator(value, random=random)
    return _do_validate

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

def regex_pattern_validator(value):
    try:
        rv = RegexValidator(value, message="Invalid regex pattern")
        rv('sample')
    except:
        raise ValueError("Invalid regex pattern")

def validate_regex_pattern():
    def _do_validate(value):
        return regex_pattern_validator(value)
    return _do_validate


VALID_DISPLAY_ELEMENTS = ['bloom', 'date', 'dirnames', 'files', 'filenames', 'mouse',
                          'progress', 'root', 'tree', 'users', 'usernames']
def display_elements_validator(value):
    elements = str(value).strip().split(',')
    for elem in elements:
        if elem not in VALID_DISPLAY_ELEMENTS:
            raise ValueError(f"Value '{elem}' not a valid display element option")

def validate_display_elements():
    "Factory to run display elements (comma-separated list) validation"
    def _do_validate(value):
        return display_elements_validator(value)
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
        'version': (0, 41),
    },
    'stop-date': {
        'label': 'Stop Date',
        'type': 'datetime',
        'description': "Stop after the last entry prior to the supplied date and optional time.",
        'description_help': "This can be used to cut off the end period of a project, or generate a video focusing on a specific period of time (e.g. last quarter or year).",
        'placeholder': 'YYYY-MM-DD [HH:mm:ss]',
        'parser': dateparse.parse_datetime,
        'version': (0, 41),
    },
    'start-position': {
        'label': 'Start Position',
        'type': 'float',
        'description': "Begin at some position in the log (between 0.0 and 1.0 or 'random').",
        'default': 0.0,
        'parser': position_parser,
        'validator': validate_position(random=True),
    },
    'stop-position': {
        'label': 'Stop Position',
        'type': 'float',
        'description': "Stop (exit) at some position in the log (between 0.0 and 1.0).",
        'default': 1.0,
        'parser': position_parser,
        'validator': validate_position(random=False),
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
        'default': 16,
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
        'validator': validate_range(min_value=0.001)
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
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value"),
        'version': (0, 47),
    },
    'dir-colour': {
        'label': 'Directory Color',
        'type': 'str',
        'description': "Font color for directories (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFFFF',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value"),
        'version': (0, 38),
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
    'time-scale': {
        'label': 'Time Scale',
        'type': 'float',
        'description': "Change simulation time scale.",
        'parser': float,
        'default': 1.0,
        'validator': validate_range(min_value=0.0, max_value=4.0),
    },
    'elasticity': {
        'label': 'Elasticity',
        'type': 'float',
        'description': "Elasticity of nodes.",
        'parser': float,
        'default': 0.0,
        'validator': validate_range(min_value=0.0),
    },
    'key': {
        'label': 'File Extension Key',
        'type': 'bool',
        'description': "Show file extension key.",
        'parser': bool,
        'default': False,
    },
    'colour-images': {
        'label': 'Color Images',
        'type': 'bool',
        'description': "Colorize user images.",
        'parser': bool,
        'default': False,
    },
    'file-idle-time': {
        'label': 'File Idle Time',
        'type': 'int',
        'description': "Time files remain idle.",
        'parser': int,
        'default': 0,
        'validator': validate_range(min_value=0.0),
        'version': (0, 41),
    },
    'file-idle-time-at-end': {
        'label': 'File Idle Time (At End)',
        'type': 'int',
        'description': "Time files remain idle at end.",
        'parser': int,
        'default': 0,
        'validator': validate_range(min_value=0.0),
        'version': (0, 52),
    },
    'max-files': {
        'label': 'Maximum Files',
        'type': 'int',
        'description': "Max number of files (or 0 for no limit).",
        'parser': int,
        'default': 0,
        'validator': validate_range(min_value=0),
    },
    'max-file-lag': {
        'label': 'Maximum File Lag',
        'type': 'int',
        'description': "Max time files of a commit can take to appear.",
        'parser': int,
        'default': None,
        'validator': validate_range(min_value=0.001),
    },
    'bloom-multiplier': {
        'label': 'Bloom Multiplier',
        'type': 'float',
        'description': "Adjust the amount of bloom.",
        'parser': float,
        'default': 1.0,
        'validator': validate_range(min_value=0.001),
    },
    'bloom-intensity': {
        'label': 'Bloom Intensity',
        'type': 'float',
        'description': "Adjust the intensity of the bloom.",
        'parser': float,
        'default': 0.75,
        'validator': validate_range(min_value=0.001),
    },
    'camera-mode': {
        'label': 'Camera Mode',
        'type': 'str',
        'description': "Camera mode.",
        'parser': str,
        'default': 'overview',  # FIXME ???
        'options': [
            {'label': 'overview', 'value': 'overview'},
            {'label': 'track', 'value': 'track'}
        ],
    },
    'crop': {
        'label': 'Crop',
        'type': 'str',
        'description': "Crop view on an axis.",
        'parser': str,
        'default': '',
        'options': [
            {'label': 'none', 'value': ''},
            {'label': 'vertical', 'value': 'vertical'},
            {'label': 'horizontal', 'value': 'horizontal'}
        ],
    },
    'padding': {
        'label': 'Padding',
        'type': 'float',
        'description': "Camera view padding.",
        'parser': float,
        'default': 1.1,
        'validator': validate_range(min_value=0.001, max_value=1.999), # 0 < X < 2
    },
    'disable-auto-rotate': {
        'label': 'Disable Auto-Rotate',
        'type': 'bool',
        'description': "Disable automatic camera rotation.",
        'parser': bool,
        'default': False,
    },
    'date-format': {
        'label': 'Date Format',
        'type': 'str',
        'description': "Specify display date string (strftime format).",
        'parser': str,
        'default': '%A, %d %B, %Y %X',
        #'validator': ... # NOTE: difficult to validate; can contain non-strftime chars
    },
    'file-extensions': {
        'label': 'File Extensions Only',
        'type': 'bool',
        'description': "Show filename extensions only.",
        'parser': bool,
        'default': False,
    },
    'file-extension-fallback': {
        'label': 'File Extension Fallback',
        'type': 'bool',
        'description': "Use filename as extension if the extension is missing or empty.",
        'parser': bool,
        'default': False,
        'version': (0, 50),
    },
    'hide': {
        'label': 'Hide Elements',
        'type': 'str',
        'description': "Comma-separated list of display elements to hide.",
        'description_help': "Options: {0}".format(", ".join(VALID_DISPLAY_ELEMENTS)),
        'parser': str,
        'default': 'filenames,progress',
        'validator': validate_display_elements(),
    },
    'user-filter': {
        'label': 'User Filter',
        'type': 'str',
        'description': "Ignore usernames matching this regex.",
        'parser': str,
        'default': '',
        'validator': validate_regex_pattern(),
    },
    'user-show-filter': {
        'label': 'User Show Filter',
        'type': 'str',
        'description': "Show only usernames matching this regex.",
        'parser': str,
        'default': '',
        'validator': validate_regex_pattern(),
        'version': (0, 50),
    },
    'file-filter': {
        'label': 'File Filter',
        'type': 'str',
        'description': "Ignore file paths matching this regex.",
        'parser': str,
        'default': '',
        'validator': validate_regex_pattern(),
    },
    'file-show-filter': {
        'label': 'File Show Filter',
        'type': 'str',
        'description': "Show only file paths matching this regex.",
        'parser': str,
        'default': '',
        'validator': validate_regex_pattern(),
        'version': (0, 47),
    },
    'user-friction': {
        'label': 'User Friction',
        'type': 'float',
        'description': "Change the rate users slow down.",
        'parser': float,
        'default': 0.67,
        'validator': validate_range(min_value=0.001),
    },
    'user-scale': {
        'label': 'User Scale',
        'type': 'float',
        'description': "Change scale of users.",
        'parser': float,
        'default': 1.0,
        'validator': validate_range(min_value=0.001, max_value=100.0),
    },
    'max-user-speed': {
        'label': 'Max User Speed',
        'type': 'float',
        'description': "Speed users can travel per second.",
        'description_help': "Units are arbitrary limiter on acceleration (greater than 0).",
        'parser': float,
        'default': 500.0,
        'validator': validate_range(min_value=0.001),
    },
    'follow-user': {
        'label': 'Follow User',
        'type': 'str',
        'description': "Camera will automatically follow this user.",
        'parser': str,
        'default': '',
    },
    'highlight-dirs': {
        'label': 'Highlight Directories',
        'type': 'bool',
        'description': "Highlight the names of all directories.",
        'parser': bool,
        'default': False,
    },
    'highlight-user': {
        'label': 'Highlight User',
        'type': 'str',
        'description': "Highlight the name of a particular user.",
        'parser': str,
        'default': '',
    },
    'highlight-users': {
        'label': 'Highlight Users',
        'type': 'bool',
        'description': "Highlight the names of all users.",
        'parser': bool,
        'default': False,
    },
    'highlight-colour': {
        'label': 'Highlight Color',
        'type': 'str',
        'description': "Font color for highlighted users (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFFFF',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value"),
        'version': (0, 34),
    },
    'selection-colour': {
        'label': 'Selection Color',
        'type': 'str',
        'description': "Font color for selected users and files (in RRGGBB hex).",
        'parser': str,
        'default': 'FFFF4D',
        'validator': RegexValidator('^[0-9A-F]{6}$', message="Invalid RRGGBB hex value"),
        'version': (0, 38),
    },
    'dir-name-depth': {
        'label': 'Directory Name Depth',
        'type': 'int',
        'description': "Draw names of directories down to a specific depth.",
        'parser': int,
        #'default': 0,  # Unset if not provided
        'validator': validate_range(min_value=1),
        'version': (0, 41),
    },
    'dir-name-position': {
        'label': 'Directory Name Position',
        'type': 'float',
        'description': "Position along edge of the directory name.",
        'description_help': "Position is between 0.0 and 1.0, default is 0.5.",
        'parser': float,
        'default': 0.5,
        'validator': validate_range(min_value=0.1, max_value=1.0),
        'version': (0, 50),
    },
    'filename-time': {
        'label': 'Filename Time',
        'type': 'float',
        'description': "Duration to keep filenames on screen.",
        'parser': float,
        'default': 4.0,
        'validator': validate_range(min_value=2.0),
        'version': (0, 47),
    },
    'hash-seed': {
        'label': 'Hash Seed',
        'type': 'int',
        'description': "Change the seed of the hash function.",
        'parser': int,
        'default': 31,
        'version': (0, 34),
    },
    'fixed-user-size': {
        'label': 'Fixed User Size',
        'type': 'bool',
        'description': "Use a fixed (user) size throughout.",
        'parser': bool,
        'default': False,
        'version': (0, 52),
    },

    #################### UNSUPPORTED OPTIONS ####################
    # Arguments unsupported, either because they are configured
    # by software or would enable endless/interactive renders.
    #############################################################
    #'fullscreen': {},
    #'screen': {},
    #'viewport': {},
    #'multi-sampling': {},
    #'no-vsync': {},
    #'high-dpi': {},
    #'dont-stop': {},
    #'loop': {},
    #'stop-at-end': {},
    #'disable-auto-skip': {},
    #'realtime': {},
    #'no-time-travel': {},
    #'user-image-dir': {},
    #'default-user-image': {},
    #'log-command': {},
    #'log-format: {},
    #'load-config': {},
    #'save-config: {},
    #'output-ppm-stream': {},
    #'output-framerate': {},
    #'output-custom-log': {},
    #'window-position': {},
    #'frameless': {},
    #'disable-input': {},
    #'font-file': {},
    #'git-branch': {},
    #'logo': {},
    #'loop-delay-seconds': {},
    #'transparent': {},
    #'path': {},
}


# List of default (Gource) `ProjectOption` arguments that should
# be applied automatically to all new projects
#   (name, value, value_type)
PROJECT_OPTION_DEFAULTS = [
    ('key', 'true', 'bool'),
    ('hide', 'filenames,progress', 'str'),
    ('highlight-users', 'true', 'bool'),
    ('user-scale', '2.0', 'float'),
    ('dir-name-depth', '4', 'int'),
    ('bloom-multiplier', '0.5', 'float'),
]


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
