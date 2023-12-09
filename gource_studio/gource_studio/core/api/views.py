from datetime import datetime, timedelta, timezone
import logging
import os
import time
import urllib

from django import forms
from django.core.files.base import ContentFile
from django.db.models import DateTimeField, Exists, Max, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404
from django.utils import dateparse
from django.utils.timezone import now as utc_now
from django.views.static import serve
from rest_framework import generics, parsers, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.reverse import reverse

from ..constants import GOURCE_OPTIONS, VIDEO_OPTIONS
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
    UserPlaylist,
    UserPlaylistProject,
)
from ..tasks import generate_gource_build
from ..utils import (
    analyze_gource_log,
    download_git_log,
    download_git_tags,
    estimate_gource_video_duration,
    test_http_url,
    validate_project_url,
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
    UserPlaylistSerializer,
    UserPlaylistProjectSerializer,
    UserPlaylistWithProjectIDsSerializer,
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


class ProjectMemberPermission(IsAuthenticatedOrReadOnly):
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


class ProjectsList(ProjectPermissionQuerySetMixin, generics.ListCreateAPIView):
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
                          Value('1970-01-01 00:00:00.000000+00:00', output_field=DateTimeField())
                        )
                      )\
                      .annotate(
                        latest_activity_time=Greatest('created_at', 'latest_build_time')
                      )

    def post(self, request, *args, **kwargs):
        # Save a new project
        response = {}
        for field in ['name', 'project_vcs', 'project_branch']:
            if field not in request.data:
                response[field] = f"Missing required field: {field}"
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

        project_name = request.data['name']
        project_url = request.data.get('project_url', '').rstrip()
        project_vcs = request.data['project_vcs']
        project_branch = request.data['project_branch']
        project_url_active = str(request.data.get('project_url_active', 'True')).lower() in ['1', 't', 'true']
        project_is_public = str(request.data.get('is_public', 'True')).lower() in ['1', 't', 'true']
        if not project_name:
            response['name'] = f"Must provide valid project name"
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        if project_vcs not in [ch[0] for ch in Project.VCS_CHOICES]:
            response['project_vcs'] = f"Invalid VCS option: {project_vcs}"
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        if not project_branch:
            response['project_branch'] = f"Must provide project branch"
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # Check that project does not exist (identified by URL)
        # TODO: Check name?
