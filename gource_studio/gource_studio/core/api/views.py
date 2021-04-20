import os

from django.shortcuts import get_object_or_404
from django.views.static import serve
from rest_framework import generics, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.reverse import reverse

from ..models import (
    Project,
    ProjectBuild,
    ProjectBuildOption,
    ProjectCaption,
    ProjectOption,
    ProjectUserAvatar,
    ProjectUserAvatarAlias,
    UserAvatar,
    UserAvatarAlias,
)
from .serializers import (
    ProjectBuildOptionSerializer,
    ProjectBuildSerializer,
    ProjectCaptionSerializer,
    ProjectLogSerializer,
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


class ProjectsList(generics.ListAPIView):
    """
    Retrieve a list of projects.

    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class ProjectDetail(generics.RetrieveAPIView):
    """
    Retrieve a list of projects.

    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_url_kwarg = 'project_id'


class ProjectLogDownload(views.APIView):
    """
    Download project (Gource) 'project.log' contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project, **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'project_log')


class ProjectBuildAudioDownload(views.APIView):
    """
    Download project 'build_audio' contents.
    """
    queryset = Project.objects.all()

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project, **{'id': self.kwargs['project_id']})
        return _serve_file_field(request, project, 'build_audio')


class ProjectOptionsList(generics.ListAPIView):
    """
    Retrieve the current list of build options for a project.
    """
    queryset = ProjectOption.objects.all()
    serializer_class = ProjectOptionSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project, **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectCaptionsList(generics.ListAPIView):
    """
    Retrieve a current list of captions for a project.
    """
    queryset = ProjectCaption.objects.all()
    serializer_class = ProjectCaptionSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project, **{'id': self.kwargs['project_id']})
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
        project = get_object_or_404(Project, **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectBuildDetail(generics.RetrieveAPIView):
    queryset = ProjectBuild.objects.all()
    serializer_class = ProjectBuildSerializer

    def get_object(self):
        return get_object_or_404(super().get_queryset(), **{
            'project_id': self.kwargs['project_id'],
            'id': self.kwargs['project_build_id']
        })


class ProjectBuildContentDownload(views.APIView):
    """
    Download project build video contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': self.kwargs['project_id'],
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'content')


class ProjectBuildProjectLogDownload(views.APIView):
    """
    Download project build (Gource) 'project.log' contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': self.kwargs['project_id'],
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'project_log')


class ProjectBuildScreenshotDownload(views.APIView):
    """
    Download project build 'screenshot' contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': self.kwargs['project_id'],
            'id': self.kwargs['project_build_id']
        })
        return _serve_file_field(request, project_build, 'screenshot')


class ProjectBuildThumbnailDownload(views.APIView):
    """
    Download project build 'thumbnail' contents.
    """
    queryset = ProjectBuild.objects.all()

    def get(self, request, *args, **kwargs):
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': self.kwargs['project_id'],
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
        project_build = get_object_or_404(ProjectBuild, **{
            'project_id': self.kwargs['project_id'],
            'id': self.kwargs['project_build_id']
        })
        return super().get_queryset().filter(build=project_build)


class ProjectUserAvatarsList(generics.ListAPIView):
    queryset = ProjectUserAvatar.objects.all()
    serializer_class = ProjectUserAvatarSerializer
    pagination_class = None

    def get_queryset(self):
        project = get_object_or_404(Project, **{'id': self.kwargs['project_id']})
        return super().get_queryset().filter(project=project)


class ProjectUserAvatarDetail(generics.RetrieveAPIView):
    queryset = ProjectUserAvatar.objects.all()
    serializer_class = ProjectUserAvatarSerializer

    def get_object(self):
        return get_object_or_404(super().get_queryset(), **{
            'project_id': self.kwargs['project_id'],
            'id': self.kwargs['project_avatar_id']
        })


class ProjectUserAvatarImageDownload(views.APIView):
    """
    Download project avatar 'image' contents.
    """
    queryset = ProjectUserAvatar.objects.all()

    def get(self, request, *args, **kwargs):
        avatar = get_object_or_404(ProjectUserAvatar, **{
            'project_id': self.kwargs['project_id'],
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
