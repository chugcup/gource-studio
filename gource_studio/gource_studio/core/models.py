import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group as AuthGroup
from django.core.files.base import ContentFile
from django.core.validators import validate_slug, RegexValidator
from django.db import models
from django.db.models import F
from django.db.models.fields.files import FieldFile
from django.urls import reverse
from django.utils.functional import SimpleLazyObject
from django.utils import timezone

#from .managers import ProjectManager
from .constants import VIDEO_OPTIONS
from .managers import ProjectQuerySet
from .tasks import generate_gource_build
from .utils import (
    analyze_gource_log,     #(data):
)


def get_project_build_logo_path(instance, filename):
    return f'projects/{instance.id}/{filename}'

def get_project_build_background_path(instance, filename):
    return f'projects/{instance.id}/{filename}'

def get_project_build_audio_path(instance, filename):
    return f'projects/{instance.id}/{filename}'

def get_project_project_log_path(instance, filename):
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
    project_url = models.TextField(blank=True, default="")
    # Flag to indicate if URL can be used to fetch VCS logs
    project_url_active = models.BooleanField(default=False)
    # Branch name (most VCS limit to 28-50 characters)
    # + Defaults => (Git="master", Mercurial="default")
    project_branch = models.CharField(max_length=256, default='master')
    # VCS software used
    project_vcs = models.CharField(max_length=16, choices=VCS_CHOICES, default="git")
    # URL slug (optional)
    project_slug = models.SlugField(max_length=256, blank=True, null=True, unique=True,
                                    error_messages={"unique": "Project with this slug already exists."})

    # Latest version of project Gource log (used for setting analysis)
    project_log = models.FileField(upload_to=get_project_project_log_path, blank=True, null=True)
    project_log_updated_at = models.DateTimeField(blank=True, null=True)
    # - Latest commit info cache
    project_log_commit_hash = models.CharField(max_length=64, blank=True, null=True)
    project_log_commit_time = models.DateTimeField(blank=True, null=True)
    project_log_commit_preview = models.CharField(max_length=128, blank=True, null=True)

    # Output video size (16:9 aspect ratio only)
    video_size = models.CharField(max_length=16, default="1280x720", choices=VIDEO_OPTIONS)
    # Optional name to display in video
    build_title = models.CharField(max_length=256, default="", blank=True)
    # Optional logo/background to display in video
    build_logo = models.ImageField(upload_to=get_project_build_logo_path, blank=True, null=True)
    build_background = models.ImageField(upload_to=get_project_build_background_path, blank=True, null=True)
    # Optional background music (MP3)
    build_audio = models.FileField(upload_to=get_project_build_audio_path, blank=True, null=True)
    build_audio_name = models.CharField(max_length=256, null=True, blank=True)

    # Determine if project is publicly-visible or restricted to project members
    is_public = models.BooleanField(default=True)
    # Flag to indicate project (settings) updated since last build
    is_project_changed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='projects_created', on_delete=models.CASCADE, null=True, blank=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('api-project-detail', args=[self.pk])

    def clean(self):
        if self.project_slug is not None:
            if self.project_slug.strip() == '':
                self.project_slug = None
            else:
                # Validate normal slug format...
                validate_slug(self.project_slug)
                # ...and does not contain only digits (to avoid confusion with PK)
                RegexValidator(r'^\d+$', message="Slug cannot contain only numbers.", inverse_match=True)(self.project_slug)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def latest_build(self):
        return self.get_latest_build()

    def get_latest_build(self):
        if hasattr(self, '_cached_latest_build'):
            return self._cached_latest_build[0] if len(self._cached_latest_build) else None
        return self.builds.exclude(content='').order_by('-created_at').first()

    @property
    def has_build_waiting(self):
        return self.builds.filter(status__in=['pending', 'queued', 'running']).exists()

    def set_project_changed(self, changed=True):
        if self.is_project_changed is bool(changed):
            return
        self.is_project_changed = bool(changed)
        self.save(update_fields=['is_project_changed'])

    def analyze_log(self):
        """
        Perform analysis on current Gource log

        Returns num commits, date range, users list, ...
        """
        if not self.project_log or not os.path.isfile(self.project_log.path):
            raise RuntimeError("No Gource log found for this project")
        with open(self.project_log.path, 'r') as _file:
            return analyze_gource_log(_file.read())

    def generate_captions_file(self):
        """
        Return a new string containing "captions" file content from current captions.

        Returns None if no captions defined.
        """
        caption_lines = []
        for pcaption in self.captions.all().order_by('timestamp'):
            caption_lines.append(pcaption.to_text())
        if not caption_lines:
            return None
        return caption_lines

    def check_permission(self, actor, action):
        """
        Return True/False if `User` can perform `action` on this project.

        The "edit" and "delete" permissions checks the `ProjectMember`/`ProjectMemberGroup` relation.
        For "view", checks the `is_public` flag set on project.
        """
        if not isinstance(actor, (get_user_model(), AnonymousUser, SimpleLazyObject)):
            raise ValueError(f"Invalid 'actor' instance: {type(actor)}")
        action = str(action).lower()
        if action == 'get':
            action = 'view'
        elif action in ['post', 'put', 'patch']:
            action = 'edit'
        if action not in ["view", "edit", "delete"]:
            raise ValueError(f"Invalid 'action' given: {action}")

        # Early short-circuit for superusers
        if actor.is_superuser or actor == self.created_by:
            return True
        # Anonymous user check
        elif actor.is_anonymous:
            if action == 'view':
                return self.is_public
            return False

        # Check each permission
        # + "view" - View project (if not `is_public` set)
        max_role = None
        member_groups = self.member_groups.all()
        if action == 'view':
            if not self.is_public:
                return self.members.filter(user=actor).exists() \
                    or actor.groups.filter(id__in=member_groups).exists()
            return True

        # Determine maximum project membership role
        # - NOTE: Direct-project membership overrides any role in Groups
        project_member = self.members.filter(user=actor)
        if project_member:
            max_role = project_member[0].role
        else:
            # Search any groups associated with Project
            project_group_roles = [g.role for g in member_groups.filter(id__in=actor.groups.all())]
            if project_group_roles:
                if 'maintainer' in project_group_roles:
                    max_role = 'maintainer'
                elif 'developer' in project_group_roles:
                    max_role = 'developer'
                elif 'viewer' in project_group_roles:
                    max_role = 'viewer'

        # + "edit" - Create new builds, change settings, add captions/user aliases
        if action == 'edit':
            return max_role in ['developer', 'maintainer']
        # + "delete" - Delete overall project
        elif action == 'delete':
            return max_role in ['maintainer']

        return ValueError(f"Invalid 'action' given: {action}")

    def create_build(self, *, defer_queue=False):
        """
        Create a new ProjectBuild instance from this Project.

        By default, build will be immediately queued for processing by
        background Celery instance.  This can be disabled and deferred
        to a later time using

            create_build(defer_queue=True)

        Returns new ProjectBuiild instance
        """
        if not bool(self.project_log):
            raise RuntimeError("Project does not have a valid 'project_log'")

        # Create new build (immediately in "queued" state)
        build = ProjectBuild.objects.create(
            project=self,
            project_branch=self.project_branch,
            project_log_commit_hash=self.project_log_commit_hash,
            project_log_commit_time=self.project_log_commit_time,
            project_log_commit_preview=self.project_log_commit_preview,
            video_size=self.video_size,
            status='queued' if not defer_queue else 'pending',
            queued_at=timezone.now() if not defer_queue else None
        )

        # Copy snapshot of `project_log` file
        with open(self.project_log.path, 'rb') as _file:
            build.project_log.save('gource.log', ContentFile(_file.read()))
        # Copy other optional artifacts
        if self.build_audio:
            # Background audio
            build.build_audio_name = self.build_audio_name
            with open(self.build_audio.path, 'rb') as _file:
                build.build_audio.save(os.path.basename(self.build_audio.name),
                                       ContentFile(_file.read()))
        if self.build_logo:
            # Project logo
            with open(self.build_logo.path, 'rb') as _file:
                build.build_logo.save(os.path.basename(self.build_logo.name),
                                      ContentFile(_file.read()))
        if self.build_background:
            # Project background
            with open(self.build_background.path, 'rb') as _file:
                build.build_background.save(os.path.basename(self.build_background.name),
                                            ContentFile(_file.read()))

        # Copy over build options for archival
        build_options = []
        for option in self.options.all():
            build_options.append(
                ProjectBuildOption(
                    build=build,
                    name=option.name,
                    value=option.value,
                    value_type=option.value_type
                )
            )
        if build_options:
            ProjectBuildOption.objects.bulk_create(build_options)

        # Copy over captions for archival
        build_captions = []
        for caption in self.captions.all():
            build_captions.append(
                ProjectBuildCaption(
                    build=build,
                    timestamp=caption.timestamp,
                    text=caption.text,
                )
            )
        if build_captions:
            ProjectBuildCaption.objects.bulk_create(build_captions)

            # Save captions to file prior to build
            captions_list = self.generate_captions_file()
            if captions_list is not None:
                captions_data = "\n".join(captions_list)
                build.project_captions.save('captions.txt', ContentFile(captions_data))

        # Send to background worker
        if not defer_queue:
            generate_gource_build.delay(build.id)

        return build


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

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return '{0}={1}'.format(self.name, self.value)

    def to_dict(self):
        return {
            "name": self.name,
            "value": self.value,
            "value_type": self.value_type
        }


