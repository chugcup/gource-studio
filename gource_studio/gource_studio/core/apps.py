from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'gource_studio.core'

    def ready(self):
        from . import signals
