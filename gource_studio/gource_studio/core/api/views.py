from datetime import timedelta
import logging
import os
import time

from django.db.models import DateTimeField, Exists, Max, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404
from django.views.static import serve
from rest_framework import generics, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.reverse import reverse

from ..models import (
    Project,
    ProjectBuild,
    ProjectBuildOption,
    ProjectCaption,
    ProjectMember,
    ProjectOption,
    ProjectUserAvatar,
    ProjectUserAvatarAlias,
    UserAvatar,
    UserAvatarAlias,
)
from ..utils import (
    download_git_tags,
    estimate_gource_video_duration,
    test_http_url,
)
from .serializers import (
    ProjectBuildOptionSerializer,
    ProjectBuildSerializer,
    ProjectCaptionSerializer,
    ProjectLogSerializer,
    ProjectMemberSerializer,
    ProjectOptionSerializer,
    ProjectSerializer,
    ProjectUserAvatarAliasSerializer,
    ProjectUserAvatarSerializer,
    UserAvatarAliasSerializer,
    UserAvatarSerializer,
)


# TODO Root API view

def _serve_file_field(request, instance, name):
    """
    Helper method to serve file contents for Model FileField.
    """
    # TODO: check if populated
    filepath = getattr(instance, name).path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


class ProjectPermissionQuerySetMixin:
    def get_queryset(self):
        return self.queryset.filter_permissions(self.request.user)


class ProjectMemberPermission(BasePermission):
    "Checks membership of request user in Project to allow CRUD operations"
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        else:
            if not isinstance(obj, Project):
                obj = obj.project
            return obj.check_permission(request.user, request.method)


class APIRoot(views.APIView):
    """
    Portal to REST API browser.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        return Response({
            'avatars': reverse('api-useravatars-list', request=request),
            'projects': reverse('api-projects-list', request=request),
            'builds': reverse('api-project-builds-list', request=request),
        })


class ProjectsList(ProjectPermissionQuerySetMixin, generics.ListAPIView):
    """
    Retrieve a list of projects.

    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (ProjectMemberPermission,)

    def get_queryset(self):
        return super().get_queryset()\
                      .with_latest_build()\
                      .annotate(
                        latest_build_time=Coalesce(
                          Max('builds__completed_at'),
                          Value('1970-01-01 00:00:00', output_field=DateTimeField())
                        )
                      )\
                      .annotate(
                        latest_activity_time=Greatest('created_at', 'latest_build_time')
                      )


class ProjectDetail(ProjectPermissionQuerySetMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve details about a project.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (ProjectMemberPermission,)
    lookup_url_kwarg = 'project_id'

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        # Check for any queued builds and cancel them
        project.builds.filter(status__in=['pending', 'queued']).update(status='aborted')
        # Check for any running Project builds and abort them
        running_builds = project.builds.filter(status='running')
        if running_builds:
            for build in running_builds:
                try:
                    build.mark_aborted()
                except:
                    pass

            time.sleep(5)   # Wait a brief period for jobs to clean up
        return super().delete(request, *args, **kwargs)


class ProjectActions(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Endpoint for a number of project actions to perform.

    Options:

        {
            "action": "load_captions_from_tags"
        }

    """
    queryset = Project.objects.all()
    permission_classes = (ProjectMemberPermission,)

    def post(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        if 'action' not in request.data:
            return Response({"detail": "Field \"action\" is required."}, status=status.HTTP_400_BAD_REQUEST)
        action_code = request.data['action']

        # + 'load_captions_from_tags' - Populate captions from project's tags
        if action_code == 'load_captions_from_tags':
            return self._action_load_captions_from_tags(project, request)

        return Response({"action": f"Invalid action choice: {action_code}"}, status=status.HTTP_400_BAD_REQUEST)

    def _action_load_captions_from_tags(self, project, request):
        """
        Load current tags from a remote project repository and add them as captions.

        Requires valid project URL.
        """
        try:
            content = test_http_url(project.project_url)
            tags_list = download_git_tags(project.project_url, branch=project.project_branch)
            for timestamp, tag_name in tags_list:
                captions_added = 0
                try:
                    caption, created = ProjectCaption.objects.get_or_create(
                        project=project,
                        timestamp=timestamp,
                        text=tag_name
                    )
                    if created:
                        captions_added += 1
                except Exception as e:
                    logging.error("Failed to load caption: %s", str(e))
            response = {"error": False, "data": {"message": "Tags loaded successfully."}}
        except Exception as e:
            logging.exception("Failed to retrieve project tags")
            response = {"error": True, "data": {"message": f"Error: {str(e)}"}}

        if response['error']:
            return Response(response["data"], status=status.HTTP_400_BAD_REQUEST)
        return Response(response["data"], status=status.HTTP_201_CREATED)


class ProjectLogDownload(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Download project (Gource) 'project.log' contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'project_log')


class ProjectBuildAudioDownload(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Download project 'build_audio' contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'build_audio')


class ProjectMembersList(generics.ListAPIView):
    """
    Retrieve the current list of members for a project.
    """
    queryset = ProjectMember.objects.all()
    serializer_class = ProjectMemberSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectOptionsList(generics.ListAPIView):
    """
    Retrieve the current list of build options for a project.
    """
    queryset = ProjectOption.objects.all()
    serializer_class = ProjectOptionSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectCaptionsList(generics.ListAPIView):
    """
    Retrieve a current list of captions for a project.
    """
    queryset = ProjectCaption.objects.all()
    serializer_class = ProjectCaptionSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectBuildsList(generics.ListAPIView):
    """
    Retrieve a list of all project builds.
    """
    queryset = ProjectBuild.objects.all()
    serializer_class = ProjectBuildSerializer


class ProjectBuildsByProjectList(ProjectBuildsList):
    """
    Retrieve a list of builds for a project.
    """
    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectBuildDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProjectBuild.objects.all()
    serializer_class = ProjectBuildSerializer

    def get_object(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return get_object_or_404(super().get_queryset(), **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })

    def patch(self, request, *args, **kwargs):
        build = self.get_object()
        if 'status' in request.data:
            if data['status'] == 'aborted':
                if build.status != 'running':
                    # Invalid state transition
                    return Response({"status": f"Cannot mark build aborted from \"{build.status}\" status"}, status=status.HTTP_400_BAD_REQUEST)
                build.mark_aborted()
        return super().patch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        build = self.get_object()
        # Check if build is running and abort it
        if build.status == 'running':
            try:
                build.mark_aborted()
            except:
                pass

            time.sleep(5)   # Wait a brief period for job to clean up
        return super().delete(request, *args, **kwargs)


class ProjectBuildContentDownload(views.APIView):
    """
    Download project build video contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'content')


class ProjectBuildProjectLogDownload(views.APIView):
    """
    Download project build (Gource) 'project.log' contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'project_log')


class ProjectBuildScreenshotDownload(views.APIView):
    """
    Download project build 'screenshot' contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'screenshot')