def get_video_build_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/video.mp4'

def get_video_screenshot_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/screenshot.jpg'

def get_video_thumbnail_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/thumb.jpg'

def get_build_project_log_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/gource.log'

def get_build_project_captions_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/captions.txt'

def get_build_logo_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/{filename}'

def get_build_background_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/{filename}'

def get_build_audio_path(instance, filename):
    return f'projects/{instance.project_id}/builds/{instance.id}/{filename}'

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
        ('canceled', 'Canceled'),
        ('running', 'Running'),
        ('aborted', 'Aborted'),
        ('completed', 'Completed'),
        ('errored', 'Errored')
    ]

    project = models.ForeignKey(Project, related_name='builds', on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')

    project_branch = models.CharField(max_length=256, default='master')
    project_log = models.FileField(upload_to=get_build_project_log_path, blank=True, null=True)
    # - Latest commit info cache
    project_log_commit_hash = models.CharField(max_length=64, blank=True, null=True)
    project_log_commit_time = models.DateTimeField(blank=True, null=True)
    project_log_commit_preview = models.CharField(max_length=128, blank=True, null=True)
    # Captions file
    project_captions = models.FileField(upload_to=get_build_project_captions_path, blank=True, null=True)
    build_logo = models.ImageField(upload_to=get_build_logo_path, blank=True, null=True)
    build_background = models.ImageField(upload_to=get_build_background_path, blank=True, null=True)
    # Optional background music (MP3)
    build_audio = models.FileField(upload_to=get_build_audio_path, blank=True, null=True)
    build_audio_name = models.CharField(max_length=256, null=True, blank=True)

    # Video/thumbnail data
    video_size = models.CharField(max_length=16, default="1280x720", choices=VIDEO_OPTIONS)
    content = models.FileField(upload_to=get_video_build_path, blank=True, null=True)
    screenshot = models.ImageField(upload_to=get_video_screenshot_path, blank=True, null=True)
    thumbnail = models.ImageField(upload_to=get_video_thumbnail_path, blank=True, null=True)
    duration = models.PositiveIntegerField(null=True)
    size = models.PositiveIntegerField(null=True)   # Cached copy of `.content_size`

    # Timestamps
    queued_at = models.DateTimeField(null=True)
    running_at = models.DateTimeField(null=True)
    aborted_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    errored_at = models.DateTimeField(null=True)

    ## Build fields
    current_build_stage = models.CharField(max_length=64, blank=True, null=True)
    current_build_message = models.CharField(max_length=512, blank=True, null=True)
    # Process output logging
    stdout = models.FileField(upload_to=get_build_stdout_path, blank=True, null=True)
    stderr = models.FileField(upload_to=get_build_stderr_path, blank=True, null=True)
    # Brief description of error for user display
    error_description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return self.created_at.isoformat()

    def get_absolute_url(self):
        return reverse('api-project-build-detail', args=[self.project_id, self.pk])

    @property
    def video_url(self):
        return reverse('project-build-video', args=[self.project_id, self.pk])

    @property
    def screenshot_url(self):
        return reverse('project-build-screenshot', args=[self.project_id, self.pk])

    @property
    def thumbnail_url(self):
        return reverse('project-build-thumbnail', args=[self.project_id, self.pk])

    @property
    def content_size(self):
        if self.content:
            return os.path.getsize(self.content.path)
        return None

    @property
    def is_finished(self):
        return self.status in ['aborted', 'completed', 'errored']

    @property
    def is_waiting(self):
        return self.status in ['pending', 'queued']

    @property
    def has_thumbnail(self):
        return bool(self.thumbnail)

    @property
    def build_stage_information(self):
        return self.get_build_stage_information()

    @property
    def build_stage_percent(self):
        return self.get_build_stage_percent()

    @property
    def current_build_duration(self):
        if self.status == 'running' and self.running_at:
            return (timezone.now()-self.running_at).total_seconds()
        return None

    ## Status transition methods

    def mark_queued(self):
        "Queue build for processing"
        if self.status == 'pending':
            self.status = 'queued'
            self.queued_at = timezone.now()
            self.save(update_fields=['status', 'queued_at'])
        else:
            raise ValueError("Cannot queue build from \"%s\" status", self.status)

    def mark_canceled(self):
        "Mark pending/queued build as canceled"
        if self.status in ['pending', 'queued']:
            self.status = 'canceled'
            self.aborted_at = timezone.now()
            self.save(update_fields=['status', 'aborted_at'])
        else:
            raise ValueError("Cannot mark build canceled from \"%s\" status", self.status)

    def mark_running(self):
        "Mark build running"
        if self.status == 'queued':
            self.status = 'running'
            self.running_at = timezone.now()
            self.save(update_fields=['status', 'running_at'])
        else:
            raise ValueError("Cannot mark build running from \"%s\" status", self.status)

    def mark_aborted(self):
        "Mark running build as aborted"
        if self.status == 'running':
            self.status = 'aborted'
            self.aborted_at = timezone.now()
            self.save(update_fields=['status', 'aborted_at'])
        else:
            raise ValueError("Cannot mark build aborted from \"%s\" status", self.status)

    def mark_completed(self):
        "Mark build as completed"
        if self.status == 'running':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'completed_at'])
        else:
            raise ValueError("Cannot mark build completed from \"%s\" status", self.status)

    def mark_errored(self, error_description=None):
        "Mark build as errored"
        # NOTE: no state check; can always transition to error state
        update_fields = []
        if self.status != 'errored':
            self.status = 'errored'
            self.errored_at = timezone.now()
            update_fields += ['status', 'errored_at']
        if error_description is not None:
            self.error_description = error_description
            update_fields.append('error_description')
        if update_fields:
            self.save(update_fields=update_fields)

    def set_build_stage(self, stage, message=None):
        "Set the current build stage (optionally with message)"
        self.current_build_stage = stage
        self.current_build_message = message
        self.save(update_fields=['current_build_stage', 'current_build_message'])

    def get_build_stage_information(self):
        build_stages = ["init", "gource", "thumbnail", "success"]
        if bool(self.build_audio_name):
            build_stages = ["init", "gource", "audio", "thumbnail", "success"]
        max_stages = len(build_stages)-1    # Success doesn't count

        if self.current_build_stage == "success":
            return [max_stages, max_stages]

        if self.current_build_stage in build_stages:
            return [
                build_stages.index(self.current_build_stage)+1,
                max_stages
            ]
        return [None, None]

    def get_build_duration(self):
        "Returns total runtime duration of build (from 'running' -> 'completed'|'errored')"
        if not self.running_at:
            return None
        if self.completed_at:
            return (self.completed_at - self.running_at).total_seconds()
        elif self.errored_at:
            return (self.errored_at - self.running_at).total_seconds()
        return None

    def get_previous_build(self, success=True):
        qs = ProjectBuild.objects.filter(project=self.project, id__lt=self.id)
        if success:
            qs = qs.exclude(content='')
        return qs.order_by('-id').first()

    def get_build_stage_percent(self):
        """
        Provide a guess (0-100%) of how far along the build is.
        """
        if self.status == 'completed':
            return 100
        elif self.status in ['pending', 'queued', 'canceled', 'aborted']:
            return 0
        elif self.status in ['errored', 'aborted']:
            return 10   # Controversial, I know
        elif self.running_at:
            # Running - here's where we do work
            # 1. If there is a previously successful build, use that duration
            #    as the anticipated amount.  Unless they tweaked settings, it
            #    should be at least close.
            prev_build_time = None
            prev_successful_build = self.get_previous_build(success=True)
            if prev_successful_build:
                prev_build_time = prev_successful_build.get_build_duration()
            if prev_build_time:
                cur_duration = (timezone.now()-self.running_at).total_seconds()
                if cur_duration < 0:
                    cur_duration = 0
                build_percent = int((cur_duration / prev_build_time)*100)
            # 2. If no prior build, guess based on number of stages
            else:
                cur_stage, max_stage = self.get_build_stage_information()
                if cur_stage is not None:
                    return int((cur_stage/max_stage)*100)
            # Set some upper/lower bounds to give *some* progress
            # (due to its active running state)
            if build_percent >= 99:
                build_percent = 99
            elif build_percent < 5:
                build_percent = 5
            return build_percent
        return 0

    def queue_build(self):
        """
        Queue the current buiid for video processing.

        Only used if ProjectBuild initialize in 'pending' state.

        Returns True if build queued successfully; False otherwise
        """
        if self.status != 'pending':
            return False
        self.mark_queued()
        generate_gource_build.delay(self.id)
        return True

    def clone_build(self, *, remix_audio=False, defer_queue=False):
        """
        Create a new ProjectBuild instance from this ProjectBuild.

        By default, build will be immediately queued for processing by
        background Celery instance.  This can be disabled and deferred
        to a later time using

            clone_build(defer_queue=True)

        Optionally can provide a new `build_audio` FileField (generally
        from `Project` instance) to use an use prior video with new audio.

            clone_build(remix_audio=project.build_audio)

        To remove audio from an existing build, use:

            clone_build(remix_audio=None)

        Returns new ProjectBuiild instance
        """
        if not bool(self.project_log):
            raise RuntimeError("Project does not have a valid 'project_log'")

        if remix_audio is not False:
            if remix_audio is not None and not isinstance(remix_audio, FieldFile):
                raise ValueError("Invalid 'remix_audio' value (must be a FieldFile or None)")

        # Create new build (immediately in "queued" state)
        build = ProjectBuild.objects.create(
            project=self.project,
            project_branch=self.project_branch,
            project_log_commit_hash=self.project_log_commit_hash,
            project_log_commit_time=self.project_log_commit_time,
            project_log_commit_preview=self.project_log_commit_preview,
            video_size=self.video_size,
            status='queued' if not defer_queue else 'pending',
            queued_at=timezone.now() if not defer_queue else None
        )

       # Copy snapshot of `project_log` file
        with open(self.project_log.path, 'rb') as _file:
            build.project_log.save('gource.log', ContentFile(_file.read()))
        # Copy other optional artifacts
        # Background audio
        if remix_audio is not False:
            build.duration = self.duration
            # Use newly provided audio
            if isinstance(remix_audio, FieldFile):
                build.build_audio_name = os.path.basename(remix_audio.name)
                with open(remix_audio.path, 'rb') as _file:
                    build.build_audio.save(os.path.basename(remix_audio.name),
                                           ContentFile(_file.read()))
        elif self.build_audio:
            # Copy from build
            build.build_audio_name = self.build_audio_name
            with open(self.build_audio.path, 'rb') as _file:
                build.build_audio.save(os.path.basename(self.build_audio.name),
                                       ContentFile(_file.read()))
        if self.build_logo:
            # Project logo
            with open(self.build_logo.path, 'rb') as _file:
                build.build_logo.save(os.path.basename(self.build_logo.name),
                                      ContentFile(_file.read()))
        if self.build_background:
            # Project background
            with open(self.build_background.path, 'rb') as _file:
                build.build_background.save(os.path.basename(self.build_background.name),
                                            ContentFile(_file.read()))

        # Copy over build options for archival
        build_options = []
        for option in self.options.all():
            build_options.append(
                ProjectBuildOption(
                    build=build,
                    name=option.name,
                    value=option.value,
                    value_type=option.value_type
                )
            )
        if build_options:
            ProjectBuildOption.objects.bulk_create(build_options)

        # Copy over captions for archival
        build_captions = []
        for caption in self.captions.all():
            build_captions.append(
                ProjectBuildCaption(
                    build=build,
                    timestamp=caption.timestamp,
                    text=caption.text,
                )
            )
        if build_captions:
            ProjectBuildCaption.objects.bulk_create(build_captions)

            # Copy captions file from prior build
            if self.project_captions:
                with open(self.project_captions.path, 'rb') as _file:
                    build.project_captions.save(os.path.basename(self.project_captions.name),
                                                ContentFile(_file.read()))

        if remix_audio is not False:
            # Remix audio only; re-use video file from prior build
            with open(self.content.path, 'rb') as _file:
                build.content.save(os.path.basename(self.content.name),
                                   ContentFile(_file.read()))

        # Send to background worker
        if not defer_queue:
            generate_gource_build.delay(build.id)

        return build


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

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return '{0}={1}'.format(self.name, self.value)

    def to_dict(self):
        return {
            "name": self.name,
            "value": self.value,
            "value_type": self.value_type
        }


