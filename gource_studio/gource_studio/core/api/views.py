from datetime import datetime, timedelta
import logging
import os
import time
import urllib

from django.core.files.base import ContentFile
from django.db.models import DateTimeField, Exists, Max, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404
from django.utils import dateparse
from django.utils.timezone import make_aware, now as utc_now
from django.views.static import serve
from rest_framework import generics, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
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
                          Value('1970-01-01 00:00:00', output_field=DateTimeField())
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
            project.project_log_commit_time = make_aware(datetime.utcfromtimestamp(int(latest_commit[0])))
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
                # Delete old options
                project.options.all().delete()
                # Add new set
                ProjectOption.objects.bulk_create(new_options)
            else:
                logging.error(f"Invalid 'gource_options' provided: {request.data['gource_options']}")
            request.data['gource_options']

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
                        timestamp = make_aware(dateparse.parse_datetime(caption['timestamp']))
                        caption_text = caption['text']
                        new_captions.append(
                            ProjectCaption(project=project, timestamp=timestamp, text=caption_text)
                        )
                    except Exception as e:
                        logging.exception(f"Gource caption error [{idx}]")
                        response['captions'] = f"Gource caption error: [{idx}]"
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)
                # Delete old options
                # TODO merge/prune
                project.captions.all().delete()
                # Add new set
                ProjectCaption.objects.bulk_create(new_captions)
            else:
                logging.error(f"Invalid 'captions' list provided: {request.data['captions']}")
            del request.data['captions']

        res = super().patch(request, *args, **kwargs)

        if res.status_code == 200:
            # Mark 'is_project_changed' on Project to indicate build needed
            if not project.is_project_changed:
                project.set_project_changed(True)
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
                            make_aware(datetime.utcfromtimestamp(int(request.data[field]))))
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


class ProjectCaptionsList(generics.ListCreateAPIView):
    """
    Retrieve a current list of captions for a project.
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
                        timestamp = make_aware(dateparse.parse_datetime(caption['timestamp']))
                        caption_text = caption['text']
                        new_captions.append(
                            ProjectCaption(project=project, timestamp=timestamp, text=caption_text)
                        )
                    except Exception as e:
                        logging.exception(f"Gource caption error [{idx}]")
                        response['captions'] = f"Gource caption error: [{idx}]"
                        return Response(response, status=status.HTTP_400_BAD_REQUEST)
                # Delete old options
                # TODO merge/prune
                project.captions.all().delete()
                # Add new set
                ProjectCaption.objects.bulk_create(new_captions)
                project_updated = True
            else:
                logging.error(f"Invalid 'captions' list provided: {request.data['captions']}")

        # Append new caption
        elif 'timestamp' in request.data and 'text' in request.data:
            try:
                timestamp = make_aware(dateparse.parse_datetime(request.data['timestamp']))
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

        response = {}
        # Check if project currently has queued build
        # TODO: allow more than one at a time?
        if project.builds.filter(status__in=['pending', 'queued', 'running']).count():
            response = {
                "detail": "Project already has pending builds."
            }
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        try:
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
                project.project_log_commit_time = make_aware(datetime.utcfromtimestamp(int(latest_commit[0])))
                if project.project_log:
                    #os.remove(project.project_log.path)
                    project.project_log.delete()
                project.project_log.save('gource.log', ContentFile(log_data))

            # Create new build (immediately in "queued" state)
            build = ProjectBuild(
                project=project,
                project_branch=project.project_branch,
                project_log_commit_hash=project.project_log_commit_hash,
                project_log_commit_time=project.project_log_commit_time,
                project_log_commit_preview=project.project_log_commit_preview,
                build_audio_name=project.build_audio_name,
                video_size=project.video_size,
                status='queued',
                queued_at=utc_now()
            )
            build.save()

            # Copy over build options from master project
            build_options = []
            for option in project.options.all():
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

            # Save captions to file prior to build
            captions = project.generate_captions_file()
            if captions is not None:
                captions_data = "\n".join(captions)
                build.project_captions.save('captions.txt', ContentFile(captions_data))

            # Update parent project to unset `is_project_changed`
            project.set_project_changed(False)

            # Generate serializer response for new ProjectBuild
            serializer = self.get_serializer(build, context={'request': request})
            response = serializer.data

            # Send to background worker
            generate_gource_build.delay(build.id)

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
