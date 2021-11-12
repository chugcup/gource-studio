from split_settings.tools import optional, include

include(
    'config/base.py',
    optional('config/secrets.py'),
    optional('custom_settings.py')
)