#        try:
#            Project.objects.get(project_url=project_url)
#            response = {"error": True, "message": f"[ERROR] Project already exists matching that URL"}
#            return HttpResponse(json.dumps(response), status=400, content_type="application/json")
#        except Project.DoesNotExist:
#            pass

        if project_url:
            if project_url_active:
                # Validate URL string (and domain)
                try:
                    validate_project_url(project_url)
                except Exception as e:
                    response['project_url'] = f"Failed to validate project URL: {str(e)}"
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)

                # Test that URL is reachable
                # NOTE: some domains don't support HEAD/OPTIONS requests...
                try:
                    test_http_url(project_url)
                except Exception as e:
                    response['project_url'] = f"Failed to reach project URL: {str(e)}"
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)

        else:
            # If no project URL provided, unset this
            project_url_active = False

        # Download initial project data
        log_data = log_hash = log_subject = tags_list = None
        if project_url and project_url_active:
            try:
                if project_vcs == 'git':
                    log_data, log_hash, log_subject, tags_list = download_git_log(project_url, branch=project_branch)
                elif project_vcs == 'hg':
                    # TODO
                    response['project_vcs'] = "Mercurial download not supported"
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)
                else:
                    response['project_vcs'] = f"Invalid VCS option: {project_vcs}"
                    return Response(response, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                response['project_url'] = f"Error downloading initial VCS log: {str(e)}"
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

        project = Project(
            name=project_name,
            project_url=project_url,
            project_url_active=project_url_active,
            project_vcs=project_vcs,
            project_branch=project_branch,
            is_public=project_is_public,
            created_by=request.user
        )
        # Populate attributes from source download
        if log_hash:
            project.project_log_commit_hash = log_hash
        if log_subject:
            project.project_log_commit_preview = log_subject
        # Get time/author from last entry
        if log_data is not None:
            latest_commit = log_data.splitlines()[-1].split('|')
            project.project_log_commit_time = datetime.utcfromtimestamp(int(latest_commit[0])).replace(tzinfo=timezone.utc)
        project.save()

        # Load initial ProjectCaptions from VCS tags
        if 'load_captions_from_tags' in request.data \
                and str(request.data['load_captions_from_tags']).lower() in ['1', 't', 'true'] \
                and tags_list:
            try:
                for timestamp, tag_name in tags_list:
                    try:
                        caption, created = ProjectCaption.objects.get_or_create(
                            project=project,
                            timestamp=timestamp,
                            text=tag_name
                        )
                    except Exception as ex:
                        logging.error("Failed to load caption: %s", str(ex))
            except Exception as e:
                logging.error("Failed to retrieve project tags: %s", str(e))

        # Save new Gource log content
        if log_data is not None:
            project.project_log.save('gource.log', ContentFile(log_data))
        response = ProjectSerializer(project, context={'request': request}).data
        return Response(response, status=status.HTTP_201_CREATED)


class ProjectDetail(ProjectPermissionQuerySetMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve details about a project.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (ProjectMemberPermission,)
    lookup_url_kwarg = 'project_id'

    def patch(self, request, *args, **kwargs):
        project = self.get_object()
        response = {}

        # Determine if request contains fields that would change video content
        # (and therefore require a new video build)
        VIDEO_FIELDS = ['gource_options', 'captions', 'video_size', 'build_title']
        has_video_settings = any(k in VIDEO_FIELDS for k in request.data.keys())

        # Gource Video options list
        # TODO: Move to new endpoint
        if 'gource_options' in request.data:
            if isinstance(request.data['gource_options'], dict):
                new_options = []
                for option, value in request.data['gource_options'].items():
                    if option in GOURCE_OPTIONS:
                        gource_opt = GOURCE_OPTIONS[option]
                        try:
                            # Parse/validate input
                            typed_value = gource_opt['parser'](value)
                            # Stage new set of options
                            new_options.append(
                                ProjectOption(
                                    project=project,
                                    name=option,
                                    value=str(value),
                                    value_type=gource_opt['type'],
                                )
                            )
                        except Exception as e:
                            logging.exception(f"Gource option error: {option} => {value}")
                            response['gource_options'] = f"Gource option error: {option} => {value}"
                            return Response(response, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        logging.warning(f"Unrecognized option: {option}")
                        response['gource_options'] = f"Invalid Gource option '{option}'"
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)

                # Delete old options
                project.options.all().delete()
                # Add new set
                ProjectOption.objects.bulk_create(new_options)
            else:
                logging.error(f"Invalid 'gource_options' provided: {request.data['gource_options']}")
                response['gource_options'] = "Invalid Gource options type (must be a dict)"
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # Project Captions list
        # TODO: Move to new endpoint
        if 'captions' in request.data:
            if isinstance(request.data['captions'], list):
                new_captions = []
                for idx, caption in enumerate(request.data['captions']):
                    if not isinstance(caption, dict):
                        # TODO error or log?
                        continue
                    try:
                        timestamp = dateparse.parse_datetime(caption['timestamp']).replace(tzinfo=timezone.utc)
                        caption_text = caption['text']
                        new_captions.append(
                            ProjectCaption(project=project, timestamp=timestamp, text=caption_text)
                        )
                    except Exception as e:
                        logging.exception(f"Gource caption error [{idx}]")
                        response['captions'] = f"Gource caption error: [{idx}]"
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)
                # Check for flag to indicate if old captions should be removed
                sync_captions = request.data.get('sync_captions', False)
                if sync_captions:
                    # Delete old options
                    project.captions.all().delete()
                    # Add new set
                    ProjectCaption.objects.bulk_create(new_captions)
                else:
                    # Merge with current set
                    ProjectCaption.objects.bulk_create(
                        new_captions,
                        update_conflicts=True,
                        unique_fields=['project', 'timestamp', 'text'],
                        update_fields=['project', 'timestamp', 'text']
                    )
            else:
                logging.error(f"Invalid 'captions' list provided: {request.data['captions']}")
            del request.data['captions']

        res = super().patch(request, *args, **kwargs)

        if res.status_code == 200 and has_video_settings:
            # Mark 'is_project_changed' on Project to indicate build needed
            if not project.is_project_changed:
                project.set_project_changed(True)
            project.refresh_from_db()
            res.data = ProjectSerializer(project, context={'request': request}).data
        return res

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        # Check for any queued builds and cancel them
        project.builds.filter(status__in=['pending', 'queued']).update(status='canceled')
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
            if not project.project_url_active:
                return Response({"detail": "VCS fetch is not enabled for this project."}, status=status.HTTP_400_BAD_REQUEST)
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


class ProjectLogDetail(ProjectPermissionQuerySetMixin, generics.RetrieveUpdateAPIView):
    """
    Update project (Gource) 'project.log' contents or metadata.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectLogSerializer

    def get_object(self, *args, **kwargs):
        if 'project_id' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        elif 'project_slug' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'project_slug': self.kwargs['project_slug']})
        else:
            project = get_object_or_404(self.get_queryset(), **{'id': None})    # Force 404
        return project

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = self.get_serializer(project, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        project = self.get_object()
        response_status = status.HTTP_200_OK
        if not project.project_log:
            response_status = status.HTTP_201_CREATED
        for field in ['project_log_commit_hash', 'project_log_commit_time', 'project_log_commit_preview']:
            if field in request.data:
                if field == 'project_log_commit_time':
                    # FIXME: not always going to be UNIX timestamp
                    setattr(project, field,
                            datetime.utcfromtimestamp(int(request.data[field])).replace(tzinfo=timezone.utc))
                else:
                    setattr(project, field, request.data[field])
        if 'project_log' in request.data:
            log_data = request.data['project_log']
            try:
                analyze_gource_log(log_data)
            except Exception as e:
                # Invalid Gource log
                logging.exception("Error analyzing log")
                return Response({"project_log": "Error analyzing project log: {0}".format(str(e))}, status=status.HTTP_400_BAD_REQUEST)
            try:
                if project.project_log:
                    #os.remove(project.project_log.path)
                    project.project_log.delete()
                project.project_log.save('gource.log', ContentFile(log_data))
            except Exception as e:
                # Error saving (500?)
                logging.exception("Error saving log")
                return Response({"project_log": "Error saving project log: {0}".format(str(e))}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(project, context={'request': request})
        return Response(serializer.data, status=response_status)


class ProjectLogDownload(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Download project (Gource) 'project.log' contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'project_log')


class ProjectLogoDetail(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Manage project (Gource) video logo contents.
    """
    queryset = Project.objects.all()

    def get_object(self, *args, **kwargs):
        if 'project_id' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        elif 'project_slug' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'project_slug': self.kwargs['project_slug']})
        else:
            project = get_object_or_404(self.get_queryset(), **{'id': None})    # Force 404
        return project

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        if project.build_logo:
            project.build_logo.delete(save=True)
            project.set_project_changed(True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectLogoDownload(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Download project (Gource) video logo contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'build_logo')


class ProjectBackgroundDetail(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Manage project (Gource) video background contents.
    """
    queryset = Project.objects.all()

    def get_object(self, *args, **kwargs):
        if 'project_id' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        elif 'project_slug' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'project_slug': self.kwargs['project_slug']})
        else:
            project = get_object_or_404(self.get_queryset(), **{'id': None})    # Force 404
        return project

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        if project.build_background:
            project.build_background.delete(save=True)
            project.set_project_changed(True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectBackgroundDownload(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Download project (Gource) video background contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'build_background')


class ProjectBuildAudioDetail(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Manage project (Gource) background audio contents.
    """
    queryset = Project.objects.all()

    def get_object(self, *args, **kwargs):
        if 'project_id' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        elif 'project_slug' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'project_slug': self.kwargs['project_slug']})
        else:
            project = get_object_or_404(self.get_queryset(), **{'id': None})    # Force 404
        return project

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        if project.build_audio:
            project.build_audio_name = None
            project.build_audio.delete(save=True)
            project.set_project_changed(True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectBuildAudioDownload(ProjectPermissionQuerySetMixin, views.APIView):
    """
    Download project 'build_audio' contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'build_audio')


class ProjectMembersList(generics.ListCreateAPIView):
    """
    Retrieve the current list of members for a project.

    To add a new user to the project:

        {
            "username": <username>,
            "role": <developer|maintainer>,
        }

    """
    queryset = ProjectMember.objects.all()
    serializer_class = ProjectMemberSerializer
    permission_classes = (ProjectMemberPermission,)
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)

    def post(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        response = {}

        if 'username' not in request.data:
            return Response({"detail": "Missing required field 'username'."}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(get_user_model(), **{'username': request.data['username']})

        if 'role' not in request.data:
            return Response({"detail": "Missing required field 'role'."}, status=status.HTTP_400_BAD_REQUEST)
        elif request.data['role'] not in ProjectMember.PROJECT_ROLES:
            return Response({"role": "fInvalid role provided: {request.data['role']}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ProjectMember.objects.get(project=project, user_id=user.id)
            return Response({"username": f"User '{user.username}' already assigned to project"}, status=status.HTTP_400_BAD_REQUEST)
        except ProjectMember.DoesNotExist:
            pm = ProjectMember.objects.create(project=project,
                                              user=user,
                                              role=role,
                                              added_by=request.user)
        serializer = self.get_serializer(pm, context={'request': request})
        return Response(serializer.data, status=response_status)


class ProjectMemberDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Update project member details.
    """
    queryset = ProjectMember.objects.all()
    permission_classes = (ProjectMemberPermission,)
    serializer_class = ProjectMemberSerializer

    def get_object(self, *args, **kwargs):
        if 'project_id' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'id': self.kwargs['project_id']})
        elif 'project_slug' in self.kwargs:
            project = get_object_or_404(self.get_queryset(), **{'project_slug': self.kwargs['project_slug']})
        else:
            project = get_object_or_404(self.get_queryset(), **{'id': None})    # Force 404
        return get_object_or_404(ProjectMember, **{'project_id': project.pk, 'member_id': self.kwargs['project_member_id']})

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