class ProjectBuildThumbnailDownload(views.APIView):
    """
    Download project build 'thumbnail' contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'thumbnail')


class ProjectBuildOptionsList(generics.ListAPIView):
    """
    Retrieve a list of build options for a project build.
    """
    queryset = ProjectBuildOption.objects.all()
    serializer_class = ProjectBuildOptionSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return super().get_queryset().filter(build=project_build)


class ProjectUserAvatarsList(generics.ListAPIView):
    queryset = ProjectUserAvatar.objects.all()
    serializer_class = ProjectUserAvatarSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectUserAvatarDetail(generics.RetrieveAPIView):
    queryset = ProjectUserAvatar.objects.all()
    serializer_class = ProjectUserAvatarSerializer

    def get_object(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return get_object_or_404(super().get_queryset(), **{
            'project_id': project.id,
            'id': self.kwargs['project_avatar_id']
        })


class ProjectUserAvatarImageDownload(views.APIView):
    """
    Download project avatar 'image' contents.
    """
    queryset = ProjectUserAvatar.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        avatar = get_object_or_404(ProjectUserAvatar, **{
            'project_id': project.id,
            'id': self.kwargs['project_avatar_id']
        })
        return _serve_file_field(request, avatar, 'image')


class UserAvatarsList(generics.ListAPIView):
    queryset = UserAvatar.objects.all()
    serializer_class = UserAvatarSerializer


class UserAvatarDetail(generics.RetrieveAPIView):
    queryset = UserAvatar.objects.all()
    serializer_class = UserAvatarSerializer
    lookup_url_kwarg = 'avatar_id'


class UserAvatarImageDownload(views.APIView):
    """
    Download avatar 'image' contents.
    """
    queryset = UserAvatar.objects.all()

    def get(self, request, *args, **kwargs):
        avatar = get_object_or_404(UserAvatar, **{'id': self.kwargs['avatar_id']})
        return _serve_file_field(request, avatar, 'image')


class ProjectDurationUtility(views.APIView):
    """
    Utility to estimate the generated Project video duration based on settings.

    Requires project to have a `project.log` saved, and will use existing
    Gource settings to estimate video length.  Custom Gource options may be
    provided using URL parameters.

        `seconds-per-day`       [float] Speed of simulation in seconds per day.
        `auto-skip-seconds`     [float] Idle duration before skipping to next date entry.

    Returns estimated video duration in seconds.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.queryset.filter_permissions(request.user), **{'id': self.kwargs['project_id']})

        # Check for project log and read contents
        if not os.path.isfile(project.project_log.path):
            return Response({"detail": "Project has no project log available for estimation."}, status=status.HTTP_400_BAD_REQUEST)
        with open(project.project_log.path, 'r') as f:
            data = f.read()

        # Parse project log and determine action counts
        added = 0
        modded = 0
        deleted = 0
        lines = data.strip().split('\n')
        for line in lines:
            # <TIME>|<AUTHOR>|<MODIFICATION>|<PATH>
            segments = line.split('|')
            if segments[2] == 'A': added += 1
            elif segments[2] == 'M': modded += 1
            elif segments[2] == 'D': deleted += 1

        # Load relevant video duration options
        PROJECT_DURATION_OPTIONS = ['seconds-per-day', 'auto-skip-seconds']
        project_options = project.options.filter(name__in=PROJECT_DURATION_OPTIONS)
        # - Gource defaults
        option_spd = 1.0
        option_ass = 3.0
        for option in project_options:
            if option.name == 'seconds-per-day':
                option_spd = float(option.value)
            if option.name == 'auto-skip-seconds':
                option_ass = float(option.value)
        # - Allow for HTTP request overrides (via URL params)
        try:
            option_spd = float(request.GET.get('seconds-per-day', None))
        except:
            pass
        try:
            option_ass = float(request.GET.get('auto-skip-seconds', None))
        except:
            pass

        # Perform estimation using project log and Gource options
        gource_options = {
            'seconds-per-day': option_spd,
            'auto-skip-seconds': option_ass,
        }
        duration = estimate_gource_video_duration(data, gource_options=gource_options)
        td_duration = str(timedelta(seconds=int(duration)))
        response = {
            "duration": duration,
            "duration_str": td_duration
        }
        return Response(response)
