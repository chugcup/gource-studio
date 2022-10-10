from django.urls import path, re_path

from . import views

# Django REST Framework API views (versioned -- /api/v_/)
urlpatterns = [
    # - Avatars
    re_path(r'^$', views.APIRoot.as_view(), name='api-root'),
    re_path(r'^avatars/?$', views.UserAvatarsList.as_view(), name='api-useravatars-list'),
    re_path(r'^avatars/(?P<avatar_id>\d+)/?$', views.UserAvatarDetail.as_view(), name='api-useravatar-detail'),
    re_path(r'^avatars/(?P<avatar_id>\d+)/download/?$', views.UserAvatarImageDownload.as_view(), name='api-useravatar-image-download'),
    re_path(r'^builds/?$', views.ProjectBuildsList.as_view(), name='api-project-builds-list'),
    re_path(r'^playlists/?$', views.UserPlaylistsList.as_view(), name='api-user-playlists-list'),
    re_path(r'^playlists/(?P<playlist_id>\d+)/?$', views.UserPlaylistDetail.as_view(), name='api-user-playlist-detail'),
    re_path(r'^playlists/(?P<playlist_id>\d+)/projects/?$', views.UserPlaylistProjectsList.as_view(), name='api-user-playlist-projects-list'),
    re_path(r'^playlists/(?P<playlist_id>\d+)/projects/(?P<playlist_project_id>\d+)/?$', views.UserPlaylistProjectDetail.as_view(), name='api-user-playlist-project-detail'),
    # - Projects
    re_path(r'^projects/?$', views.ProjectsList.as_view(), name='api-projects-list'),
    re_path(r'^projects/(?P<project_id>\d+)/?$', views.ProjectDetail.as_view(), name='api-project-detail'),
    re_path(r'^projects/(?P<project_id>\d+)/actions/?$', views.ProjectActions.as_view(), name='api-project-actions'),
    re_path(r'^projects/(?P<project_id>\d+)/avatars/?$', views.ProjectUserAvatarsList.as_view(), name='api-project-useravatars-list'),
    re_path(r'^projects/(?P<project_id>\d+)/avatars/(?P<project_avatar_id>\d+)/?$', views.ProjectUserAvatarDetail.as_view(), name='api-project-useravatar-detail'),
    re_path(r'^projects/(?P<project_id>\d+)/avatars/(?P<project_avatar_id>\d+)/download/?$', views.ProjectUserAvatarImageDownload.as_view(), name='api-project-useravatar-image-download'),
    re_path(r'^projects/(?P<project_id>\d+)/build_audio/?$', views.ProjectBuildAudioDetail.as_view(), name='api-project-build-audio-detail'),
    re_path(r'^projects/(?P<project_id>\d+)/build_audio/download/?$', views.ProjectBuildAudioDownload.as_view(), name='api-project-build-audio-download'),
    re_path(r'^projects/(?P<project_id>\d+)/build_background/?$', views.ProjectBackgroundDetail.as_view(), name='api-project-background-detail'),
    re_path(r'^projects/(?P<project_id>\d+)/build_background/download/?$', views.ProjectBackgroundDownload.as_view(), name='api-project-background-download'),
    re_path(r'^projects/(?P<project_id>\d+)/build_logo/?$', views.ProjectLogoDetail.as_view(), name='api-project-logo-detail'),
    re_path(r'^projects/(?P<project_id>\d+)/build_logo/download/?$', views.ProjectLogoDownload.as_view(), name='api-project-logo-download'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/?$', views.ProjectBuildsByProjectList.as_view(), name='api-project-builds-byproject-list'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/new/?$', views.CreateNewProjectBuild.as_view(), name='api-new-project-build'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/?$', views.ProjectBuildDetail.as_view(), name='api-project-build-detail'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/options/?$', views.ProjectBuildOptionsList.as_view(), name='api-project-build-options-list'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/build_background/download/?$', views.ProjectBuildBackgroundDownload.as_view(), name='api-project-build-background-download'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/build_logo/download/?$', views.ProjectBuildLogoDownload.as_view(), name='api-project-build-logo-download'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/content/download/?$', views.ProjectBuildContentDownload.as_view(), name='api-project-build-content-download'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/project_log/download/?$', views.ProjectBuildProjectLogDownload.as_view(), name='api-project-build-project-log-download'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/screenshot/download/?$', views.ProjectBuildScreenshotDownload.as_view(), name='api-project-build-screenshot-download'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<project_build_id>\d+)/thumbnail/download/?$', views.ProjectBuildThumbnailDownload.as_view(), name='api-project-build-thumbnail-download'),
    re_path(r'^projects/(?P<project_id>\d+)/captions/?$', views.ProjectCaptionsList.as_view(), name='api-project-captions-list'),
    re_path(r'^projects/(?P<project_id>\d+)/members/?$', views.ProjectMembersList.as_view(), name='api-project-members-list'),
    re_path(r'^projects/(?P<project_id>\d+)/options/?$', views.ProjectOptionsList.as_view(), name='api-project-options-list'),
    re_path(r'^projects/(?P<project_id>\d+)/project_log/?$', views.ProjectLogDetail.as_view(), name='api-project-log'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/project_log/?$', views.ProjectLogDetail.as_view(), name='api-project-log-slug'),
    re_path(r'^projects/(?P<project_id>\d+)/project_log/download/?$', views.ProjectLogDownload.as_view(), name='api-project-log-download'),
    re_path(r'^projects/(?P<project_id>\d+)/utils/duration/?$', views.ProjectDurationUtility.as_view(), name='api-project-duration-utility'),
]