class ProjectCaptionsList(generics.ListCreateAPIView):
    """
    Retrieve a current list of captions for a project.

    Can create a new caption using:

        {
            "timestamp": <datetime>,
            "text": <str>
        }

    Or in bulk using:

        {
            "captions": [
                {"timestamp", "text"},
                ...
            ]
        }

    By default, `captions` will be added/merged to existing entries.
    To reset captions, set the `sync_captions` field.

        {

            "captions": [ ... ],
            "sync_captions": true
        }


    """
    queryset = ProjectCaption.objects.all()
    serializer_class = ProjectCaptionSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)

    def post(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        response = {}
        project_updated = False

        # Write all new captions
        if 'captions' in request.data:
            if isinstance(request.data['captions'], list):
                new_captions = []
                for idx, caption in enumerate(request.data['captions']):
                    if not isinstance(caption, dict):
                        # TODO error or log?
                        continue
                    try:
                        timestamp = dateparse.parse_datetime(caption['timestamp']).replace(tzinfo=timezone.utc)
                        caption_text = caption['text']
                        new_captions.append(
                            ProjectCaption(project=project, timestamp=timestamp, text=caption_text)
                        )
                    except Exception as e:
                        logging.exception(f"Gource caption error [{idx}]")
                        response['captions'] = f"Gource caption error: [{idx}]"
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)
                # Check for flag to indicate if old captions should be removed
                sync_captions = request.data.get('sync_captions', False)
                if sync_captions:
                    # Delete old options
                    project.captions.all().delete()
                    # Add new set
                    ProjectCaption.objects.bulk_create(new_captions)
                else:
                    # Merge with current set
                    ProjectCaption.objects.bulk_create(
                        new_captions,
                        update_conflicts=True,
                        unique_fields=['project', 'timestamp', 'text'],
                        update_fields=['project', 'timestamp', 'text']
                    )
                project_updated = True
            else:
                logging.error(f"Invalid 'captions' list provided: {request.data['captions']}")

        # Append new caption
        elif 'timestamp' in request.data and 'text' in request.data:
            try:
                timestamp = dateparse.parse_datetime(request.data['timestamp']).replace(tzinfo=timezone.utc)
                caption_text = request.data['text']
                caption = ProjectCaption.objects.create(project=project, timestamp=timestamp, text=caption_text)
                project_updated = True
            except Exception as e:
                logging.exception(f"Gource caption error [{idx}]")
                response['detail'] = f"Gource caption error: [{idx}]"
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # Successful (or no change)
        if project_updated:
            project.set_project_changed(True)
        # Return full list of captions
        response = [ProjectCaptionSerializer(c, context={'request': request}).data for c in project.captions.all()]
        return Response(response, status=status.HTTP_200_OK)


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
    permission_classes = (ProjectMemberPermission,)

    def get_object(self):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        return get_object_or_404(super().get_queryset(), **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })

    def patch(self, request, *args, **kwargs):
        build = self.get_object()
        if 'status' in request.data:
            request_status = request.data['status']
            if request_status in ['canceled', 'aborted']:
                if build.status not in ['pending', 'queued', 'running']:
                    # Invalid state transition
                    return Response({"status": f"Cannot mark build {request_status} from \"{build.status}\" status"}, status=status.HTTP_400_BAD_REQUEST)
                if build.status in ['pending', 'queued']:
                    build.mark_canceled()
                else:
                    build.mark_aborted()
            # TODO: prevent other status changes?
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


