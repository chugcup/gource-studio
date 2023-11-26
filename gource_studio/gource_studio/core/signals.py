import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .constants import PROJECT_OPTION_DEFAULTS
from .models import Project, ProjectOption


@receiver(post_save, sender=Project, dispatch_uid='gource_studio.core.signals.project_post_save_handler')
def project_post_save_handler(sender, instance, created, **kwargs):
    if not created:
        return

    # Upon creation, automatically load default Gource options to project
    logging.debug("Loading %s default options onto Project ID=%s", len(PROJECT_OPTION_DEFAULTS), instance.pk)
    for option in PROJECT_OPTION_DEFAULTS:
        ProjectOption.objects.create(
            project=instance,
            name=option[0],
            value=option[1],
            value_type=option[2]
        )