class BaseCaption(models.Model):
    """
    Abstract class for Caption entries.

    Format line:

        TIMESTAMP|TEXT

    """
    timestamp = models.DateTimeField(null=False)
    text = models.CharField(max_length=256)

    class Meta:
        ordering = ('timestamp',)
        abstract = True

    def __str__(self):
        return self.text

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "text": self.text,
        }

    def to_text(self):
        return f"{int(self.timestamp.timestamp())}|{self.text}"


class ProjectCaption(BaseCaption):
    """
    Caption entry for Gource video project.

    Intended to be the latest version of captions for ongoing builds.

    Format line:

        TIMESTAMP|TEXT

    """
    project = models.ForeignKey(Project, related_name='captions', on_delete=models.CASCADE)
    #timestamp = models.DateTimeField(null=False)
    #text = models.CharField(max_length=256)

    class Meta:
        ordering = ('timestamp',)


class ProjectBuildCaption(BaseCaption):
    """
    Caption entry for individual Gource video build.

    Intended to be readonly archive of captions for each build.

    Format line:

        TIMESTAMP|TEXT

    """
    build = models.ForeignKey(ProjectBuild, related_name='captions', on_delete=models.CASCADE)
    #timestamp = models.DateTimeField(null=False)
    #text = models.CharField(max_length=256)

    class Meta:
        ordering = ('timestamp',)