class CreateNewProjectBuild(generics.CreateAPIView):
    queryset = ProjectBuild.objects.all()
    serializer_class = ProjectBuildSerializer
    permission_classes = (ProjectMemberPermission,)

    def post(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})

        # Determine if project log should be re-downloaded
        refetch_log = request.data.get('refetch_log', None)
        # Determine if new build should only remix audio from preview build
        remix_audio = request.data.get('remix_audio', None)

        response = {}
        # Check if project currently has queued build
        # TODO: allow more than one at a time?
        if project.builds.filter(status__in=['pending', 'queued', 'running']).count():
            response = {
                "detail": "Project already has pending builds."
            }
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Utilize feature to remix audio only
            if str(remix_audio).lower() in ['t', 'true', '1']:
                latest_build = project.latest_build
                if not latest_build:
                    return Response({"detail": "Remix audio requested but no prior build found."}, status=status.HTTP_400_BAD_REQUEST)
                if not latest_build.content:
                    return Response({"detail": "Remix audio requested but latest build does not have video file."}, status=status.HTTP_400_BAD_REQUEST)

                if project.build_audio:
                    remix_audio = project.build_audio
                else:
                    remix_audio = None  # Remove audio track
                build = latest_build.clone_build(remix_audio=remix_audio)

                # Update parent project to unset `is_project_changed`
                project.set_project_changed(False)

                # Generate serializer response for new ProjectBuild
                serializer = self.get_serializer(build, context={'request': request})
                response = serializer.data

                # Return success response
                return Response(response, status=status.HTTP_201_CREATED)

            if not project.project_log:
                response = {
                    "detail": "Project does not have a log yet. Cannot build."
                }
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            # Check if user requested new VCS log to be downloaded
            if str(refetch_log).lower() in ['t', 'true', '1']:
                if not project.project_url_active:
                    return Response({"detail": "VCS fetch is not enabled for this project."}, status=status.HTTP_400_BAD_REQUEST)
                # Download latest VCS branch; generate Gource log
                content = test_http_url(project.project_url)
                log_data, log_hash, log_subject, tags_list = download_git_log(project.project_url, branch=project.project_branch)
                project.project_log_commit_hash = log_hash
                project.project_log_commit_preview = log_subject
                # Get time/author from last entry
                latest_commit = log_data.splitlines()[-1].split('|')
                project.project_log_commit_time = datetime.utcfromtimestamp(int(latest_commit[0])).replace(tzinfo=timezone.utc)
                if project.project_log:
                    #os.remove(project.project_log.path)
                    project.project_log.delete()
                project.project_log.save('gource.log', ContentFile(log_data))

            if not project.project_log:
                response = {
                    "detail": "Project does not have a log yet. Cannot build."
                }
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            # Create new build (immediately in "queued" state)
            build = project.create_build()

            # Update parent project to unset `is_project_changed`
            project.set_project_changed(False)

            # Generate serializer response for new ProjectBuild
            serializer = self.get_serializer(build, context={'request': request})
            response = serializer.data

            # Return success response
            return Response(response, status=status.HTTP_201_CREATED)
        except urllib.error.URLError as e:
            response = {
                "detail": f'URL/HTTP error: {e.reason}'
            }
        except Exception as e:
            logging.exception("Uncaught exception")
            response = {
                "detail": f'Server error: [{e.__class__.__name__}] {e}'
            }
        return Response(response, status=status.HTTP_400_BAD_REQUEST)


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


