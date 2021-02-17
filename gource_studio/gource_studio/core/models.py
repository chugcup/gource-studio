import os

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.timezone import make_aware, now as utc_now

from .utils import (
    analyze_gource_log,     #(data):
)


def get_build_logo_path(instance, filename):
    return f'projects/{instance.id}/{filename}'

def get_build_audio_path(instance, filename):
    return f'projects/{instance.id}/{filename}'

def get_project_log_path(instance, filename):
    return f'projects/{instance.id}/gource.log'

## TODO: Use custom OverwriteStorage() class
## https://stackoverflow.com/a/9523400

class Project(models.Model):
    """
    Base configuration for Gource project.
    """
    VCS_CHOICES = [
        ('git', 'Git'),
        ('hg', 'Mercurial')
    ]

    name = models.CharField(max_length=256)
    # Project URL
    project_url = models.TextField()
    # Branch name (most VCS limit to 28-50 characters)
    # + Defaults => (Git="master", Mercurial="default")
    project_branch = models.CharField(max_length=255, default='master')
    # VCS software used
    project_vcs = models.CharField(max_length=16, choices=VCS_CHOICES, default="git")
    # URL slug (optional)
    project_slug = models.SlugField(max_length=255, blank=True, null=True, unique=True)

    # Latest version of project Gource log (used for setting analysis)
    project_log = models.FileField(upload_to=get_project_log_path, blank=True, null=True)
    project_log_updated_at = models.DateTimeField(blank=True, null=True)
    # - Latest commit info cache
    project_log_commit_hash = models.CharField(max_length=64, blank=True, null=True)
    project_log_commit_time = models.DateTimeField(blank=True, null=True)
    project_log_commit_preview = models.CharField(max_length=128, blank=True, null=True)

    # Optional name to display in video
    build_title = models.CharField(max_length=255, default="")
    # Optional logo to display in video
    # TODO: logo location
    build_logo = models.ImageField(upload_to=get_build_logo_path, blank=True, null=True)
    # Optional background music (MP3)
    build_audio = models.FileField(upload_to=get_build_audio_path, blank=True, null=True)
    build_audio_name = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='projects', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    @property
    def latest_build(self):
        return self.get_latest_build()

    def get_latest_build(self):
        return self.builds.exclude(content='').order_by('-created_at').first()

    def analyze_log(self):
        """
        Perform analysis on current Gource log

        Returns num commits, date range, users list, ...
        """
        if not self.project_log or not os.path.isfile(self.project_log.path):
            raise RuntimeError("No Gource log found for this project")
        with open(self.project_log.path, 'r') as f:
            return analyze_gource_log(f.read())


class ProjectOption(models.Model):
    """
    Individual Gource option used for project build.

    Stores command line option without -- prefix. Example:

        name='seconds-per-day', value='0.5'

    """
    project = models.ForeignKey(Project, related_name='options', on_delete=models.CASCADE)
    name = models.CharField(max_length=128, blank=False)
    value = models.CharField(max_length=1024)
    value_type = models.CharField(max_length=32, blank=False)

    def __str__(self):
        return '{0}={1}'.format(self.name, self.value)