def get_global_avatar_path(instance, filename):
    return f'avatars/{filename}'

class UserAvatar(models.Model):
    """
    User avatar image to use in videos

    (Global registry)
    """
    name = models.CharField(max_length=256, unique=True)
    image = models.ImageField(upload_to=get_global_avatar_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='uploaded_avatars', on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('api-useravatar-image-download', args=[self.pk])

    @property
    def image_url(self):
        return self.get_absolute_url()

    @property
    def aliases_count(self):
        return self.aliases.count()


class UserAvatarAlias(models.Model):
    """
    Alias names for a given avatar.

    (Global registry)
    """
    avatar = models.ForeignKey(UserAvatar, related_name='aliases', on_delete=models.CASCADE)
    name = models.CharField(max_length=256, unique=True)

    class Meta:
        ordering = ('name',)

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
    name = models.CharField(max_length=256)
    image = models.ImageField(upload_to=get_project_avatar_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='uploaded_project_avatars', on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('project', 'name')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('api-project-useravatar-image-download', args=[self.project_id, self.pk])

    @property
    def image_url(self):
        return self.get_absolute_url()

    @property
    def aliases_count(self):
        return self.aliases.count()


class ProjectUserAvatarAlias(models.Model):
    """
    Alias names for a given avatar.

    (Project override)
    """
    avatar = models.ForeignKey(ProjectUserAvatar, related_name='aliases', on_delete=models.CASCADE)
    name = models.CharField(max_length=256)

    class Meta:
        ordering = ('name',)
        unique_together = ('avatar', 'name')

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    """
    Tracks per-project member rights that allows non-creators to manage project.
    """
    PROJECT_ROLES = [
        ("viewer", "Viewer"),
        ("developer", "Developer"),
        ("maintainer", "Maintainer"),
    ]

    project = models.ForeignKey(Project, related_name="members", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="projects", on_delete=models.CASCADE)
    role = models.CharField(max_length=32, choices=PROJECT_ROLES, default="viewer")

    date_added = models.DateTimeField(auto_now=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ('-date_added',)
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.project.name} ({self.user.username})"


class ProjectMemberGroup(models.Model):
    """
    Tracks per-project member rights that allows non-creators to manage project.
    """
    PROJECT_ROLES = [
        ("viewer", "Viewer"),
        ("developer", "Developer"),
        ("maintainer", "Maintainer"),
    ]

    project = models.ForeignKey(Project, related_name="member_groups", on_delete=models.CASCADE)
    group = models.ForeignKey(AuthGroup, related_name="projects", on_delete=models.CASCADE)
    role = models.CharField(max_length=32, choices=PROJECT_ROLES, default="viewer")

    date_added = models.DateTimeField(auto_now=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ('-date_added',)
        unique_together = ('project', 'group')

    def __str__(self):
        return f"{self.project.name} ({self.group.name})"


class UserPlaylist(models.Model):
    """
    User playlist to manage videos (mainly for autoplay).

    Projects are not unique (and can be added multiple times).
    The intent is to show the latest video build for any project.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='playlists', on_delete=models.CASCADE)
    name = models.CharField(max_length=256)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('user-playlist-detail', args=[self.pk])

    def add_project(self, project, index=None):
        """
        Add a new project (video) to the playlist.

        By default, adds to end.  Can insert into `index` using 0-based index.

        Projects can be added multiple times, and playlist `index` values will
        be corrected automatically at the end.
        """
        projects_count = self.projects.count()
        if index is None or index >= projects_count:
            index = projects_count   # Add to end
        else:
            # Inserting into list; update current set to shift all indexes forward
            self.projects.filter(index__gte=index).update(index=F('index')+1)

        playlist_project = UserPlaylistProject.objects.create(
            playlist=self,
            project=project,
            index=index
        )
        # Update index values (in case of gaps/duplicates)
        self.update_project_indexes()

    def update_project_indexes(self):
        """
        Iterate through list of playlist projects and correct `index` values.

        Used to sort out duplicates or shift to fill gaps due to deletions.
        """
        cur_indexes = self.projects.all().order_by('index', 'id')
        if cur_indexes.count() == 0:
            return  # Nothing to do

        indexes_changed = []
        for idx, playlist_project in enumerate(cur_indexes):
            if playlist_project.index != idx:
                playlist_project.index = idx
                indexes_changed.append(playlist_project)

        if indexes_changed:
            UserPlaylistProject.objects.bulk_update(indexes_changed, ['index'])


class UserPlaylistProject(models.Model):
    """
    M2M relation between UserPlaylist and Project (video) instance.
    """
    playlist = models.ForeignKey(UserPlaylist, related_name='projects', on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    index = models.PositiveIntegerField(default=0)      # Order within playlist

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('index',)

    def __str__(self):
        return f'{self.project.name} ({self.index})'

    def get_latest_build(self):
        """
        Retrieve the latest successful video build for this project.
        """
        return self.project.get_latest_build()

    def move_to_index(self, index):
        """
        Move the given project (video) to a new location in playlist.
        """
        playlist = self.playlist
        projects_count = playlist.projects.count()
        if index is None or index >= projects_count:
            index = projects_count   # Add to end
        else:
            # Inserting into list; update current set to shift all indexes forward
            playlist.projects.filter(index__gte=index).update(index=F('index')+1)

        self.index = index
        self.save(update_fields=['index'])
        # Update index values (in case of gaps/duplicates)
        playlist.update_project_indexes()