class ProjectBuildLogoDownload(views.APIView):
    """
    Download project build (Gource) video logo contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'build_logo')


class ProjectBuildBackgroundDownload(views.APIView):
    """
    Download project build (Gource) video background contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'build_background')


class ProjectBuildBuildAudioDownload(views.APIView):
    """
    Download project build (Gource) audio file contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': project.id,
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'build_audio')


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


class ProjectUserAvatarsList(generics.ListCreateAPIView):
    queryset = ProjectUserAvatar.objects.all()
    serializer_class = ProjectUserAvatarSerializer
    pagination_class = None
    parser_classes = (parsers.MultiPartParser,)

    def get_parent_object(self):
        return get_object_or_404(Project.objects.filter_permissions(self.request.user), **{'id': self.kwargs['project_id']})

    def get_queryset(self):
        project = self.get_parent_object()
        return super().get_queryset().filter(project=project)

    def post(self, request, *args, **kwargs):
        project = self.get_parent_object()
        form = UploadAvatarForm(
            request.data,   # POST
            request.data,   # FILE
        )
        if form.is_valid():
            try:
                if ProjectUserAvatar.objects.filter(project=project, name=request.POST['name']).exists():
                    raise ValueError("Project avatar by that name already exists.")
                # TODO: Validate as .jpg or .png (or convert)
                # TODO: rescale to 256x256
                avatar = ProjectUserAvatar(
                    project=project,
                    name=request.POST['name'],
                    image=request.FILES['image']
                )
                avatar.created_by = request.user
                avatar.save()

                # Generate serializer response for new ProjectBuild
                serializer = self.get_serializer(avatar, context={'request': request})
                response = serializer.data
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": form.errors}, status=status.HTTP_400_BAD_REQUEST)


class ProjectUserAvatarDetail(generics.RetrieveDestroyAPIView):
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


class UploadAvatarForm(forms.Form):
    name = forms.CharField(max_length=255)
    image = forms.ImageField()

class UserAvatarsList(generics.ListCreateAPIView):
    """
    Retrieve a list of global avatars.
    """
    queryset = UserAvatar.objects.all()
    serializer_class = UserAvatarSerializer
    parser_classes = (parsers.MultiPartParser,)

    def post(self, request, *args, **kwargs):
        form = UploadAvatarForm(
            request.data,   # POST
            request.data,   # FILE
        )
        if form.is_valid():
            try:
                if UserAvatar.objects.filter(name=request.POST['name']).exists():
                    raise ValueError("Avatar by that name already exists.")
                # TODO: Validate as .jpg or .png (or convert)
                # TODO: rescale to 256x256
                avatar = UserAvatar(
                    name=request.POST['name'],
                    image=request.FILES['image']
                )
                avatar.created_by = request.user
                avatar.save()

                # Generate serializer response for new ProjectBuild
                serializer = self.get_serializer(avatar, context={'request': request})
                response = serializer.data
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": form.errors}, status=status.HTTP_400_BAD_REQUEST)


class UserAvatarDetail(generics.RetrieveDestroyAPIView):
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
        if not bool(project.project_log):
            return Response({"detail": "Project has no project log available for estimation."}, status=status.HTTP_400_BAD_REQUEST)
        with open(project.project_log.path, 'r') as _file:
            data = _file.read()

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


class UserPlaylistsList(generics.ListCreateAPIView):
    """
    Retrieve a list of playlists for the current user.

    Set `include_project_ids=True` query param to return an ordered list of
    Project IDs assigned to each playlist.

    """
    queryset = UserPlaylist.objects.all()
    serializer_class = UserPlaylistSerializer
    permission_classes = (ProjectMemberPermission,)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_class(self):
        # `include_project_ids=True` to return alternate serialize with `project_ids`
        if 'include_project_ids' in self.request.query_params \
                and str(self.request.query_params['include_project_ids']).lower() in ['1', 't', 'true']:
            return UserPlaylistWithProjectIDsSerializer
        return self.serializer_class

    def get_queryset(self):
        if not self.request.user or self.request.user.is_anonymous:
            return super().get_queryset().none()
        return super().get_queryset()\
                      .filter(user=self.request.user)


class UserPlaylistDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve an individual playlist for the current user.

    Set `include_project_ids=True` query param to return an ordered list of
    Project IDs assigned to this playlist.

    """
    queryset = UserPlaylist.objects.all().select_related()
    serializer_class = UserPlaylistSerializer
    permission_classes = (ProjectMemberPermission,)

    def get_serializer_class(self):
        # `include_project_ids=True` to return alternate serialize with `project_ids`
        if 'include_project_ids' in self.request.query_params \
                and str(self.request.query_params['include_project_ids']).lower() in ['1', 't', 'true']:
            return UserPlaylistWithProjectIDsSerializer
        return self.serializer_class

    def get_object(self):
        playlist = get_object_or_404(UserPlaylist.objects.filter(user=self.request.user), **{'id': self.kwargs['playlist_id']})
        return get_object_or_404(super().get_queryset(), **{
            'id': self.kwargs['playlist_id']
        })