class ProjectCaption(models.Model):
    """
    Caption entry for Gource video

    Format line:

        TIMESTAMP|TEXT

    """
    project = models.ForeignKey(Project, related_name='captions', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(null=False, unique=True)
    text = models.CharField(max_length=255)

    class Meta:
        ordering = ('timestamp',)

    def __str__(self):
        return self.text


def get_video_build_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/video.mp4'

def get_video_screenshot_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/screenshot.jpg'

def get_video_thumbnail_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/thumb.jpg'

def get_build_project_log_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/gource.log'

def get_build_stdout_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/stdout.log'

def get_build_stderr_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/stderr.log'


class ProjectBuild(models.Model):
    """
    Individual build of Gource project (video).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('errored', 'Errored')
    ]

    project = models.ForeignKey(Project, related_name='builds', on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')

    project_branch = models.CharField(max_length=255, default='master')
    project_log = models.FileField(upload_to=get_build_project_log_path, blank=True, null=True)

    # Video/thumbnail data
    content = models.FileField(upload_to=get_video_build_path, blank=True, null=True)
    screenshot = models.ImageField(upload_to=get_video_screenshot_path, blank=True, null=True)
    thumbnail = models.ImageField(upload_to=get_video_thumbnail_path, blank=True, null=True)
    duration = models.PositiveIntegerField(null=True)
    size = models.PositiveIntegerField(null=True)

    # Timestamps
    queued_at = models.DateTimeField(null=True)
    running_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    errored_at = models.DateTimeField(null=True)

    ## Build fields
    # Process output logging
    stdout = models.FileField(upload_to=get_build_stdout_path, blank=True, null=True)
    stderr = models.FileField(upload_to=get_build_stderr_path, blank=True, null=True)
    # Brief description of error for user display
    error_description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.created_at.isoformat()

    @property
    def video_url(self):
        return reverse('project-build-video', [self.project_id, self.pk])

    @property
    def screenshot_url(self):
        return reverse('project-build-screenshot', [self.project_id, self.pk])

    @property
    def thumbnail_url(self):
        return reverse('project-build-thumbnail', [self.project_id, self.pk])

    ## Status transition methods

    def mark_queued(self):
        "Queue build for processing"
        if self.status == 'pending':
            self.status = 'queued'
            self.queued_at = utc_now()
            self.save(update_fields=['status', 'queued_at'])
        else:
            raise ValueError("Cannot queue build from \"%s\" status", self.status)

    def mark_running(self):
        "Mark build running"
        if self.status == 'queued':
            self.status = 'running'
            self.running_at = utc_now()
            self.save(update_fields=['status', 'running_at'])
        else:
            raise ValueError("Cannot mark build running from \"%s\" status", self.status)

    def mark_completed(self):
        "Mark build as completed"
        if self.status == 'running':
            self.status = 'completed'
            self.completed_at = utc_now()
            self.save(update_fields=['status', 'completed_at'])
        else:
            raise ValueError("Cannot mark build completed from \"%s\" status", self.status)

    def mark_errored(self, error_description=None):
        "Mark build as errored"
        # NOTE: no state check; can always transition to error state
        update_fields = []
        if self.status != 'error':
            self.status = 'error'
            self.errored_at = utc_now()
            update_fields += ['status', 'errored_at']
        if error_description is not None:
            self.error_description = error_description
            update_fields.append('error_description')
        if update_fields:
            self.save(update_fields=update_fields)


class ProjectBuildOption(models.Model):
    """
    Individual Gource option used for project build

    Stores command line option without -- prefix. Example:

        name='seconds-per-day', value='0.5'

    * NOTE: Cached copy of options used in base ProjectOption
    """
    build = models.ForeignKey(ProjectBuild, related_name='options', on_delete=models.CASCADE)
    name = models.CharField(max_length=128, blank=False)
    value = models.CharField(max_length=1024)
    value_type = models.CharField(max_length=32, blank=False)

    def __str__(self):
        return '{0}={1}'.format(self.name, self.value)


def get_global_avatar_path(instance, filename):
    return f'avatars/{filename}'

class UserAvatar(models.Model):
    """
    User avatar image to use in videos

    (Global registry)
    """
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to=get_global_avatar_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='uploaded_avatars', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    @property
    def aliases_count(self):
        return self.aliases.count()


class UserAvatarAlias(models.Model):
    """
    Alias names for a given avatar.

    (Global registry)
    """
    avatar = models.ForeignKey(UserAvatar, related_name='aliases', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


def get_project_avatar_path(instance, filename):
    return f'projects/{instance.id}/avatars/{filename}'

class ProjectUserAvatar(models.Model):
    """
    User avatar image to use in videos

    (Project override)
    """
    project = models.ForeignKey(Project, related_name='avatars', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to=get_project_avatar_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='uploaded_project_avatars', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    @property
    def aliases_count(self):
        return self.aliases.count()


class ProjectUserAvatarAlias(models.Model):
    """
    Alias names for a given avatar.

    (Project override)
    """
    avatar = models.ForeignKey(ProjectUserAvatar, related_name='aliases', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