class UserPlaylistProjectsList(generics.ListCreateAPIView):
    """
    Retrieve a list of projects for a given playlist.

    """
    queryset = UserPlaylistProject.objects.all()
    serializer_class = UserPlaylistProjectSerializer
    permission_classes = (ProjectMemberPermission,)
    pagination_class = None     # Not paginated

    def get_object(self):
        return get_object_or_404(UserPlaylist.objects.filter(user=self.request.user), **{'id': self.kwargs['playlist_id']})

    def get_queryset(self):
        if not self.request.user or self.request.user.is_anonymous:
            return super().get_queryset().none()

        playlist = self.get_object()
        return super().get_queryset().filter(playlist=playlist).order_by('index')

    def post(self, request, *args, **kwargs):
        playlist = self.get_object()
        # Append one or more projects to playlist
        if 'projects' in request.data:
            project_ids_list = request.data['projects']
            if not isinstance(project_ids_list, (list, tuple)):
                project_ids_list = [project_ids_list]

            projects_list = []
            projects_qs = Project.objects.all().filter_permissions(request.user)
            for project_id in project_ids_list:
                try:
                    projects_list.append(
                        projects_qs.get(id=project_id)
                    )
                except Project.DoesNotExist:
                    return Response({"projects": [f"Invalid project ID: {project_id}"]}, status=status.HTTP_400_BAD_REQUEST)
            for project in projects_list:
                playlist.add_project(project)   # Added to end
            return Response({}, status=status.HTTP_201_CREATED if len(projects_list) else status.HTTP_200_OK)

        return Response({}, status=status.HTTP_200_OK)


class UserPlaylistProjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserPlaylistProject.objects.all().select_related()
    serializer_class = UserPlaylistProjectSerializer
    permission_classes = (ProjectMemberPermission,)

    def get_object(self):
        playlist = get_object_or_404(UserPlaylist.objects.filter(user=self.request.user), **{'id': self.kwargs['playlist_id']})
        return get_object_or_404(super().get_queryset(), **{
            'playlist_id': playlist.id,
            'id': self.kwargs['playlist_project_id']
        })

    def patch(self, request, *args, **kwargs):
        playlist_project = self.get_object()
        playlist = playlist_project.playlist
        status_code = 200
        if 'index' in request.data:
            new_index = request.data['index']
            try:
                new_index = int(new_index)
                if new_index < 0:
                    raise ValueError
            except (ValueError, TypeError):
                return Response({"index": f"Invalid 'index' position: {new_index}"}, status=status.HTTP_400_BAD_REQUEST)

            playlist_project.move_to_index(new_index)
        result = UserPlaylistProjectSerializer(playlist_project, context={'request': request}).data
        return Response(result, status_code=status.HTTP_200_PK)

    def delete(self, request, *args, **kwargs):
        playlist_project = self.get_object()
        res = super().delete(request, *args, **kwargs)
        playlist_project.playlist.update_project_indexes()
        return res
